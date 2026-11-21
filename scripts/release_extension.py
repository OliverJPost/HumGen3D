"""Build the extension zip and the repository index for humgen3d.com/ext, and
publish them to the mirror.

    python scripts/release_extension.py [--blender <path>] [--out <folder>]
    python scripts/release_extension.py --publish [--dry-run]

The build writes `<out>/humgen3d-<version>.zip` and `<out>/index.json` with
Blender's own `extension build` and `extension server-generate` commands.

`--publish` then uploads both to the mirror, the folder `ext/` of the
downloads bucket. The website serves the repository from there when its
`EXT_INDEX_URL` / `EXT_ARCHIVE_BASE_URL` point at it, and the trial page's
script reads the zip there to add a lead's trial id (the website repo's
docs/addon-setup.md, "The mirror"). Afterwards it checks what a visitor gets:
the index, the bytes of the zip, and that a page of the site may read the
zip. This is the whole release of the staged rollout; no git tag is involved.
`--dry-run` does everything but the upload.

Publishing needs the AWS command line tool and a profile for the bucket, set
up once on this computer (nothing of it is kept in the repository):

    aws configure --profile humgen-r2
        key id and secret of an R2 API token with "Object Read & Write" on
        the bucket, region "auto"
    aws configure set endpoint_url https://<account id>.r2.cloudflarestorage.com --profile humgen-r2

Run it from the add-on folder after the version in blender_manifest.toml was
bumped and the tests passed.
"""
import argparse
import glob
import hashlib
import json
import os
import platform
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from typing import Dict, List, Optional, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_BLENDER = {
    "Darwin": "/Applications/Blender 5.1.app/Contents/MacOS/Blender",
    "Windows": r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe",
    "Linux": "blender",
}

# Where the mirror is: the public downloads bucket and its address
PROFILE = "humgen-r2"
BUCKET = "humgen3d"
PREFIX = "ext"
BASE_URL = "https://downloads.humangenerator3d.com"
SITE = "https://humgen3d.com"

# What a zip must hold, and what must never be in one. A `.git` *file* is
# what a git worktree has in place of the folder: it names a path on the
# computer the build ran on. `trial.json` is the trial page's to add.
REQUIRED = ("blender_manifest.toml", "__init__.py")
FORBIDDEN_FILES = (".git", "trial.json")
FORBIDDEN_FOLDERS = (".git", "tests", "docs", "scripts", "research_notes", "reports")

CORS_RULE = '[{ "AllowedOrigins": ["%s"], "AllowedMethods": ["GET"] }]'


def manifest_version() -> str:
    with open(os.path.join(ROOT, "blender_manifest.toml"), encoding="utf-8") as f:
        match = re.search(r'^version\s*=\s*"([^"]+)"', f.read(), re.MULTILINE)
    if not match:
        raise SystemExit("No version in blender_manifest.toml")
    return match.group(1)


def run(blender: str, *args: str, env: Optional[Dict[str, str]] = None) -> None:
    cmd = [blender, "--command", *args]
    print("+", " ".join(cmd), flush=True)
    subprocess.check_call(cmd, cwd=ROOT, env=env)


def sha256_of(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def unfit(names: List[str]) -> Tuple[List[str], List[str]]:
    """What a zip with these entries lacks, and what it holds that must not ship."""
    missing = [name for name in REQUIRED if name not in names]
    stray = [name for name in names if name in FORBIDDEN_FILES or ("/" in name and name.split("/")[0] in FORBIDDEN_FOLDERS)]
    return missing, stray


def check_zip(zip_path: str) -> None:
    """Stop when the zip lacks what an extension needs or holds what must not ship."""
    with zipfile.ZipFile(zip_path) as zf:
        missing, stray = unfit(zf.namelist())
    if missing or stray:
        raise SystemExit(
            f"{os.path.basename(zip_path)} is not fit to publish."
            + (f" Missing: {missing}." if missing else "")
            + (f" Must not ship: {stray[:8]} (see [build] paths_exclude_pattern in blender_manifest.toml)." if stray else "")
        )


def build(blender: str, out: str) -> Tuple[str, dict]:
    """The zip and the index in `out`. Returns the zip's path and its entry of the index."""
    version = manifest_version()
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out)

    # A Blender profile and settings file of its own: neither the add-ons of
    # whoever runs this nor their Human Generator settings take part
    profile = tempfile.mkdtemp(prefix="hg_build_profile_")
    env = dict(os.environ, BLENDER_USER_RESOURCES=profile, HUMGEN_SETTINGS_FILE=os.path.join(profile, "settings.json"))
    run(blender, "extension", "validate", ROOT, env=env)
    run(blender, "extension", "build", "--source-dir", ROOT, "--output-dir", out, env=env)
    zips = glob.glob(os.path.join(out, "*.zip"))
    if len(zips) != 1:
        raise SystemExit(f"Expected one zip in {out}, found {zips}")
    zip_path = os.path.join(out, f"humgen3d-{version}.zip")
    os.replace(zips[0], zip_path)
    check_zip(zip_path)
    run(blender, "extension", "server-generate", "--repo-dir", out, env=env)

    with open(os.path.join(out, "index.json"), encoding="utf-8") as f:
        index = json.load(f)
    entry = index["data"][0]
    if entry["version"] != version:
        raise SystemExit(f"The index lists version {entry['version']}, the manifest says {version}")
    return zip_path, entry


