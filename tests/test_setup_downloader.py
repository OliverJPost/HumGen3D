"""The download engine against a local HTTP server: resume, checksums, cancel,
installing over an older version without touching the user's own files."""
import hashlib
import http.server
import json
import os
import threading
import zipfile

import pytest
from setup_fakes import Handler, make_pack

from HumGen3D.backend.setup import downloader
from HumGen3D.backend.setup.catalogue import installed_packs


@pytest.fixture(scope="module")
def server():
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()


@pytest.fixture(autouse=True)
def fresh_server_state():
    Handler.files = {}
    Handler.ranges = True
    Handler.hits = []


def test_download_verifies_checksum(server, tmp_path):
    data = b"x" * 10000
    Handler.files["/a.bin"] = data
    dest = str(tmp_path / "a.bin")
    seen = []
    downloader.download(server + "/a.bin", dest, len(data), hashlib.sha256(data).hexdigest(), lambda d, t: seen.append((d, t)), threading.Event())
    assert open(dest, "rb").read() == data
    assert seen[-1] == (len(data), len(data))
    # A second call with the file complete does not fetch again
    hits = len(Handler.hits)
    downloader.download(server + "/a.bin", dest, len(data), hashlib.sha256(data).hexdigest())
    assert len(Handler.hits) == hits


def test_download_rejects_bad_checksum(server, tmp_path):
    Handler.files["/b.bin"] = b"y" * 100
    with pytest.raises(downloader.DownloadError) as e:
        downloader.download(server + "/b.bin", str(tmp_path / "b.bin"), 100, "00" * 32)
    assert e.value.code == "checksum"
    assert not os.path.exists(tmp_path / "b.bin") and not os.path.exists(tmp_path / "b.bin.part")


def test_download_resumes_a_part_file(server, tmp_path):
    data = bytes(range(256)) * 40
    Handler.files["/c.bin"] = data
    dest = tmp_path / "c.bin"
    with open(str(dest) + ".part", "wb") as f:
        f.write(data[:3000])
    downloader.download(server + "/c.bin", str(dest), len(data), hashlib.sha256(data).hexdigest())
    assert dest.read_bytes() == data
    # Only the rest was asked for
    assert Handler.hits == ["/c.bin"]


def test_download_restarts_when_server_ignores_range(server, tmp_path):
    data = b"z" * 5000
    Handler.files["/d.bin"] = data
    Handler.ranges = False
    dest = tmp_path / "d.bin"
    with open(str(dest) + ".part", "wb") as f:
        f.write(b"garbage")
    downloader.download(server + "/d.bin", str(dest), len(data), hashlib.sha256(data).hexdigest())
    assert dest.read_bytes() == data


def test_download_errors(server, tmp_path):
    with pytest.raises(downloader.DownloadError) as e:
        downloader.download(server + "/missing.bin", str(tmp_path / "m.bin"))
    assert e.value.code == "http" and "404" in e.value.message
    with pytest.raises(downloader.DownloadError) as e:
        downloader.download("http://127.0.0.1:9/x.bin", str(tmp_path / "x.bin"))
    assert e.value.code == "offline"


def test_download_cancel_keeps_the_part(server, tmp_path):
    data = b"q" * (3 * 1024 * 1024)
    Handler.files["/e.bin"] = data
    cancel = threading.Event()

    def progress(done, total):
        if done > 256 * 1024:
            cancel.set()

    with pytest.raises(downloader.DownloadError) as e:
        downloader.download(server + "/e.bin", str(tmp_path / "e.bin"), len(data), None, progress, cancel)
    assert e.value.code == "cancelled"
    assert os.path.exists(tmp_path / "e.bin.part")


