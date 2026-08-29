#!/usr/bin/env python3

"""Materialize immutable StrategicAI M3 training or validation runs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path


PLAN_VERSION = "1.0.0"
REGISTRATION_VERSION = "1.0.0"
CANDIDATE_VERSION = "1.0.0"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def serialized(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_immutable(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != content:
            raise ValueError(f"Refusing to overwrite changed registered artifact: {path}")
        return

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


def load_plan(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "schemaVersion", "experimentId", "candidateSquadSizes", "baselineSquadSize",
        "executionMode", "maxWorldTicks", "startingCash", "matchTimeoutSeconds",
        "verificationTimeoutSeconds", "training", "validation", "decisionRule",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError("M3 plan must contain exactly the documented properties")
    if value["schemaVersion"] != PLAN_VERSION:
        raise ValueError(f"Unsupported M3 plan schemaVersion {value['schemaVersion']!r}")
    candidates = value["candidateSquadSizes"]
    if candidates != [20, 30, 40, 50, 60]:
        raise ValueError("M3 v1 candidates must be exactly [20, 30, 40, 50, 60]")
    if value["baselineSquadSize"] != 40:
        raise ValueError("M3 v1 baselineSquadSize must be 40")
    if value["executionMode"] != "UNCAPPED":
        raise ValueError("M3 v1 requires UNCAPPED execution")
    if not isinstance(value["maxWorldTicks"], int) or value["maxWorldTicks"] <= 0:
        raise ValueError("maxWorldTicks must be positive")
    if value["decisionRule"] != {
        "bootstrapIterations": 10000,
        "bootstrapSeed": 20260829,
        "confidenceLevel": 0.95,
        "minimumWinRateDifference": 0.10,
        "failureRateMustNotIncrease": True,
    }:
        raise ValueError("M3 v1 decisionRule is frozen and must not be changed")

    training = value["training"]
    validation = value["validation"]
    for name, scenario_set, map_count, opponents in (
        ("training", training, 3, ["normal", "rush"]),
        ("validation", validation, 3, ["normal", "rush", "turtle"]),
    ):
        if not isinstance(scenario_set, dict) or set(scenario_set) != {"maps", "opponents", "seeds"}:
            raise ValueError(f"{name} must contain maps, opponents, and seeds")
        if len(scenario_set["maps"]) != map_count or scenario_set["opponents"] != opponents:
            raise ValueError(f"{name} map/opponent matrix differs from the registered M3 v1 design")
        if len(scenario_set["seeds"]) != 10 or len(set(scenario_set["seeds"])) != 10:
            raise ValueError(f"{name} must contain ten unique seeds")

    training_uids = {item["uid"] for item in training["maps"]}
    validation_uids = {item["uid"] for item in validation["maps"]}
    if training_uids & validation_uids:
        raise ValueError("Training and validation map UIDs must be disjoint")
    if set(training["seeds"]) & set(validation["seeds"]):
        raise ValueError("Training and validation seeds must be disjoint")
    return value


def candidate_value(squad_size: int, baseline_path: Path) -> bytes:
    if squad_size == 40:
        value = json.loads(baseline_path.read_text(encoding="utf-8"))
        if value.get("schemaVersion") != CANDIDATE_VERSION or value.get("squadSize") != 40:
            raise ValueError("Committed baseline candidate is invalid")
        return baseline_path.read_bytes()
    return serialized(
        {
            "schemaVersion": CANDIDATE_VERSION,
            "candidateId": f"squad-size-{squad_size}",
            "squadSize": squad_size,
            "notes": "Pre-registered StrategicAI M3 integer-grid candidate.",
        }
    )


def prepare(plan_path: Path, phase: str, output_dir: Path, selected_squad_size: int | None = None) -> Path:
    plan_path = plan_path.resolve()
    plan = load_plan(plan_path)
    output_dir = output_dir.resolve()
    baseline_path = plan_path.parent / "m3-candidate-baseline.json"
    if not baseline_path.is_file():
        raise ValueError(f"Baseline candidate is missing: {baseline_path}")

    if phase == "training":
        if selected_squad_size is not None:
            raise ValueError("Training registration does not accept a selected candidate")
        squad_sizes = plan["candidateSquadSizes"]
        scenario_set = plan["training"]
    elif phase == "validation":
        if selected_squad_size not in plan["candidateSquadSizes"]:
            raise ValueError("Validation selected candidate must be one of the registered grid values")
        squad_sizes = sorted({plan["baselineSquadSize"], selected_squad_size})
        scenario_set = plan["validation"]
    else:
        raise ValueError("phase must be training or validation")

    candidates = []
    candidate_by_size = {}
    for squad_size in squad_sizes:
        candidate_path = output_dir / "candidates" / f"squad-size-{squad_size}.json"
        write_immutable(candidate_path, candidate_value(squad_size, baseline_path))
        candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
        identity = {
            "candidateId": candidate["candidateId"],
            "squadSize": squad_size,
            "path": str(candidate_path),
            "sha256": file_sha256(candidate_path),
        }
        candidates.append(identity)
        candidate_by_size[squad_size] = identity

    matches = []
    cells = []
    for map_value in scenario_set["maps"]:
        for opponent in scenario_set["opponents"]:
            for seed_index, seed in enumerate(scenario_set["seeds"], start=1):
                scenario_id = f"{phase[:2]}-{map_value['id']}-{opponent}-s{seed_index:02d}"
                for squad_size in squad_sizes:
                    candidate = candidate_by_size[squad_size]
                    job_ids = []
                    for repeat in range(2):
                        job_id = f"{scenario_id}-c{squad_size}-r{repeat}"
                        job_ids.append(job_id)
                        specification_path = output_dir / "specifications" / f"{job_id}.json"
                        relative_candidate = os.path.relpath(candidate["path"], specification_path.parent)
                        specification = {
                            "schemaVersion": "1.2.0",
                            "modId": "ra",
                            "mapUid": map_value["uid"],
                            "randomSeed": seed,
                            "options": {
                                "gamespeed": "fastest",
                                "shortgame": "True",
                                "startingcash": plan["startingCash"],
                            },
                            "players": [
                                {
                                    "slot": "Multi0", "botType": "strategic", "faction": "england",
                                    "color": "F50606", "spawnPoint": 1, "team": 1, "handicap": 0,
                                },
                                {
                                    "slot": "Multi1", "botType": opponent, "faction": "russia",
                                    "color": "280DF6", "spawnPoint": 2, "team": 2, "handicap": 0,
                                },
                            ],
                            "maxWorldTicks": plan["maxWorldTicks"],
                            "recordReplay": True,
                            "executionMode": plan["executionMode"],
                            "candidatePath": Path(relative_candidate).as_posix(),
                        }
                        write_immutable(specification_path, serialized(specification))
                        matches.append(
                            {
                                "id": job_id,
                                "specificationPath": os.path.relpath(specification_path, output_dir).replace("\\", "/"),
                                "expectedExecutionMode": None,
                                "expectedMatchStatus": None,
                                "expectedCandidateId": candidate["candidateId"],
                                "expectedCandidateSha256": candidate["sha256"],
                                "expectedSquadSize": squad_size,
                            }
                        )
                        matches[-1] = {key: value for key, value in matches[-1].items() if value is not None}

                    cells.append(
                        {
                            "cellId": f"{scenario_id}-c{squad_size}",
                            "phase": phase,
                            "mapId": map_value["id"],
                            "mapUid": map_value["uid"],
                            "opponent": opponent,
                            "seed": seed,
                            "candidateId": candidate["candidateId"],
                            "squadSize": squad_size,
                            "jobIds": job_ids,
                        }
                    )

    manifest_path = output_dir / "experiment-manifest.json"
    manifest = {
        "schemaVersion": "1.0.0",
        "matchTimeoutSeconds": plan["matchTimeoutSeconds"],
        "verificationTimeoutSeconds": plan["verificationTimeoutSeconds"],
        "matches": matches,
    }
    write_immutable(manifest_path, serialized(manifest))

    registration_path = output_dir / "m3-registration.json"
    registration = {
        "schemaVersion": REGISTRATION_VERSION,
        "experimentId": plan["experimentId"],
        "phase": phase,
        "planPath": str(plan_path),
        "planSha256": file_sha256(plan_path),
        "manifestPath": str(manifest_path),
        "manifestSha256": file_sha256(manifest_path),
        "baselineSquadSize": plan["baselineSquadSize"],
        "selectedSquadSize": selected_squad_size,
        "decisionRule": plan["decisionRule"],
        "candidates": candidates,
        "cells": cells,
    }
    write_immutable(registration_path, serialized(registration))
    return manifest_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--phase", choices=("training", "validation"), required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--selected-squad-size", type=int)
    args = parser.parse_args()
    manifest = prepare(args.plan, args.phase, args.output_dir, args.selected_squad_size)
    print(manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
