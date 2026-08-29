#!/usr/bin/env python3

"""Select the frozen StrategicAI GitHub runner calibration jobs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path


SCHEMA_VERSION = "1.0.0"
CALIBRATION_CELLS = (
    "tr-ore-lord-normal-s01-c20",
    "tr-behind-the-veil-rush-s06-c20",
    "tr-siberian-pass-normal-s02-c30",
    "tr-ore-lord-rush-s07-c30",
    "tr-behind-the-veil-normal-s03-c40",
    "tr-siberian-pass-rush-s08-c40",
    "tr-ore-lord-normal-s04-c50",
    "tr-behind-the-veil-rush-s09-c50",
    "tr-siberian-pass-normal-s05-c60",
    "tr-ore-lord-rush-s10-c60",
)
CALIBRATION_JOB_IDS = tuple(f"{cell}-r{repeat}" for cell in CALIBRATION_CELLS for repeat in range(2))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def serialized(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, path)
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def select_calibration(source_manifest: Path, output_manifest: Path) -> Path:
    source_manifest = source_manifest.resolve()
    output_manifest = output_manifest.resolve()
    source = json.loads(source_manifest.read_text(encoding="utf-8"))
    if not isinstance(source, dict) or set(source) != {
        "schemaVersion",
        "matchTimeoutSeconds",
        "verificationTimeoutSeconds",
        "matches",
    }:
        raise ValueError("Source experiment manifest has an unsupported shape")
    if source["schemaVersion"] != SCHEMA_VERSION or not isinstance(source["matches"], list):
        raise ValueError("Source experiment manifest has an unsupported version")

    by_id = {}
    for match in source["matches"]:
        if not isinstance(match, dict) or not isinstance(match.get("id"), str):
            raise ValueError("Source experiment manifest contains an invalid match")
        if match["id"] in by_id:
            raise ValueError(f"Source experiment manifest contains duplicate match {match['id']!r}")
        by_id[match["id"]] = match

    missing = [job_id for job_id in CALIBRATION_JOB_IDS if job_id not in by_id]
    if missing:
        raise ValueError(f"Source experiment manifest lacks calibration jobs: {', '.join(missing)}")

    selected = []
    for job_id in CALIBRATION_JOB_IDS:
        match = dict(by_id[job_id])
        source_specification = (source_manifest.parent / match["specificationPath"]).resolve()
        if not source_specification.is_file():
            raise ValueError(f"Calibration specification does not exist: {source_specification}")
        match["specificationPath"] = Path(
            os.path.relpath(source_specification, output_manifest.parent)
        ).as_posix()
        selected.append(match)

    calibration = {
        "schemaVersion": SCHEMA_VERSION,
        "matchTimeoutSeconds": source["matchTimeoutSeconds"],
        "verificationTimeoutSeconds": source["verificationTimeoutSeconds"],
        "matches": selected,
    }
    atomic_write(output_manifest, serialized(calibration))
    registration = {
        "schemaVersion": SCHEMA_VERSION,
        "sourceManifestSha256": file_sha256(source_manifest),
        "calibrationManifestSha256": file_sha256(output_manifest),
        "jobCount": len(selected),
        "jobIds": list(CALIBRATION_JOB_IDS),
    }
    atomic_write(output_manifest.with_name("github-calibration-registration.json"), serialized(registration))
    return output_manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--output-manifest", type=Path, required=True)
    args = parser.parse_args()
    select_calibration(args.source_manifest, args.output_manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
