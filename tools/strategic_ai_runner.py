#!/usr/bin/env python3

"""Launch and supervise reproducible OpenRA StrategicAI experiments."""

from __future__ import annotations

import argparse
import concurrent.futures
import ctypes
import datetime as dt
import hashlib
import json
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


SCHEMA_VERSION = "1.0.0"
MAX_WORKERS = 8
SAFE_JOB_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
ACTIVE_PROCESSES: set[subprocess.Popen[bytes]] = set()
ACTIVE_PROCESSES_LOCK = threading.Lock()


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def controller_execution_identity() -> dict:
    script_path = Path(__file__).resolve()
    return {
        "executionId": str(uuid.uuid4()),
        "startedUtc": utc_now(),
        "processId": os.getpid(),
        "pythonExecutable": sys.executable,
        "pythonVersion": platform.python_version(),
        "platform": platform.platform(),
        "controllerScriptPath": str(script_path),
        "controllerScriptBytes": script_path.stat().st_size,
        "controllerScriptSha256": file_sha256(script_path),
        "workingDirectory": str(Path.cwd().resolve()),
        "argv": list(sys.argv),
    }


def atomic_json(path: Path, value: object) -> None:
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


@dataclass(frozen=True)
class Job:
    job_id: str
    specification: Path
    specification_sha256: str
    pair_id: str | None = None
    expected_execution_mode: str | None = None
    expected_match_status: str | None = None
    expected_candidate_id: str | None = None
    expected_candidate_sha256: str | None = None
    expected_squad_size: int | None = None
    candidate_path: Path | None = None


@dataclass(frozen=True)
class Manifest:
    path: Path
    sha256: str
    match_timeout_seconds: int
    verification_timeout_seconds: int
    jobs: tuple[Job, ...]


