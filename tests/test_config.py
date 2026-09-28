import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from validate_config import InvalidConfig, ROOT, load_config, validate


class StagingConfigTests(unittest.TestCase):
    def setUp(self):
        self.config = load_config((ROOT / "tinfoil-config.yml").read_text())
        self.container = self.config["containers"][0]

    def set_env(self, name, value):
        for item in self.container["env"]:
            if name in item:
                item[name] = value
                return
        self.container["env"].append({name: value})

    def test_actual_manifest(self):
        validate(self.config)

    def test_wrong_environment_values(self):
        changes = {
            "SUPABASE_URL": "https://wrongproject.supabase.co",
            "SUPABASE_JWKS_URL": "https://wrongproject.supabase.co/auth/v1/.well-known/jwks.json",
            "SUPABASE_JWT_VERIFY_MODE": "parse",
            "VITA_AGENT_ENCLAVE_URL": "https://vita-agent-prod.vitality-now.containers.tinfoil.dev/",
            "VITA_AGENT_CORS_ORIGINS": "https://app.vitadao.com",
            "SENTRY_ENVIRONMENT": "production",
            "VITA_AGENT_REQUIRE_SEALED_DEK": "0",
            "VITA_AGENT_ACCEPT_LEGACY_DEK_HEADERS": "1",
            "OPENAI_AGENTS_DISABLE_TRACING": "0",
            "VITA_AGENT_ENABLE_LEGACY_ROUTES": "1",
            "SENTRY_RELEASE": "vita-agent@wrong",
            "VITA_AGENT_DEPLOYMENT_ID": "vita-agent-prod-3683399",
            "VITA_CONTEXT_V2_CANARY_PERCENT": "0",
            "VITA_SESSION_V2": "0",
            "ALLOW_PLAINTEXT_DEK": "true",
            "VITA_AGENT_DEBUG_ALLOW_SERVICE_ROLE_INTERNAL_CLIENT": "1",
            "VITA_STAGING_SYNTHETIC_FIXTURES": "1",
            "SUPABASE_INTERNAL_AUTH_PASSWORD": "not-a-real-password",
            "SUPABASE_ANON_KEY": "not-a-real-key",
            "BACKUP_DATABASE_URL": "https://wrongproject.supabase.co",
            "CUSTOM_API_KEY": "not-a-real-key",
        }
        baseline = copy.deepcopy(self.config)
        for name, value in changes.items():
            with self.subTest(name=name):
                self.config = copy.deepcopy(baseline)
                self.container = self.config["containers"][0]
                self.set_env(name, value)
                with self.assertRaises(InvalidConfig):
                    validate(self.config)

    def test_duplicate_environment_name(self):
        self.container["env"].append({"SUPABASE_URL": "https://wrongproject.supabase.co"})
        with self.assertRaises(InvalidConfig):
            validate(self.config)

    def test_duplicate_yaml_key(self):
        with self.assertRaises(InvalidConfig):
            load_config("name: first\nname: second\n")

    def test_unknown_yaml_tag(self):
        with self.assertRaises(InvalidConfig):
            load_config("!!python/object/apply:os.system ['echo forbidden']")

    def test_production_and_wallet_secret_bindings(self):
        for secret in ("SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_INTERNAL_AUTH_EMAIL", "SUPABASE_INTERNAL_AUTH_PASSWORD", "SUPABASE_SERVICE_ROLE_KEY", "X402_WALLET_PRIVATE_KEY"):
            with self.subTest(secret=secret):
                self.container["secrets"].append(secret)
                with self.assertRaises(InvalidConfig):
                    validate(self.config)
                self.container["secrets"].pop()

    def test_missing_staging_secret(self):
        self.container["secrets"].remove("STAGING_SUPABASE_ANON_KEY")
        with self.assertRaises(InvalidConfig):
            validate(self.config)

    def test_mutable_image(self):
        self.container["image"] = "ghcr.io/vitadao/vita-agent:latest"
        with self.assertRaises(InvalidConfig):
            validate(self.config)

    def test_version_drift(self):
        self.set_env("VITA_AGENT_VERSION", "vita-agent@old")
        with self.assertRaises(InvalidConfig):
            validate(self.config)

    def test_wildcard_route(self):
        self.config["shim"]["paths"].append("/*")
        with self.assertRaises(InvalidConfig):
            validate(self.config)

    def test_extra_workload(self):
        self.config["containers"].append(copy.deepcopy(self.container))
        with self.assertRaises(InvalidConfig):
            validate(self.config)

    def test_malformed_env(self):
        self.container["env"].append({"first": "1", "second": "2"})
        with self.assertRaises(InvalidConfig):
            validate(self.config)

    def test_release_is_manual_and_repository_scoped(self):
        workflow = load_config((ROOT / ".github/workflows/tinfoil-release-publish.yml").read_text())
        self.assertEqual(set(workflow["on"]), {"workflow_dispatch"})
        job = workflow["jobs"]["attest"]
        self.assertEqual(job["if"], "github.repository == 'VitaDAO/vita-agent-tinfoil-config-staging' && github.ref_type == 'tag'")
        measure = [s for s in job["steps"] if s.get("uses", "").startswith("tinfoilsh/")]
        self.assertEqual(len(measure), 1)
        self.assertEqual(measure[0]["with"]["mark-as-latest"], "false")
        script = "\n".join(s.get("run", "") for s in job["steps"])
        self.assertIn("--prerelease --latest=false", script)
        self.assertNotIn("tinfoil container", script)
        self.assertNotIn("tinfoil deployment", script)

    def test_checks_have_read_only_permissions(self):
        workflow = load_config((ROOT / ".github/workflows/check.yml").read_text())
        self.assertEqual(workflow["permissions"], {"contents": "read"})
        self.assertNotIn("permissions", workflow["jobs"]["check"])
        self.assertNotIn("pull_request_target", workflow["on"])

    def test_actions_are_pinned(self):
        for path in (ROOT / ".github/workflows").glob("*.yml"):
            workflow = load_config(path.read_text())
            for job in workflow["jobs"].values():
                for step in job["steps"]:
                    if "uses" in step:
                        self.assertRegex(step["uses"], r"^[\w-]+/[\w-]+@[a-f0-9]{40}$")


if __name__ == "__main__":
    unittest.main()