# Publishing


def fetch(url: str, headers: Optional[Dict[str, str]] = None, read: bool = True) -> Tuple[int, Dict[str, str], bytes]:
    """Status, headers (lower-case names) and body of a GET. Status 0 when the server can't be reached."""
    request = urllib.request.Request(url, headers=dict({"User-Agent": "humgen3d-release"}, **(headers or {})))
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            body = response.read() if read else b""
            return response.status, {k.lower(): v for k, v in response.headers.items()}, body
    except urllib.error.HTTPError as error:
        return error.code, {k.lower(): v for k, v in error.headers.items()}, b""
    except (urllib.error.URLError, OSError) as error:
        print("   could not reach", url, "-", error)
        return 0, {}, b""


def fresh(url: str) -> str:
    """`url` with a query string nobody used before. The bucket ignores it,
    but Cloudflare in front of the bucket keeps answers per address, a "not
    found" included (for minutes at the edge, and it tells browsers hours):
    asking the plain address for a zip before it is uploaded would leave that
    answer behind for everyone. So every look that only wants to know what
    the bucket holds goes to a fresh address."""
    return f"{url}?n={secrets.token_hex(4)}"


def mirror_url(base_url: str, prefix: str, name: str) -> str:
    return "/".join(part.strip("/") for part in (base_url, prefix, name) if part.strip("/"))


def aws(profile: str, *args: str) -> None:
    cmd = ["aws", "--profile", profile, *args]
    print("+", " ".join(cmd), flush=True)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(f"The upload failed:\n{(result.stderr or result.stdout).strip()}")


def check_profile(profile: str) -> None:
    """Stop with the setup steps when the AWS tool or the bucket's profile is missing."""
    setup = (
        f"Set it up once:\n"
        f"    aws configure --profile {profile}\n"
        f'        key id and secret of an R2 API token with "Object Read & Write" on the bucket, region "auto"\n'
        f"    aws configure set endpoint_url https://<account id>.r2.cloudflarestorage.com --profile {profile}"
    )
    if shutil.which("aws") is None:
        raise SystemExit("Publishing needs the AWS command line tool (aws), which is not installed.\n" + setup)
    for key in ("aws_access_key_id", "endpoint_url"):
        result = subprocess.run(["aws", "configure", "get", key, "--profile", profile], capture_output=True, text=True)
        if result.returncode != 0 or not result.stdout.strip():
            raise SystemExit(f'The AWS profile "{profile}" has no {key}.\n' + setup)


def released_as_tag(version: str) -> bool:
    try:
        result = subprocess.run(["git", "tag", "--list", f"v{version}"], cwd=ROOT, capture_output=True, text=True)
    except OSError:
        return False
    return bool(result.stdout.strip())


def page_may_read(url: str, site: str) -> bool:
    """Whether a script on a page of `site` may read `url`: the answer to a
    request from that origin names it (or everyone). Asked with a fresh query
    string, as the trial page does, so no cached copy answers."""
    status, headers, _ = fetch(fresh(url), {"Origin": site}, read=False)
    allowed = headers.get("access-control-allow-origin", "")
    return status == 200 and allowed in (site, "*")


def listed_entry(body: bytes) -> Optional[dict]:
    """The first entry of an index.json, or None when it is not one."""
    try:
        entry = json.loads(body)["data"][0]
    except (ValueError, KeyError, IndexError, TypeError):
        return None
    return entry if isinstance(entry, dict) else None


