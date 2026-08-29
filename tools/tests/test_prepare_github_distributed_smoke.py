import hashlib
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import prepare_github_distributed_smoke as distributed_smoke


EXECUTION_SHA = "1" * 40
DESIGN_BASE_SHA = "31e30ab3831f03b66e7fb49b96aa5825ba6ba437"


class PrepareGithubDistributedSmokeTests(unittest.TestCase):
    def create_source(self, root: Path) -> tuple[Path, Path, bytes]:
        source = root / "source"
        candidate = source / "candidates" / "squad-size-40.json"
        candidate.parent.mkdir(parents=True)
        candidate_bytes = distributed_smoke.serialized(
            {
                "schemaVersion": "1.0.0",
                "candidateId": "squad-size-40-baseline",
                "squadSize": 40,
            }
        )
        candidate.write_bytes(candidate_bytes)
        candidate_sha256 = hashlib.sha256(candidate_bytes).hexdigest()

        source_ids = {
            selection.source_job_id
            for shard in range(distributed_smoke.SHARD_COUNT)
            for selection in distributed_smoke.selections_for_shard(shard)
        }
        matches = []
        for index, source_job_id in enumerate(sorted(source_ids), start=1):
            specification = source / "specifications" / f"{source_job_id}.json"
            specification.parent.mkdir(parents=True, exist_ok=True)
            specification.write_bytes(
                distributed_smoke.serialized(
                    {
                        "schemaVersion": "1.2.0",
                        "modId": "ra",
                        "mapUid": f"map-{index}",
                        "randomSeed": 3100 + index,
                        "candidatePath": "../candidates/squad-size-40.json",
                        "executionMode": "UNCAPPED",
                        "maxWorldTicks": 90000,
                    }
                )
            )
            matches.append(
                {
                    "id": source_job_id,
                    "specificationPath": specification.relative_to(source).as_posix(),
                    "expectedCandidateId": "squad-size-40-baseline",
                    "expectedCandidateSha256": candidate_sha256,
                    "expectedSquadSize": 40,
                }
            )

        source_manifest = source / "experiment-manifest.json"
        source_manifest.write_bytes(
            distributed_smoke.serialized(
                {
                    "schemaVersion": "1.0.0",
                    "matchTimeoutSeconds": 300,
                    "verificationTimeoutSeconds": 180,
                    "matches": matches,
                }
            )
        )
        controller = root / "strategic_ai_runner.py"
        controller.write_text("print('controller')\n", encoding="utf-8")
        return source_manifest, controller, candidate_bytes

    def test_materializes_four_shards_with_two_exact_sentinels_and_two_unique_jobs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_manifest, controller, candidate_bytes = self.create_source(root)
            source_value = json.loads(source_manifest.read_text(encoding="utf-8"))
            source_jobs = {job["id"]: job for job in source_value["matches"]}
            sentinel_ids = None
            unique_ids = set()
            specification_hashes = []
            sentinel_hashes: dict[str, set[str]] = {}

            for shard in range(distributed_smoke.SHARD_COUNT):
                output = root / f"output-{shard}"
                manifest_path = distributed_smoke.prepare(
                    source_manifest,
                    output,
                    shard,
                    controller,
                    EXECUTION_SHA,
                    DESIGN_BASE_SHA,
                )
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                registration_path = output / "github-distributed-smoke-registration.json"
                registration = json.loads(registration_path.read_text(encoding="utf-8"))

                self.assertEqual(120, manifest["matchTimeoutSeconds"])
                self.assertEqual(90, manifest["verificationTimeoutSeconds"])
                self.assertEqual(4, len(manifest["matches"]))
                self.assertEqual("GITHUB_RUNNER_DISTRIBUTED_SMOKE", registration["purpose"])
                self.assertEqual("NONE", registration["decisionInfluence"])
                self.assertFalse(registration["formalSelection"])
                self.assertEqual(shard, registration["shardIndex"])
                self.assertEqual(4, registration["shardCount"])
                self.assertEqual(4, registration["maxWorkers"])
                self.assertEqual(EXECUTION_SHA, registration["executionSha"])
                self.assertEqual(DESIGN_BASE_SHA, registration["designBaseSha"])
                self.assertEqual(
                    distributed_smoke.file_sha256(source_manifest),
                    registration["sourceManifestSha256"],
                )
                self.assertEqual(
                    distributed_smoke.file_sha256(controller),
                    registration["controllerScriptSha256"],
                )
                self.assertEqual(
                    distributed_smoke.file_sha256(manifest_path),
                    registration["manifestSha256"],
                )

                if sentinel_ids is None:
                    sentinel_ids = registration["sentinelJobIds"]
                self.assertEqual(sentinel_ids, registration["sentinelJobIds"])
                self.assertTrue(unique_ids.isdisjoint(registration["uniqueJobIds"]))
                unique_ids.update(registration["uniqueJobIds"])
                self.assertEqual(
                    ["SENTINEL", "SENTINEL", "UNIQUE", "UNIQUE"],
                    [job["role"] for job in registration["jobs"]],
                )

                manifest_jobs = {job["id"]: job for job in manifest["matches"]}
                for provenance in registration["jobs"]:
                    job_id = provenance["id"]
                    self.assertNotRegex(job_id, r"-r[01]$")
                    quick_job = manifest_jobs[job_id]
                    source_job = source_jobs[provenance["sourceJobId"]]
                    self.assertEqual(
                        distributed_smoke.object_sha256(source_job),
                        provenance["sourceJobSha256"],
                    )
                    self.assertEqual(
                        distributed_smoke.object_sha256(quick_job),
                        provenance["jobSha256"],
                    )
                    specification = output / provenance["specificationPath"]
                    source_specification = source_manifest.parent / provenance["sourceSpecificationPath"]
                    quick_value = json.loads(specification.read_text(encoding="utf-8"))
                    source_specification_value = json.loads(
                        source_specification.read_text(encoding="utf-8")
                    )
                    self.assertEqual(30000, quick_value["maxWorldTicks"])
                    self.assertEqual(90000, source_specification_value["maxWorldTicks"])
                    source_specification_value["maxWorldTicks"] = 30000
                    self.assertEqual(source_specification_value, quick_value)
                    self.assertEqual(
                        distributed_smoke.file_sha256(specification),
                        provenance["specificationSha256"],
                    )
                    self.assertEqual(
                        distributed_smoke.file_sha256(source_specification),
                        provenance["sourceSpecificationSha256"],
                    )
                    candidate = output / provenance["candidatePath"]
                    self.assertEqual(candidate_bytes, candidate.read_bytes())
                    self.assertEqual(
                        hashlib.sha256(candidate_bytes).hexdigest(),
                        provenance["expectedCandidateSha256"],
                    )
                    specification_hashes.append(provenance["specificationSha256"])
                    if provenance["role"] == "SENTINEL":
                        sentinel_hashes.setdefault(job_id, set()).add(
                            provenance["specificationSha256"]
                        )

                # Identical regeneration is immutable and resumable.
                distributed_smoke.prepare(
                    source_manifest,
                    output,
                    shard,
                    controller,
                    EXECUTION_SHA,
                    DESIGN_BASE_SHA,
                )

            self.assertEqual(8, len(unique_ids))
            self.assertEqual(16, len(specification_hashes))
            self.assertEqual(10, len(set(specification_hashes)))
            self.assertEqual(2, len(sentinel_hashes))
            self.assertTrue(all(len(values) == 1 for values in sentinel_hashes.values()))

    def test_rejects_invalid_shard_sha_missing_source_and_output_drift(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_manifest, controller, _ = self.create_source(root)

            with self.assertRaisesRegex(ValueError, "range 0..3"):
                distributed_smoke.prepare(
                    source_manifest,
                    root / "invalid-shard",
                    4,
                    controller,
                    EXECUTION_SHA,
                    DESIGN_BASE_SHA,
                )
            with self.assertRaisesRegex(ValueError, "40-character Git SHA"):
                distributed_smoke.prepare(
                    source_manifest,
                    root / "invalid-sha",
                    0,
                    controller,
                    "short",
                    DESIGN_BASE_SHA,
                )

            source = json.loads(source_manifest.read_text(encoding="utf-8"))
            source["matches"] = [
                job
                for job in source["matches"]
                if job["id"] != distributed_smoke.SENTINELS[0].source_job_id
            ]
            missing_manifest = root / "missing-source.json"
            missing_manifest.write_bytes(distributed_smoke.serialized(source))
            with self.assertRaisesRegex(ValueError, "lacks selected job"):
                distributed_smoke.prepare(
                    missing_manifest,
                    root / "missing-output",
                    0,
                    controller,
                    EXECUTION_SHA,
                    DESIGN_BASE_SHA,
                )

            output = root / "drift-output"
            distributed_smoke.prepare(
                source_manifest,
                output,
                0,
                controller,
                EXECUTION_SHA,
                DESIGN_BASE_SHA,
            )
            specification = output / "specifications" / f"{distributed_smoke.SENTINELS[0].job_id}.json"
            specification.write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Refusing to overwrite"):
                distributed_smoke.prepare(
                    source_manifest,
                    output,
                    0,
                    controller,
                    EXECUTION_SHA,
                    DESIGN_BASE_SHA,
                )


if __name__ == "__main__":
    unittest.main()