def load_manifest(path: Path) -> Manifest:
    full_path = path.resolve()
    value = json.loads(full_path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or set(value) != {
        "schemaVersion",
        "matchTimeoutSeconds",
        "verificationTimeoutSeconds",
        "matches",
    }:
        raise ValueError("Experiment manifest must contain only the documented top-level properties")
    if value["schemaVersion"] != SCHEMA_VERSION:
        raise ValueError(f"Unsupported experiment manifest schemaVersion {value['schemaVersion']!r}")
    match_timeout = value["matchTimeoutSeconds"]
    verification_timeout = value["verificationTimeoutSeconds"]
    if not isinstance(match_timeout, int) or match_timeout <= 0:
        raise ValueError("matchTimeoutSeconds must be a positive integer")
    if not isinstance(verification_timeout, int) or verification_timeout <= 0:
        raise ValueError("verificationTimeoutSeconds must be a positive integer")

    matches = value["matches"]
    if not isinstance(matches, list) or not matches:
        raise ValueError("matches must be a non-empty array")

    jobs = []
    identifiers = set()
    for raw_job in matches:
        if not isinstance(raw_job, dict) or not {"id", "specificationPath"}.issubset(raw_job) or not set(raw_job).issubset(
            {
                "id", "specificationPath", "pairId", "executionMode", "expectedMatchStatus",
                "expectedCandidateId", "expectedCandidateSha256", "expectedSquadSize",
            }
        ):
            raise ValueError("Each match must contain id/specificationPath and only documented optional properties")
        job_id = raw_job["id"]
        if not isinstance(job_id, str) or not SAFE_JOB_ID.fullmatch(job_id):
            raise ValueError(f"Unsafe or invalid match id {job_id!r}")
        if job_id in identifiers:
            raise ValueError(f"Duplicate match id {job_id!r}")
        identifiers.add(job_id)

        specification = (full_path.parent / raw_job["specificationPath"]).resolve()
        if not specification.is_file():
            raise ValueError(f"Specification does not exist: {specification}")
        pair_id = raw_job.get("pairId")
        if pair_id is not None and (not isinstance(pair_id, str) or not SAFE_JOB_ID.fullmatch(pair_id)):
            raise ValueError(f"Unsafe or invalid pairId {pair_id!r}")
        execution_mode = raw_job.get("executionMode")
        if execution_mode is not None and execution_mode not in {"PACED", "UNCAPPED"}:
            raise ValueError(f"Invalid expected executionMode {execution_mode!r}")
        if (pair_id is None) != (execution_mode is None):
            raise ValueError("pairId and executionMode must be specified together")
        expected_match_status = raw_job.get("expectedMatchStatus")
        if expected_match_status is not None and expected_match_status not in {"COMPLETED", "TIMED_OUT"}:
            raise ValueError(f"Invalid expectedMatchStatus {expected_match_status!r}")

        expected_candidate_id = raw_job.get("expectedCandidateId")
        if expected_candidate_id is not None and (
            not isinstance(expected_candidate_id, str) or not SAFE_JOB_ID.fullmatch(expected_candidate_id)
        ):
            raise ValueError(f"Invalid expectedCandidateId {expected_candidate_id!r}")
        expected_candidate_sha256 = raw_job.get("expectedCandidateSha256")
        if expected_candidate_sha256 is not None and (
            not isinstance(expected_candidate_sha256, str)
            or not re.fullmatch(r"[0-9a-f]{64}", expected_candidate_sha256)
        ):
            raise ValueError("expectedCandidateSha256 must be a lowercase SHA-256")
        expected_squad_size = raw_job.get("expectedSquadSize")
        if expected_squad_size is not None and (
            not isinstance(expected_squad_size, int) or expected_squad_size <= 0
        ):
            raise ValueError("expectedSquadSize must be a positive integer")
        candidate_expectations = (
            expected_candidate_id,
            expected_candidate_sha256,
            expected_squad_size,
        )
        if any(value is not None for value in candidate_expectations) and not all(
            value is not None for value in candidate_expectations
        ):
            raise ValueError("Candidate expectations must specify id, SHA-256, and squad size together")

        candidate_path = None
        if expected_candidate_id is not None:
            specification_value = json.loads(specification.read_text(encoding="utf-8"))
            if not isinstance(specification_value, dict):
                raise ValueError(f"Specification must be a JSON object: {specification}")
            candidate_relative = specification_value.get("candidatePath")
            if not isinstance(candidate_relative, str) or not candidate_relative:
                raise ValueError(f"Specification lacks candidatePath: {specification}")
            candidate_path = (specification.parent / candidate_relative).resolve()
            validate_candidate_file(
                candidate_path,
                expected_candidate_id,
                expected_candidate_sha256,
                expected_squad_size,
            )

        jobs.append(
            Job(
                job_id,
                specification,
                file_sha256(specification),
                pair_id,
                execution_mode,
                expected_match_status,
                expected_candidate_id,
                expected_candidate_sha256,
                expected_squad_size,
                candidate_path,
            )
        )

    paired_modes: dict[str, list[str]] = {}
    for job in jobs:
        if job.pair_id is not None:
            paired_modes.setdefault(job.pair_id, []).append(job.expected_execution_mode)
    for pair_id, modes in paired_modes.items():
        if sorted(modes) != ["PACED", "UNCAPPED"]:
            raise ValueError(f"Parity pair {pair_id!r} must contain exactly one PACED and one UNCAPPED job")

    return Manifest(
        full_path,
        file_sha256(full_path),
        match_timeout,
        verification_timeout,
        tuple(jobs),
    )


def validate_candidate_file(path: Path, candidate_id: str, expected_sha256: str, squad_size: int) -> None:
    if not path.is_file():
        raise ValueError(f"Candidate file does not exist: {path}")
    if file_sha256(path) != expected_sha256:
        raise ValueError(f"Candidate SHA-256 differs from the registered expectation: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Candidate must be a JSON object: {path}")
    if value.get("candidateId") != candidate_id or value.get("squadSize") != squad_size:
        raise ValueError(f"Candidate identity differs from the registered expectation: {path}")


def validate_job_inputs(job: Job) -> None:
    if file_sha256(job.specification) != job.specification_sha256:
        raise ValueError(f"Specification changed after manifest load: {job.specification}")
    if job.candidate_path is not None:
        validate_candidate_file(
            job.candidate_path,
            job.expected_candidate_id,
            job.expected_candidate_sha256,
            job.expected_squad_size,
        )


def _link_or_copy(source: str, destination: str) -> str:
    try:
        os.link(source, destination)
    except OSError:
        shutil.copy2(source, destination)
    return destination


def materialize_content(content_dir: Path, support_dir: Path) -> None:
    source = content_dir.resolve()
    if not (source / "ra" / "v2" / "allies.mix").is_file():
        raise ValueError(f"RA content directory is incomplete: {source}")
    destination = support_dir / "Content"
    if destination.exists():
        return
    shutil.copytree(source, destination, copy_function=_link_or_copy)


def resolve_executable(engine_dir: Path) -> Path:
    name = "OpenRA.exe" if os.name == "nt" else "OpenRA"
    executable = engine_dir.resolve() / "bin" / name
    if not executable.is_file():
        raise ValueError(f"Built OpenRA executable was not found: {executable}")
    return executable


def terminate_process_tree(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def terminate_active_processes() -> None:
    with ACTIVE_PROCESSES_LOCK:
        processes = tuple(ACTIVE_PROCESSES)
    for process in processes:
        terminate_process_tree(process)


def worker_creation_flags() -> int:
    if os.name != "nt":
        return 0
    return subprocess.CREATE_NO_WINDOW


def invoke_process(command: list[str], stdout_path: Path, stderr_path: Path, timeout_seconds: int) -> dict:
    started = time.monotonic()
    worker_environment = os.environ.copy()
    worker_environment["OPENRA_BACKGROUND_WINDOW"] = "1"
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        process = subprocess.Popen(
            command,
            stdout=stdout,
            stderr=stderr,
            cwd=command[1].removeprefix("Engine.EngineDir="),
            start_new_session=os.name != "nt",
            creationflags=worker_creation_flags(),
            env=worker_environment,
        )
        with ACTIVE_PROCESSES_LOCK:
            ACTIVE_PROCESSES.add(process)
        timed_out = False
        peak_working_set_bytes = 0
        try:
            try:
                deadline = time.monotonic() + timeout_seconds
                while True:
                    resident = process_resident_bytes(process.pid)
                    if resident is not None:
                        peak_working_set_bytes = max(peak_working_set_bytes, resident)
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        timed_out = True
                        terminate_process_tree(process)
                        exit_code = process.wait(timeout=15)
                        break
                    try:
                        exit_code = process.wait(timeout=min(0.25, remaining))
                        break
                    except subprocess.TimeoutExpired:
                        continue
            except KeyboardInterrupt:
                terminate_process_tree(process)
                process.wait(timeout=15)
                raise
        finally:
            with ACTIVE_PROCESSES_LOCK:
                ACTIVE_PROCESSES.discard(process)
    return {
        "exitCode": exit_code,
        "timedOut": timed_out,
        "elapsedSeconds": round(time.monotonic() - started, 6),
        "peakWorkingSetBytes": peak_working_set_bytes or None,
    }


ProcessInvoker = Callable[[list[str], Path, Path, int], dict]


def next_attempt_number(job_root: Path) -> int:
    previous = read_json(job_root / "job-result.json")
    if previous is None:
        return 1
    attempt = previous.get("attempt")
    return (attempt if isinstance(attempt, int) and attempt > 0 else 1) + 1


def target_platform() -> str:
    architecture = "arm64" if platform.machine().lower() in {"arm64", "aarch64"} else "x64"
    if os.name == "nt":
        return f"win-{architecture}"
    if sys.platform == "darwin":
        return f"osx-{architecture}"
    return f"linux-{architecture}"


def build_engine(engine_dir: Path, output_root: Path, timeout_seconds: int = 1800) -> dict:
    output_root.mkdir(parents=True, exist_ok=True)
    command = [
        "dotnet",
        "build",
        "-c",
        "Debug",
        "-nologo",
        "-warnaserror",
        f"-p:TargetPlatform={target_platform()}",
    ]
    started = time.monotonic()
    with (output_root / "build.stdout.log").open("wb") as stdout, (
        output_root / "build.stderr.log"
    ).open("wb") as stderr:
        process = subprocess.Popen(
            command,
            cwd=engine_dir.resolve(),
            stdout=stdout,
            stderr=stderr,
            start_new_session=os.name != "nt",
            creationflags=worker_creation_flags(),
        )
        with ACTIVE_PROCESSES_LOCK:
            ACTIVE_PROCESSES.add(process)
        timed_out = False
        try:
            try:
                exit_code = process.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                timed_out = True
                terminate_process_tree(process)
                exit_code = process.wait(timeout=15)
            except KeyboardInterrupt:
                terminate_process_tree(process)
                process.wait(timeout=15)
                raise
        finally:
            with ACTIVE_PROCESSES_LOCK:
                ACTIVE_PROCESSES.discard(process)

    result = {
        "command": command,
        "targetPlatform": target_platform(),
        "exitCode": exit_code,
        "timedOut": timed_out,
        "elapsedSeconds": round(time.monotonic() - started, 6),
        "endedUtc": utc_now(),
    }
    atomic_json(output_root / "build-result.json", result)
    return result


def read_json(path: Path) -> dict | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None


def openra_command(executable: Path, engine_dir: Path, support_dir: Path, launch_argument: str) -> list[str]:
    return [
        str(executable),
        f"Engine.EngineDir={engine_dir.resolve()}",
        f"Engine.SupportDir={support_dir.resolve()}",
        "Game.Mod=ra",
        "Graphics.Mode=Windowed",
        "Graphics.WindowedSize=1024,768",
        "Graphics.VSync=false",
        launch_argument,
    ]


def run_job(
    job: Job,
    output_root: Path,
    content_dir: Path,
    engine_dir: Path,
    executable: Path,
    match_timeout: int,
    verification_timeout: int,
    invoker: ProcessInvoker = invoke_process,
    controller_execution_id: str | None = None,
    controller_script_sha256: str | None = None,
) -> dict:
    validate_job_inputs(job)
    job_root = output_root / "workers" / job.job_id
    attempt = next_attempt_number(job_root)
    attempt_root = job_root / "attempts" / f"{attempt:03d}"
    match_support = attempt_root / "match"
    verification_support = attempt_root / "verify"
    match_support.mkdir(parents=True, exist_ok=True)
    verification_support.mkdir(parents=True, exist_ok=True)
    materialize_content(content_dir, match_support)
    materialize_content(content_dir, verification_support)

    result = {
        "id": job.job_id,
        "attempt": attempt,
        "status": "RUNNING",
        "specificationPath": str(job.specification),
        "specificationSha256": job.specification_sha256,
        "pairId": job.pair_id,
        "expectedExecutionMode": job.expected_execution_mode,
        "expectedMatchStatus": job.expected_match_status,
        "expectedCandidateId": job.expected_candidate_id,
        "expectedCandidateSha256": job.expected_candidate_sha256,
        "expectedSquadSize": job.expected_squad_size,
        "controllerExecutionId": controller_execution_id,
        "controllerScriptSha256": controller_script_sha256,
        "startedUtc": utc_now(),
        "endedUtc": None,
        "match": None,
        "verification": None,
    }
    atomic_json(job_root / "job-result.json", result)

    match_process = invoker(
        openra_command(executable, engine_dir, match_support, f"Launch.Match={job.specification}"),
        job_root / "match.stdout.log",
        job_root / "match.stderr.log",
        match_timeout,
    )
    match_artifact = read_json(match_support / "match-result.json")
    result["match"] = {**match_process, "result": match_artifact}

    replay_path = None if match_artifact is None else match_artifact.get("replayPath")
    match_ok = match_process["exitCode"] in {0, 4} and not match_process["timedOut"]
    if match_ok and isinstance(replay_path, str) and Path(replay_path).is_file():
        verification_process = invoker(
            openra_command(
                executable,
                engine_dir,
                verification_support,
                f"Launch.VerifyReplay={Path(replay_path).resolve()}",
            ),
            job_root / "verify.stdout.log",
            job_root / "verify.stderr.log",
            verification_timeout,
        )
        verification_artifact = read_json(verification_support / "replay-verification-result.json")
        result["verification"] = {**verification_process, "result": verification_artifact}
        verification_ok = (
            verification_process["exitCode"] == 0
            and not verification_process["timedOut"]
            and verification_artifact is not None
            and verification_artifact.get("status") == "VERIFIED"
        )
    else:
        verification_ok = False

    mode_ok = (
        job.expected_execution_mode is None
        or (match_artifact is not None and match_artifact.get("executionMode") == job.expected_execution_mode)
    )
    status_ok = (
        job.expected_match_status is None
        or (match_artifact is not None and match_artifact.get("status") == job.expected_match_status)
    )
    candidate_ok = job.expected_candidate_id is None or (
        match_artifact is not None
        and match_artifact.get("candidateId") == job.expected_candidate_id
        and match_artifact.get("candidateSha256") == job.expected_candidate_sha256
        and match_artifact.get("squadSize") == job.expected_squad_size
    )
    result["status"] = "VALID" if match_ok and verification_ok and mode_ok and status_ok and candidate_ok else "FAILED"
    result["endedUtc"] = utc_now()
    atomic_json(job_root / "job-result.json", result)
    return result


def completed_job_is_reusable(output_root: Path, job: Job) -> dict | None:
    validate_job_inputs(job)
    result = read_json(output_root / "workers" / job.job_id / "job-result.json")
    if result is None or result.get("status") != "VALID":
        return None
    if result.get("specificationSha256") != job.specification_sha256:
        return None
    if (
        result.get("expectedCandidateId") != job.expected_candidate_id
        or result.get("expectedCandidateSha256") != job.expected_candidate_sha256
        or result.get("expectedSquadSize") != job.expected_squad_size
    ):
        return None
    return result


def controller_provenance_summary(jobs: dict[str, dict], executions: list[dict], expected_job_count: int) -> dict:
    execution_hashes = {
        item.get("executionId"): item.get("controllerScriptSha256")
        for item in executions
        if isinstance(item, dict) and isinstance(item.get("executionId"), str)
    }
    unattributed = []
    invalid = []
    for job_id, job in sorted(jobs.items()):
        execution_id = job.get("controllerExecutionId") if isinstance(job, dict) else None
        script_sha256 = job.get("controllerScriptSha256") if isinstance(job, dict) else None
        if execution_id is None and script_sha256 is None:
            unattributed.append(job_id)
        elif execution_id not in execution_hashes or execution_hashes[execution_id] != script_sha256:
            invalid.append(job_id)
    return {
        "expectedJobCount": expected_job_count,
        "recordedJobCount": len(jobs),
        "attributedJobCount": len(jobs) - len(unattributed) - len(invalid),
        "legacyCoverageGap": bool(unattributed),
        "unattributedJobIds": unattributed,
        "invalidAttributionJobIds": invalid,
        "complete": len(jobs) == expected_job_count and not unattributed and not invalid,
    }


def parity_report(jobs: dict[str, dict]) -> dict:
    grouped: dict[str, dict[str, dict]] = {}
    for job in jobs.values():
        pair_id = job.get("pairId")
        mode = job.get("expectedExecutionMode")
        if pair_id is not None and mode is not None:
            grouped.setdefault(pair_id, {})[mode] = job

    comparisons = []
    evidence_fields = (
        "finalWorldTick",
        "finalSyncHash",
        "orderDigestSha256",
        "strategicDecisionDigestSha256",
        "players",
    )
    for pair_id, modes in sorted(grouped.items()):
        differences = []
        if set(modes) != {"PACED", "UNCAPPED"}:
            differences.append("pair must contain exactly PACED and UNCAPPED jobs")
        elif modes["PACED"].get("status") != "VALID" or modes["UNCAPPED"].get("status") != "VALID":
            differences.append("both jobs must be VALID")
        else:
            paced = modes["PACED"]["match"]["result"]
            uncapped = modes["UNCAPPED"]["match"]["result"]
            for field in evidence_fields:
                if paced.get(field) != uncapped.get(field):
                    differences.append(field)
        comparisons.append({"pairId": pair_id, "matches": not differences, "differences": differences})

    return {
        "pairCount": len(comparisons),
        "mismatchCount": sum(not item["matches"] for item in comparisons),
        "comparisons": comparisons,
    }


def calibration_job_evidence(job: dict) -> dict:
    """Return only deterministic evidence suitable for cross-run comparison."""
    match = job.get("match") or {}
    match_result = match.get("result") or {}
    verification = job.get("verification") or {}
    verification_result = verification.get("result") or {}
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
        "outOfSyncFrame": verification_result.get("outOfSyncFrame"),
        "scheduledMatchTimeoutTick": verification_result.get("scheduledMatchTimeoutTick"),
    }


def calibration_equivalence_report(output_root: Path, worker_counts: tuple[int, ...]) -> dict:
    """Compare every higher-concurrency run with the one-worker evidence."""
    if not worker_counts or worker_counts[0] != 1:
        raise ValueError("Calibration equivalence requires a one-worker baseline")

    runs = {}
    for workers in worker_counts:
        result_path = output_root / f"workers-{workers}" / "experiment-result.json"
        result = read_json(result_path)
        if result is None or not isinstance(result.get("jobs"), dict):
            raise ValueError(f"Calibration result is missing jobs: {result_path}")
        runs[workers] = result["jobs"]

    baseline = runs[1]
    by_workers = {"1": {"comparedJobCount": len(baseline), "mismatchCount": 0}}
    comparisons = []
    deterministic_fields = tuple(calibration_job_evidence({}).keys())
    for workers in worker_counts[1:]:
        candidate = runs[workers]
        job_ids = sorted(set(baseline) | set(candidate))
        mismatch_count = 0
        for job_id in job_ids:
            differences = []
            if job_id not in baseline:
                differences.append("unexpectedJob")
            elif job_id not in candidate:
                differences.append("missingJob")
            else:
                expected = calibration_job_evidence(baseline[job_id])
                observed = calibration_job_evidence(candidate[job_id])
                differences.extend(field for field in deterministic_fields if expected[field] != observed[field])

            if differences:
                mismatch_count += 1
                comparisons.append(
                    {
                        "workers": workers,
                        "jobId": job_id,
                        "matches": False,
                        "differences": differences,
                    }
                )

        by_workers[str(workers)] = {
            "comparedJobCount": len(job_ids),
            "mismatchCount": mismatch_count,
        }

    return {
        "baselineWorkers": 1,
        "workerCounts": list(worker_counts),
        "byWorkers": by_workers,
        "mismatchCount": sum(value["mismatchCount"] for value in by_workers.values()),
        "comparisons": comparisons,
    }


def repeat_equivalence_report(jobs: dict[str, dict]) -> dict:
    """Compare registered r0/r1 repetitions inside one experiment run."""
    grouped = {}
    for job_id, job in jobs.items():
        match = re.fullmatch(r"(.+)-r([01])", job_id)
        if match is not None:
            grouped.setdefault(match.group(1), {})[int(match.group(2))] = job

    comparisons = []
    deterministic_fields = tuple(calibration_job_evidence({}).keys())
    for cell_id, repeats in sorted(grouped.items()):
        differences = []
        if set(repeats) != {0, 1}:
            differences.append("pair must contain exactly r0 and r1")
        else:
            primary = calibration_job_evidence(repeats[0])
            repeated = calibration_job_evidence(repeats[1])
            differences.extend(field for field in deterministic_fields if primary[field] != repeated[field])
        comparisons.append(
            {
                "cellId": cell_id,
                "matches": not differences,
                "differences": differences,
            }
        )

    return {
        "pairCount": len(comparisons),
        "mismatchCount": sum(not item["matches"] for item in comparisons),
        "comparisons": comparisons,
    }


def run_manifest(args: argparse.Namespace) -> int:
    run_started = time.monotonic()
    controller_execution = controller_execution_identity()
    manifest = load_manifest(args.manifest)
    output_root = args.output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    engine_dir = args.engine_dir.resolve()
    content_dir = args.content_dir.resolve()
    if not getattr(args, "skip_build", False):
        build = build_engine(engine_dir, output_root / "build")
        if build["exitCode"] != 0 or build["timedOut"]:
            atomic_json(
                output_root / "run-state.json",
                {
                    "schemaVersion": SCHEMA_VERSION,
                    "manifestPath": str(manifest.path),
                    "manifestSha256": manifest.sha256,
                    "controllerExecutions": [controller_execution],
                    "status": "BUILD_FAILED",
                    "build": build,
                    "endedUtc": utc_now(),
                },
            )
            return 1
    executable = resolve_executable(engine_dir)

    state_path = output_root / "run-state.json"
    existing = read_json(state_path)
    if existing is not None and existing.get("manifestSha256") != manifest.sha256:
        raise ValueError("Output root belongs to a different experiment manifest")
    previous_elapsed = float(existing.get("wallClockElapsedSeconds") or 0) if existing else 0
    controller_executions = list(existing.get("controllerExecutions", [])) if existing else []
    controller_executions.append(controller_execution)

    state = {
        "schemaVersion": SCHEMA_VERSION,
        "manifestPath": str(manifest.path),
        "manifestSha256": manifest.sha256,
        "controllerExecutions": controller_executions,
        "maxWorkers": args.max_workers,
        "startedUtc": existing.get("startedUtc") if existing else utc_now(),
        "endedUtc": None,
        "status": "RUNNING",
        "wallClockElapsedSeconds": previous_elapsed,
        "jobs": {},
    }
    pending = []
    for job in manifest.jobs:
        reusable = completed_job_is_reusable(output_root, job)
        if reusable is None:
            pending.append(job)
        else:
            state["jobs"][job.job_id] = reusable
    state["controllerProvenance"] = controller_provenance_summary(
        state["jobs"], controller_executions, len(manifest.jobs)
    )
    atomic_json(state_path, state)

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=args.max_workers)
    interrupted = False
    try:
        futures = {
            executor.submit(
                run_job,
                job,
                output_root,
                content_dir,
                engine_dir,
                executable,
                manifest.match_timeout_seconds,
                manifest.verification_timeout_seconds,
                invoke_process,
                controller_execution["executionId"],
                controller_execution["controllerScriptSha256"],
            ): job
            for job in pending
        }
        for future in concurrent.futures.as_completed(futures):
            job = futures[future]
            try:
                state["jobs"][job.job_id] = future.result()
            except Exception as exc:
                state["jobs"][job.job_id] = {
                    "id": job.job_id,
                    "status": "FAILED",
                    "failure": f"{type(exc).__name__}: {exc}",
                    "specificationSha256": job.specification_sha256,
                    "expectedCandidateId": job.expected_candidate_id,
                    "expectedCandidateSha256": job.expected_candidate_sha256,
                    "expectedSquadSize": job.expected_squad_size,
                    "controllerExecutionId": controller_execution["executionId"],
                    "controllerScriptSha256": controller_execution["controllerScriptSha256"],
                    "endedUtc": utc_now(),
                }
            state["controllerProvenance"] = controller_provenance_summary(
                state["jobs"], controller_executions, len(manifest.jobs)
            )
            state["wallClockElapsedSeconds"] = round(
                previous_elapsed + time.monotonic() - run_started, 6
            )
            atomic_json(state_path, state)
    except KeyboardInterrupt:
        interrupted = True
        terminate_active_processes()
        state["status"] = "INTERRUPTED"
        state["endedUtc"] = utc_now()
        state["wallClockElapsedSeconds"] = round(previous_elapsed + time.monotonic() - run_started, 6)
        atomic_json(state_path, state)
    finally:
        executor.shutdown(wait=True, cancel_futures=True)

    if interrupted:
        return 130

    state["endedUtc"] = utc_now()
    if pending:
        state["wallClockElapsedSeconds"] = round(previous_elapsed + time.monotonic() - run_started, 6)
    state["parity"] = parity_report(state["jobs"])
    state["repeatEquivalence"] = repeat_equivalence_report(state["jobs"])
    state["controllerProvenance"] = controller_provenance_summary(
        state["jobs"], controller_executions, len(manifest.jobs)
    )
    state["status"] = "COMPLETED" if all(
        result.get("status") == "VALID" for result in state["jobs"].values()
    ) and len(state["jobs"]) == len(manifest.jobs) and state["parity"]["mismatchCount"] == 0 \
        and state["repeatEquivalence"]["mismatchCount"] == 0 else "FAILED"
    atomic_json(state_path, state)
    atomic_json(output_root / "experiment-result.json", state)
    return 0 if state["status"] == "COMPLETED" else 1