def publish(args: argparse.Namespace, zip_path: str, entry: dict) -> int:
    """Upload the zip and the index, then check what the mirror holds and
    serves. Returns the exit code. Before the upload it asks only fresh
    addresses (`fresh`), never the plain ones."""
    out = os.path.dirname(zip_path)
    name = os.path.basename(zip_path)
    version = entry["version"]
    local_hash = sha256_of(zip_path)
    zip_url = mirror_url(args.base_url, args.prefix, name)
    index_url = mirror_url(args.base_url, args.prefix, "index.json")
    target = "s3://" + mirror_url(args.bucket, args.prefix, "") + "/"
    print()
    print(f"Publishing {name} to {zip_url}" + (" (dry run: nothing is uploaded)" if args.dry_run else ""))
    if not args.dry_run:
        check_profile(args.profile)
    if released_as_tag(version):
        print(f"   NOTE: v{version} is a git tag, so a release with this number is out already.")
        print("         A build with other code under the same number cannot be told apart from it.")

    # A published version never changes: Blender checks a zip against the hash in the index it holds
    status, _, body = fetch(fresh(zip_url))
    same = status == 200 and hashlib.sha256(body).hexdigest() == local_hash
    if status == 200 and not same and not args.replace:
        raise SystemExit(
            f"A different {name} is on the mirror already. A published version does not change: "
            f"bump the version in blender_manifest.toml (and bl_info), or pass --replace if nobody installed it yet."
        )
    if same:
        print("   the same zip is on the mirror already; only the index is uploaded")
    uploads: List[Tuple[str, str]] = [] if same else [(zip_path, "application/zip")]
    uploads.append((os.path.join(out, "index.json"), "application/json"))  # last: it must not list a zip that is not there yet
    for path, content_type in uploads:
        if args.dry_run:
            print(f"   would upload {os.path.basename(path)} to {target}")
        else:
            aws(args.profile, "s3", "cp", path, target + os.path.basename(path), "--content-type", content_type, "--no-progress")

    print()
    print("What the mirror holds now:")
    problems: List[str] = []
    status, _, body = fetch(fresh(index_url))
    listed = listed_entry(body) if status == 200 else None
    index_ok = bool(listed and listed.get("version") == version and listed.get("archive_hash") == entry["archive_hash"])
    if index_ok:
        print(f"   index.json: version {version}")
    else:
        print(f"   index.json: NOT this build (status {status}, version {listed.get('version') if listed else None})")
    status, _, body = fetch(fresh(zip_url))
    zip_ok = status == 200 and hashlib.sha256(body).hexdigest() == local_hash
    print(f"   {name}: " + (f"these {len(body)} bytes" if zip_ok else f"NOT this build (status {status})"))
    if not args.dry_run:
        if not index_ok:
            problems.append("the index on the mirror is not the one just built")
        if not zip_ok:
            problems.append("the zip on the mirror is not the one just built")
    if status == 200:
        readable = page_may_read(zip_url, args.site)
        print(f"   readable by a page of {args.site}: {'yes' if readable else 'NO'}")
        if not readable:
            problems.append(
                f"a page of {args.site} may not read the zip, so every download on the trial page fails.\n"
                f"   Add this CORS policy to the bucket (R2 dashboard, the bucket, Settings, CORS Policy):\n"
                f"      {CORS_RULE % args.site}"
            )
    else:
        print(f"   readable by a page of {args.site}: not checked, the zip is not there")
    if zip_ok and index_ok and not args.dry_run:
        # What Blender gets: the plain addresses, which Cloudflare may answer from what it kept
        status, _, body = fetch(zip_url)
        plain_zip = status == 200 and hashlib.sha256(body).hexdigest() == local_hash
        status_index, _, body = fetch(index_url)
        plain_entry = listed_entry(body) if status_index == 200 else None
        plain_index = bool(plain_entry and plain_entry.get("archive_hash") == entry["archive_hash"])
        print(f"   at the plain addresses, as Blender asks: {'the same' if plain_zip and plain_index else 'NOT yet'}")
        if not (plain_zip and plain_index):
            problems.append(
                f"Cloudflare still answers the plain address with what it kept from before the upload "
                f"(zip: status {status}, index: status {status_index}). It lets go of that by itself, a missing file within minutes, "
                f"a replaced zip within hours; to end it now, purge these two addresses in the Cloudflare dashboard "
                f"(Caching, Configuration, Custom Purge):\n      {zip_url}\n      {index_url}"
            )

    status, _, body = fetch(f"{args.site}/ext/index.json")
    served = listed_entry(body) if status == 200 else None
    print()
    if served and served.get("version") == version:
        print(f"{args.site}/ext/index.json lists version {version}.")
    else:
        print(f"{args.site}/ext/index.json lists {served.get('version') if served else f'nothing (status {status})'}, not {version}.")
        print("It follows the mirror within five minutes when the website has these two variables (Vercel, Production):")
        print(f"    EXT_INDEX_URL={index_url}")
        print(f"    EXT_ARCHIVE_BASE_URL={mirror_url(args.base_url, args.prefix, '')}")
    for problem in problems:
        print("PROBLEM:", problem)
    if not problems:
        print("Dry run finished." if args.dry_run else "Published.")
    return 1 if problems else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--blender", default=DEFAULT_BLENDER.get(platform.system(), "blender"))
    parser.add_argument("--out", default=os.path.join(ROOT, "build", "ext"))
    parser.add_argument("--publish", action="store_true", help="upload the zip and the index to the mirror and check them")
    parser.add_argument("--dry-run", action="store_true", help="with --publish: everything but the upload")
    parser.add_argument("--replace", action="store_true", help="with --publish: overwrite a different zip of this version on the mirror")
    parser.add_argument("--profile", default=PROFILE, help="AWS profile with the bucket's token and endpoint_url")
    parser.add_argument("--bucket", default=BUCKET)
    parser.add_argument("--prefix", default=PREFIX, help="folder of the mirror in the bucket")
    parser.add_argument("--base-url", default=BASE_URL, help="public address of the bucket")
    parser.add_argument("--site", default=SITE, help="origin of the website, which must be allowed to read the zip")
    args = parser.parse_args()

    zip_path, entry = build(args.blender, os.path.abspath(args.out))
    print()
    print("Built", os.path.basename(zip_path), entry["archive_size"], "bytes", entry["archive_hash"])
    if args.publish:
        return publish(args, zip_path, entry)
    print("Publish it with: python scripts/release_extension.py --publish")
    return 0


if __name__ == "__main__":
    sys.exit(main())
