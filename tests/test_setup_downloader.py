"""The download engine against a local HTTP server: resume, checksums, cancel,
installing over an older version without touching the user's own files."""
import hashlib
import http.server
import json
import os
import threading
import zipfile

import pytest
from setup_fakes import Handler, exists, make_pack, write_file, write_pack

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
    Handler.overrides = {}


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


# Network errors in plain words


def test_resume_refuses_a_portal_page(server, tmp_path):
    """A sign-in page answering a resume must not truncate a big .part."""
    Handler.overrides["/f.bin"] = (200, "text/html; charset=utf-8", b"<html>Please sign in</html>")
    dest = tmp_path / "f.bin"
    part = str(dest) + ".part"
    with open(part, "wb") as f:
        f.write(b"p" * 5000)
    with pytest.raises(downloader.DownloadError) as e:
        downloader.download(server + "/f.bin", str(dest), 10000)
    assert e.value.code == "bad_response" and e.value.retryable
    assert os.path.getsize(part) == 5000


def test_proxy_tls_and_server_errors(server, tmp_path):
    Handler.overrides["/p.bin"] = (407, "text/html", b"<html>Proxy Authentication Required</html>")
    with pytest.raises(downloader.DownloadError) as e:
        downloader.download(server + "/p.bin", str(tmp_path / "p.bin"))
    assert e.value.code == "proxy" and not e.value.retryable
    Handler.overrides["/s.bin"] = (503, "text/html", b"<html>busy</html>")
    with pytest.raises(downloader.DownloadError) as e:
        downloader.download(server + "/s.bin", str(tmp_path / "s.bin"))
    assert e.value.code == "http" and e.value.status == 503 and e.value.retryable
    # https against a plain http server: the handshake fails
    with pytest.raises(downloader.DownloadError) as e:
        downloader.download(server.replace("http://", "https://") + "/a.bin", str(tmp_path / "t.bin"))
    assert e.value.code == "tls" and not e.value.retryable


def test_retryable():
    retry = {code: downloader.DownloadError(code).retryable for code in ("offline", "timeout", "bad_response", "tls", "proxy", "disk", "checksum", "cancelled", "not_a_pack")}
    assert retry == {"offline": True, "timeout": True, "bad_response": True, "tls": False, "proxy": False, "disk": False, "checksum": False, "cancelled": False, "not_a_pack": False}
    assert downloader.DownloadError("http", status=500).retryable and downloader.DownloadError("http", status=403).retryable
    assert not downloader.DownloadError("http", status=404).retryable


def test_unwritable_destination_is_a_disk_error(server, tmp_path):
    blocker = tmp_path / "a_file"
    blocker.write_bytes(b"x")
    with pytest.raises(downloader.DownloadError) as e:
        downloader.download(server + "/a.bin", str(blocker / "sub" / "a.bin"))
    assert e.value.code == "disk"


def test_free_space(tmp_path):
    assert downloader.free_space(str(tmp_path)) > 0
    assert downloader.free_space(str(tmp_path / "not" / "yet")) > 0  # the nearest existing parent
    assert downloader.free_space("") is None


# Removing only what nobody else lists


def test_remove_keeps_files_other_packs_list(tmp_path):
    folder = str(tmp_path)
    write_pack(folder, "Base_Hair", (4, 1), ["hair/shared.blend", "hair/base.blend"])
    write_pack(folder, "Extra", (1, 0), ["hair/shared.blend", "hair/extra.blend"])
    assert downloader.remove(folder, "Extra")
    assert exists(folder, "hair/shared.blend") and exists(folder, "hair/base.blend")
    assert not exists(folder, "hair/extra.blend")
    assert set(installed_packs(folder)) == {"Base_Hair"}


def test_update_keeps_a_dropped_file_another_pack_lists(tmp_path):
    folder = str(tmp_path / "content")
    v1 = tmp_path / "v1.hgpack"
    v1.write_bytes(make_pack("Base_Poses", (4, 0), {"poses/a.blend": b"a", "poses/shared.blend": b"s"}))
    downloader.install(str(v1), folder)
    write_pack(folder, "Other", (1, 0), ["poses/shared.blend"], on_disk=False)
    v2 = tmp_path / "v2.hgpack"
    v2.write_bytes(make_pack("Base_Poses", (4, 1), {"poses/a.blend": b"a2"}))
    downloader.install(str(v2), folder)
    assert exists(folder, "poses/shared.blend")
    assert installed_packs(folder)["Base_Poses"].files == ["poses/a.blend"]


