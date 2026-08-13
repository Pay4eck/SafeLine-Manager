from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import stat
import tempfile
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_METADATA = REPOSITORY_ROOT / "tests" / "fixtures" / "xray-v26.3.27.json"
OFFICIAL_RELEASE_PREFIX = "https://github.com/XTLS/Xray-core/releases/download/"


def detect_platform() -> str:
    operating_system = platform.system().lower()
    architecture = platform.machine().lower()
    architecture_name = {
        "x86_64": "amd64",
        "amd64": "amd64",
        "aarch64": "arm64",
        "arm64": "arm64",
    }.get(architecture)
    if operating_system not in {"linux", "windows"} or architecture_name is None:
        raise RuntimeError(f"Unsupported validation host: {operating_system}-{architecture}")
    return f"{operating_system}-{architecture_name}"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_extract(archive_path: Path, destination: Path) -> None:
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path) as archive:
        for member in archive.infolist():
            member_path = PurePosixPath(member.filename)
            if member_path.is_absolute() or ".." in member_path.parts:
                raise RuntimeError(f"Unsafe path in Xray archive: {member.filename}")
            file_type = (member.external_attr >> 16) & 0o170000
            if file_type == stat.S_IFLNK:
                raise RuntimeError(f"Symlink is not allowed in Xray archive: {member.filename}")

            target = (destination / Path(*member_path.parts)).resolve()
            try:
                target.relative_to(destination)
            except ValueError as error:
                raise RuntimeError(f"Archive path escaped destination: {member.filename}") from error
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download an exact official Xray archive and verify its pinned SHA-256."
    )
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    parser.add_argument("--platform", default="auto")
    parser.add_argument("--destination", type=Path, required=True)
    arguments = parser.parse_args()

    metadata = json.loads(arguments.metadata.read_text(encoding="utf-8"))
    platform_name = detect_platform() if arguments.platform == "auto" else arguments.platform
    artifact = metadata["artifacts"].get(platform_name)
    if artifact is None:
        raise RuntimeError(f"No pinned Xray artifact for {platform_name}")

    url = artifact["url"]
    expected_digest = artifact["sha256"]
    version = metadata["version"]
    if not url.startswith(OFFICIAL_RELEASE_PREFIX):
        raise RuntimeError("Refusing non-official Xray download source")
    if f"/v{version}/" not in url or "/latest/" in url:
        raise RuntimeError("Xray URL does not pin the selected release version")
    if len(expected_digest) != 64:
        raise RuntimeError("Pinned Xray SHA-256 is malformed")

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "SafeLine-Manager-Xray-validation"},
    )
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(prefix="safeline-xray-", suffix=".zip", delete=False) as temporary:
            temporary_path = Path(temporary.name)
            with urllib.request.urlopen(request, timeout=120) as response:
                shutil.copyfileobj(response, temporary)

        actual_digest = sha256(temporary_path)
        if actual_digest != expected_digest:
            raise RuntimeError(
                f"Xray checksum mismatch: expected {expected_digest}, got {actual_digest}"
            )
        safe_extract(temporary_path, arguments.destination)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

    executable = arguments.destination / artifact["executable"]
    if not executable.is_file():
        raise RuntimeError(f"Verified archive did not contain {artifact['executable']}")
    if os.name != "nt":
        executable.chmod(executable.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    print(f"Installed official Xray {version} for {platform_name}")
    print(f"Source: {url}")
    print(f"Verified SHA-256: {expected_digest}")
    print(f"Executable: {executable.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
