import importlib.util
import contextlib
import io
import json
import shutil
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock


TOOLS_ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


aggregate = load_module(
    "aggregate_github_distributed_smoke",
    TOOLS_ROOT / "aggregate_github_distributed_smoke.py",
)
prepare = load_module(
    "prepare_github_distributed_smoke_for_aggregate_test",
    TOOLS_ROOT / "prepare_github_distributed_smoke.py",
)


class AggregateGithubDistributedSmokeTest(unittest.TestCase):
    execution_sha = "1" * 40
    design_base_sha = "2" * 40
    repository = "example/OpenRA"
    run_id = 123456
    run_attempt = 2
    sample_base_ms = 1_800_000_000_000

    def write_json(self, path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def make_source_manifest(self, root: Path) -> Path:
        source_root = root / "source"
        specifications = source_root / "specifications"
        candidates = source_root / "candidates"
        specifications.mkdir(parents=True)
        candidates.mkdir(parents=True)
        candidate = candidates / "candidate-c40.json"
        self.write_json(candidate, {"candidateId": "candidate-c40", "squadSize": 40})
        candidate_sha = aggregate.file_sha256(candidate)

        source_ids = []
        for shard in range(prepare.SHARD_COUNT):
            for selection in prepare.selections_for_shard(shard):
                if selection.source_job_id not in source_ids:
                    source_ids.append(selection.source_job_id)
        matches = []
        for index, source_id in enumerate(source_ids):
            specification = specifications / f"{source_id}.json"
            self.write_json(
                specification,
                {
                    "schemaVersion": "1.2.0",
                    "modId": "ra",
                    "mapUid": f"map-{index}",
                    "randomSeed": index + 1,
                    "options": {"gamespeed": "fastest"},
                    "players": [],
                    "maxWorldTicks": 90000,
                    "recordReplay": True,
                    "executionMode": "UNCAPPED",
                    "candidatePath": "../candidates/candidate-c40.json",
                },
            )
            matches.append(
                {
                    "id": source_id,
                    "specificationPath": f"specifications/{source_id}.json",
                    "expectedCandidateId": "candidate-c40",
                    "expectedCandidateSha256": candidate_sha,
                    "expectedSquadSize": 40,
                }
            )
        manifest = source_root / "experiment-manifest.json"
        self.write_json(
            manifest,
            {
                "schemaVersion": "1.0.0",
                "matchTimeoutSeconds": 300,
                "verificationTimeoutSeconds": 180,
                "matches": matches,
            },
        )
        return manifest

    def deterministic_result(self, job_id: str, manifest_job: dict, specification_sha: str) -> dict:
        identity = "sentinel" if "sentinel" in job_id else job_id
        numeric = int(aggregate.hashlib.sha256(identity.encode()).hexdigest()[:8], 16)
        if numeric >= 2**31:
            numeric -= 2**32
        replay_sha = aggregate.hashlib.sha256((identity + "-replay").encode()).hexdigest()
        synchronized_timeout = job_id == prepare.UNIQUE_BY_SHARD[2][1].job_id
        match_status = "TIMED_OUT" if synchronized_timeout else "COMPLETED"
        match_exit_code = 4 if synchronized_timeout else 0
        final_world_tick = aggregate.MAX_WORLD_TICKS if synchronized_timeout else 25000
        player_outcomes = ("UNDEFINED", "UNDEFINED") if synchronized_timeout else ("WON", "LOST")
        return {
            "id": job_id,
            "attempt": 1,
            "status": "VALID",
            "specificationSha256": specification_sha,
            "expectedCandidateId": manifest_job["expectedCandidateId"],
            "expectedCandidateSha256": manifest_job["expectedCandidateSha256"],
            "expectedSquadSize": manifest_job["expectedSquadSize"],
            "controllerExecutionId": None,
            "controllerScriptSha256": None,
            "match": {
                "exitCode": match_exit_code,
                "timedOut": False,
                "elapsedSeconds": 1.25,
                "result": {
                    "status": match_status,
                    "executionMode": "UNCAPPED",
                    "finalWorldTick": final_world_tick,
                    "finalNetworkFrame": 1500,
                    "finalSyncHash": numeric,
                    "orderDigestSha256": aggregate.hashlib.sha256((identity + "-orders").encode()).hexdigest(),
                    "strategicDecisionDigestSha256": aggregate.hashlib.sha256((identity + "-decisions").encode()).hexdigest(),
                    "players": [
                        {"botType": "strategic", "outcome": player_outcomes[0], "slot": "Multi0"},
                        {"botType": "normal", "outcome": player_outcomes[1], "slot": "Multi1"},
                    ],
                    "candidateId": manifest_job["expectedCandidateId"],
                    "candidateSha256": manifest_job["expectedCandidateSha256"],
                    "squadSize": manifest_job["expectedSquadSize"],
                    "specificationSha256": specification_sha,
                    "modId": "ra",
                    "mapUid": None,
                    "randomSeed": None,
                    "replaySha256": replay_sha,
                    "replaySizeBytes": 123456,
                },
            },
            "verification": {
                "exitCode": 0,
                "timedOut": False,
                "elapsedSeconds": 0.75,
                "result": {
                    "status": "VERIFIED",
                    "recordedFinalWorldTick": final_world_tick,
                    "observedFinalWorldTick": final_world_tick,
                    "finalNetworkFrame": 1500,
                    "lastValidatedSyncFrame": 1498,
                    "outOfSyncFrame": None,
                    "scheduledMatchTimeoutTick": 30000,
                    "verificationTimestepMs": 1,
                    "replaySha256": replay_sha,
                    "replaySizeBytes": 123456,
                },
            },
        }

    def make_shard(
        self,
        root: Path,
        source_manifest: Path,
        shard: int,
        mutate=None,
        mutate_after=None,
        sample_offset_ms: int | None = None,
        profile=aggregate.FOUR_SHARD_PROFILE,
    ) -> Path:
        stage = root / "stage" / f"shard-{shard}"
        evidence_root = stage / f"m3-distributed-shard-{shard}"
        registration_root = stage / f"m3-distributed-registration-{shard}"
        shutil.copytree(source_manifest.parent, registration_root)
        local_source_manifest = registration_root / source_manifest.name
        prepare.prepare(
            local_source_manifest,
            registration_root,
            shard,
            TOOLS_ROOT / "strategic_ai_runner.py",
            self.execution_sha,
            self.design_base_sha,
            profile.cli_name if profile.include_profile_field else None,
        )
        registration = json.loads(
            (registration_root / "github-distributed-smoke-registration.json").read_text(encoding="utf-8")
        )
        manifest = json.loads(
            (registration_root / "github-distributed-smoke-manifest.json").read_text(encoding="utf-8")
        )
        registration_jobs = {job["id"]: job for job in registration["jobs"]}
        execution_id = f"controller-execution-{shard}"
        jobs = {}
        for manifest_job in manifest["matches"]:
            job_id = manifest_job["id"]
            job = self.deterministic_result(
                job_id,
                manifest_job,
                registration_jobs[job_id]["specificationSha256"],
            )
            specification = json.loads(
                (registration_root / manifest_job["specificationPath"]).read_text(encoding="utf-8")
            )
            job["match"]["result"]["mapUid"] = specification["mapUid"]
            job["match"]["result"]["randomSeed"] = specification["randomSeed"]
            job["controllerExecutionId"] = execution_id
            job["controllerScriptSha256"] = registration["controllerScriptSha256"]
            jobs[job_id] = job
            replay_log = (
                evidence_root
                / "run"
                / "workers"
                / job_id
                / "attempts"
                / "001"
                / "verify"
                / "Logs"
                / "strategic-decisions.log"
            )
            replay_log.parent.mkdir(parents=True, exist_ok=True)
            replay_log.write_bytes(b"")
        result = {
            "schemaVersion": "1.0.0",
            "manifestPath": str(registration_root / "github-distributed-smoke-manifest.json"),
            "manifestSha256": registration["manifestSha256"],
            "controllerExecutions": [
                {
                    "executionId": execution_id,
                    "controllerScriptSha256": registration["controllerScriptSha256"],
                }
            ],
            "maxWorkers": profile.max_workers,
            "status": "COMPLETED",
            "controllerProvenance": {
                "expectedJobCount": profile.jobs_per_shard,
                "recordedJobCount": profile.jobs_per_shard,
                "attributedJobCount": profile.jobs_per_shard,
                "legacyCoverageGap": False,
                "unattributedJobIds": [],
                "invalidAttributionJobIds": [],
                "complete": True,
            },
            "parity": {"pairCount": 0, "mismatchCount": 0, "comparisons": []},
            "repeatEquivalence": {"pairCount": 0, "mismatchCount": 0, "comparisons": []},
            "jobs": jobs,
        }
        if mutate is not None:
            mutate(shard, registration, manifest, result, evidence_root)
            self.write_json(
                registration_root / "github-distributed-smoke-registration.json",
                registration,
            )
            self.write_json(
                registration_root / "github-distributed-smoke-manifest.json",
                manifest,
            )
        self.write_json(evidence_root / "run" / "experiment-result.json", result)
        workers = profile.max_workers
        (evidence_root / f"controller-exit-code-workers-{workers}.txt").write_text("0\n", encoding="utf-8")
        (evidence_root / f"workers-{workers}-time.txt").write_text(
            "Elapsed (wall clock) time: 0:03.00\n", encoding="utf-8"
        )
        events = "oom 0\noom_kill 0\n"
        (evidence_root / f"memory-events-before-workers-{workers}.txt").write_text(
            events, encoding="utf-8"
        )
        (evidence_root / f"memory-events-after-workers-{workers}.txt").write_text(
            events, encoding="utf-8"
        )
        self.write_json(
            evidence_root / "runner-metadata.json",
            {
                "GITHUB_REPOSITORY": self.repository,
                "GITHUB_RUN_ID": str(self.run_id),
                "GITHUB_RUN_ATTEMPT": str(self.run_attempt),
                "GITHUB_SHA": self.execution_sha,
                "RUNNER_NAME": f"GitHub Actions {shard + 1}",
                "SHARD_INDEX": str(shard),
                "gitHeadSha": self.execution_sha,
                "maxWorkers": workers,
            },
        )

        base = self.sample_base_ms + (shard * 20 if sample_offset_ms is None else sample_offset_ms)
        csv_path = evidence_root / f"resource-samples-workers-{workers}.csv"
        csv_path.write_text(
            "unix_ms,mem_available_bytes,swap_used_bytes,load_1m,openra_processes,openra_rss_kib,disk_available_bytes\n"
            + "\n".join(
                f"{base + index * 200},{8 * 1024**3},0,1.0,{processes},{2 * 1024**2},{12 * 1024**3}"
                for index, processes in enumerate((0, workers, workers, workers, 0))
            )
            + "\n",
            encoding="utf-8",
        )

        if mutate_after is not None:
            mutate_after(shard, registration_root, evidence_root)

        artifact_dir = root / "downloads" / f"artifact-{shard}"
        artifact_dir.mkdir(parents=True)
        archive = artifact_dir / f"shard-{shard}.tar.gz"
        with tarfile.open(archive, "w:gz") as stream:
            stream.add(evidence_root, arcname=evidence_root.name)
            stream.add(registration_root, arcname=registration_root.name)
        return archive

    def make_actions_documents(
        self,
        root: Path,
        mutate=None,
        profile=aggregate.FOUR_SHARD_PROFILE,
    ) -> tuple[Path, Path]:
        run_document = {
            "id": self.run_id,
            "run_attempt": self.run_attempt,
            "head_sha": self.execution_sha,
            "repository": {"full_name": self.repository},
            "event": "workflow_dispatch",
            "created_at": "2027-01-15T07:59:50Z",
            "status": "in_progress",
            "conclusion": None,
        }
        jobs = []
        for shard in range(profile.shard_count):
            jobs.append(
                {
                    "id": 9000 + shard,
                    "run_id": self.run_id,
                    "run_attempt": self.run_attempt,
                    "head_sha": self.execution_sha,
                    "name": f"Distributed smoke shard {shard}",
                    "runner_name": f"GitHub Actions {shard + 1}",
                    "status": "completed",
                    "conclusion": "success",
                    "started_at": "2027-01-15T08:00:00Z",
                    "completed_at": "2027-01-15T08:05:00Z",
                }
            )
        jobs_document = {
            "total_count": profile.shard_count + 1,
            "jobs": jobs + [{"id": 9999, "name": "Aggregate"}],
        }
        if mutate is not None:
            mutate(run_document, jobs_document)
        run_path = root / "run.json"
        jobs_path = root / "jobs.json"
        self.write_json(run_path, run_document)
        self.write_json(jobs_path, jobs_document)
        return jobs_path, run_path

    def make_bundle(
        self,
        root: Path,
        mutate_shard=None,
        mutate_after=None,
        sample_offsets=None,
        mutate_actions=None,
        profile=aggregate.FOUR_SHARD_PROFILE,
    ):
        source = self.make_source_manifest(root)
        for shard in range(profile.shard_count):
            self.make_shard(
                root,
                source,
                shard,
                mutate=mutate_shard,
                mutate_after=mutate_after,
                sample_offset_ms=None if sample_offsets is None else sample_offsets[shard],
                profile=profile,
            )
        jobs_path, run_path = self.make_actions_documents(
            root, mutate=mutate_actions, profile=profile
        )
        return jobs_path, run_path

    def run_aggregate(
        self,
        root: Path,
        jobs_path: Path,
        run_path: Path,
        profile=aggregate.FOUR_SHARD_PROFILE,
    ) -> tuple[int, dict]:
        output = root / "decision" / "distributed-smoke-result.json"
        arguments = [
            "--artifacts-root", str(root / "downloads"),
            "--output", str(output),
            "--run-id", str(self.run_id),
            "--run-attempt", str(self.run_attempt),
            "--repository", self.repository,
            "--expected-execution-sha", self.execution_sha,
            "--jobs-json", str(jobs_path),
            "--run-json", str(run_path),
        ]
        if profile.include_profile_field:
            arguments.extend(("--profile", profile.cli_name))
        with contextlib.redirect_stdout(io.StringIO()):
            exit_code = aggregate.main(arguments)
        return exit_code, json.loads(output.read_text(encoding="utf-8"))

    def test_valid_four_shard_evidence_proves_sixteen_simultaneous_processes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            jobs_path, run_path = self.make_bundle(root)
            exit_code, result = self.run_aggregate(root, jobs_path, run_path)

            self.assertEqual(0, exit_code)
            self.assertTrue(result["passed"])
            self.assertEqual(0, result["failureCount"])
            self.assertEqual(16, result["compositeJobCount"])
            self.assertEqual(16, result["validCompositeJobCount"])
            self.assertEqual(16, result["replayStrategicLogCount"])
            self.assertEqual(0, result["replayStrategicLogBytes"])
            self.assertEqual(6, result["sentinelEvidence"]["comparedValidPairCount"])
            self.assertEqual(0, result["sentinelEvidence"]["driftCount"])
            self.assertTrue(result["fourWayProcessOverlap"]["proven"])
            self.assertEqual(16, result["fourWayProcessOverlap"]["simultaneousOpenRaProcesses"])
            self.assertIn("requiredProcessIntervals", result["shards"][0]["resource"])
            self.assertIn("fourProcessIntervals", result["shards"][0]["resource"])
            self.assertEqual(4, result["actionsEvidence"]["distinctJobIdCount"])
            self.assertEqual(4, result["actionsEvidence"]["distinctRunnerNameCount"])
            self.assertGreater(result["actionsEvidence"]["jobOverlap"]["durationMs"], 0)

    def test_valid_twenty_shard_canary_proves_twenty_one_worker_processes(self):
        profile = aggregate.TWENTY_SHARD_PROFILE
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            jobs_path, run_path = self.make_bundle(root, profile=profile)
            exit_code, result = self.run_aggregate(
                root, jobs_path, run_path, profile=profile
            )

            self.assertEqual(0, exit_code)
            self.assertTrue(result["passed"])
            self.assertEqual(profile.cli_name, result["profile"])
            self.assertEqual(profile.purpose, result["purpose"])
            self.assertIn("does not prove 20x4 or 80", result["scopeStatement"])
            self.assertEqual(20, result["compositeJobCount"])
            self.assertEqual(20, result["validCompositeJobCount"])
            self.assertEqual(20, result["replayStrategicLogCount"])
            self.assertEqual(0, result["replayStrategicLogBytes"])
            self.assertEqual(19, result["sentinelEvidence"]["comparedValidPairCount"])
            self.assertEqual(0, result["sentinelEvidence"]["driftCount"])
            self.assertTrue(result["twentyWayProcessOverlap"]["proven"])
            self.assertEqual(
                20,
                result["twentyWayProcessOverlap"]["simultaneousOpenRaProcesses"],
            )
            self.assertIn("requiredProcessIntervals", result["shards"][0]["resource"])
            self.assertNotIn("fourProcessIntervals", result["shards"][0]["resource"])
            self.assertEqual(20, result["actionsEvidence"]["distinctJobIdCount"])
            self.assertEqual(
                20, result["actionsEvidence"]["distinctRunnerNameCount"]
            )
            self.assertGreater(result["actionsEvidence"]["jobOverlap"]["durationMs"], 0)

    def test_twenty_shard_canary_detects_one_valid_sentinel_drift(self):
        profile = aggregate.TWENTY_SHARD_PROFILE
        sentinel = prepare.TWENTY_SHARD_PROFILE.sentinels[0].job_id

        def mutate_after(shard, registration_root, evidence_root):
            if shard != 19:
                return
            result_path = evidence_root / "run" / "experiment-result.json"
            result = json.loads(result_path.read_text(encoding="utf-8"))
            current = result["jobs"][sentinel]["match"]["result"]["finalSyncHash"]
            result["jobs"][sentinel]["match"]["result"]["finalSyncHash"] = current ^ 1
            self.write_json(result_path, result)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            jobs_path, run_path = self.make_bundle(
                root,
                mutate_after=mutate_after,
                profile=profile,
            )
            exit_code, result = self.run_aggregate(
                root, jobs_path, run_path, profile=profile
            )

            self.assertEqual(1, exit_code)
            self.assertFalse(result["passed"])
            self.assertEqual(20, result["validCompositeJobCount"])
            self.assertEqual(19, result["sentinelEvidence"]["comparedValidPairCount"])
            self.assertEqual(1, result["sentinelEvidence"]["driftCount"])
            self.assertEqual(
                ["finalSyncHash"],
                result["sentinelEvidence"]["drift"][0]["differences"],
            )

    def test_controller_valid_jobs_with_empty_runtime_results_do_not_pass(self):
        def mutate(shard, registration, manifest, result, evidence_root):
            for job in result["jobs"].values():
                job["match"]["result"] = {}
                job["verification"]["result"] = {}

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            jobs_path, run_path = self.make_bundle(root, mutate_shard=mutate)
            exit_code, result = self.run_aggregate(root, jobs_path, run_path)

            self.assertEqual(1, exit_code)
            self.assertFalse(result["passed"])
            self.assertEqual(0, result["validCompositeJobCount"])
            self.assertEqual(0, result["sentinelEvidence"]["driftCount"])
            self.assertEqual(6, result["sentinelEvidence"]["notComparableCount"])
            self.assertIn(
                "job_runtime_evidence_invalid",
                {item["code"] for item in result["failures"]},
            )

    def test_last_validated_sync_frame_is_required_but_not_a_cross_runner_digest(self):
        sentinel = prepare.SENTINELS[0].job_id

        def mutate_after(shard, registration_root, evidence_root):
            if shard == 2:
                result_path = evidence_root / "run" / "experiment-result.json"
                result = json.loads(result_path.read_text(encoding="utf-8"))
                result["jobs"][sentinel]["verification"]["result"][
                    "lastValidatedSyncFrame"
                ] -= 1
                self.write_json(result_path, result)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            jobs_path, run_path = self.make_bundle(root, mutate_after=mutate_after)
            exit_code, result = self.run_aggregate(root, jobs_path, run_path)

            self.assertEqual(0, exit_code)
            self.assertTrue(result["passed"])
            self.assertEqual(6, result["sentinelEvidence"]["comparedValidPairCount"])
            self.assertEqual(0, result["sentinelEvidence"]["driftCount"])

    def test_source_manifest_and_source_job_sha_tampering_do_not_pass(self):
        def mutate(shard, registration, manifest, result, evidence_root):
            if shard == 1:
                registration["jobs"][0]["sourceJobSha256"] = "e" * 64

        def mutate_after(shard, registration_root, evidence_root):
            if shard == 0:
                source_manifest = registration_root / "experiment-manifest.json"
                source_manifest.write_bytes(source_manifest.read_bytes() + b"\n")

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            jobs_path, run_path = self.make_bundle(
                root,
                mutate_shard=mutate,
                mutate_after=mutate_after,
            )
            exit_code, result = self.run_aggregate(root, jobs_path, run_path)

            self.assertEqual(1, exit_code)
            codes = {item["code"] for item in result["failures"]}
            self.assertIn("source_manifest_sha_mismatch", codes)
            self.assertIn("source_job_sha_mismatch", codes)

    def test_jointly_forged_controller_sha_is_not_bound_by_self_attestation(self):
        fake_sha = "d" * 64

        def mutate(shard, registration, manifest, result, evidence_root):
            registration["controllerScriptSha256"] = fake_sha
            for execution in result["controllerExecutions"]:
                execution["controllerScriptSha256"] = fake_sha
            for job in result["jobs"].values():
                job["controllerScriptSha256"] = fake_sha

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            jobs_path, run_path = self.make_bundle(root, mutate_shard=mutate)
            exit_code, result = self.run_aggregate(root, jobs_path, run_path)

            self.assertEqual(1, exit_code)
            self.assertIn(
                "controller_checkout_sha_mismatch",
                {item["code"] for item in result["failures"]},
            )

    def test_runner_metadata_is_bound_to_shard_and_worker_count(self):
        def mutate_after(shard, registration_root, evidence_root):
            if shard != 2:
                return
            metadata_path = evidence_root / "runner-metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["SHARD_INDEX"] = "1"
            metadata["maxWorkers"] = 3
            self.write_json(metadata_path, metadata)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            jobs_path, run_path = self.make_bundle(root, mutate_after=mutate_after)
            exit_code, result = self.run_aggregate(root, jobs_path, run_path)

            self.assertEqual(1, exit_code)
            metadata_failures = [
                item for item in result["failures"]
                if item["code"] == "runner_metadata_mismatch"
            ]
            self.assertEqual(
                {"SHARD_INDEX", "maxWorkers"},
                {item["context"]["field"] for item in metadata_failures},
            )

    def test_archive_review_rejects_escape_links_devices_content_and_payloads(self):
        cases = (
            ("../escape", tarfile.REGTYPE),
            ("/absolute", tarfile.REGTYPE),
            ("m3-distributed-shard-0/link", tarfile.SYMTYPE),
            ("m3-distributed-shard-0/device", tarfile.CHRTYPE),
            ("m3-distributed-shard-0/Content/file", tarfile.REGTYPE),
            ("m3-distributed-shard-0/file.zip", tarfile.REGTYPE),
            ("m3-distributed-shard-0/file.mix", tarfile.REGTYPE),
            ("m3-distributed-shard-0/file.aud", tarfile.REGTYPE),
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for index, (unsafe_name, member_type) in enumerate(cases):
                archive = root / f"unsafe-{index}.tar.gz"
                with tarfile.open(archive, "w:gz") as stream:
                    for dirname in ("m3-distributed-shard-0", "m3-distributed-registration-0"):
                        directory = tarfile.TarInfo(dirname)
                        directory.type = tarfile.DIRTYPE
                        stream.addfile(directory)
                    member = tarfile.TarInfo(unsafe_name)
                    member.type = member_type
                    if member_type == tarfile.REGTYPE:
                        member.size = 1
                        stream.addfile(member, io.BytesIO(b"x"))
                    else:
                        member.linkname = "target"
                        stream.addfile(member)
                with self.subTest(unsafe_name=unsafe_name):
                    with self.assertRaises(aggregate.ArchiveSafetyError):
                        aggregate.safe_extract_tar(archive, root / f"extract-{index}", 0)

    def test_archive_member_and_size_limits_are_enforced_before_extraction(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "limits.tar.gz"
            with tarfile.open(archive, "w:gz") as stream:
                for dirname in ("m3-distributed-shard-0", "m3-distributed-registration-0"):
                    member = tarfile.TarInfo(dirname)
                    member.type = tarfile.DIRTYPE
                    stream.addfile(member)
                member = tarfile.TarInfo("m3-distributed-shard-0/evidence.bin")
                member.size = 2
                stream.addfile(member, io.BytesIO(b"xx"))
            with mock.patch.object(aggregate, "MAX_ARCHIVE_MEMBERS", 2):
                with self.assertRaisesRegex(aggregate.ArchiveSafetyError, "members"):
                    aggregate.safe_extract_tar(archive, root / "member-limit", 0)
            with mock.patch.object(aggregate, "MAX_ARCHIVE_BYTES", 1):
                with self.assertRaisesRegex(aggregate.ArchiveSafetyError, "expands beyond"):
                    aggregate.safe_extract_tar(archive, root / "byte-limit", 0)

    def test_unsafe_tar_still_writes_failure_artifact_and_does_not_escape(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            jobs_path, run_path = self.make_bundle(root)
            archive = root / "downloads" / "artifact-2" / "shard-2.tar.gz"
            archive.unlink()
            with tarfile.open(archive, "w:gz") as stream:
                for dirname in ("m3-distributed-shard-2", "m3-distributed-registration-2"):
                    member = tarfile.TarInfo(dirname)
                    member.type = tarfile.DIRTYPE
                    stream.addfile(member)
                member = tarfile.TarInfo("../escaped.txt")
                member.size = 7
                stream.addfile(member, io.BytesIO(b"escaped"))

            exit_code, result = self.run_aggregate(root, jobs_path, run_path)
            self.assertEqual(1, exit_code)
            self.assertFalse(result["passed"])
            self.assertIn("unsafe_or_invalid_archive", {item["code"] for item in result["failures"]})
            self.assertFalse((root / "escaped.txt").exists())

    def test_sentinel_missing_invalid_and_valid_drift_are_reported_separately(self):
        sentinel_normal = prepare.SENTINELS[0].job_id
        sentinel_rush = prepare.SENTINELS[1].job_id

        def mutate(shard, registration, manifest, result, evidence_root):
            if shard == 1:
                del result["jobs"][sentinel_normal]
            elif shard == 2:
                current = result["jobs"][sentinel_rush]["match"]["result"]["finalSyncHash"]
                result["jobs"][sentinel_rush]["match"]["result"]["finalSyncHash"] = current ^ 1
            elif shard == 3:
                result["jobs"][sentinel_normal]["status"] = "FAILED"
                result["jobs"][sentinel_normal]["match"]["result"]["finalSyncHash"] = "ignored-drift"

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            jobs_path, run_path = self.make_bundle(root, mutate_shard=mutate)
            exit_code, result = self.run_aggregate(root, jobs_path, run_path)

            self.assertEqual(1, exit_code)
            evidence = result["sentinelEvidence"]
            self.assertEqual(1, evidence["missingCount"])
            self.assertEqual(1, evidence["notComparableCount"])
            self.assertEqual(1, evidence["driftCount"])
            self.assertEqual(["finalSyncHash"], evidence["drift"][0]["differences"])
            ignored = [
                item for item in evidence["comparisons"]
                if item["candidateShard"] == 3 and item["jobId"] == sentinel_normal
            ][0]
            self.assertFalse(ignored["compared"])
            self.assertEqual([], ignored["differences"])

    def test_independent_resource_peaks_without_four_way_interval_do_not_pass(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            jobs_path, run_path = self.make_bundle(
                root,
                sample_offsets=(0, 20, 40, 5000),
            )
            exit_code, result = self.run_aggregate(root, jobs_path, run_path)
            self.assertEqual(1, exit_code)
            self.assertFalse(result["fourWayProcessOverlap"]["proven"])
            self.assertIn("four_way_process_overlap_missing", {item["code"] for item in result["failures"]})

    def test_actions_job_overlap_and_runner_identity_are_required(self):
        def mutate_actions(run_document, jobs_document):
            jobs_document["jobs"][3]["started_at"] = "2027-01-15T08:06:00Z"
            jobs_document["jobs"][3]["completed_at"] = "2027-01-15T08:07:00Z"
            jobs_document["jobs"][3]["runner_name"] = jobs_document["jobs"][0]["runner_name"]

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            jobs_path, run_path = self.make_bundle(root, mutate_actions=mutate_actions)
            exit_code, result = self.run_aggregate(root, jobs_path, run_path)
            codes = {item["code"] for item in result["failures"]}
            self.assertEqual(1, exit_code)
            self.assertIn("actions_runner_names_not_distinct", codes)
            self.assertIn("actions_jobs_do_not_overlap", codes)


if __name__ == "__main__":
    unittest.main()
