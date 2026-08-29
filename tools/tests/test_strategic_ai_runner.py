import argparse
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import strategic_ai_runner
import prepare_parity_experiment


class StrategicAiRunnerTest(unittest.TestCase):
    def test_controller_execution_identity_binds_script_and_python(self):
        identity = strategic_ai_runner.controller_execution_identity()
        script = Path(strategic_ai_runner.__file__).resolve()
        self.assertEqual(str(script), identity["controllerScriptPath"])
        self.assertEqual(strategic_ai_runner.file_sha256(script), identity["controllerScriptSha256"])
        self.assertEqual(sys.executable, identity["pythonExecutable"])
        self.assertEqual(list(sys.argv), identity["argv"])
        self.assertRegex(identity["executionId"], r"^[0-9a-f]{8}-[0-9a-f-]{27}$")

    def test_run_manifest_records_controller_execution(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            specification = root / "match.json"
            specification.write_text("{}", encoding="utf-8")
            manifest_path = root / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "schemaVersion": "1.0.0",
                        "matchTimeoutSeconds": 10,
                        "verificationTimeoutSeconds": 20,
                        "matches": [{"id": "sample", "specificationPath": "match.json"}],
                    }
                ),
                encoding="utf-8",
            )
            engine = root / "engine"
            executable = engine / "bin" / ("OpenRA.exe" if os.name == "nt" else "OpenRA")
            executable.parent.mkdir(parents=True)
            executable.write_bytes(b"")
            args = argparse.Namespace(
                manifest=manifest_path,
                output_root=root / "output",
                content_dir=root / "content",
                engine_dir=engine,
                max_workers=1,
                skip_build=True,
            )
            def valid_job(*values):
                return {
                    "id": "sample",
                    "status": "VALID",
                    "specificationSha256": strategic_ai_runner.file_sha256(specification),
                    "expectedCandidateId": None,
                    "expectedCandidateSha256": None,
                    "expectedSquadSize": None,
                    "controllerExecutionId": values[8],
                    "controllerScriptSha256": values[9],
                }

            with mock.patch.object(strategic_ai_runner, "run_job", side_effect=valid_job):
                self.assertEqual(0, strategic_ai_runner.run_manifest(args))
            result = json.loads((args.output_root / "experiment-result.json").read_text(encoding="utf-8"))
            self.assertEqual(1, len(result["controllerExecutions"]))
            self.assertEqual(
                strategic_ai_runner.file_sha256(Path(strategic_ai_runner.__file__)),
                result["controllerExecutions"][0]["controllerScriptSha256"],
            )
            self.assertTrue(result["controllerProvenance"]["complete"])
            self.assertFalse(result["controllerProvenance"]["legacyCoverageGap"])

    def test_full_reuse_resume_preserves_legacy_controller_gap(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            specification = root / "match.json"
            specification.write_text("{}", encoding="utf-8")
            manifest_path = root / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "schemaVersion": "1.0.0",
                        "matchTimeoutSeconds": 10,
                        "verificationTimeoutSeconds": 20,
                        "matches": [{"id": "legacy", "specificationPath": "match.json"}],
                    }
                ),
                encoding="utf-8",
            )
            engine = root / "engine"
            executable = engine / "bin" / ("OpenRA.exe" if os.name == "nt" else "OpenRA")
            executable.parent.mkdir(parents=True)
            executable.write_bytes(b"")
            output = root / "output"
            job_root = output / "workers" / "legacy"
            job_root.mkdir(parents=True)
            (job_root / "job-result.json").write_text(
                json.dumps(
                    {
                        "id": "legacy",
                        "status": "VALID",
                        "specificationSha256": strategic_ai_runner.file_sha256(specification),
                        "expectedCandidateId": None,
                        "expectedCandidateSha256": None,
                        "expectedSquadSize": None,
                    }
                ),
                encoding="utf-8",
            )
            args = argparse.Namespace(
                manifest=manifest_path,
                output_root=output,
                content_dir=root / "content",
                engine_dir=engine,
                max_workers=1,
                skip_build=True,
            )

            with mock.patch.object(strategic_ai_runner, "run_job") as run_job:
                self.assertEqual(0, strategic_ai_runner.run_manifest(args))
                run_job.assert_not_called()

            result = json.loads((output / "experiment-result.json").read_text(encoding="utf-8"))
            self.assertTrue(result["controllerProvenance"]["legacyCoverageGap"])
            self.assertEqual(["legacy"], result["controllerProvenance"]["unattributedJobIds"])
            self.assertFalse(result["controllerProvenance"]["complete"])

    def test_candidate_byte_drift_fails_before_resume(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate = root / "candidate.json"
            candidate.write_text(
                json.dumps({"candidateId": "squad-size-40", "squadSize": 40}), encoding="utf-8"
            )
            specification = root / "match.json"
            specification.write_text(json.dumps({"candidatePath": "candidate.json"}), encoding="utf-8")
            manifest_path = root / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "schemaVersion": "1.0.0",
                        "matchTimeoutSeconds": 10,
                        "verificationTimeoutSeconds": 20,
                        "matches": [
                            {
                                "id": "candidate",
                                "specificationPath": "match.json",
                                "expectedCandidateId": "squad-size-40",
                                "expectedCandidateSha256": strategic_ai_runner.file_sha256(candidate),
                                "expectedSquadSize": 40,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            job = strategic_ai_runner.load_manifest(manifest_path).jobs[0]
            candidate.write_text(
                json.dumps({"candidateId": "squad-size-40", "squadSize": 50}), encoding="utf-8"
            )

            with self.assertRaisesRegex(ValueError, "Candidate SHA-256 differs"):
                strategic_ai_runner.completed_job_is_reusable(root / "output", job)

    def test_manifest_is_strict_and_resolves_specs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            specification = root / "match.json"
            specification.write_text("{}", encoding="utf-8")
            manifest_path = root / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "schemaVersion": "1.0.0",
                        "matchTimeoutSeconds": 10,
                        "verificationTimeoutSeconds": 20,
                        "matches": [{"id": "sample-1", "specificationPath": "match.json"}],
                    }
                ),
                encoding="utf-8",
            )

            manifest = strategic_ai_runner.load_manifest(manifest_path)
            self.assertEqual(specification.resolve(), manifest.jobs[0].specification)
            self.assertEqual(strategic_ai_runner.file_sha256(specification), manifest.jobs[0].specification_sha256)

    def test_manifest_rejects_unsafe_job_id(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "match.json").write_text("{}", encoding="utf-8")
            manifest_path = root / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "schemaVersion": "1.0.0",
                        "matchTimeoutSeconds": 10,
                        "verificationTimeoutSeconds": 20,
                        "matches": [{"id": "../escape", "specificationPath": "match.json"}],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                strategic_ai_runner.load_manifest(manifest_path)

    def test_manifest_rejects_incomplete_or_duplicate_parity_pair(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "match.json").write_text("{}", encoding="utf-8")
            for modes in (("PACED",), ("PACED", "PACED")):
                manifest_path = root / "manifest.json"
                manifest_path.write_text(
                    json.dumps(
                        {
                            "schemaVersion": "1.0.0",
                            "matchTimeoutSeconds": 10,
                            "verificationTimeoutSeconds": 20,
                            "matches": [
                                {
                                    "id": f"sample-{index}",
                                    "specificationPath": "match.json",
                                    "pairId": "pair-1",
                                    "executionMode": mode,
                                }
                                for index, mode in enumerate(modes)
                            ],
                        }
                    ),
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(ValueError, "exactly one PACED and one UNCAPPED"):
                    strategic_ai_runner.load_manifest(manifest_path)

    def test_manifest_accepts_machine_checked_natural_termination(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "match.json").write_text("{}", encoding="utf-8")
            manifest_path = root / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "schemaVersion": "1.0.0",
                        "matchTimeoutSeconds": 10,
                        "verificationTimeoutSeconds": 20,
                        "matches": [
                            {
                                "id": f"sample-{mode.lower()}",
                                "specificationPath": "match.json",
                                "pairId": "pair-1",
                                "executionMode": mode,
                                "expectedMatchStatus": "COMPLETED",
                            }
                            for mode in ("PACED", "UNCAPPED")
                        ],
                    }
                ),
                encoding="utf-8",
            )
            manifest = strategic_ai_runner.load_manifest(manifest_path)
            self.assertTrue(all(job.expected_match_status == "COMPLETED" for job in manifest.jobs))

    def test_manifest_accepts_complete_candidate_identity_and_rejects_partial_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate = root / "candidate.json"
            candidate.write_text(
                json.dumps({"candidateId": "squad-size-20", "squadSize": 20}), encoding="utf-8"
            )
            (root / "match.json").write_text(
                json.dumps({"candidatePath": "candidate.json"}), encoding="utf-8"
            )
            manifest_path = root / "manifest.json"
            base = {
                "schemaVersion": "1.0.0",
                "matchTimeoutSeconds": 10,
                "verificationTimeoutSeconds": 20,
                "matches": [
                    {
                        "id": "candidate-20",
                        "specificationPath": "match.json",
                        "expectedCandidateId": "squad-size-20",
                        "expectedCandidateSha256": strategic_ai_runner.file_sha256(candidate),
                        "expectedSquadSize": 20,
                    }
                ],
            }
            manifest_path.write_text(json.dumps(base), encoding="utf-8")
            job = strategic_ai_runner.load_manifest(manifest_path).jobs[0]
            self.assertEqual("squad-size-20", job.expected_candidate_id)
            self.assertEqual(20, job.expected_squad_size)

            del base["matches"][0]["expectedCandidateSha256"]
            manifest_path.write_text(json.dumps(base), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Candidate expectations"):
                strategic_ai_runner.load_manifest(manifest_path)

    def test_valid_result_is_reused_only_for_same_specification(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            job_root = root / "workers" / "sample"
            job_root.mkdir(parents=True)
            specification = root / "match.json"
            specification.write_text("{}", encoding="utf-8")
            specification_sha256 = strategic_ai_runner.file_sha256(specification)
            job = strategic_ai_runner.Job("sample", specification, specification_sha256)
            strategic_ai_runner.atomic_json(
                job_root / "job-result.json",
                {"status": "VALID", "specificationSha256": specification_sha256},
            )
            self.assertIsNotNone(strategic_ai_runner.completed_job_is_reusable(root, job))
            specification.write_text('{"changed":true}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Specification changed"):
                strategic_ai_runner.completed_job_is_reusable(root, job)

    def test_failed_retry_uses_a_new_attempt_number(self):
        with tempfile.TemporaryDirectory() as temporary:
            job_root = Path(temporary)
            self.assertEqual(1, strategic_ai_runner.next_attempt_number(job_root))
            strategic_ai_runner.atomic_json(job_root / "job-result.json", {"status": "FAILED", "attempt": 1})
            self.assertEqual(2, strategic_ai_runner.next_attempt_number(job_root))

    def test_max_workers_accepts_up_to_eight_and_rejects_nine(self):
        parser = strategic_ai_runner.build_parser()
        parsed = parser.parse_args(
            [
                "run",
                "--manifest",
                "m.json",
                "--output-root",
                "out",
                "--content-dir",
                "content",
                "--max-workers",
                "8",
            ]
        )
        self.assertEqual(8, parsed.max_workers)
        with self.assertRaises(SystemExit):
            parser.parse_args(
                [
                    "run",
                    "--manifest",
                    "m.json",
                    "--output-root",
                    "out",
                    "--content-dir",
                    "content",
                    "--max-workers",
                    "9",
                ]
            )

    def test_parity_report_detects_synchronized_evidence_drift(self):
        evidence = {
            "finalWorldTick": 600,
            "finalSyncHash": 123,
            "orderDigestSha256": "a" * 64,
            "strategicDecisionDigestSha256": "b" * 64,
            "players": [{"outcome": "UNDEFINED"}],
        }
        jobs = {
            "paced": {
                "status": "VALID",
                "pairId": "pair-1",
                "expectedExecutionMode": "PACED",
                "match": {"result": evidence},
            },
            "uncapped": {
                "status": "VALID",
                "pairId": "pair-1",
                "expectedExecutionMode": "UNCAPPED",
                "match": {"result": {**evidence, "finalSyncHash": 456}},
            },
        }

        report = strategic_ai_runner.parity_report(jobs)
        self.assertEqual(1, report["mismatchCount"])
        self.assertEqual(["finalSyncHash"], report["comparisons"][0]["differences"])

    def test_percentile95_uses_nearest_rank(self):
        self.assertEqual(10, strategic_ai_runner.percentile95(list(range(1, 11))))

    def test_efficiency_decision_enforces_memory_and_predicts_m3_duration(self):
        single = {
            "usefulMatchesPerHour": 20.0,
            "perWorkerUsefulMatchesPerHour": 20.0,
            "p95JobElapsedSeconds": 180.0,
            "estimatedConcurrentPeakWorkingSetBytes": 2 * 1024**3,
            "validCount": 10,
            "jobCount": 10,
            "parityMismatchCount": 0,
            "meanJobElapsedSeconds": 180.0,
            "medianTicksPerSecond": 900.0,
        }
        dual = {
            **single,
            "usefulMatchesPerHour": 30.0,
            "perWorkerUsefulMatchesPerHour": 15.0,
            "p95JobElapsedSeconds": 220.0,
            "estimatedConcurrentPeakWorkingSetBytes": 4 * 1024**3,
            "meanJobElapsedSeconds": 200.0,
            "medianTicksPerSecond": 1100.0,
        }

        ready = strategic_ai_runner.build_efficiency_decision(single, dual, 8 * 1024**3)
        self.assertEqual(2, ready["selectedWorkers"])
        self.assertEqual("M3_READY", ready["status"])
        self.assertEqual(20.0, ready["m3Readiness"]["predictedHours"])
        self.assertEqual("DEFERRED", ready["headlessDecision"])

        memory_limited = strategic_ai_runner.build_efficiency_decision(single, dual, 3 * 1024**3)
        self.assertEqual(1, memory_limited["selectedWorkers"])
        self.assertFalse(memory_limited["criteria"]["systemAvailableMemoryAtLeast4GiB"])
        self.assertEqual("PERFORMANCE_BLOCKED", memory_limited["status"])
        self.assertEqual("PROFILE_REQUIRED", memory_limited["headlessDecision"])

    def test_scaling_decision_selects_highest_worker_count_that_keeps_retention(self):
        def run(workers, useful, p95=100, peak=1024):
            return {
                "workers": workers,
                "usefulMatchesPerHour": useful,
                "perWorkerUsefulMatchesPerHour": useful / workers,
                "p95JobElapsedSeconds": p95,
                "estimatedConcurrentPeakWorkingSetBytes": peak,
                "validCount": 10,
                "jobCount": 10,
                "parityMismatchCount": 0,
                "meanJobElapsedSeconds": 50,
                "medianTicksPerSecond": 1000,
            }

        decision = strategic_ai_runner.build_scaling_decision(
            [run(1, 100), run(2, 170), run(3, 210), run(4, 240)],
            8 * 1024**3,
        )
        self.assertEqual(3, decision["selectedWorkers"])
        self.assertEqual([1, 2, 3, 4], decision["calibratedWorkerCounts"])
        self.assertTrue(decision["candidateCriteria"]["3"]["perWorkerRetentionAtLeast0Point65"])
        self.assertFalse(decision["candidateCriteria"]["4"]["perWorkerRetentionAtLeast0Point65"])

    def test_scaling_decision_requires_ordered_counts_starting_at_one(self):
        with self.assertRaisesRegex(ValueError, "start with a one-worker run"):
            strategic_ai_runner.build_scaling_decision([{"workers": 2}], 8 * 1024**3)

    def test_scaling_decision_does_not_skip_a_failed_lower_count(self):
        def run(workers, retention):
            useful = 100 * workers * retention
            return {
                "workers": workers,
                "usefulMatchesPerHour": useful,
                "perWorkerUsefulMatchesPerHour": useful / workers,
                "p95JobElapsedSeconds": 100,
                "estimatedConcurrentPeakWorkingSetBytes": 1024,
                "validCount": 10,
                "jobCount": 10,
                "parityMismatchCount": 0,
                "meanJobElapsedSeconds": 50,
                "medianTicksPerSecond": 1000,
            }

        decision = strategic_ai_runner.build_scaling_decision(
            [run(1, 1.0), run(2, 0.8), run(3, 0.6), run(4, 0.8)],
            8 * 1024**3,
        )
        self.assertEqual(2, decision["selectedWorkers"])
        self.assertFalse(decision["candidateCriteria"]["3"]["perWorkerRetentionAtLeast0Point65"])
        self.assertTrue(decision["candidateCriteria"]["4"]["perWorkerRetentionAtLeast0Point65"])

    def test_scaling_decision_requires_marginal_gain_and_cross_run_equivalence(self):
        def run(workers, useful, mismatches=0):
            return {
                "workers": workers,
                "usefulMatchesPerHour": useful,
                "perWorkerUsefulMatchesPerHour": useful / workers,
                "p95JobElapsedSeconds": 100,
                "estimatedConcurrentPeakWorkingSetBytes": 1024,
                "validCount": 10,
                "jobCount": 10,
                "parityMismatchCount": 0,
                "crossRunMismatchCount": mismatches,
                "meanJobElapsedSeconds": 50,
                "medianTicksPerSecond": 1000,
            }

        insufficient_gain = strategic_ai_runner.build_scaling_decision(
            [run(1, 100), run(2, 170), run(4, 300), run(5, 315)],
            8 * 1024**3,
        )
        self.assertEqual(4, insufficient_gain["selectedWorkers"])
        self.assertFalse(
            insufficient_gain["candidateCriteria"]["5"]["aggregateGainOverPreviousAtLeast1Point10"]
        )

        mismatch = strategic_ai_runner.build_scaling_decision(
            [run(1, 100), run(2, 170), run(4, 300, mismatches=1), run(5, 400)],
            8 * 1024**3,
        )
        self.assertEqual(2, mismatch["selectedWorkers"])
        self.assertFalse(mismatch["candidateCriteria"]["4"]["noCrossRunMismatch"])

    def test_calibration_equivalence_compares_deterministic_job_evidence(self):
        def job(final_tick=600):
            return {
                "status": "VALID",
                "specificationSha256": "a" * 64,
                "expectedCandidateId": "squad-size-40-baseline",
                "expectedCandidateSha256": "b" * 64,
                "expectedSquadSize": 40,
                "match": {
                    "exitCode": 4,
                    "result": {
                        "status": "TIMED_OUT",
                        "executionMode": "UNCAPPED",
                        "finalWorldTick": final_tick,
                        "finalNetworkFrame": 200,
                        "finalSyncHash": 123,
                        "orderDigestSha256": "c" * 64,
                        "strategicDecisionDigestSha256": "d" * 64,
                        "players": [],
                    },
                },
                "verification": {
                    "exitCode": 0,
                    "result": {
                        "status": "VERIFIED",
                        "recordedFinalWorldTick": final_tick,
                        "observedFinalWorldTick": final_tick,
                        "finalNetworkFrame": 200,
                        "lastValidatedSyncFrame": 198,
                        "outOfSyncFrame": None,
                        "scheduledMatchTimeoutTick": 600,
                    },
                },
            }

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for workers, final_tick in ((1, 600), (2, 600), (4, 601)):
                path = root / f"workers-{workers}"
                path.mkdir()
                (path / "experiment-result.json").write_text(
                    json.dumps({"jobs": {"job-a": job(final_tick)}}),
                    encoding="utf-8",
                )

            report = strategic_ai_runner.calibration_equivalence_report(root, (1, 2, 4))
            self.assertEqual(1, report["mismatchCount"])
            self.assertEqual(0, report["byWorkers"]["2"]["mismatchCount"])
            self.assertEqual(1, report["byWorkers"]["4"]["mismatchCount"])
            self.assertIn("finalWorldTick", report["comparisons"][0]["differences"])

    def test_repeat_equivalence_rejects_deterministic_drift(self):
        def job(final_hash):
            return {
                "status": "VALID",
                "match": {
                    "exitCode": 0,
                    "result": {
                        "status": "COMPLETED",
                        "executionMode": "UNCAPPED",
                        "finalWorldTick": 1000,
                        "finalNetworkFrame": 334,
                        "finalSyncHash": final_hash,
                        "orderDigestSha256": "c" * 64,
                        "strategicDecisionDigestSha256": "d" * 64,
                        "players": [],
                    },
                },
                "verification": {
                    "exitCode": 0,
                    "result": {
                        "status": "VERIFIED",
                        "recordedFinalWorldTick": 1000,
                        "observedFinalWorldTick": 1000,
                        "finalNetworkFrame": 334,
                        "lastValidatedSyncFrame": 330,
                        "outOfSyncFrame": None,
                        "scheduledMatchTimeoutTick": 90000,
                    },
                },
            }

        report = strategic_ai_runner.repeat_equivalence_report(
            {
                "cell-a-r0": job(123),
                "cell-a-r1": job(123),
                "cell-b-r0": job(123),
                "cell-b-r1": job(456),
            }
        )
        self.assertEqual(2, report["pairCount"])
        self.assertEqual(1, report["mismatchCount"])
        self.assertEqual(["finalSyncHash"], report["comparisons"][1]["differences"])

    def test_calibration_writes_lower_count_decision_after_capacity_failure(self):
        def summary(workers, valid=10):
            return {
                "workers": workers,
                "status": "COMPLETED" if valid == 10 else "FAILED",
                "jobCount": 10,
                "validCount": valid,
                "wallClockElapsedSeconds": 100,
                "usefulMatchesPerHour": 100 * workers,
                "perWorkerUsefulMatchesPerHour": 100,
                "meanJobElapsedSeconds": 50,
                "p95JobElapsedSeconds": 100,
                "estimatedConcurrentPeakWorkingSetBytes": workers * 1024,
                "medianTicksPerSecond": 1000,
                "parityMismatchCount": 0,
            }

        with tempfile.TemporaryDirectory() as temporary, mock.patch.object(
            strategic_ai_runner, "run_manifest", side_effect=[0, 0, 1]
        ) as run_manifest, mock.patch.object(
            strategic_ai_runner, "summarize_run", side_effect=[summary(1), summary(2), summary(3, 9)]
        ), mock.patch.object(
            strategic_ai_runner, "available_memory_bytes", return_value=8 * 1024**3
        ), mock.patch.object(
            strategic_ai_runner,
            "calibration_equivalence_report",
            return_value={
                "baselineWorkers": 1,
                "workerCounts": [1, 2, 3],
                "byWorkers": {
                    "1": {"comparedJobCount": 10, "mismatchCount": 0},
                    "2": {"comparedJobCount": 10, "mismatchCount": 0},
                    "3": {"comparedJobCount": 10, "mismatchCount": 0},
                },
                "mismatchCount": 0,
                "comparisons": [],
            },
        ):
            root = Path(temporary)
            args = argparse.Namespace(
                skip_build=True,
                worker_counts=(1, 2, 3, 4),
                manifest=root / "manifest.json",
                output_root=root,
                content_dir=root / "content",
                engine_dir=root / "engine",
            )
            self.assertEqual(0, strategic_ai_runner.calibrate_manifest(args))
            self.assertEqual(3, run_manifest.call_count)
            decision = json.loads((root / "efficiency-decision.json").read_text(encoding="utf-8"))
            self.assertEqual([1, 2, 3], decision["calibratedWorkerCounts"])
            self.assertEqual(2, decision["selectedWorkers"])
            self.assertFalse(decision["candidateCriteria"]["3"]["allRunsValid"])

    def test_available_memory_probe_returns_a_positive_value(self):
        available = strategic_ai_runner.available_memory_bytes()
        self.assertIsNotNone(available)
        self.assertGreater(available, 0)

    def test_parse_macos_vm_stat_counts_reclaimable_pages(self):
        output = """Mach Virtual Memory Statistics: (page size of 16384 bytes)
Pages free:                               100.
Pages active:                             999.
Pages inactive:                           200.
Pages speculative:                         30.
Pages purgeable:                           40.
"""
        self.assertEqual(370 * 16384, strategic_ai_runner.parse_macos_vm_stat(output))

    def test_summarize_run_prefers_supervisor_peak_memory(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            (path / "experiment-result.json").write_text(
                json.dumps(
                    {
                        "status": "COMPLETED",
                        "wallClockElapsedSeconds": 10,
                        "parity": {"mismatchCount": 0},
                        "jobs": {
                            "job": {
                                "status": "VALID",
                                "match": {
                                    "elapsedSeconds": 4,
                                    "peakWorkingSetBytes": 1234,
                                    "result": {"peakWorkingSetBytes": 0, "ticksPerSecond": 100},
                                },
                                "verification": {"elapsedSeconds": 1},
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            summary = strategic_ai_runner.summarize_run(path, 1)
            self.assertEqual(1234, summary["estimatedConcurrentPeakWorkingSetBytes"])

    def test_worker_command_forces_windowed_non_vsync_renderer(self):
        command = strategic_ai_runner.openra_command(
            Path("OpenRA.exe"), Path("engine"), Path("support"), "Launch.Match=match.json"
        )
        self.assertIn("Graphics.Mode=Windowed", command)
        self.assertIn("Graphics.WindowedSize=1024,768", command)
        self.assertIn("Graphics.VSync=false", command)

    def test_registered_parity_matrix_materializes_twenty_machine_checked_jobs(self):
        matrix = Path(__file__).resolve().parents[2] / "docs" / "ai" / "examples" / "parity-matrix.json"
        with tempfile.TemporaryDirectory() as temporary:
            manifest_path = prepare_parity_experiment.prepare(matrix, Path(temporary))
            manifest = strategic_ai_runner.load_manifest(manifest_path)
            self.assertEqual(20, len(manifest.jobs))
            self.assertEqual(10, len({job.pair_id for job in manifest.jobs}))
            self.assertEqual(2, sum(job.expected_match_status == "COMPLETED" for job in manifest.jobs))
            self.assertEqual(18, sum(job.expected_match_status == "TIMED_OUT" for job in manifest.jobs))
            self.assertTrue((Path(temporary) / "parity-registration.json").is_file())

            # Identical regeneration is resumable, but a modified registered artifact is rejected.
            prepare_parity_experiment.prepare(matrix, Path(temporary))
            first_specification = manifest.jobs[0].specification
            first_specification.write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Refusing to overwrite"):
                prepare_parity_experiment.prepare(matrix, Path(temporary))


if __name__ == "__main__":
    unittest.main()
