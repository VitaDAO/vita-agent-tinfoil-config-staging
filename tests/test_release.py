"""Test Tinfoil's workflow contract and execute tag preparation against local Git."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from validate_config import ROOT, load_config

WORKFLOWS = ROOT / ".github/workflows"
REPOSITORY = "VitaDAO/vita-agent-tinfoil-config-staging"


class ReleaseContractTests(unittest.TestCase):
    def setUp(self):
        self.prepare = load_config((WORKFLOWS / "tinfoil-release.yml").read_text())
        self.publish = load_config((WORKFLOWS / "tinfoil-release-publish.yml").read_text())

    def test_dashboard_entrypoint_and_version_input(self):
        self.assertEqual(self.prepare["name"], "Tinfoil Release")
        self.assertEqual(set(self.prepare["on"]), {"workflow_dispatch"})
        inputs = self.prepare["on"]["workflow_dispatch"]["inputs"]
        self.assertEqual(set(inputs), {"version"})
        self.assertIs(inputs["version"]["required"], True)
        self.assertEqual(inputs["version"]["type"], "string")
        self.assertFalse((WORKFLOWS / "release.yml").exists())

    def test_prepare_checks_before_tagging_and_dispatches_tag(self):
        job = self.prepare["jobs"]["prepare-release"]
        self.assertEqual(job["if"], f"github.repository == '{REPOSITORY}' && github.ref == 'refs/heads/main'")
        self.assertEqual(job["permissions"], {"contents": "write", "actions": "write"})
        steps = job["steps"]
        tag_index = next(i for i, step in enumerate(steps) if step.get("name") == "Create and push the release tag")
        before = "\n".join(step.get("run", "") for step in steps[:tag_index])
        self.assertIn("scripts/validate_config.py", before)
        self.assertIn("unittest discover", before)
        dispatch = steps[tag_index + 1]
        self.assertIn('gh workflow run tinfoil-release-publish.yml --repo "$GH_REPO" --ref "$VERSION"', dispatch["run"])
        self.assertEqual(dispatch["env"]["GH_REPO"], "${{ github.repository }}")
        self.assertEqual(dispatch["env"]["VERSION"], "${{ inputs.version }}")
        self.assertNotEqual(self.prepare["concurrency"]["group"], self.publish["concurrency"]["group"])

    def test_workflows_cannot_deploy_or_modify_secrets(self):
        for workflow in (self.prepare, self.publish):
            self.assertEqual(set(workflow["on"]), {"workflow_dispatch"})
            scripts = "\n".join(step.get("run", "") for job in workflow["jobs"].values() for step in job["steps"])
            for forbidden in ("tinfoil container", "tinfoil deployment", "tinfoil secret", "--force"):
                self.assertNotIn(forbidden, scripts)


class ReleaseTagTests(unittest.TestCase):
    def setUp(self):
        workflow = load_config((WORKFLOWS / "tinfoil-release.yml").read_text())
        steps = workflow["jobs"]["prepare-release"]["steps"]
        self.script = next(step["run"] for step in steps if step.get("name") == "Create and push the release tag")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.remote = Path(self.temp.name) / "remote.git"
        self.checkout = Path(self.temp.name) / "checkout"
        self.git("clone", "--quiet", "--bare", str(ROOT), str(self.remote))
        self.git("clone", "--quiet", str(self.remote), str(self.checkout))
        self.sha = self.git("rev-parse", "HEAD", cwd=self.checkout).strip()

    def git(self, *args, cwd=None):
        return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout

    def run_tag_step(self, version):
        env = {**os.environ, "VERSION": version, "GITHUB_SHA": self.sha, "GIT_TERMINAL_PROMPT": "0"}
        return subprocess.run(["bash", "-e", "-c", self.script], cwd=self.checkout, env=env, capture_output=True, text=True)

    def test_creates_lightweight_tag_at_exact_commit(self):
        result = self.run_tag_step("v99.0.1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.git("rev-parse", "refs/tags/v99.0.1", cwd=self.remote).strip(), self.sha)
        self.assertEqual(self.git("cat-file", "-t", "refs/tags/v99.0.1", cwd=self.remote).strip(), "commit")

    def test_retry_refuses_to_overwrite_existing_tag(self):
        self.assertEqual(self.run_tag_step("v99.0.2").returncode, 0)
        result = self.run_tag_step("v99.0.2")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("already exists", result.stdout)
        self.assertEqual(self.git("rev-parse", "refs/tags/v99.0.2", cwd=self.remote).strip(), self.sha)

    def test_rejects_invalid_or_injected_versions_before_git_mutation(self):
        before = self.git("tag", "--list", cwd=self.remote)
        for version in ("", "main", "--force", "v1.2", "v1.2.3/extra", "v1.2.3; touch injected", "$(touch injected)", "v1.2.3\nother"):
            with self.subTest(version=version):
                self.assertNotEqual(self.run_tag_step(version).returncode, 0)
        self.assertEqual(self.git("tag", "--list", cwd=self.remote), before)
        self.assertFalse((self.checkout / "injected").exists())

    def test_remote_failure_does_not_create_a_local_tag(self):
        self.git("remote", "set-url", "origin", str(Path(self.temp.name) / "missing.git"), cwd=self.checkout)
        self.assertNotEqual(self.run_tag_step("v99.0.3").returncode, 0)
        self.assertEqual(self.git("tag", "--list", "v99.0.3", cwd=self.checkout), "")


if __name__ == "__main__":
    unittest.main()
