#!/usr/bin/env python3

"""Validate and aggregate the four-runner GitHub distributed smoke evidence."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import re
import statistics
import tarfile
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any


SCHEMA_VERSION = "1.0.0"
PURPOSE = "GITHUB_RUNNER_DISTRIBUTED_SMOKE"
SHARD_COUNT = 4
JOBS_PER_SHARD = 4
MAX_WORKERS = 4
MAX_WORLD_TICKS = 30000
MATCH_TIMEOUT_SECONDS = 120
VERIFICATION_TIMEOUT_SECONDS = 90
MAX_ARCHIVE_MEMBERS = 4096
MAX_ARCHIVE_BYTES = 256 * 1024**2
MAX_ARCHIVE_MEMBER_BYTES = 64 * 1024**2
MAX_COMBINED_RSS_BYTES = 11 * 1024**3
MIN_AVAILABLE_MEMORY_BYTES = 4 * 1024**3
MIN_DISK_AVAILABLE_BYTES = 10 * 1024**3
MAX_SAMPLE_GAP_MS = 2000

SHA256 = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA = re.compile(r"^[0-9a-f]{40}$")
REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")

# Keep this in the same order as strategic_ai_runner.calibration_job_evidence.
DETERMINISTIC_FIELDS = (
    "status",
    "specificationSha256",
    "expectedCandidateId",
    "expectedCandidateSha256",
    "expectedSquadSize",
    "matchExitCode",
    "matchStatus",
    "executionMode",
    "finalWorldTick",
    "finalNetworkFrame",
    "finalSyncHash",
    "orderDigestSha256",
    "strategicDecisionDigestSha256",
    "players",
    "verificationExitCode",
    "verificationStatus",
    "recordedFinalWorldTick",
    "observedFinalWorldTick",
    "verifiedFinalNetworkFrame",
    "lastValidatedSyncFrame",
    "outOfSyncFrame",
    "scheduledMatchTimeoutTick",
)


class ArchiveSafetyError(ValueError):
    """Raised before extraction when an archive violates the evidence contract."""


@dataclass
class Issues:
    failures: list[dict[str, Any]] = field(default_factory=list)

    def add(self, code: str, message: str, **context: Any) -> None:
        item: dict[str, Any] = {"code": code, "message": message}
        if context:
            item["context"] = context
        self.failures.append(item)

    def check(self, condition: bool, code: str, message: str, **context: Any) -> bool:
        if not condition:
            self.add(code, message, **context)
        return condition


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def object_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def atomic_write_json(path: Path, value: object) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, path)
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def read_json_object(path: Path, issues: Issues, code: str, *, shard: int | None = None) -> dict[str, Any] | None:
    context = {} if shard is None else {"shard": shard}
    if not path.is_file():
        issues.add(code, "Required JSON evidence is missing", path=path.name, **context)
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        issues.add(code, "Required JSON evidence is unreadable", path=path.name, error=str(exc), **context)
        return None
    if not isinstance(value, dict):
        issues.add(code, "Required JSON evidence is not an object", path=path.name, **context)
        return None
    return value


def _safe_archive_name(name: str, allowed_roots: set[str]) -> tuple[str, ...]:
    if not isinstance(name, str) or not name or "\x00" in name:
        raise ArchiveSafetyError("archive member has an empty or NUL-containing name")
    if "\\" in name:
        raise ArchiveSafetyError(f"archive member uses a backslash path: {name!r}")
    posix = PurePosixPath(name)
    windows = PureWindowsPath(name)
    if posix.is_absolute() or windows.is_absolute() or windows.drive:
        raise ArchiveSafetyError(f"archive member has an absolute path: {name!r}")
    parts = posix.parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise ArchiveSafetyError(f"archive member has an unsafe path component: {name!r}")
    if parts[0] not in allowed_roots:
        raise ArchiveSafetyError(f"archive member has an unexpected top-level path: {name!r}")
    lowered = tuple(part.casefold() for part in parts)
    if "content" in lowered:
        raise ArchiveSafetyError(f"archive member contains a forbidden Content directory: {name!r}")
    if lowered[-1] == "ra-quickinstall.zip" or lowered[-1].endswith((".zip", ".mix", ".aud")):
        raise ArchiveSafetyError(f"archive member has a forbidden payload suffix: {name!r}")
    return parts


def safe_extract_tar(archive: Path, destination: Path, shard: int) -> dict[str, Any]:
    """Review every member, then manually copy regular files into a new root."""

    allowed_roots = {
        f"m3-distributed-shard-{shard}",
        f"m3-distributed-registration-{shard}",
    }
    destination.mkdir(parents=True, exist_ok=False)
    with tarfile.open(archive, mode="r:gz") as stream:
        members = stream.getmembers()
        if len(members) > MAX_ARCHIVE_MEMBERS:
            raise ArchiveSafetyError(
                f"archive has {len(members)} members; limit is {MAX_ARCHIVE_MEMBERS}"
            )

        reviewed: list[tuple[tarfile.TarInfo, tuple[str, ...]]] = []
        seen: set[str] = set()
        roots: set[str] = set()
        total_bytes = 0
        for member in members:
            parts = _safe_archive_name(member.name, allowed_roots)
            roots.add(parts[0])
            collision_key = "/".join(parts).casefold()
            if collision_key in seen:
                raise ArchiveSafetyError(f"archive contains a duplicate path: {member.name!r}")
            seen.add(collision_key)

            if member.issym() or member.islnk():
                raise ArchiveSafetyError(f"archive contains a link: {member.name!r}")
            if member.ischr() or member.isblk() or member.isfifo() or member.isdev():
                raise ArchiveSafetyError(f"archive contains a device or FIFO: {member.name!r}")
            if not member.isdir() and not member.isreg():
                raise ArchiveSafetyError(f"archive contains an unsupported member type: {member.name!r}")
            if getattr(member, "sparse", None):
                raise ArchiveSafetyError(f"archive contains a sparse file: {member.name!r}")
            if member.size < 0 or member.size > MAX_ARCHIVE_MEMBER_BYTES:
                raise ArchiveSafetyError(f"archive member is too large: {member.name!r}")
            if member.isdir() and member.size != 0:
                raise ArchiveSafetyError(f"archive directory has a nonzero size: {member.name!r}")
            if member.isreg():
                total_bytes += member.size
                if total_bytes > MAX_ARCHIVE_BYTES:
                    raise ArchiveSafetyError(
                        f"archive expands beyond the {MAX_ARCHIVE_BYTES}-byte limit"
                    )
            reviewed.append((member, parts))

        if roots != allowed_roots:
            raise ArchiveSafetyError(
                f"archive top-level directories are {sorted(roots)!r}; expected {sorted(allowed_roots)!r}"
            )

        # Do not use extract/extractall: archive metadata is deliberately not applied.
        for member, parts in reviewed:
            target = destination.joinpath(*parts)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            source = stream.extractfile(member)
            if source is None:
                raise ArchiveSafetyError(f"regular archive member has no data: {member.name!r}")
            copied = 0
            with source, target.open("xb") as output:
                while True:
                    block = source.read(min(1024 * 1024, member.size - copied + 1))
                    if not block:
                        break
                    copied += len(block)
                    if copied > member.size:
                        raise ArchiveSafetyError(f"archive member exceeds its declared size: {member.name!r}")
                    output.write(block)
            if copied != member.size:
                raise ArchiveSafetyError(f"archive member is truncated: {member.name!r}")

    return {
        "archive": archive.name,
        "memberCount": len(members),
        "totalRegularFileBytes": total_bytes,
        "allowedTopLevelDirectories": sorted(allowed_roots),
        "safe": True,
    }


def resolve_confined_path(
    base: Path,
    relative: object,
    containment_root: Path,
    issues: Issues,
    code: str,
    shard: int,
) -> Path | None:
    if not isinstance(relative, str) or not relative or "\\" in relative:
        issues.add(code, "Registered path is missing or unsafe", shard=shard, path=relative)
        return None
    posix = PurePosixPath(relative)
    windows = PureWindowsPath(relative)
    if posix.is_absolute() or windows.is_absolute() or windows.drive:
        issues.add(code, "Registered path must be relative", shard=shard, path=relative)
        return None
    target = (base / Path(*posix.parts)).resolve()
    root = containment_root.resolve()
    try:
        target.relative_to(root)
    except ValueError:
        issues.add(code, "Registered path escapes its evidence root", shard=shard, path=relative)
        return None
    return target


def calibration_job_evidence(job: dict[str, Any]) -> dict[str, Any]:
    match = job.get("match") if isinstance(job.get("match"), dict) else {}
    match_result = match.get("result") if isinstance(match.get("result"), dict) else {}
    verification = job.get("verification") if isinstance(job.get("verification"), dict) else {}
    verification_result = (
        verification.get("result") if isinstance(verification.get("result"), dict) else {}
    )
    return {
        "status": job.get("status"),
        "specificationSha256": job.get("specificationSha256"),
        "expectedCandidateId": job.get("expectedCandidateId"),
        "expectedCandidateSha256": job.get("expectedCandidateSha256"),
        "expectedSquadSize": job.get("expectedSquadSize"),
        "matchExitCode": match.get("exitCode"),
        "matchStatus": match_result.get("status"),
        "executionMode": match_result.get("executionMode"),
        "finalWorldTick": match_result.get("finalWorldTick"),
        "finalNetworkFrame": match_result.get("finalNetworkFrame"),
        "finalSyncHash": match_result.get("finalSyncHash"),
        "orderDigestSha256": match_result.get("orderDigestSha256"),
        "strategicDecisionDigestSha256": match_result.get("strategicDecisionDigestSha256"),
        "players": match_result.get("players"),
        "verificationExitCode": verification.get("exitCode"),
        "verificationStatus": verification_result.get("status"),
        "recordedFinalWorldTick": verification_result.get("recordedFinalWorldTick"),
        "observedFinalWorldTick": verification_result.get("observedFinalWorldTick"),
        "verifiedFinalNetworkFrame": verification_result.get("finalNetworkFrame"),
        "lastValidatedSyncFrame": verification_result.get("lastValidatedSyncFrame"),
        "outOfSyncFrame": verification_result.get("outOfSyncFrame"),
        "scheduledMatchTimeoutTick": verification_result.get("scheduledMatchTimeoutTick"),
    }


def is_integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def is_positive_integer(value: object) -> bool:
    return is_integer(value) and value > 0


def is_sha256(value: object) -> bool:
    return isinstance(value, str) and SHA256.fullmatch(value) is not None


def validate_players(value: object, match_status: object) -> bool:
    if not isinstance(value, list) or len(value) != 2:
        return False

    slots: set[str] = set()
    outcomes = []
    for player in value:
        if not isinstance(player, dict):
            return False
        slot = player.get("slot")
        bot_type = player.get("botType")
        outcome = player.get("outcome")
        if (
            not isinstance(slot, str)
            or not slot
            or slot in slots
            or not isinstance(bot_type, str)
            or not bot_type
            or outcome not in {"WON", "LOST", "UNDEFINED"}
        ):
            return False
        slots.add(slot)
        outcomes.append(outcome)

    if match_status == "COMPLETED":
        return sorted(outcomes) == ["LOST", "WON"]
    if match_status == "TIMED_OUT":
        return outcomes == ["UNDEFINED", "UNDEFINED"]
    return False


def validate_valid_job_evidence(
    job: dict[str, Any],
    manifest_job: dict[str, Any],
    specification: dict[str, Any] | None,
    issues: Issues,
    shard: int,
    job_id: str,
) -> bool:
    """Independently prove that a controller-VALID job has complete runtime evidence."""

    failures: list[tuple[str, object, object]] = []

    def require(name: str, passed: bool, observed: object, expected: object) -> None:
        if not passed:
            failures.append((name, observed, expected))

    match = job.get("match")
    verification = job.get("verification")
    if not isinstance(match, dict):
        failures.append(("match", match, "object"))
        match = {}
    if not isinstance(verification, dict):
        failures.append(("verification", verification, "object"))
        verification = {}
    match_result = match.get("result")
    verification_result = verification.get("result")
    if not isinstance(match_result, dict):
        failures.append(("match.result", match_result, "object"))
        match_result = {}
    if not isinstance(verification_result, dict):
        failures.append(("verification.result", verification_result, "object"))
        verification_result = {}

    match_status = match_result.get("status")
    match_exit = match.get("exitCode")
    require(
        "match.statusExit",
        (match_status == "COMPLETED" and match_exit == 0)
        or (match_status == "TIMED_OUT" and match_exit == 4),
        {"status": match_status, "exitCode": match_exit},
        "COMPLETED/0 or TIMED_OUT/4",
    )
    require("match.timedOut", match.get("timedOut") is False, match.get("timedOut"), False)
    require(
        "match.executionMode",
        match_result.get("executionMode") == "UNCAPPED",
        match_result.get("executionMode"),
        "UNCAPPED",
    )

    final_tick = match_result.get("finalWorldTick")
    require(
        "match.finalWorldTick",
        is_positive_integer(final_tick) and final_tick <= MAX_WORLD_TICKS,
        final_tick,
        f"integer in 1..{MAX_WORLD_TICKS}",
    )
    if match_status == "TIMED_OUT":
        require(
            "match.timedOutFinalWorldTick",
            final_tick == MAX_WORLD_TICKS,
            final_tick,
            MAX_WORLD_TICKS,
        )
    final_network_frame = match_result.get("finalNetworkFrame")
    require(
        "match.finalNetworkFrame",
        is_positive_integer(final_network_frame),
        final_network_frame,
        "positive integer",
    )
    final_sync_hash = match_result.get("finalSyncHash")
    require(
        "match.finalSyncHash",
        is_integer(final_sync_hash) and -(2**31) <= final_sync_hash < 2**31,
        final_sync_hash,
        "signed 32-bit integer",
    )
    for field_name in ("orderDigestSha256", "strategicDecisionDigestSha256"):
        require(
            f"match.{field_name}",
            is_sha256(match_result.get(field_name)),
            match_result.get(field_name),
            "lowercase SHA-256",
        )
    require(
        "match.players",
        validate_players(match_result.get("players"), match_status),
        match_result.get("players"),
        "two valid bot outcomes for the terminal status",
    )

    expected_candidate = {
        "candidateId": manifest_job.get("expectedCandidateId"),
        "candidateSha256": manifest_job.get("expectedCandidateSha256"),
        "squadSize": manifest_job.get("expectedSquadSize"),
    }
    for field_name, expected in expected_candidate.items():
        require(
            f"match.{field_name}",
            match_result.get(field_name) == expected,
            match_result.get(field_name),
            expected,
        )
    require(
        "match.specificationSha256",
        match_result.get("specificationSha256") == job.get("specificationSha256"),
        match_result.get("specificationSha256"),
        job.get("specificationSha256"),
    )
    if specification is None:
        failures.append(("specification", None, "validated specification"))
    else:
        for field_name in ("modId", "mapUid", "randomSeed"):
            require(
                f"match.{field_name}",
                match_result.get(field_name) == specification.get(field_name),
                match_result.get(field_name),
                specification.get(field_name),
            )

    match_replay_sha = match_result.get("replaySha256")
    verification_replay_sha = verification_result.get("replaySha256")
    match_replay_size = match_result.get("replaySizeBytes")
    verification_replay_size = verification_result.get("replaySizeBytes")
    require("match.replaySha256", is_sha256(match_replay_sha), match_replay_sha, "lowercase SHA-256")
    require(
        "match.replaySizeBytes",
        is_positive_integer(match_replay_size),
        match_replay_size,
        "positive integer",
    )

    require("verification.exitCode", verification.get("exitCode") == 0, verification.get("exitCode"), 0)
    require(
        "verification.timedOut",
        verification.get("timedOut") is False,
        verification.get("timedOut"),
        False,
    )
    require(
        "verification.status",
        verification_result.get("status") == "VERIFIED",
        verification_result.get("status"),
        "VERIFIED",
    )
    require(
        "verification.recordedFinalWorldTick",
        verification_result.get("recordedFinalWorldTick") == final_tick,
        verification_result.get("recordedFinalWorldTick"),
        final_tick,
    )
    require(
        "verification.observedFinalWorldTick",
        verification_result.get("observedFinalWorldTick") == final_tick,
        verification_result.get("observedFinalWorldTick"),
        final_tick,
    )
    require(
        "verification.finalNetworkFrame",
        verification_result.get("finalNetworkFrame") == final_network_frame,
        verification_result.get("finalNetworkFrame"),
        final_network_frame,
    )
    last_sync_frame = verification_result.get("lastValidatedSyncFrame")
    require(
        "verification.lastValidatedSyncFrame",
        is_positive_integer(last_sync_frame)
        and is_positive_integer(final_network_frame)
        and last_sync_frame <= final_network_frame,
        last_sync_frame,
        "positive integer no later than finalNetworkFrame",
    )
    require(
        "verification.outOfSyncFrame",
        verification_result.get("outOfSyncFrame") is None,
        verification_result.get("outOfSyncFrame"),
        None,
    )
    require(
        "verification.scheduledMatchTimeoutTick",
        verification_result.get("scheduledMatchTimeoutTick") == MAX_WORLD_TICKS,
        verification_result.get("scheduledMatchTimeoutTick"),
        MAX_WORLD_TICKS,
    )
    require(
        "verification.verificationTimestepMs",
        verification_result.get("verificationTimestepMs") == 1,
        verification_result.get("verificationTimestepMs"),
        1,
    )
    require(
        "verification.replaySha256",
        is_sha256(verification_replay_sha) and verification_replay_sha == match_replay_sha,
        verification_replay_sha,
        match_replay_sha,
    )
    require(
        "verification.replaySizeBytes",
        verification_replay_size == match_replay_size and is_positive_integer(verification_replay_size),
        verification_replay_size,
        match_replay_size,
    )

    for field_name, observed, expected in failures:
        issues.add(
            "job_runtime_evidence_invalid",
            "A controller-VALID job lacks complete independent runtime evidence",
            shard=shard,
            jobId=job_id,
            field=field_name,
            expected=expected,
            observed=observed,
        )
    return not failures


def read_memory_events(path: Path, issues: Issues, shard: int, phase: str) -> dict[str, int]:
    if not path.is_file():
        issues.add("memory_events_missing", "Memory event evidence is missing", shard=shard, phase=phase)
        return {}
    values: dict[str, int] = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            fields = line.split()
            if len(fields) != 2 or not re.fullmatch(r"[A-Za-z0-9_]+", fields[0]):
                raise ValueError(f"invalid line {line!r}")
            values[fields[0]] = int(fields[1])
    except (OSError, UnicodeError, ValueError) as exc:
        issues.add(
            "memory_events_invalid",
            "Memory event evidence is invalid",
            shard=shard,
            phase=phase,
            error=str(exc),
        )
        return {}
    for key in ("oom", "oom_kill"):
        if key not in values:
            issues.add(
                "memory_events_incomplete",
                "Memory event evidence lacks a required counter",
                shard=shard,
                phase=phase,
                counter=key,
            )
    return values


def _merge_intervals(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, end in sorted(intervals):
        if end <= start:
            continue
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def four_process_intervals(samples: list[dict[str, int]]) -> list[tuple[int, int]]:
    intervals = []
    for left, right in zip(samples, samples[1:]):
        gap = right["unix_ms"] - left["unix_ms"]
        if (
            left["openra_processes"] == MAX_WORKERS
            and right["openra_processes"] == MAX_WORKERS
            and 0 < gap <= MAX_SAMPLE_GAP_MS
        ):
            intervals.append((left["unix_ms"], right["unix_ms"]))
    return _merge_intervals(intervals)


def intersect_interval_sets(interval_sets: list[list[tuple[int, int]]]) -> list[tuple[int, int]]:
    if not interval_sets:
        return []
    current = interval_sets[0]
    for candidate in interval_sets[1:]:
        intersections = []
        for left_start, left_end in current:
            for right_start, right_end in candidate:
                start = max(left_start, right_start)
                end = min(left_end, right_end)
                if end > start:
                    intersections.append((start, end))
        current = _merge_intervals(intersections)
        if not current:
            break
    return current


def read_resource_samples(path: Path, issues: Issues, shard: int) -> tuple[list[dict[str, int]], dict[str, Any]]:
    required = (
        "unix_ms",
        "mem_available_bytes",
        "swap_used_bytes",
        "openra_processes",
        "openra_rss_kib",
        "disk_available_bytes",
    )
    if not path.is_file():
        issues.add("resource_samples_missing", "Resource sample CSV is missing", shard=shard)
        return [], {}
    samples: list[dict[str, int]] = []
    try:
        with path.open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames is None or not set(required).issubset(reader.fieldnames):
                raise ValueError(f"required columns are {required!r}")
            for row_number, row in enumerate(reader, start=2):
                sample = {key: int(row[key]) for key in required}
                if any(value < 0 for value in sample.values()):
                    raise ValueError(f"negative value on row {row_number}")
                samples.append(sample)
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        issues.add(
            "resource_samples_invalid",
            "Resource sample CSV is invalid",
            shard=shard,
            error=str(exc),
        )
        return [], {}

    if len(samples) < 2:
        issues.add("resource_samples_too_short", "Resource sample CSV has fewer than two rows", shard=shard)
        return samples, {}
    timestamps = [sample["unix_ms"] for sample in samples]
    gaps = [right - left for left, right in zip(timestamps, timestamps[1:])]
    issues.check(
        all(gap > 0 for gap in gaps),
        "resource_timestamps_not_increasing",
        "Resource sample timestamps must be strictly increasing",
        shard=shard,
    )
    median_gap = statistics.median(gaps)
    issues.check(
        100 <= median_gap <= 600 and max(gaps) <= MAX_SAMPLE_GAP_MS,
        "resource_sampling_cadence_invalid",
        "Resource samples do not demonstrate the expected 0.2-second cadence",
        shard=shard,
        medianGapMs=median_gap,
        maxGapMs=max(gaps),
    )

    maximum_processes = max(sample["openra_processes"] for sample in samples)
    maximum_rss = max(sample["openra_rss_kib"] for sample in samples) * 1024
    minimum_memory = min(sample["mem_available_bytes"] for sample in samples)
    minimum_disk = min(sample["disk_available_bytes"] for sample in samples)
    maximum_swap = max(sample["swap_used_bytes"] for sample in samples)
    checks = {
        "maxOpenRaProcessesExactlyFour": maximum_processes == MAX_WORKERS,
        "rssWithinLimit": maximum_rss <= MAX_COMBINED_RSS_BYTES,
        "availableMemoryWithinLimit": minimum_memory >= MIN_AVAILABLE_MEMORY_BYTES,
        "diskWithinLimit": minimum_disk >= MIN_DISK_AVAILABLE_BYTES,
        "noSwap": maximum_swap == 0,
    }
    for name, passed in checks.items():
        issues.check(
            passed,
            "resource_limit_failed",
            "A shard resource gate failed",
            shard=shard,
            check=name,
        )
    summary = {
        "sampleCount": len(samples),
        "medianSampleGapMs": median_gap,
        "maxSampleGapMs": max(gaps),
        "maxOpenRaProcesses": maximum_processes,
        "maxCombinedRssBytes": maximum_rss,
        "minAvailableMemoryBytes": minimum_memory,
        "minDiskAvailableBytes": minimum_disk,
        "maxSwapUsedBytes": maximum_swap,
        "fourProcessIntervals": [
            {"startUnixMs": start, "endUnixMs": end, "durationMs": end - start}
            for start, end in four_process_intervals(samples)
        ],
        "checks": checks,
    }
    return samples, summary


def _expect_equal(
    value: object,
    expected: object,
    issues: Issues,
    code: str,
    message: str,
    shard: int,
    **context: Any,
) -> bool:
    return issues.check(value == expected, code, message, shard=shard, expected=expected, observed=value, **context)


def validate_shard(
    shard: int,
    extracted_root: Path,
    run_id: int,
    run_attempt: int,
    repository: str,
    expected_execution_sha: str,
    issues: Issues,
) -> dict[str, Any]:
    evidence_root = extracted_root / f"m3-distributed-shard-{shard}"
    registration_root = extracted_root / f"m3-distributed-registration-{shard}"
    registration_path = registration_root / "github-distributed-smoke-registration.json"
    manifest_path = registration_root / "github-distributed-smoke-manifest.json"
    result_path = evidence_root / "run" / "experiment-result.json"
    registration = read_json_object(registration_path, issues, "registration_missing_or_invalid", shard=shard)
    manifest = read_json_object(manifest_path, issues, "manifest_missing_or_invalid", shard=shard)
    result = read_json_object(result_path, issues, "result_missing_or_invalid", shard=shard)
    summary: dict[str, Any] = {
        "shard": shard,
        "registrationPresent": registration is not None,
        "manifestPresent": manifest is not None,
        "resultPresent": result is not None,
        "jobIds": [],
        "validJobCount": 0,
        "timedOutProcessCount": 0,
    }

    registration_jobs: dict[str, dict[str, Any]] = {}
    manifest_jobs: dict[str, dict[str, Any]] = {}
    result_jobs: dict[str, dict[str, Any]] = {}
    source_jobs: dict[str, dict[str, Any]] = {}
    specifications_by_job: dict[str, dict[str, Any]] = {}
    source_manifest_path: Path | None = None
    sentinel_ids: list[str] = []
    unique_ids: list[str] = []

    if registration is not None:
        exact_fields = {
            "schemaVersion": SCHEMA_VERSION,
            "purpose": PURPOSE,
            "decisionInfluence": "NONE",
            "formalSelection": False,
            "shardIndex": shard,
            "shardCount": SHARD_COUNT,
            "maxWorkers": MAX_WORKERS,
            "jobCount": JOBS_PER_SHARD,
            "maxWorldTicks": MAX_WORLD_TICKS,
            "matchTimeoutSeconds": MATCH_TIMEOUT_SECONDS,
            "verificationTimeoutSeconds": VERIFICATION_TIMEOUT_SECONDS,
            "executionSha": expected_execution_sha,
        }
        for key, expected in exact_fields.items():
            _expect_equal(
                registration.get(key),
                expected,
                issues,
                "registration_field_mismatch",
                "Registration field differs from the distributed smoke contract",
                shard,
                field=key,
            )
        issues.check(
            isinstance(registration.get("designBaseSha"), str)
            and GIT_SHA.fullmatch(registration["designBaseSha"]) is not None,
            "registration_design_sha_invalid",
            "Registration designBaseSha is not a full lowercase Git SHA",
            shard=shard,
        )
        issues.check(
            registration.get("manifestPath") == "github-distributed-smoke-manifest.json",
            "registration_manifest_path_mismatch",
            "Registration manifestPath must be artifact-relative and canonical",
            shard=shard,
        )
        actual_manifest_sha = file_sha256(manifest_path) if manifest_path.is_file() else None
        _expect_equal(
            registration.get("manifestSha256"),
            actual_manifest_sha,
            issues,
            "manifest_sha_mismatch",
            "Registered manifest SHA-256 differs from the artifact",
            shard,
        )
        for key in ("sourceManifestSha256", "controllerScriptSha256"):
            issues.check(
                isinstance(registration.get(key), str) and SHA256.fullmatch(registration[key]) is not None,
                "registration_sha_invalid",
                "Registration contains an invalid SHA-256",
                shard=shard,
                field=key,
            )

        source_manifest_path = resolve_confined_path(
            registration_root,
            registration.get("sourceManifestPath"),
            registration_root,
            issues,
            "source_manifest_path_unsafe",
            shard,
        )
        if source_manifest_path is None or not source_manifest_path.is_file():
            issues.add(
                "source_manifest_missing",
                "Registered source manifest is missing from the shard artifact",
                shard=shard,
            )
        else:
            _expect_equal(
                file_sha256(source_manifest_path),
                registration.get("sourceManifestSha256"),
                issues,
                "source_manifest_sha_mismatch",
                "Source manifest SHA-256 differs from its registration",
                shard,
            )
            source_manifest = read_json_object(
                source_manifest_path,
                issues,
                "source_manifest_invalid",
                shard=shard,
            )
            if source_manifest is not None:
                _expect_equal(
                    source_manifest.get("schemaVersion"),
                    SCHEMA_VERSION,
                    issues,
                    "source_manifest_invalid",
                    "Source manifest schemaVersion differs from the registered contract",
                    shard,
                )
                source_matches = source_manifest.get("matches")
                if not isinstance(source_matches, list):
                    issues.add(
                        "source_manifest_invalid",
                        "Source manifest matches must be an array",
                        shard=shard,
                    )
                else:
                    for source_job in source_matches:
                        if (
                            not isinstance(source_job, dict)
                            or not isinstance(source_job.get("id"), str)
                        ):
                            issues.add(
                                "source_manifest_invalid",
                                "Source manifest contains a malformed job",
                                shard=shard,
                            )
                            continue
                        source_job_id = source_job["id"]
                        if source_job_id in source_jobs:
                            issues.add(
                                "source_manifest_duplicate_job",
                                "Source manifest contains a duplicate job ID",
                                shard=shard,
                                sourceJobId=source_job_id,
                            )
                            continue
                        source_jobs[source_job_id] = source_job

        controller_path = Path(__file__).resolve().parent / "strategic_ai_runner.py"
        actual_controller_sha = file_sha256(controller_path) if controller_path.is_file() else None
        _expect_equal(
            registration.get("controllerScriptSha256"),
            actual_controller_sha,
            issues,
            "controller_checkout_sha_mismatch",
            "Registered controller SHA-256 is not the controller in the verified checkout",
            shard,
        )

        raw_sentinels = registration.get("sentinelJobIds")
        raw_unique = registration.get("uniqueJobIds")
        if isinstance(raw_sentinels, list) and all(isinstance(item, str) for item in raw_sentinels):
            sentinel_ids = raw_sentinels
        else:
            issues.add("sentinel_registration_invalid", "sentinelJobIds must be a string array", shard=shard)
        if isinstance(raw_unique, list) and all(isinstance(item, str) for item in raw_unique):
            unique_ids = raw_unique
        else:
            issues.add("unique_registration_invalid", "uniqueJobIds must be a string array", shard=shard)
        issues.check(
            len(sentinel_ids) == 2 and len(set(sentinel_ids)) == 2,
            "sentinel_registration_invalid",
            "Each shard must register exactly two distinct sentinels",
            shard=shard,
        )
        issues.check(
            len(unique_ids) == 2 and len(set(unique_ids)) == 2,
            "unique_registration_invalid",
            "Each shard must register exactly two distinct unique jobs",
            shard=shard,
        )
        issues.check(
            not set(sentinel_ids) & set(unique_ids),
            "registration_job_roles_overlap",
            "Sentinel and unique job identifiers overlap",
            shard=shard,
        )

        raw_jobs = registration.get("jobs")
        if not isinstance(raw_jobs, list):
            issues.add("registration_jobs_invalid", "Registration jobs must be an array", shard=shard)
        else:
            for raw_job in raw_jobs:
                if not isinstance(raw_job, dict) or not isinstance(raw_job.get("id"), str):
                    issues.add("registration_jobs_invalid", "Registration contains an invalid job", shard=shard)
                    continue
                job_id = raw_job["id"]
                if job_id in registration_jobs:
                    issues.add("registration_jobs_duplicate", "Registration contains a duplicate job", shard=shard, jobId=job_id)
                registration_jobs[job_id] = raw_job
            expected_ids = set(sentinel_ids) | set(unique_ids)
            issues.check(
                len(registration_jobs) == JOBS_PER_SHARD and set(registration_jobs) == expected_ids,
                "registration_job_set_mismatch",
                "Registration does not contain the exact four role-indexed jobs",
                shard=shard,
                expected=sorted(expected_ids),
                observed=sorted(registration_jobs),
            )
            for job_id, raw_job in registration_jobs.items():
                expected_role = "SENTINEL" if job_id in sentinel_ids else "UNIQUE"
                _expect_equal(
                    raw_job.get("role"),
                    expected_role,
                    issues,
                    "registration_job_role_mismatch",
                    "Registration job role is incorrect",
                    shard,
                    jobId=job_id,
                )
                for key in (
                    "sourceSpecificationSha256",
                    "specificationSha256",
                    "sourceJobSha256",
                    "jobSha256",
                    "expectedCandidateSha256",
                ):
                    issues.check(
                        isinstance(raw_job.get(key), str) and SHA256.fullmatch(raw_job[key]) is not None,
                        "registration_job_sha_invalid",
                        "Registration job contains an invalid SHA-256",
                        shard=shard,
                        jobId=job_id,
                        field=key,
                    )
                for key in (
                    "sourceJobId",
                    "sourceSpecificationPath",
                    "specificationPath",
                    "sourceCandidatePath",
                    "candidatePath",
                ):
                    issues.check(
                        isinstance(raw_job.get(key), str) and bool(raw_job[key]),
                        "registration_job_provenance_invalid",
                        "Registration job lacks provenance",
                        shard=shard,
                        jobId=job_id,
                        field=key,
                    )

    if manifest is not None:
        _expect_equal(
            manifest.get("schemaVersion"), SCHEMA_VERSION, issues, "manifest_field_mismatch",
            "Manifest schemaVersion differs from the contract", shard, field="schemaVersion"
        )
        _expect_equal(
            manifest.get("matchTimeoutSeconds"), MATCH_TIMEOUT_SECONDS, issues, "manifest_field_mismatch",
            "Manifest match timeout differs from the contract", shard, field="matchTimeoutSeconds"
        )
        _expect_equal(
            manifest.get("verificationTimeoutSeconds"), VERIFICATION_TIMEOUT_SECONDS, issues,
            "manifest_field_mismatch", "Manifest verification timeout differs from the contract", shard,
            field="verificationTimeoutSeconds"
        )
        raw_matches = manifest.get("matches")
        if not isinstance(raw_matches, list):
            issues.add("manifest_jobs_invalid", "Manifest matches must be an array", shard=shard)
        else:
            for raw_job in raw_matches:
                if not isinstance(raw_job, dict) or not isinstance(raw_job.get("id"), str):
                    issues.add("manifest_jobs_invalid", "Manifest contains an invalid match", shard=shard)
                    continue
                job_id = raw_job["id"]
                if job_id in manifest_jobs:
                    issues.add("manifest_jobs_duplicate", "Manifest contains a duplicate match", shard=shard, jobId=job_id)
                manifest_jobs[job_id] = raw_job
        issues.check(
            len(manifest_jobs) == JOBS_PER_SHARD and set(manifest_jobs) == set(registration_jobs),
            "manifest_job_set_mismatch",
            "Manifest does not contain the exact registered jobs",
            shard=shard,
            expected=sorted(registration_jobs),
            observed=sorted(manifest_jobs),
        )

    for job_id in sorted(set(registration_jobs) & set(manifest_jobs)):
        registered_job = registration_jobs[job_id]
        manifest_job = manifest_jobs[job_id]
        _expect_equal(
            registered_job.get("jobSha256"),
            object_sha256(manifest_job),
            issues,
            "job_sha_mismatch",
            "Registered job SHA-256 differs from the manifest job object",
            shard,
            jobId=job_id,
        )
        _expect_equal(
            manifest_job.get("specificationPath"),
            registered_job.get("specificationPath"),
            issues,
            "specification_path_mismatch",
            "Manifest and registration specification paths differ",
            shard,
            jobId=job_id,
        )
        specification_path = resolve_confined_path(
            manifest_path.parent,
            manifest_job.get("specificationPath"),
            registration_root,
            issues,
            "specification_path_unsafe",
            shard,
        )
        if specification_path is None or not specification_path.is_file():
            issues.add("specification_missing", "Registered specification is missing", shard=shard, jobId=job_id)
            continue
        specification_sha = file_sha256(specification_path)
        _expect_equal(
            registered_job.get("specificationSha256"),
            specification_sha,
            issues,
            "specification_sha_mismatch",
            "Registered specification SHA-256 differs from the artifact",
            shard,
            jobId=job_id,
        )
        specification = read_json_object(
            specification_path, issues, "specification_invalid", shard=shard
        )
        if specification is None:
            continue
        specifications_by_job[job_id] = specification
        _expect_equal(
            specification.get("maxWorldTicks"),
            MAX_WORLD_TICKS,
            issues,
            "specification_world_ticks_mismatch",
            "Specification maxWorldTicks differs from the smoke contract",
            shard,
            jobId=job_id,
        )
        expected_candidate_sha = registered_job.get("expectedCandidateSha256")
        _expect_equal(
            manifest_job.get("expectedCandidateSha256"),
            expected_candidate_sha,
            issues,
            "candidate_sha_mismatch",
            "Manifest and registration candidate SHA-256 differ",
            shard,
            jobId=job_id,
        )
        candidate_path = resolve_confined_path(
            registration_root,
            registered_job.get("candidatePath"),
            registration_root,
            issues,
            "candidate_path_unsafe",
            shard,
        )
        if candidate_path is None or not candidate_path.is_file():
            issues.add("candidate_missing", "Registered candidate is missing", shard=shard, jobId=job_id)
            continue
        specification_candidate = resolve_confined_path(
            specification_path.parent,
            specification.get("candidatePath"),
            registration_root,
            issues,
            "candidate_path_unsafe",
            shard,
        )
        issues.check(
            specification_candidate == candidate_path,
            "candidate_path_mismatch",
            "Specification and registration do not resolve to the same candidate",
            shard=shard,
            jobId=job_id,
        )
        _expect_equal(
            file_sha256(candidate_path),
            expected_candidate_sha,
            issues,
            "candidate_sha_mismatch",
            "Candidate artifact SHA-256 differs from the registered expectation",
            shard,
            jobId=job_id,
        )
        candidate = read_json_object(candidate_path, issues, "candidate_invalid", shard=shard)
        if candidate is not None:
            _expect_equal(
                candidate.get("candidateId"), manifest_job.get("expectedCandidateId"), issues,
                "candidate_identity_mismatch", "Candidate ID differs from the manifest", shard, jobId=job_id
            )
            _expect_equal(
                candidate.get("squadSize"), manifest_job.get("expectedSquadSize"), issues,
                "candidate_identity_mismatch", "Candidate squad size differs from the manifest", shard, jobId=job_id
            )

        source_job_id = registered_job.get("sourceJobId")
        source_job = source_jobs.get(source_job_id) if isinstance(source_job_id, str) else None
        if source_job is None:
            issues.add(
                "source_job_missing",
                "Registered source job is absent from the source manifest",
                shard=shard,
                jobId=job_id,
                sourceJobId=source_job_id,
            )
            continue
        _expect_equal(
            object_sha256(source_job),
            registered_job.get("sourceJobSha256"),
            issues,
            "source_job_sha_mismatch",
            "Source job object SHA-256 differs from its registration",
            shard,
            jobId=job_id,
        )
        expected_quick_job = dict(source_job)
        expected_quick_job["id"] = job_id
        expected_quick_job["specificationPath"] = registered_job.get("specificationPath")
        _expect_equal(
            manifest_job,
            expected_quick_job,
            issues,
            "source_job_derivation_mismatch",
            "Quick manifest job is not the registered source job with only ID and specification path changed",
            shard,
            jobId=job_id,
        )

        if source_manifest_path is None:
            continue
        source_specification_path = resolve_confined_path(
            source_manifest_path.parent,
            registered_job.get("sourceSpecificationPath"),
            registration_root,
            issues,
            "source_specification_path_unsafe",
            shard,
        )
        source_job_specification_path = resolve_confined_path(
            source_manifest_path.parent,
            source_job.get("specificationPath"),
            registration_root,
            issues,
            "source_specification_path_unsafe",
            shard,
        )
        issues.check(
            source_specification_path == source_job_specification_path,
            "source_specification_path_mismatch",
            "Source job and registration do not resolve to the same specification",
            shard=shard,
            jobId=job_id,
        )
        if source_specification_path is None or not source_specification_path.is_file():
            issues.add(
                "source_specification_missing",
                "Registered source specification is missing",
                shard=shard,
                jobId=job_id,
            )
            continue
        _expect_equal(
            file_sha256(source_specification_path),
            registered_job.get("sourceSpecificationSha256"),
            issues,
            "source_specification_sha_mismatch",
            "Source specification SHA-256 differs from its registration",
            shard,
            jobId=job_id,
        )
        source_specification = read_json_object(
            source_specification_path,
            issues,
            "source_specification_invalid",
            shard=shard,
        )
        if source_specification is None:
            continue
        expected_quick_specification = dict(source_specification)
        expected_quick_specification["maxWorldTicks"] = MAX_WORLD_TICKS
        _expect_equal(
            specification,
            expected_quick_specification,
            issues,
            "quick_specification_derivation_mismatch",
            "Quick specification differs from its source by more than maxWorldTicks",
            shard,
            jobId=job_id,
        )

        source_candidate_path = resolve_confined_path(
            source_manifest_path.parent,
            registered_job.get("sourceCandidatePath"),
            registration_root,
            issues,
            "source_candidate_path_unsafe",
            shard,
        )
        source_spec_candidate_path = resolve_confined_path(
            source_specification_path.parent,
            source_specification.get("candidatePath"),
            registration_root,
            issues,
            "source_candidate_path_unsafe",
            shard,
        )
        issues.check(
            source_candidate_path == source_spec_candidate_path,
            "source_candidate_path_mismatch",
            "Source specification and registration do not resolve to the same candidate",
            shard=shard,
            jobId=job_id,
        )
        if source_candidate_path is None or not source_candidate_path.is_file():
            issues.add(
                "source_candidate_missing",
                "Registered source candidate is missing",
                shard=shard,
                jobId=job_id,
            )
            continue
        _expect_equal(
            file_sha256(source_candidate_path),
            expected_candidate_sha,
            issues,
            "source_candidate_sha_mismatch",
            "Source candidate SHA-256 differs from the job expectation",
            shard,
            jobId=job_id,
        )
        _expect_equal(
            file_sha256(source_candidate_path),
            file_sha256(candidate_path),
            issues,
            "candidate_derivation_mismatch",
            "Quick and source candidates do not contain the same bytes",
            shard,
            jobId=job_id,
        )
        source_candidate = read_json_object(
            source_candidate_path,
            issues,
            "source_candidate_invalid",
            shard=shard,
        )
        if source_candidate is not None:
            _expect_equal(
                source_candidate.get("candidateId"),
                manifest_job.get("expectedCandidateId"),
                issues,
                "source_candidate_identity_mismatch",
                "Source candidate ID differs from the manifest expectation",
                shard,
                jobId=job_id,
            )
            _expect_equal(
                source_candidate.get("squadSize"),
                manifest_job.get("expectedSquadSize"),
                issues,
                "source_candidate_identity_mismatch",
                "Source candidate squad size differs from the manifest expectation",
                shard,
                jobId=job_id,
            )

    controller_exit_path = evidence_root / "controller-exit-code-workers-4.txt"
    controller_exit: int | None = None
    try:
        controller_exit = int(controller_exit_path.read_text(encoding="utf-8").strip())
    except (OSError, UnicodeError, ValueError) as exc:
        issues.add("controller_exit_invalid", "Controller exit-code evidence is missing or invalid", shard=shard, error=str(exc))
    _expect_equal(
        controller_exit, 0, issues, "controller_exit_nonzero", "Controller did not exit successfully", shard
    )

    if result is not None:
        _expect_equal(result.get("status"), "COMPLETED", issues, "result_status_invalid", "Shard result is not COMPLETED", shard)
        _expect_equal(result.get("maxWorkers"), MAX_WORKERS, issues, "result_workers_invalid", "Shard did not record maxWorkers=4", shard)
        expected_manifest_sha = registration.get("manifestSha256") if registration else None
        _expect_equal(result.get("manifestSha256"), expected_manifest_sha, issues, "result_manifest_sha_mismatch", "Result manifest SHA-256 differs from registration", shard)

        provenance = result.get("controllerProvenance")
        if not isinstance(provenance, dict):
            issues.add("controller_provenance_invalid", "Controller provenance is missing", shard=shard)
        else:
            expected_provenance = {
                "expectedJobCount": JOBS_PER_SHARD,
                "recordedJobCount": JOBS_PER_SHARD,
                "attributedJobCount": JOBS_PER_SHARD,
                "legacyCoverageGap": False,
                "unattributedJobIds": [],
                "invalidAttributionJobIds": [],
                "complete": True,
            }
            for key, expected in expected_provenance.items():
                _expect_equal(
                    provenance.get(key), expected, issues, "controller_provenance_invalid",
                    "Controller provenance is incomplete or inconsistent", shard, field=key
                )
        for report_name in ("parity", "repeatEquivalence"):
            subreport = result.get(report_name)
            if not isinstance(subreport, dict):
                issues.add("result_equivalence_invalid", "Result equivalence report is missing", shard=shard, report=report_name)
            else:
                _expect_equal(subreport.get("pairCount"), 0, issues, "result_equivalence_invalid", "Unexpected implicit comparison pairs were recorded", shard, report=report_name)
                _expect_equal(subreport.get("mismatchCount"), 0, issues, "result_equivalence_invalid", "Result equivalence report contains mismatches", shard, report=report_name)

        raw_result_jobs = result.get("jobs")
        if not isinstance(raw_result_jobs, dict):
            issues.add("result_jobs_invalid", "Result jobs must be an object", shard=shard)
        else:
            result_jobs = {
                key: value for key, value in raw_result_jobs.items()
                if isinstance(key, str) and isinstance(value, dict)
            }
            if len(result_jobs) != len(raw_result_jobs):
                issues.add("result_jobs_invalid", "Result contains a malformed job entry", shard=shard)
        issues.check(
            len(result_jobs) == JOBS_PER_SHARD and set(result_jobs) == set(registration_jobs),
            "result_job_set_mismatch",
            "Result does not contain the exact registered jobs",
            shard=shard,
            expected=sorted(registration_jobs),
            observed=sorted(result_jobs),
        )

        controller_sha = registration.get("controllerScriptSha256") if registration else None
        executions = result.get("controllerExecutions")
        execution_ids: set[str] = set()
        if not isinstance(executions, list) or not executions:
            issues.add("controller_executions_invalid", "Result lacks controller execution identities", shard=shard)
        else:
            for execution in executions:
                if not isinstance(execution, dict) or not isinstance(execution.get("executionId"), str):
                    issues.add("controller_executions_invalid", "Result has a malformed controller execution", shard=shard)
                    continue
                execution_ids.add(execution["executionId"])
                _expect_equal(
                    execution.get("controllerScriptSha256"), controller_sha, issues,
                    "controller_script_sha_mismatch", "Controller script SHA-256 differs from registration", shard
                )

        valid_count = 0
        timed_out_count = 0
        evidence_valid_job_ids: set[str] = set()
        for job_id, job in result_jobs.items():
            if job.get("status") == "VALID":
                if validate_valid_job_evidence(
                    job,
                    manifest_jobs.get(job_id, {}),
                    specifications_by_job.get(job_id),
                    issues,
                    shard,
                    job_id,
                ):
                    valid_count += 1
                    evidence_valid_job_ids.add(job_id)
            else:
                issues.add("job_not_valid", "Composite job is not VALID", shard=shard, jobId=job_id, status=job.get("status"))
            for phase in ("match", "verification"):
                process = job.get(phase)
                timed_out = None if not isinstance(process, dict) else process.get("timedOut")
                if timed_out is not False:
                    timed_out_count += 1
                    issues.add("process_timeout", "Match or verification timed out or lacks explicit timeout evidence", shard=shard, jobId=job_id, phase=phase, timedOut=timed_out)
            registered_job = registration_jobs.get(job_id, {})
            manifest_job = manifest_jobs.get(job_id, {})
            _expect_equal(job.get("id"), job_id, issues, "result_job_identity_mismatch", "Result job ID differs from its key", shard, jobId=job_id)
            _expect_equal(job.get("specificationSha256"), registered_job.get("specificationSha256"), issues, "result_specification_sha_mismatch", "Result specification SHA-256 differs from registration", shard, jobId=job_id)
            for key in ("expectedCandidateId", "expectedCandidateSha256", "expectedSquadSize"):
                _expect_equal(job.get(key), manifest_job.get(key), issues, "result_candidate_identity_mismatch", "Result candidate expectation differs from the exact manifest job", shard, jobId=job_id, field=key)
            _expect_equal(job.get("controllerScriptSha256"), controller_sha, issues, "controller_script_sha_mismatch", "Job controller script SHA-256 differs from registration", shard, jobId=job_id)
            issues.check(
                isinstance(job.get("controllerExecutionId"), str) and job["controllerExecutionId"] in execution_ids,
                "controller_job_attribution_invalid",
                "Job is not attributed to a registered controller execution",
                shard=shard,
                jobId=job_id,
            )
        summary["validJobCount"] = valid_count
        summary["timedOutProcessCount"] = timed_out_count
        summary["evidenceValidJobIds"] = sorted(evidence_valid_job_ids)

    expected_log_jobs = set(registration_jobs)
    replay_logs = list((evidence_root / "run" / "workers").glob("*/attempts/*/verify/Logs/strategic-decisions.log"))
    replay_by_job: dict[str, list[Path]] = {}
    for replay_log in replay_logs:
        try:
            relative = replay_log.relative_to(evidence_root / "run" / "workers")
            replay_by_job.setdefault(relative.parts[0], []).append(replay_log)
        except (ValueError, IndexError):
            continue
    issues.check(
        len(replay_logs) == JOBS_PER_SHARD
        and set(replay_by_job) == expected_log_jobs
        and all(len(paths) == 1 for paths in replay_by_job.values()),
        "replay_log_set_mismatch",
        "Shard does not contain exactly one replay strategic log per registered job",
        shard=shard,
        expected=sorted(expected_log_jobs),
        observed=sorted(replay_by_job),
        logCount=len(replay_logs),
    )
    nonempty_logs = [
        path.relative_to(evidence_root).as_posix()
        for path in replay_logs
        if path.stat().st_size != 0
    ]
    issues.check(
        not nonempty_logs,
        "replay_log_nonempty",
        "Replay strategic-decision logs must all be empty",
        shard=shard,
        paths=nonempty_logs,
    )

    samples, resource_summary = read_resource_samples(
        evidence_root / "resource-samples-workers-4.csv", issues, shard
    )
    before = read_memory_events(evidence_root / "memory-events-before-workers-4.txt", issues, shard, "before")
    after = read_memory_events(evidence_root / "memory-events-after-workers-4.txt", issues, shard, "after")
    oom_delta = after.get("oom", 0) - before.get("oom", 0)
    oom_kill_delta = after.get("oom_kill", 0) - before.get("oom_kill", 0)
    required_oom_counters = {"oom", "oom_kill"}
    no_oom = (
        required_oom_counters.issubset(before)
        and required_oom_counters.issubset(after)
        and oom_delta == 0
        and oom_kill_delta == 0
    )
    issues.check(no_oom, "oom_detected", "OOM counters changed or are incomplete", shard=shard, oomDelta=oom_delta, oomKillDelta=oom_kill_delta)
    resource_summary.update({"oomDelta": oom_delta, "oomKillDelta": oom_kill_delta, "noOom": no_oom})

    time_path = evidence_root / "workers-4-time.txt"
    issues.check(
        time_path.is_file() and time_path.stat().st_size > 0,
        "wall_time_evidence_missing",
        "GNU time evidence is missing or empty",
        shard=shard,
    )

    metadata = read_json_object(evidence_root / "runner-metadata.json", issues, "runner_metadata_invalid", shard=shard)
    runner_name: str | None = None
    if metadata is not None:
        metadata_expectations = {
            "GITHUB_REPOSITORY": repository,
            "GITHUB_RUN_ID": str(run_id),
            "GITHUB_RUN_ATTEMPT": str(run_attempt),
            "GITHUB_SHA": expected_execution_sha,
            "gitHeadSha": expected_execution_sha,
            "SHARD_INDEX": str(shard),
            "maxWorkers": str(MAX_WORKERS),
        }
        for key, expected in metadata_expectations.items():
            _expect_equal(
                str(metadata.get(key)) if metadata.get(key) is not None else None,
                expected,
                issues,
                "runner_metadata_mismatch",
                "Runner metadata differs from the requested workflow execution",
                shard,
                field=key,
            )
        if isinstance(metadata.get("RUNNER_NAME"), str) and metadata["RUNNER_NAME"]:
            runner_name = metadata["RUNNER_NAME"]
        else:
            issues.add("runner_name_missing", "Runner metadata lacks RUNNER_NAME", shard=shard)

    summary.update(
        {
            "jobIds": sorted(registration_jobs),
            "sentinelJobIds": sentinel_ids,
            "uniqueJobIds": unique_ids,
            "registration": registration,
            "manifestJobs": manifest_jobs,
            "resultJobs": result_jobs,
            "evidenceValidJobIds": summary.get("evidenceValidJobIds", []),
            "runnerName": runner_name,
            "resource": resource_summary,
            "samples": samples,
            "controllerExitCode": controller_exit,
            "replayStrategicLogCount": len(replay_logs),
            "replayStrategicLogBytes": sum(path.stat().st_size for path in replay_logs),
        }
    )
    return summary


def validate_cross_shard(shards: list[dict[str, Any]], issues: Issues) -> dict[str, Any]:
    registrations = [item.get("registration") for item in shards]
    available = [item for item in shards if isinstance(item.get("registration"), dict)]
    issues.check(
        len(available) == SHARD_COUNT,
        "registration_count_mismatch",
        "Exactly four valid shard registrations are required",
        observed=len(available),
    )

    for field_name in (
        "executionSha",
        "designBaseSha",
        "sourceManifestSha256",
        "controllerScriptSha256",
    ):
        values = {
            registration.get(field_name)
            for registration in registrations
            if isinstance(registration, dict)
        }
        issues.check(
            len(values) == 1,
            "cross_shard_registration_mismatch",
            "A provenance field differs across shard registrations",
            field=field_name,
            observed=sorted(str(value) for value in values),
        )

    composite_ids: list[str] = []
    derived_ids: set[str] = set()
    source_ids: set[str] = set()
    sentinel_source_by_id: dict[str, set[str]] = {}
    unique_source_ids: list[str] = []
    for item in shards:
        shard = item["shard"]
        registration = item.get("registration")
        if not isinstance(registration, dict):
            continue
        jobs = registration.get("jobs")
        if not isinstance(jobs, list):
            continue
        for job in jobs:
            if not isinstance(job, dict) or not isinstance(job.get("id"), str):
                continue
            job_id = job["id"]
            composite_ids.append(f"shard-{shard}/{job_id}")
            derived_ids.add(job_id)
            source_job_id = job.get("sourceJobId")
            if isinstance(source_job_id, str):
                source_ids.add(source_job_id)
                if job_id in item.get("sentinelJobIds", []):
                    sentinel_source_by_id.setdefault(job_id, set()).add(source_job_id)
                else:
                    unique_source_ids.append(source_job_id)

    issues.check(
        len(composite_ids) == SHARD_COUNT * JOBS_PER_SHARD and len(set(composite_ids)) == len(composite_ids),
        "composite_job_count_mismatch",
        "Distributed smoke must contain exactly 16 distinct composite jobs",
        observed=len(composite_ids),
    )
    issues.check(
        len(derived_ids) == 10,
        "derived_job_identity_mismatch",
        "Distributed smoke must contain two shared sentinel IDs and eight unique IDs",
        observed=len(derived_ids),
    )
    issues.check(
        len(source_ids) == 10,
        "source_job_identity_mismatch",
        "Distributed smoke must bind exactly ten distinct source jobs",
        observed=len(source_ids),
    )
    issues.check(
        len(unique_source_ids) == 8 and len(set(unique_source_ids)) == 8,
        "unique_source_job_overlap",
        "Unique jobs must bind eight distinct source job IDs",
        observed=len(set(unique_source_ids)),
    )
    for job_id, sources in sentinel_source_by_id.items():
        issues.check(
            len(sources) == 1,
            "sentinel_source_mismatch",
            "A sentinel ID maps to different source jobs across shards",
            jobId=job_id,
            observed=sorted(sources),
        )

    baseline = next((item for item in shards if item["shard"] == 0), None)
    baseline_sentinels = [] if baseline is None else list(baseline.get("sentinelJobIds", []))
    comparisons: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    not_comparable: list[dict[str, Any]] = []
    drift: list[dict[str, Any]] = []
    if len(baseline_sentinels) != 2:
        issues.add(
            "sentinel_baseline_invalid",
            "Shard zero does not provide the two-sentinel comparison baseline",
        )
    shards_by_index = {item["shard"]: item for item in shards}
    for candidate_shard in range(1, SHARD_COUNT):
        item = shards_by_index.get(
            candidate_shard,
            {"shard": candidate_shard, "sentinelJobIds": [], "resultJobs": {}},
        )
        issues.check(
            set(item.get("sentinelJobIds", [])) == set(baseline_sentinels),
            "sentinel_registration_mismatch",
            "Sentinel registrations differ across shards",
            shard=item["shard"],
        )
        baseline_jobs = {} if baseline is None else baseline.get("resultJobs", {})
        candidate_jobs = item.get("resultJobs", {})
        for job_id in baseline_sentinels:
            comparison = {
                "baselineShard": 0,
                "candidateShard": item["shard"],
                "jobId": job_id,
                "compared": False,
                "matches": None,
                "differences": [],
            }
            absent = []
            if job_id not in baseline_jobs:
                absent.append("baseline")
            if job_id not in candidate_jobs:
                absent.append("candidate")
            if absent:
                missing_item = {
                    "baselineShard": 0,
                    "candidateShard": item["shard"],
                    "jobId": job_id,
                    "missingSides": absent,
                }
                missing.append(missing_item)
                comparison["missingSides"] = absent
                comparisons.append(comparison)
                continue
            left = baseline_jobs[job_id]
            right = candidate_jobs[job_id]
            invalid_sides = []
            baseline_evidence_valid = set(
                [] if baseline is None else baseline.get("evidenceValidJobIds", [])
            )
            candidate_evidence_valid = set(item.get("evidenceValidJobIds", []))
            if left.get("status") != "VALID" or job_id not in baseline_evidence_valid:
                invalid_sides.append("baseline")
            if right.get("status") != "VALID" or job_id not in candidate_evidence_valid:
                invalid_sides.append("candidate")
            if invalid_sides:
                item_value = {
                    "baselineShard": 0,
                    "candidateShard": item["shard"],
                    "jobId": job_id,
                    "invalidSides": invalid_sides,
                }
                not_comparable.append(item_value)
                comparison["invalidSides"] = invalid_sides
                comparisons.append(comparison)
                continue

            left_evidence = calibration_job_evidence(left)
            right_evidence = calibration_job_evidence(right)
            differences = [
                field_name
                for field_name in DETERMINISTIC_FIELDS
                if left_evidence[field_name] != right_evidence[field_name]
            ]
            comparison.update(
                {
                    "compared": True,
                    "matches": not differences,
                    "differences": differences,
                }
            )
            comparisons.append(comparison)
            if differences:
                drift.append(
                    {
                        "baselineShard": 0,
                        "candidateShard": item["shard"],
                        "jobId": job_id,
                        "differences": differences,
                    }
                )

    if missing:
        issues.add(
            "sentinel_missing",
            "One or more registered sentinel results are missing",
            count=len(missing),
        )
    if not_comparable:
        issues.add(
            "sentinel_not_comparable",
            "One or more sentinel pairs are not both VALID",
            count=len(not_comparable),
        )
    if drift:
        issues.add(
            "sentinel_deterministic_drift",
            "VALID sentinel results differ in deterministic fields",
            count=len(drift),
        )
    issues.check(
        len(comparisons) == 6,
        "sentinel_comparison_count_mismatch",
        "The two sentinels must produce six baseline-to-shard comparisons",
        observed=len(comparisons),
    )

    return {
        "compositeJobCount": len(composite_ids),
        "compositeJobIds": sorted(composite_ids),
        "distinctDerivedJobCount": len(derived_ids),
        "distinctSourceJobCount": len(source_ids),
        "sentinelEvidence": {
            "baselineShard": 0,
            "expectedComparisonCount": 6,
            "comparisonCount": len(comparisons),
            "comparedValidPairCount": sum(item["compared"] for item in comparisons),
            "missingCount": len(missing),
            "notComparableCount": len(not_comparable),
            "driftCount": len(drift),
            "missing": missing,
            "notComparable": not_comparable,
            "drift": drift,
            "comparisons": comparisons,
        },
    }


def parse_timestamp(value: object) -> dt.datetime:
    if not isinstance(value, str) or not value:
        raise ValueError("timestamp is missing")
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp lacks a timezone")
    return parsed.astimezone(dt.timezone.utc)


def fetch_github_json(url: str, token: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "OpenRA-distributed-smoke-aggregator",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = response.read()
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
        raise ValueError(f"GitHub API request failed: {exc}") from exc
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"GitHub API returned invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("GitHub API response is not a JSON object")
    return value


def load_actions_documents(
    repository: str,
    run_id: int,
    run_attempt: int,
    jobs_json: Path | None,
    run_json: Path | None,
    token: str | None,
    issues: Issues,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if (jobs_json is None) != (run_json is None):
        issues.add(
            "actions_documents_incomplete",
            "--jobs-json and --run-json must be provided together",
        )
        return None, None
    if jobs_json is not None and run_json is not None:
        return (
            read_json_object(jobs_json, issues, "actions_jobs_document_invalid"),
            read_json_object(run_json, issues, "actions_run_document_invalid"),
        )

    if not token:
        issues.add(
            "github_token_missing",
            "GITHUB_TOKEN is required when fixture documents are not supplied",
        )
        return None, None
    api_root = os.environ.get("GITHUB_API_URL", "https://api.github.com").rstrip("/")
    base = f"{api_root}/repos/{repository}/actions/runs/{run_id}/attempts/{run_attempt}"
    try:
        run_document = fetch_github_json(base, token)
        jobs_document = fetch_github_json(base + "/jobs?per_page=100", token)
    except ValueError as exc:
        issues.add("github_api_failed", "Unable to load Actions run evidence", error=str(exc))
        return None, None
    return jobs_document, run_document


def infer_job_shard(name: object) -> int | None:
    if not isinstance(name, str):
        return None
    patterns = (
        r"(?i)(?:^|[^a-z0-9])shard[\s_:#/\-]*(?P<index>[0-3])(?:$|[^0-9])",
        r"\(\s*(?P<index>[0-3])\s*\)\s*$",
    )
    for pattern in patterns:
        match = re.search(pattern, name)
        if match is not None:
            return int(match.group("index"))
    return None


def validate_actions_evidence(
    jobs_document: dict[str, Any] | None,
    run_document: dict[str, Any] | None,
    shards: list[dict[str, Any]],
    repository: str,
    run_id: int,
    run_attempt: int,
    expected_execution_sha: str,
    issues: Issues,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "runIdentityValid": False,
        "jobCount": 0,
        "distinctJobIdCount": 0,
        "distinctRunnerNameCount": 0,
        "jobOverlap": None,
        "jobs": [],
    }
    if run_document is None or jobs_document is None:
        return summary

    repository_document = run_document.get("repository")
    repository_name = (
        repository_document.get("full_name") if isinstance(repository_document, dict) else None
    )
    run_checks = {
        "id": run_document.get("id") == run_id,
        "runAttempt": run_document.get("run_attempt") == run_attempt,
        "headSha": run_document.get("head_sha") == expected_execution_sha,
        "repository": repository_name == repository,
        "event": run_document.get("event") == "workflow_dispatch",
    }
    for name, passed in run_checks.items():
        issues.check(
            passed,
            "actions_run_identity_mismatch",
            "Actions run document differs from the requested workflow execution",
            field=name,
        )
    summary["runIdentityValid"] = all(run_checks.values())

    raw_jobs = jobs_document.get("jobs")
    if not isinstance(raw_jobs, list):
        issues.add("actions_jobs_document_invalid", "Actions jobs document lacks a jobs array")
        return summary
    by_shard: dict[int, list[dict[str, Any]]] = {index: [] for index in range(SHARD_COUNT)}
    for raw_job in raw_jobs:
        if not isinstance(raw_job, dict):
            continue
        shard = infer_job_shard(raw_job.get("name"))
        if shard is not None:
            by_shard[shard].append(raw_job)

    selected: list[tuple[int, dict[str, Any]]] = []
    for shard in range(SHARD_COUNT):
        candidates = by_shard[shard]
        if len(candidates) != 1:
            issues.add(
                "actions_shard_job_count_mismatch",
                "Actions jobs document must contain exactly one job for each shard",
                shard=shard,
                observed=len(candidates),
            )
            continue
        selected.append((shard, candidates[0]))

    starts: list[dt.datetime] = []
    ends: list[dt.datetime] = []
    job_ids: list[object] = []
    runner_names: list[str] = []
    created: dt.datetime | None = None
    try:
        created = parse_timestamp(run_document.get("created_at"))
    except ValueError:
        issues.add("actions_run_timestamp_invalid", "Actions run created_at is invalid")

    metadata_by_shard = {item["shard"]: item.get("runnerName") for item in shards}
    job_summaries = []
    for shard, job in selected:
        job_id = job.get("id")
        runner_name = job.get("runner_name")
        checks = {
            "runId": job.get("run_id") == run_id,
            "runAttempt": job.get("run_attempt") == run_attempt,
            "headSha": job.get("head_sha") == expected_execution_sha,
            "completed": job.get("status") == "completed",
            "success": job.get("conclusion") == "success",
            "runnerNameMatchesArtifact": runner_name == metadata_by_shard.get(shard),
        }
        for name, passed in checks.items():
            issues.check(
                passed,
                "actions_job_identity_mismatch",
                "Actions shard job differs from its artifact metadata",
                shard=shard,
                field=name,
            )
        try:
            started = parse_timestamp(job.get("started_at"))
            completed = parse_timestamp(job.get("completed_at"))
            if completed <= started:
                raise ValueError("completed_at is not later than started_at")
            starts.append(started)
            ends.append(completed)
            started_text = started.isoformat().replace("+00:00", "Z")
            completed_text = completed.isoformat().replace("+00:00", "Z")
            dispatch_to_start = None if created is None else int((started - created).total_seconds() * 1000)
        except ValueError as exc:
            issues.add(
                "actions_job_timestamp_invalid",
                "Actions shard job timestamps are invalid",
                shard=shard,
                error=str(exc),
            )
            started_text = None
            completed_text = None
            dispatch_to_start = None
        if isinstance(runner_name, str) and runner_name:
            runner_names.append(runner_name)
        else:
            issues.add("actions_runner_name_missing", "Actions shard job lacks runner_name", shard=shard)
        job_ids.append(job_id)
        job_summaries.append(
            {
                "shard": shard,
                "jobId": job_id,
                "name": job.get("name"),
                "runnerName": runner_name,
                "startedAt": started_text,
                "completedAt": completed_text,
                "dispatchToStartMs": dispatch_to_start,
                "checks": checks,
            }
        )

    distinct_job_ids = len(set(job_ids))
    distinct_runner_names = len(set(runner_names))
    issues.check(
        len(job_ids) == SHARD_COUNT and distinct_job_ids == SHARD_COUNT and all(job_id is not None for job_id in job_ids),
        "actions_job_ids_not_distinct",
        "Four distinct Actions job IDs are required",
        observed=distinct_job_ids,
    )
    issues.check(
        len(runner_names) == SHARD_COUNT and distinct_runner_names == SHARD_COUNT,
        "actions_runner_names_not_distinct",
        "Four distinct Actions runner names are required",
        observed=distinct_runner_names,
    )

    overlap = None
    if len(starts) == SHARD_COUNT and len(ends) == SHARD_COUNT:
        overlap_start = max(starts)
        overlap_end = min(ends)
        duration_ms = int((overlap_end - overlap_start).total_seconds() * 1000)
        if duration_ms > 0:
            overlap = {
                "startUtc": overlap_start.isoformat().replace("+00:00", "Z"),
                "endUtc": overlap_end.isoformat().replace("+00:00", "Z"),
                "durationMs": duration_ms,
            }
        else:
            issues.add(
                "actions_jobs_do_not_overlap",
                "The four shard jobs have no common execution interval",
            )
    else:
        issues.add(
            "actions_jobs_do_not_overlap",
            "Complete timestamps for four shard jobs are required to prove overlap",
        )

    summary.update(
        {
            "jobCount": len(selected),
            "distinctJobIdCount": distinct_job_ids,
            "distinctRunnerNameCount": distinct_runner_names,
            "jobOverlap": overlap,
            "jobs": sorted(job_summaries, key=lambda item: item["shard"]),
        }
    )
    return summary


def aggregate_distributed_smoke(
    artifacts_root: Path,
    output: Path,
    run_id: int,
    run_attempt: int,
    repository: str,
    expected_execution_sha: str,
    *,
    jobs_json: Path | None = None,
    run_json: Path | None = None,
    token: str | None = None,
) -> dict[str, Any]:
    issues = Issues()
    report: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "purpose": PURPOSE,
        "decisionInfluence": "NONE",
        "formalSelection": False,
        "runId": run_id,
        "runAttempt": run_attempt,
        "repository": repository,
        "expectedExecutionSha": expected_execution_sha,
        "measurementComplete": False,
        "passed": False,
    }
    try:
        issues.check(run_id > 0, "run_id_invalid", "run ID must be positive")
        issues.check(run_attempt > 0, "run_attempt_invalid", "run attempt must be positive")
        issues.check(
            REPOSITORY.fullmatch(repository) is not None,
            "repository_invalid",
            "repository must have owner/name form",
        )
        issues.check(
            GIT_SHA.fullmatch(expected_execution_sha) is not None,
            "execution_sha_invalid",
            "expected execution SHA must be a full lowercase Git SHA",
        )
        artifacts_root = artifacts_root.resolve()
        issues.check(
            artifacts_root.is_dir(),
            "artifacts_root_missing",
            "Downloaded artifact root does not exist",
            path=str(artifacts_root),
        )

        archives_by_shard: dict[int, Path] = {}
        all_archives = list(artifacts_root.rglob("*.tar.gz")) if artifacts_root.is_dir() else []
        canonical_names = {f"shard-{shard}.tar.gz" for shard in range(SHARD_COUNT)}
        unexpected = sorted(path.name for path in all_archives if path.name not in canonical_names)
        if unexpected:
            issues.add(
                "unexpected_archive",
                "Downloaded artifact root contains an unexpected tar archive",
                archives=unexpected,
            )
        for shard in range(SHARD_COUNT):
            matches = [path for path in all_archives if path.name == f"shard-{shard}.tar.gz"]
            if len(matches) != 1:
                issues.add(
                    "shard_archive_count_mismatch",
                    "Exactly one canonical tar is required for each shard",
                    shard=shard,
                    observed=len(matches),
                )
            else:
                archives_by_shard[shard] = matches[0]
        issues.check(
            len(all_archives) == SHARD_COUNT,
            "archive_count_mismatch",
            "Downloaded artifact root must contain exactly four shard tar files",
            observed=len(all_archives),
        )
        parent_directories = {path.parent.resolve() for path in archives_by_shard.values()}
        issues.check(
            len(parent_directories) == SHARD_COUNT,
            "artifact_directories_not_independent",
            "Each shard tar must come from its own download-artifact directory",
            observed=len(parent_directories),
        )

        archive_audits = []
        shards: list[dict[str, Any]] = []
        with tempfile.TemporaryDirectory(prefix="openra-distributed-smoke-") as temporary:
            extraction_root = Path(temporary)
            for shard in range(SHARD_COUNT):
                archive = archives_by_shard.get(shard)
                if archive is None:
                    continue
                destination = extraction_root / f"shard-{shard}"
                try:
                    audit = safe_extract_tar(archive, destination, shard)
                    archive_audits.append({"shard": shard, **audit})
                except (ArchiveSafetyError, OSError, tarfile.TarError) as exc:
                    issues.add(
                        "unsafe_or_invalid_archive",
                        "Shard archive failed the pre-extraction safety review",
                        shard=shard,
                        archive=archive.name,
                        error=str(exc),
                    )
                    archive_audits.append(
                        {"shard": shard, "archive": archive.name, "safe": False, "error": str(exc)}
                    )
                    continue
                failure_start = len(issues.failures)
                shard_summary = validate_shard(
                    shard,
                    destination,
                    run_id,
                    run_attempt,
                    repository,
                    expected_execution_sha,
                    issues,
                )
                shard_summary["passed"] = len(issues.failures) == failure_start
                shards.append(shard_summary)

            issues.check(
                len(shards) == SHARD_COUNT,
                "extracted_shard_count_mismatch",
                "Exactly four safely extracted shard evidence sets are required",
                observed=len(shards),
            )
            cross_summary = validate_cross_shard(shards, issues)

            interval_sets = []
            for item in sorted(shards, key=lambda value: value["shard"]):
                interval_sets.append(four_process_intervals(item.get("samples", [])))
            process_overlaps = intersect_interval_sets(interval_sets) if len(interval_sets) == SHARD_COUNT else []
            if process_overlaps:
                longest = max(process_overlaps, key=lambda pair: pair[1] - pair[0])
                process_overlap_summary = {
                    "proven": True,
                    "simultaneousOpenRaProcesses": SHARD_COUNT * MAX_WORKERS,
                    "startUnixMs": longest[0],
                    "endUnixMs": longest[1],
                    "durationMs": longest[1] - longest[0],
                    "allOverlaps": [
                        {"startUnixMs": start, "endUnixMs": end, "durationMs": end - start}
                        for start, end in process_overlaps
                    ],
                }
            else:
                issues.add(
                    "four_way_process_overlap_missing",
                    "The 0.2-second samples do not prove four simultaneous four-process intervals",
                )
                process_overlap_summary = {
                    "proven": False,
                    "simultaneousOpenRaProcesses": None,
                    "allOverlaps": [],
                }

            jobs_document, run_document = load_actions_documents(
                repository,
                run_id,
                run_attempt,
                jobs_json,
                run_json,
                token,
                issues,
            )
            actions_summary = validate_actions_evidence(
                jobs_document,
                run_document,
                shards,
                repository,
                run_id,
                run_attempt,
                expected_execution_sha,
                issues,
            )

            public_shards = []
            for item in sorted(shards, key=lambda value: value["shard"]):
                public_shards.append(
                    {
                        key: value
                        for key, value in item.items()
                        if key not in {"registration", "manifestJobs", "resultJobs", "samples"}
                    }
                )
            report.update(
                {
                    "archiveAudits": sorted(archive_audits, key=lambda item: item["shard"]),
                    "shards": public_shards,
                    **cross_summary,
                    "fourWayProcessOverlap": process_overlap_summary,
                    "actionsEvidence": actions_summary,
                    "validCompositeJobCount": sum(item.get("validJobCount", 0) for item in shards),
                    "timedOutProcessCount": sum(item.get("timedOutProcessCount", 0) for item in shards),
                    "replayStrategicLogCount": sum(item.get("replayStrategicLogCount", 0) for item in shards),
                    "replayStrategicLogBytes": sum(item.get("replayStrategicLogBytes", 0) for item in shards),
                }
            )
    except Exception as exc:  # Preserve a machine-readable artifact for unforeseen failures too.
        issues.add(
            "internal_aggregation_error",
            "Unexpected exception while aggregating distributed smoke evidence",
            error=f"{type(exc).__name__}: {exc}",
        )

    report["failures"] = issues.failures
    report["failureCount"] = len(issues.failures)
    report["measurementComplete"] = not issues.failures
    report["passed"] = not issues.failures
    atomic_write_json(output, report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--run-attempt", type=int, required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--expected-execution-sha", required=True)
    parser.add_argument("--jobs-json", type=Path)
    parser.add_argument("--run-json", type=Path)
    args = parser.parse_args(argv)
    report = aggregate_distributed_smoke(
        args.artifacts_root,
        args.output,
        args.run_id,
        args.run_attempt,
        args.repository,
        args.expected_execution_sha.lower(),
        jobs_json=args.jobs_json,
        run_json=args.run_json,
        token=os.environ.get("GITHUB_TOKEN"),
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
