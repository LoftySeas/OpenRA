#!/usr/bin/env python3

"""Materialize one immutable GitHub Actions distributed-smoke shard."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path


SCHEMA_VERSION = "1.0.0"
PURPOSE = "GITHUB_RUNNER_DISTRIBUTED_SMOKE"
SHARD_COUNT = 4
MAX_WORKERS = 4
MAX_WORLD_TICKS = 30000
MATCH_TIMEOUT_SECONDS = 240
VERIFICATION_TIMEOUT_SECONDS = 180
GIT_SHA = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class Selection:
    role: str
    source_job_id: str
    job_id: str


@dataclass(frozen=True)
class SmokeProfile:
    cli_name: str
    purpose: str
    shard_count: int
    max_workers: int
    max_world_ticks: int
    match_timeout_seconds: int
    verification_timeout_seconds: int
    sentinels: tuple[Selection, ...]
    unique_by_shard: tuple[tuple[Selection, ...], ...]
    include_profile_field: bool = False


SENTINELS = (
    Selection(
        "SENTINEL",
        "tr-ore-lord-normal-s01-c40-r0",
        "quick-sentinel-ore-lord-normal-c40",
    ),
    Selection(
        "SENTINEL",
        "tr-ore-lord-rush-s02-c40-r0",
        "quick-sentinel-ore-lord-rush-c40",
    ),
)

UNIQUE_BY_SHARD = (
    (
        Selection(
            "UNIQUE",
            "tr-siberian-pass-normal-s03-c40-r0",
            "quick-shard-0-siberian-pass-normal-c40",
        ),
        Selection(
            "UNIQUE",
            "tr-siberian-pass-rush-s04-c40-r0",
            "quick-shard-0-siberian-pass-rush-c40",
        ),
    ),
    (
        Selection(
            "UNIQUE",
            "tr-behind-the-veil-normal-s05-c40-r0",
            "quick-shard-1-behind-the-veil-normal-c40",
        ),
        Selection(
            "UNIQUE",
            "tr-behind-the-veil-rush-s06-c40-r0",
            "quick-shard-1-behind-the-veil-rush-c40",
        ),
    ),
    (
        Selection(
            "UNIQUE",
            "tr-ore-lord-normal-s07-c40-r0",
            "quick-shard-2-ore-lord-normal-c40",
        ),
        Selection(
            "UNIQUE",
            "tr-ore-lord-rush-s08-c40-r0",
            "quick-shard-2-ore-lord-rush-c40",
        ),
    ),
    (
        Selection(
            "UNIQUE",
            "tr-siberian-pass-normal-s09-c40-r0",
            "quick-shard-3-siberian-pass-normal-c40",
        ),
        Selection(
            "UNIQUE",
            "tr-behind-the-veil-rush-s10-c40-r0",
            "quick-shard-3-behind-the-veil-rush-c40",
        ),
    ),
)

FOUR_SHARD_PROFILE = SmokeProfile(
    "four-shard-smoke",
    PURPOSE,
    SHARD_COUNT,
    MAX_WORKERS,
    MAX_WORLD_TICKS,
    MATCH_TIMEOUT_SECONDS,
    VERIFICATION_TIMEOUT_SECONDS,
    SENTINELS,
    UNIQUE_BY_SHARD,
)
TWENTY_SHARD_PROFILE = SmokeProfile(
    "twenty-shard-canary",
    "GITHUB_RUNNER_TWENTY_SHARD_CANARY",
    20,
    1,
    30000,
    120,
    90,
    (
        Selection(
            "SENTINEL",
            "tr-ore-lord-normal-s01-c40-r0",
            "canary-sentinel-ore-lord-normal-c40",
        ),
    ),
    tuple(() for _ in range(20)),
    True,
)
PROFILES = {
    FOUR_SHARD_PROFILE.cli_name: FOUR_SHARD_PROFILE,
    TWENTY_SHARD_PROFILE.cli_name: TWENTY_SHARD_PROFILE,
}


def smoke_profile(profile_name: str | None = None) -> SmokeProfile:
    if profile_name is None:
        return FOUR_SHARD_PROFILE
    try:
        return PROFILES[profile_name]
    except KeyError as exc:
        raise ValueError(f"Unknown distributed-smoke profile: {profile_name!r}") from exc


def serialized(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def bytes_sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def object_sha256(value: object) -> str:
    canonical = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return bytes_sha256(canonical)


def write_immutable(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != content:
            raise ValueError(f"Refusing to overwrite changed smoke artifact: {path}")
        return

    handle, temporary_name = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, path)
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def relative_or_absolute(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def validate_git_sha(name: str, value: str) -> str:
    normalized = value.lower()
    if not GIT_SHA.fullmatch(normalized):
        raise ValueError(f"{name} must be a full 40-character Git SHA")
    return normalized


def selections_for_shard(
    shard_index: int,
    profile_name: str | None = None,
) -> tuple[Selection, ...]:
    profile = smoke_profile(profile_name)
    if shard_index < 0 or shard_index >= profile.shard_count:
        raise ValueError(
            f"shard_index must be in the range 0..{profile.shard_count - 1}"
        )
    selections = profile.sentinels + profile.unique_by_shard[shard_index]
    if (
        len(selections) != len(profile.sentinels) + len(profile.unique_by_shard[shard_index])
        or len({item.job_id for item in selections}) != len(selections)
        or len(selections) < 1
    ):
        raise AssertionError("Distributed smoke profile contains invalid derived jobs")
    invalid = [item.job_id for item in selections if re.search(r"-r[01]$", item.job_id)]
    if invalid:
        raise AssertionError(f"Derived smoke ids must not form implicit repeat pairs: {invalid!r}")
    return selections


def load_source_manifest(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to read source manifest {path}: {exc}") from exc
    if not isinstance(value, dict) or set(value) != {
        "schemaVersion",
        "matchTimeoutSeconds",
        "verificationTimeoutSeconds",
        "matches",
    }:
        raise ValueError("Source manifest must have the registered experiment-manifest shape")
    if value["schemaVersion"] != SCHEMA_VERSION or not isinstance(value["matches"], list):
        raise ValueError("Source manifest schemaVersion or matches is invalid")
    return value


def prepare(
    source_manifest: Path,
    output_dir: Path,
    shard_index: int,
    controller_script: Path,
    execution_sha: str,
    design_base_sha: str,
    profile_name: str | None = None,
) -> Path:
    source_manifest = source_manifest.resolve()
    source_root = source_manifest.parent
    output_dir = output_dir.resolve()
    controller_script = controller_script.resolve()
    execution_sha = validate_git_sha("execution_sha", execution_sha)
    design_base_sha = validate_git_sha("design_base_sha", design_base_sha)
    profile = smoke_profile(profile_name)
    selections = selections_for_shard(shard_index, profile.cli_name)

    if not source_manifest.is_file():
        raise ValueError(f"Source manifest does not exist: {source_manifest}")
    if not controller_script.is_file():
        raise ValueError(f"Controller script does not exist: {controller_script}")

    source = load_source_manifest(source_manifest)
    source_jobs: dict[str, dict] = {}
    for raw_job in source["matches"]:
        if not isinstance(raw_job, dict) or not isinstance(raw_job.get("id"), str):
            raise ValueError("Source manifest contains an invalid job")
        if raw_job["id"] in source_jobs:
            raise ValueError(f"Source manifest contains duplicate job {raw_job['id']!r}")
        source_jobs[raw_job["id"]] = raw_job

    quick_matches = []
    job_provenance = []
    for selection in selections:
        source_job = source_jobs.get(selection.source_job_id)
        if source_job is None:
            raise ValueError(f"Source manifest lacks selected job {selection.source_job_id!r}")
        specification_name = source_job.get("specificationPath")
        if not isinstance(specification_name, str) or not specification_name:
            raise ValueError(f"Source job lacks specificationPath: {selection.source_job_id}")
        source_specification = (source_root / specification_name).resolve()
        try:
            source_specification.relative_to(source_root)
        except ValueError as exc:
            raise ValueError(
                f"Source specification escapes the manifest root: {specification_name!r}"
            ) from exc
        if not source_specification.is_file():
            raise ValueError(f"Source specification does not exist: {source_specification}")
        try:
            specification = json.loads(source_specification.read_text(encoding="utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"Invalid source specification {source_specification}: {exc}") from exc
        if not isinstance(specification, dict):
            raise ValueError(f"Source specification must be an object: {source_specification}")

        candidate_name = specification.get("candidatePath")
        candidate_sha256 = source_job.get("expectedCandidateSha256")
        if not isinstance(candidate_name, str) or not candidate_name:
            raise ValueError(f"Selected source specification lacks candidatePath: {source_specification}")
        if not isinstance(candidate_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", candidate_sha256):
            raise ValueError(f"Selected source job lacks an exact candidate SHA-256: {selection.source_job_id}")
        source_candidate = (source_specification.parent / candidate_name).resolve()
        if not source_candidate.is_file() or file_sha256(source_candidate) != candidate_sha256:
            raise ValueError(f"Candidate bytes differ from source job provenance: {source_candidate}")

        quick_specification = output_dir / "specifications" / f"{selection.job_id}.json"
        output_candidate = (quick_specification.parent / candidate_name).resolve()
        try:
            output_candidate.relative_to(output_dir)
        except ValueError as exc:
            raise ValueError(
                f"candidatePath escapes the distributed-smoke output: {candidate_name!r}"
            ) from exc
        write_immutable(output_candidate, source_candidate.read_bytes())

        quick_specification_value = dict(specification)
        quick_specification_value["maxWorldTicks"] = profile.max_world_ticks
        quick_specification_bytes = serialized(quick_specification_value)
        write_immutable(quick_specification, quick_specification_bytes)

        quick_job = dict(source_job)
        quick_job["id"] = selection.job_id
        quick_job["specificationPath"] = quick_specification.relative_to(output_dir).as_posix()
        quick_matches.append(quick_job)
        job_provenance.append(
            {
                "id": selection.job_id,
                "role": selection.role,
                "sourceJobId": selection.source_job_id,
                "sourceJobSha256": object_sha256(source_job),
                "jobSha256": object_sha256(quick_job),
                "sourceSpecificationPath": relative_or_absolute(source_specification, source_root),
                "sourceSpecificationSha256": file_sha256(source_specification),
                "specificationPath": quick_job["specificationPath"],
                "specificationSha256": bytes_sha256(quick_specification_bytes),
                "sourceCandidatePath": relative_or_absolute(source_candidate, source_root),
                "candidatePath": output_candidate.relative_to(output_dir).as_posix(),
                "expectedCandidateSha256": candidate_sha256,
            }
        )

    manifest = {
        "schemaVersion": SCHEMA_VERSION,
        "matchTimeoutSeconds": profile.match_timeout_seconds,
        "verificationTimeoutSeconds": profile.verification_timeout_seconds,
        "matches": quick_matches,
    }
    manifest_path = output_dir / "github-distributed-smoke-manifest.json"
    manifest_bytes = serialized(manifest)
    write_immutable(manifest_path, manifest_bytes)

    registration = {
        "schemaVersion": SCHEMA_VERSION,
        "purpose": profile.purpose,
        "decisionInfluence": "NONE",
        "formalSelection": False,
        "shardIndex": shard_index,
        "shardCount": profile.shard_count,
        "maxWorkers": profile.max_workers,
        "jobCount": len(quick_matches),
        "maxWorldTicks": profile.max_world_ticks,
        "matchTimeoutSeconds": profile.match_timeout_seconds,
        "verificationTimeoutSeconds": profile.verification_timeout_seconds,
        "executionSha": execution_sha,
        "designBaseSha": design_base_sha,
        "sourceManifestPath": relative_or_absolute(source_manifest, output_dir),
        "sourceManifestSha256": file_sha256(source_manifest),
        "manifestPath": manifest_path.relative_to(output_dir).as_posix(),
        "manifestSha256": bytes_sha256(manifest_bytes),
        "controllerScriptPath": str(controller_script),
        "controllerScriptSha256": file_sha256(controller_script),
        "sentinelJobIds": [item.job_id for item in profile.sentinels],
        "uniqueJobIds": [item.job_id for item in profile.unique_by_shard[shard_index]],
        "jobs": job_provenance,
    }
    if profile.include_profile_field:
        registration["profile"] = profile.cli_name
    registration_path = output_dir / "github-distributed-smoke-registration.json"
    write_immutable(registration_path, serialized(registration))
    return manifest_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--shard-index", type=int, required=True)
    parser.add_argument("--controller-script", type=Path, required=True)
    parser.add_argument("--execution-sha", required=True)
    parser.add_argument("--design-base-sha", required=True)
    parser.add_argument("--profile", choices=sorted(PROFILES))
    args = parser.parse_args()
    manifest = prepare(
        args.source_manifest,
        args.output_dir,
        args.shard_index,
        args.controller_script,
        args.execution_sha,
        args.design_base_sha,
        args.profile,
    )
    print(manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
