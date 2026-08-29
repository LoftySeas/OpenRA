import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "prepare_github_runner_calibration.py"
SPEC = importlib.util.spec_from_file_location("prepare_github_runner_calibration", MODULE_PATH)
prepare_github_runner_calibration = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prepare_github_runner_calibration)


class PrepareGithubRunnerCalibrationTest(unittest.TestCase):
    def make_source(self, root: Path, omitted: str | None = None) -> Path:
        specifications = root / "source" / "specifications"
        specifications.mkdir(parents=True)
        matches = []
        for job_id in prepare_github_runner_calibration.CALIBRATION_JOB_IDS:
            if job_id == omitted:
                continue
            specification = specifications / f"{job_id}.json"
            specification.write_text("{}\n", encoding="utf-8")
            matches.append({"id": job_id, "specificationPath": f"specifications/{job_id}.json"})
        matches.append({"id": "unselected-job", "specificationPath": "specifications/unselected.json"})
        (specifications / "unselected.json").write_text("{}\n", encoding="utf-8")
        manifest = root / "source" / "experiment-manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "schemaVersion": "1.0.0",
                    "matchTimeoutSeconds": 300,
                    "verificationTimeoutSeconds": 180,
                    "matches": matches,
                }
            ),
            encoding="utf-8",
        )
        return manifest

    def test_selects_exact_balanced_twenty_job_set_and_rewrites_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.make_source(root)
            output = root / "output" / "calibration-manifest.json"
            prepare_github_runner_calibration.select_calibration(source, output)

            value = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(
                list(prepare_github_runner_calibration.CALIBRATION_JOB_IDS),
                [match["id"] for match in value["matches"]],
            )
            self.assertEqual(20, len(value["matches"]))
            for match in value["matches"]:
                self.assertTrue((output.parent / match["specificationPath"]).resolve().is_file())

            registration = json.loads(
                (output.parent / "github-calibration-registration.json").read_text(encoding="utf-8")
            )
            self.assertEqual(20, registration["jobCount"])
            self.assertEqual(
                prepare_github_runner_calibration.file_sha256(output),
                registration["calibrationManifestSha256"],
            )

    def test_rejects_missing_registered_job(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            missing = prepare_github_runner_calibration.CALIBRATION_JOB_IDS[-1]
            source = self.make_source(root, omitted=missing)
            with self.assertRaisesRegex(ValueError, "lacks calibration jobs"):
                prepare_github_runner_calibration.select_calibration(
                    source,
                    root / "output" / "calibration-manifest.json",
                )


if __name__ == "__main__":
    unittest.main()