def test_interrupted_update_keeps_the_old_version(tmp_path):
    """Cancel (or a crash, or a full disk) halfway through: the old version
    stays recorded, with every file that may be on disk, so the pack is not
    "up to date" with an empty list, and the next install cleans up."""
    folder = str(tmp_path / "content")
    v1 = tmp_path / "v1.hgpack"
    v1.write_bytes(make_pack("Base_Clothes", (4, 0), {"a.blend": b"a1", "old_only.blend": b"o"}))
    downloader.install(str(v1), folder)
    v2 = tmp_path / "v2.hgpack"
    v2.write_bytes(make_pack("Base_Clothes", (4, 1), {"a.blend": b"a2", "b.blend": b"b", "c.blend": b"c", "d.blend": b"d"}))
    cancel = threading.Event()

    def progress(done, total):
        if done == 2:
            cancel.set()

    with pytest.raises(downloader.DownloadError) as e:
        downloader.install(str(v2), folder, progress, cancel)
    assert e.value.code == "cancelled"
    pack = installed_packs(folder)["Base_Clothes"]
    assert pack.version == (4, 0)
    assert set(pack.files) == {"a.blend", "old_only.blend", "b.blend", "c.blend", "d.blend"}
    assert exists(folder, "old_only.blend")
    downloader.install(str(v2), folder)
    pack = installed_packs(folder)["Base_Clothes"]
    assert pack.version == (4, 1) and sorted(pack.files) == ["a.blend", "b.blend", "c.blend", "d.blend"]
    assert not exists(folder, "old_only.blend")
    assert sorted(os.listdir(os.path.join(folder, "content_packs"))) == ["Base_Clothes.json"]


def test_case_only_rename_keeps_the_new_file(tmp_path):
    folder = str(tmp_path / "content")
    v1 = tmp_path / "v1.hgpack"
    v1.write_bytes(make_pack("Base_Hair", (4, 0), {"hair/Short Bob.blend": b"old"}))
    downloader.install(str(v1), folder)
    v2 = tmp_path / "v2.hgpack"
    v2.write_bytes(make_pack("Base_Hair", (4, 1), {"hair/short bob.blend": b"new"}))
    downloader.install(str(v2), folder)
    names = os.listdir(os.path.join(folder, "hair"))
    assert len(names) == 1
    with open(os.path.join(folder, "hair", names[0]), "rb") as f:
        assert f.read() == b"new"


def test_case_insensitive_detection(tmp_path):
    (tmp_path / "Probe").mkdir()
    insensitive = os.path.exists(str(tmp_path / "PROBE"))
    assert downloader.is_case_insensitive(str(tmp_path)) == insensitive


def test_remove_empty_dirs_prunes_only_emptied_parents(tmp_path):
    folder = str(tmp_path)
    os.makedirs(os.path.join(folder, "my projects", "empty"))
    path = write_file(folder, "poses/deep/er/a.blend")
    write_file(folder, "poses/keep.blend")
    os.remove(path)
    downloader.remove_empty_dirs(folder, [path])
    assert not os.path.exists(os.path.join(folder, "poses", "deep"))
    assert exists(folder, "poses/keep.blend")
    assert os.path.isdir(os.path.join(folder, "my projects", "empty"))
    downloader.remove_empty_dirs(folder, [os.path.join(folder, "x.blend")])  # the folder itself stays
    assert os.path.isdir(folder)


def test_remove_leaves_the_users_empty_folders(tmp_path):
    folder = str(tmp_path / "content")
    os.makedirs(os.path.join(folder, "outfits", "my empty folder"))
    pack = tmp_path / "p.hgpack"
    pack.write_bytes(make_pack("Base_Poses", (4, 0), {"poses/a.blend": b"a"}))
    downloader.install(str(pack), folder)
    downloader.remove(folder, "Base_Poses")
    assert os.path.isdir(os.path.join(folder, "outfits", "my empty folder"))
    assert not os.path.exists(os.path.join(folder, "poses"))


# The download lock


def test_lock(tmp_path):
    folder = str(tmp_path)
    assert downloader.acquire_lock(folder)
    assert downloader.acquire_lock(folder)  # ours already
    assert downloader.lock_holder(folder) is None
    downloader.refresh_lock(folder)
    downloader.clear_downloads(folder)  # keeps a held lock
    assert os.path.exists(downloader.lock_path(folder))
    downloader.release_lock(folder)
    assert not os.path.exists(downloader.lock_path(folder))
    # Another live process on this machine holds it
    os.makedirs(downloader.download_folder(folder), exist_ok=True)
    other = {"pid": os.getppid(), "host": __import__("socket").gethostname(), "time": __import__("time").time()}
    with open(downloader.lock_path(folder), "w") as f:
        json.dump(other, f)
    assert not downloader.acquire_lock(folder)
    assert downloader.lock_holder(folder)["pid"] == os.getppid()
    downloader.release_lock(folder)  # not ours: stays
    assert os.path.exists(downloader.lock_path(folder))
    # A lock not refreshed for longer than LOCK_STALE is taken over
    other["time"] -= downloader.LOCK_STALE + 1
    with open(downloader.lock_path(folder), "w") as f:
        json.dump(other, f)
    assert downloader.acquire_lock(folder)
    downloader.release_lock(folder)
    # So is a garbled one
    os.makedirs(downloader.download_folder(folder), exist_ok=True)
    with open(downloader.lock_path(folder), "w") as f:
        f.write("{")
    assert downloader.acquire_lock(folder)
    downloader.release_lock(folder)