def percentile95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, (95 * len(ordered) + 99) // 100 - 1)
    return ordered[index]


def parse_macos_vm_stat(output: str) -> int | None:
    page_size_match = re.search(r"page size of (\d+) bytes", output)
    if page_size_match is None:
        return None
    page_size = int(page_size_match.group(1))
    available_pages = 0
    found = False
    for label in ("Pages free", "Pages inactive", "Pages speculative", "Pages purgeable"):
        match = re.search(rf"^{re.escape(label)}:\s+(\d+)\.", output, re.MULTILINE)
        if match is not None:
            available_pages += int(match.group(1))
            found = True
    return page_size * available_pages if found else None


def process_resident_bytes(pid: int) -> int | None:
    if os.name == "nt":
        return None
    if sys.platform == "darwin":
        try:
            result = subprocess.run(
                ["ps", "-o", "rss=", "-p", str(pid)],
                capture_output=True,
                check=False,
                text=True,
                timeout=1,
            )
            return int(result.stdout.strip()) * 1024 if result.returncode == 0 and result.stdout.strip() else None
        except (OSError, subprocess.TimeoutExpired, ValueError):
            return None

    try:
        for line in Path(f"/proc/{pid}/status").read_text(encoding="ascii").splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) * 1024
    except (OSError, UnicodeError, ValueError, IndexError):
        pass
    return None