def test_install_and_update_keep_user_files(tmp_path):
    folder = str(tmp_path / "content")
    os.makedirs(os.path.join(folder, "outfits"))
    with open(os.path.join(folder, "outfits", "mine.blend"), "wb") as f:
        f.write(b"user")
    v1 = tmp_path / "p1.hgpack"
    v1.write_bytes(make_pack("Base_Poses", (4, 0), {"poses/a.blend": b"a", "poses/old.blend": b"old"}))
    info = downloader.install(str(v1), folder)
    assert info.key == "Base_Poses" and info.version == (4, 0)
    assert sorted(info.files) == ["poses/a.blend", "poses/old.blend"]
    assert installed_packs(folder)["Base_Poses"].files == info.files
    v2 = tmp_path / "p2.hgpack"
    v2.write_bytes(make_pack("Base_Poses", (4, 1), {"poses/a.blend": b"a2", "poses/new.blend": b"new"}))
    steps = []
    downloader.install(str(v2), folder, progress=lambda i, n: steps.append((i, n)))
    assert steps[-1][0] == steps[-1][1] == 3
    assert not os.path.exists(os.path.join(folder, "poses", "old.blend"))
    assert open(os.path.join(folder, "poses", "a.blend"), "rb").read() == b"a2"
    assert os.path.exists(os.path.join(folder, "poses", "new.blend"))
    assert open(os.path.join(folder, "outfits", "mine.blend"), "rb").read() == b"user"
    assert installed_packs(folder)["Base_Poses"].version == (4, 1)


def test_install_rejects_other_zips_and_zip_slip(tmp_path):
    folder = str(tmp_path / "content")
    bad = tmp_path / "bad.zip"
    with zipfile.ZipFile(bad, "w") as zf:
        zf.writestr("readme.txt", "x")
    with pytest.raises(downloader.DownloadError) as e:
        downloader.install(str(bad), folder)
    assert e.value.code == "not_a_pack"
    with pytest.raises(downloader.DownloadError):
        downloader.inspect(str(tmp_path / "nothing.zip"))
    evil = tmp_path / "evil.hgpack"
    with zipfile.ZipFile(evil, "w") as zf:
        zf.writestr("content_packs/Evil.json", json.dumps({"config": {"pack_name": "Evil", "pack_version": [1, 0]}}))
        zf.writestr("../escape.txt", "x")
    downloader.install(str(evil), folder)
    assert not os.path.exists(tmp_path / "escape.txt")


def test_install_skips_macos_junk(tmp_path):
    """Packs zipped on a Mac carry __MACOSX and .DS_Store entries: not content."""
    folder = str(tmp_path / "content")
    pack = tmp_path / "mac.hgpack"
    pack.write_bytes(make_pack("Base_Poses", (4, 0), {"poses/a.blend": b"a", "__MACOSX/poses/._a.blend": b"junk", "poses/.DS_Store": b"junk"}))
    info = downloader.install(str(pack), folder)
    assert info.files == ["poses/a.blend"]
    assert not os.path.exists(os.path.join(folder, "__MACOSX"))
    assert not os.path.exists(os.path.join(folder, "poses", ".DS_Store"))


def test_remove_pack(tmp_path):
    folder = str(tmp_path / "content")
    pack = tmp_path / "p.hgpack"
    pack.write_bytes(make_pack("Trial_Content", (1, 0), {"models/trial.blend": b"t", "deep/er/x.txt": b"x"}))
    downloader.install(str(pack), folder)
    assert downloader.remove(folder, "Trial_Content")
    assert not os.path.exists(os.path.join(folder, "models"))
    assert not os.path.exists(os.path.join(folder, "deep"))
    assert "Trial_Content" not in installed_packs(folder)
    assert not downloader.remove(folder, "Trial_Content")


def test_clear_downloads(tmp_path):
    folder = str(tmp_path)
    dl = downloader.download_folder(folder)
    os.makedirs(dl)
    open(os.path.join(dl, "a.hgpack.part"), "w").close()
    downloader.clear_downloads(folder)
    assert not os.path.exists(dl)
    downloader.clear_downloads(folder)  # nothing there: fine
