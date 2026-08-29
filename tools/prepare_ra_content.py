#!/usr/bin/env python3

"""Prepare the freeware Red Alert content required by automated workers.

The repository installer manifest remains the source of truth.  This helper
downloads the declared quick-install archive, verifies its SHA-1, and extracts
only the explicitly mapped files into a worker SupportDir.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import stat
import tempfile
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class QuickInstall:
    sha1: str
    mirror_list: str
    extracts: tuple[tuple[Path, str], ...]


def parse_quickinstall(manifest: Path) -> QuickInstall:
    lines = manifest.read_text(encoding="utf-8").splitlines()
    start = next((i for i, line in enumerate(lines) if line == "quickinstall: Quick Install Package"), None)
    if start is None:
        raise ValueError(f"{manifest}: quickinstall section is missing")

    sha1 = None
    mirror_list = None
    extracts: list[tuple[Path, str]] = []
    in_extract = False
    for line in lines[start + 1 :]:
        if line and not line[0].isspace():
            break

        stripped = line.strip()
        if stripped.startswith("SHA1:"):
            sha1 = stripped.split(":", 1)[1].strip().lower()
        elif stripped.startswith("MirrorList:"):
            mirror_list = stripped.split(":", 1)[1].strip()
        elif stripped == "Extract:":
            in_extract = True
        elif in_extract and stripped:
            destination, separator, member = stripped.partition(":")
            if not separator or not destination.startswith("^SupportDir|"):
                raise ValueError(f"{manifest}: invalid quickinstall extract mapping {stripped!r}")
            extracts.append((Path(destination.removeprefix("^SupportDir|")), member.strip()))

    if sha1 is None or len(sha1) != 40:
        raise ValueError(f"{manifest}: quickinstall SHA1 is missing or invalid")
    if mirror_list is None:
        raise ValueError(f"{manifest}: quickinstall MirrorList is missing")
    if not extracts:
        raise ValueError(f"{manifest}: quickinstall Extract mapping is empty")

    return QuickInstall(sha1, mirror_list, tuple(extracts))


def sha1(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_mirrors(url: str) -> list[str]:
    with urllib.request.urlopen(url, timeout=30) as response:
        text = response.read().decode("utf-8")

    mirrors = []
    for line in text.splitlines():
        candidate = line.strip()
        if not candidate or candidate.startswith("#"):
            continue
        parsed = urllib.parse.urlparse(candidate)
        if parsed.scheme not in {"https", "http"} or not parsed.netloc:
            raise ValueError(f"Mirror list contains an unsupported URL: {candidate!r}")
        mirrors.append(candidate)

    if not mirrors:
        raise ValueError(f"Mirror list {url!r} did not contain any download URLs")
    return mirrors


def download_verified(specification: QuickInstall, destination: Path) -> None:
    errors = []
    for mirror in read_mirrors(specification.mirror_list):
        temporary = destination.with_suffix(destination.suffix + ".part")
        try:
            temporary.unlink(missing_ok=True)
            with urllib.request.urlopen(mirror, timeout=120) as response, temporary.open("wb") as output:
                shutil.copyfileobj(response, output)
            actual = sha1(temporary)
            if actual != specification.sha1:
                raise ValueError(f"SHA-1 mismatch: expected {specification.sha1}, got {actual}")
            os.replace(temporary, destination)
            return
        except Exception as exc:  # Mirrors are independent fallbacks.
            errors.append(f"{mirror}: {exc}")
            temporary.unlink(missing_ok=True)

    raise RuntimeError("Unable to download a verified RA quick-install archive:\n" + "\n".join(errors))


def _safe_destination(root: Path, relative: Path) -> Path:
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"Unsafe support-directory path: {relative}")
    destination = (root / relative).resolve()
    if destination != root and root not in destination.parents:
        raise ValueError(f"Extract path escapes the SupportDir: {relative}")
    return destination


def extract_declared(archive: Path, support_dir: Path, specification: QuickInstall) -> None:
    support_root = support_dir.resolve()
    support_root.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as package:
        for relative, member_name in specification.extracts:
            member = package.getinfo(member_name)
            unix_mode = member.external_attr >> 16
            if member.is_dir() or stat.S_ISLNK(unix_mode):
                raise ValueError(f"Declared archive member is not a regular file: {member_name}")

            destination = _safe_destination(support_root, relative)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with package.open(member) as source, tempfile.NamedTemporaryFile(
                dir=destination.parent, delete=False
            ) as temporary:
                shutil.copyfileobj(source, temporary)
                temporary_path = Path(temporary.name)
            os.replace(temporary_path, destination)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine-dir", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--support-dir", type=Path, required=True)
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()

    manifest = args.engine_dir.resolve() / "mods" / "ra-content" / "installer" / "downloads.yaml"
    specification = parse_quickinstall(manifest)
    archive = args.archive.resolve() if args.archive else args.support_dir.resolve() / "ra-quickinstall.zip"
    archive.parent.mkdir(parents=True, exist_ok=True)
    if not archive.exists() or sha1(archive) != specification.sha1:
        download_verified(specification, archive)

    extract_declared(archive, args.support_dir, specification)
    print(f"Prepared {len(specification.extracts)} declared RA files in {args.support_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