def available_memory_bytes() -> int | None:
    if os.name == "nt":
        class MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("length", ctypes.c_uint32),
                ("memoryLoad", ctypes.c_uint32),
                ("totalPhysical", ctypes.c_uint64),
                ("availablePhysical", ctypes.c_uint64),
                ("totalPageFile", ctypes.c_uint64),
                ("availablePageFile", ctypes.c_uint64),
                ("totalVirtual", ctypes.c_uint64),
                ("availableVirtual", ctypes.c_uint64),
                ("availableExtendedVirtual", ctypes.c_uint64),
            ]

        status = MemoryStatus()
        status.length = ctypes.sizeof(status)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return int(status.availablePhysical)
        return None

    if sys.platform == "darwin":
        try:
            result = subprocess.run(
                ["vm_stat"],
                capture_output=True,
                check=False,
                text=True,
                timeout=2,
            )
            return parse_macos_vm_stat(result.stdout) if result.returncode == 0 else None
        except (OSError, subprocess.TimeoutExpired):
            return None

    try:
        return int(os.sysconf("SC_AVPHYS_PAGES")) * int(os.sysconf("SC_PAGE_SIZE"))
    except (AttributeError, OSError, TypeError, ValueError):
        return None


def summarize_run(path: Path, workers: int) -> dict:
    result = read_json(path / "experiment-result.json")
    if result is None:
        raise ValueError(f"Experiment result is missing: {path}")
    jobs = list(result.get("jobs", {}).values())
    elapsed = result.get("wallClockElapsedSeconds") or 0
    valid = [job for job in jobs if job.get("status") == "VALID"]
    job_elapsed = []
    peak_memory = []
    throughputs = []
    for job in valid:
        match = job.get("match") or {}
        verification = job.get("verification") or {}
        job_elapsed.append(float(match.get("elapsedSeconds", 0)) + float(verification.get("elapsedSeconds", 0)))
        artifact = match.get("result") or {}
        supervised_peak = match.get("peakWorkingSetBytes")
        artifact_peak = artifact.get("peakWorkingSetBytes")
        if isinstance(supervised_peak, int) and supervised_peak > 0:
            peak_memory.append(supervised_peak)
        elif isinstance(artifact_peak, int) and artifact_peak > 0:
            peak_memory.append(artifact_peak)
        if isinstance(artifact.get("ticksPerSecond"), (int, float)):
            throughputs.append(float(artifact["ticksPerSecond"]))

    useful_per_hour = len(valid) * 3600 / elapsed if elapsed > 0 else 0
    estimated_memory = sum(sorted(peak_memory, reverse=True)[:workers])
    return {
        "workers": workers,
        "status": result.get("status"),
        "jobCount": len(jobs),
        "validCount": len(valid),
        "wallClockElapsedSeconds": elapsed,
        "usefulMatchesPerHour": useful_per_hour,
        "perWorkerUsefulMatchesPerHour": useful_per_hour / workers,
        "meanJobElapsedSeconds": sum(job_elapsed) / len(job_elapsed) if job_elapsed else 0,
        "p95JobElapsedSeconds": percentile95(job_elapsed),
        "estimatedConcurrentPeakWorkingSetBytes": estimated_memory,
        "medianTicksPerSecond": sorted(throughputs)[len(throughputs) // 2] if throughputs else 0,
        "parityMismatchCount": (result.get("parity") or {}).get("mismatchCount", 0),
        "repeatMismatchCount": (result.get("repeatEquivalence") or {}).get("mismatchCount", 0),
    }


def build_efficiency_decision(single: dict, dual: dict, system_available_memory_bytes: int | None) -> dict:
    criteria = {
        "aggregateGainAtLeast1Point30": dual["usefulMatchesPerHour"] >= 1.30 * single["usefulMatchesPerHour"],
        "perWorkerRetentionAtLeast0Point65": (
            dual["perWorkerUsefulMatchesPerHour"] >= 0.65 * single["usefulMatchesPerHour"]
        ),
        "p95InflationAtMost1Point60": dual["p95JobElapsedSeconds"] <= 1.60 * single["p95JobElapsedSeconds"],
        "estimatedPeakWorkingSetAtMost11GiB": dual["estimatedConcurrentPeakWorkingSetBytes"] <= 11 * 1024**3,
        "systemAvailableMemoryAtLeast4GiB": (
            system_available_memory_bytes is not None and system_available_memory_bytes >= 4 * 1024**3
        ),
        "allRunsValid": dual["validCount"] == dual["jobCount"],
        "noParityMismatch": dual["parityMismatchCount"] == 0,
        "noRepeatMismatch": dual.get("repeatMismatchCount", 0) == 0,
        "noCrossRunMismatch": dual.get("crossRunMismatchCount", 0) == 0,
    }
    selected = 2 if all(criteria.values()) else 1
    selected_summary = dual if selected == 2 else single
    useful_per_hour = selected_summary["usefulMatchesPerHour"]
    predicted_m3_hours = 600 / useful_per_hour if useful_per_hour > 0 else None
    m3_ready = (
        useful_per_hour >= 25
        and selected_summary["meanJobElapsedSeconds"] <= 288
        and selected_summary["validCount"] == selected_summary["jobCount"]
        and selected_summary["parityMismatchCount"] == 0
    )
    headless_gate = not m3_ready and (
        selected_summary["medianTicksPerSecond"] < 1000
        or predicted_m3_hours is None
        or predicted_m3_hours > 24
    )
    return {
        "schemaVersion": SCHEMA_VERSION,
        "status": "M3_READY" if m3_ready else "PERFORMANCE_BLOCKED",
        "selectedWorkers": selected,
        "criteria": criteria,
        "runs": [single, dual],
        "systemAvailableMemoryBytes": system_available_memory_bytes,
        "m3Readiness": {
            "minimumUsefulMatchesPerHour": 25,
            "maximumMeanJobElapsedSeconds": 288,
            "plannedVerifiedRuns": 600,
            "predictedHours": predicted_m3_hours,
            "passed": m3_ready,
        },
        "headlessDecision": "PROFILE_REQUIRED" if headless_gate else "DEFERRED",
        "generatedUtc": utc_now(),
    }


def build_scaling_decision(runs: list[dict], system_available_memory_bytes: int | None) -> dict:
    if not runs or runs[0].get("workers") != 1:
        raise ValueError("Scaling calibration must start with a one-worker run")
    worker_counts = [run.get("workers") for run in runs]
    if worker_counts != sorted(set(worker_counts)) or any(
        not isinstance(workers, int) or workers < 1 or workers > MAX_WORKERS for workers in worker_counts
    ):
        raise ValueError(f"Scaling calibration worker counts must be unique, ordered, and within 1..{MAX_WORKERS}")

    single = runs[0]
    candidate_criteria = {}
    selected = 1
    selection_open = True
    previous_run = None
    for run in runs:
        workers = run["workers"]
        criteria = {
            "aggregateThroughputMeetsPerWorkerFloor": (
                run["usefulMatchesPerHour"] >= workers * 0.65 * single["usefulMatchesPerHour"]
            ),
            "perWorkerRetentionAtLeast0Point65": (
                run["perWorkerUsefulMatchesPerHour"] >= 0.65 * single["usefulMatchesPerHour"]
            ),
            "p95InflationAtMost1Point60": (
                run["p95JobElapsedSeconds"] <= 1.60 * single["p95JobElapsedSeconds"]
            ),
            "estimatedPeakWorkingSetAtMost11GiB": (
                run["estimatedConcurrentPeakWorkingSetBytes"] <= 11 * 1024**3
            ),
            "systemAvailableMemoryAtLeast4GiB": (
                system_available_memory_bytes is not None
                and system_available_memory_bytes >= 4 * 1024**3
            ),
            "allRunsValid": run["validCount"] == run["jobCount"],
            "noParityMismatch": run["parityMismatchCount"] == 0,
            "noRepeatMismatch": run.get("repeatMismatchCount", 0) == 0,
            "noCrossRunMismatch": run.get("crossRunMismatchCount", 0) == 0,
            "aggregateGainOverPreviousAtLeast1Point10": (
                previous_run is None
                or run["usefulMatchesPerHour"] >= 1.10 * previous_run["usefulMatchesPerHour"]
            ),
        }
        candidate_criteria[str(workers)] = criteria
        if selection_open and all(criteria.values()):
            selected = workers
        else:
            selection_open = False
        previous_run = run

    selected_summary = next(run for run in runs if run["workers"] == selected)
    useful_per_hour = selected_summary["usefulMatchesPerHour"]
    predicted_m3_hours = 600 / useful_per_hour if useful_per_hour > 0 else None
    m3_ready = (
        useful_per_hour >= 25
        and selected_summary["meanJobElapsedSeconds"] <= 288
        and selected_summary["validCount"] == selected_summary["jobCount"]
        and selected_summary["parityMismatchCount"] == 0
    )
    headless_gate = not m3_ready and (
        selected_summary["medianTicksPerSecond"] < 1000
        or predicted_m3_hours is None
        or predicted_m3_hours > 24
    )
    return {
        "schemaVersion": SCHEMA_VERSION,
        "status": "M3_READY" if m3_ready else "PERFORMANCE_BLOCKED",
        "selectedWorkers": selected,
        "calibratedWorkerCounts": worker_counts,
        "criteria": candidate_criteria[str(selected)],
        "candidateCriteria": candidate_criteria,
        "runs": runs,
        "systemAvailableMemoryBytes": system_available_memory_bytes,
        "m3Readiness": {
            "minimumUsefulMatchesPerHour": 25,
            "maximumMeanJobElapsedSeconds": 288,
            "plannedVerifiedRuns": 600,
            "predictedHours": predicted_m3_hours,
            "passed": m3_ready,
        },
        "headlessDecision": "PROFILE_REQUIRED" if headless_gate else "DEFERRED",
        "generatedUtc": utc_now(),
    }


def calibrate_manifest(args: argparse.Namespace) -> int:
    build = None
    if not getattr(args, "skip_build", False):
        build = build_engine(args.engine_dir.resolve(), args.output_root.resolve() / "build")
        if build["exitCode"] != 0 or build["timedOut"]:
            return 1

    worker_counts = tuple(getattr(args, "worker_counts", (1, 2)))
    if not worker_counts or worker_counts[0] != 1 or list(worker_counts) != sorted(set(worker_counts)):
        raise ValueError("--worker-counts must be unique, ascending, and start with 1")

    summaries = []
    for workers in worker_counts:
        run_args = argparse.Namespace(
            manifest=args.manifest,
            output_root=args.output_root / f"workers-{workers}",
            content_dir=args.content_dir,
            engine_dir=args.engine_dir,
            max_workers=workers,
            skip_build=True,
        )
        run_exit_code = run_manifest(run_args)
        summaries.append(summarize_run(run_args.output_root.resolve(), workers))
        if run_exit_code != 0 and not getattr(args, "continue_after_failure", False):
            break

    completed_counts = tuple(summary["workers"] for summary in summaries)
    equivalence = calibration_equivalence_report(args.output_root.resolve(), completed_counts)
    for summary in summaries:
        summary["crossRunMismatchCount"] = equivalence["byWorkers"][str(summary["workers"])]["mismatchCount"]
    if completed_counts == (1, 2):
        decision = build_efficiency_decision(summaries[0], summaries[1], available_memory_bytes())
    else:
        decision = build_scaling_decision(summaries, available_memory_bytes())
    decision["build"] = build
    decision["crossRunEquivalence"] = equivalence
    atomic_json(args.output_root.resolve() / "calibration-equivalence.json", equivalence)
    atomic_json(args.output_root.resolve() / "efficiency-decision.json", decision)
    return 0 if decision["status"] == "M3_READY" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subcommands = parser.add_subparsers(dest="command", required=True)
    run = subcommands.add_parser("run")
    run.add_argument("--manifest", type=Path, required=True)
    run.add_argument("--output-root", type=Path, required=True)
    run.add_argument("--content-dir", type=Path, required=True)
    run.add_argument("--engine-dir", type=Path, default=Path(__file__).resolve().parents[1])
    worker_choices = tuple(range(1, MAX_WORKERS + 1))
    run.add_argument("--max-workers", type=int, choices=worker_choices, default=1)
    run.add_argument("--skip-build", action="store_true")
    run.set_defaults(handler=run_manifest)
    calibrate = subcommands.add_parser("calibrate")
    calibrate.add_argument("--manifest", type=Path, required=True)
    calibrate.add_argument("--output-root", type=Path, required=True)
    calibrate.add_argument("--content-dir", type=Path, required=True)
    calibrate.add_argument("--engine-dir", type=Path, default=Path(__file__).resolve().parents[1])
    calibrate.add_argument("--worker-counts", type=int, nargs="+", choices=worker_choices, default=(1, 2))
    calibrate.add_argument("--continue-after-failure", action="store_true")
    calibrate.add_argument("--skip-build", action="store_true")
    calibrate.set_defaults(handler=calibrate_manifest)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.handler(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"strategic_ai_runner: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
