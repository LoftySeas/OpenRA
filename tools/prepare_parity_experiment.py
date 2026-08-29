#!/usr/bin/env python3

"""Materialize the registered StrategicAI paced/uncapped parity experiment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from strategic_ai_runner import SAFE_JOB_ID, atomic_json, file_sha256


def load_matrix(path: Path) -> dict:
    value = json.loads(path.resolve().read_text(encoding="utf-8"))
    if not isinstance(value, dict) or set(value) != {
        "schemaVersion",
        "matchTimeoutSeconds",
        "verificationTimeoutSeconds",
        "options",
        "scenarios",
    }:
        raise ValueError("Parity matrix contains undocumented top-level properties")
    if value["schemaVersion"] != "1.0.0":
        raise ValueError("Parity matrix schemaVersion must be 1.0.0")
    scenarios = value["scenarios"]
    if not isinstance(scenarios, list) or len(scenarios) != 10:
        raise ValueError("Parity matrix must contain exactly ten scenarios")

    identifiers = set()
    statuses = set()
    for scenario in scenarios:
        required = {"id", "mapUid", "randomSeed", "opponentBotType", "maxWorldTicks", "expectedMatchStatus"}
        if not isinstance(scenario, dict) or not required.issubset(scenario) or not set(scenario).issubset(
            required | {"strategicHandicap"}
        ):
            raise ValueError("Parity scenario contains undocumented or missing properties")
        identifier = scenario["id"]
        if not isinstance(identifier, str) or not SAFE_JOB_ID.fullmatch(identifier) or identifier in identifiers:
            raise ValueError(f"Invalid or duplicate parity scenario id {identifier!r}")
        identifiers.add(identifier)
        if scenario["opponentBotType"] not in {"normal", "rush"}:
            raise ValueError(f"Invalid opponentBotType for {identifier}")
        if scenario["expectedMatchStatus"] not in {"COMPLETED", "TIMED_OUT"}:
            raise ValueError(f"Invalid expectedMatchStatus for {identifier}")
        statuses.add(scenario["expectedMatchStatus"])
    if statuses != {"COMPLETED", "TIMED_OUT"}:
        raise ValueError("Parity matrix must preregister both natural completion and synchronized timeout")
    return value


def write_immutable(path: Path, value: dict) -> None:
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing != value:
            raise ValueError(f"Refusing to overwrite a different registered artifact: {path}")
        return
    atomic_json(path, value)


def prepare(matrix_path: Path, output_dir: Path) -> Path:
    matrix_path = matrix_path.resolve()
    matrix = load_matrix(matrix_path)
    output_dir = output_dir.resolve()
    specifications_dir = output_dir / "specifications"
    matches = []
    for scenario in matrix["scenarios"]:
        for mode in ("PACED", "UNCAPPED"):
            job_id = f"{scenario['id']}-{mode.lower()}"
            specification_path = specifications_dir / f"{job_id}.json"
            specification = {
                "schemaVersion": "1.1.0",
                "modId": "ra",
                "mapUid": scenario["mapUid"],
                "randomSeed": scenario["randomSeed"],
                "options": matrix["options"],
                "players": [
                    {
                        "slot": "Multi0",
                        "botType": "strategic",
                        "faction": "england",
                        "color": "F50606",
                        "spawnPoint": 1,
                        "team": 1,
                        "handicap": scenario.get("strategicHandicap", 0),
                    },
                    {
                        "slot": "Multi1",
                        "botType": scenario["opponentBotType"],
                        "faction": "russia",
                        "color": "280DF6",
                        "spawnPoint": 2,
                        "team": 2,
                        "handicap": 0,
                    },
                ],
                "maxWorldTicks": scenario["maxWorldTicks"],
                "recordReplay": True,
                "executionMode": mode,
            }
            write_immutable(specification_path, specification)
            matches.append(
                {
                    "id": job_id,
                    "specificationPath": specification_path.relative_to(output_dir).as_posix(),
                    "pairId": scenario["id"],
                    "executionMode": mode,
                    "expectedMatchStatus": scenario["expectedMatchStatus"],
                }
            )

    manifest_path = output_dir / "experiment-manifest.json"
    manifest = {
        "schemaVersion": "1.0.0",
        "matchTimeoutSeconds": matrix["matchTimeoutSeconds"],
        "verificationTimeoutSeconds": matrix["verificationTimeoutSeconds"],
        "matches": matches,
    }
    write_immutable(manifest_path, manifest)
    write_immutable(
        output_dir / "parity-registration.json",
        {
            "schemaVersion": "1.0.0",
            "matrixPath": str(matrix_path),
            "matrixSha256": file_sha256(matrix_path),
            "manifestSha256": file_sha256(manifest_path),
            "scenarioCount": len(matrix["scenarios"]),
            "jobCount": len(matches),
        },
    )
    return manifest_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(prepare(args.matrix, args.output_dir))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"prepare_parity_experiment: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
