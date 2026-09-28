"""Check the public staging manifest, without network access or secret values."""
import argparse
from pathlib import Path
import re

import yaml

ROOT = Path(__file__).resolve().parents[1]
PROJECT = "onqhfjiymokeljclyqdu"
SUPABASE_URL = f"https://{PROJECT}.supabase.co"
AGENT_URL = "https://staging-vita-agent.debug.vitality-now.containers.tinfoil.dev/"
SECRET_NAMES = {
    "VITA_AGENT_GHCR_TOKEN", "TINFOIL_API_KEY", "OPEN_JEV_API_KEY", "SENTRY_DSN",
    "STAGING_SUPABASE_ANON_KEY", "STAGING_SUPABASE_INTERNAL_AUTH_EMAIL",
    "STAGING_SUPABASE_INTERNAL_AUTH_PASSWORD", "VITA_PROTOCOL_TICKET_HMAC_KEY",
}
PATHS = {
    "/api/health", "/metrics", "/.well-known/enclave-pubkey",
    "/.well-known/vita-agent-capabilities", "/.well-known/vita-agent-turn-features",
    "/api/v1/turn-protocol-ticket", "/api/v1/capsule", "/api/v1/capsule/stream",
    "/api/v1/jobs", "/api/v1/jobs/*",
}
REQUIRED_ENV = {
    "VITA_AGENT_PORT": "8787",
    "STORAGE_BACKEND": "supabase",
    "SUPABASE_URL": SUPABASE_URL,
    "SUPABASE_JWKS_URL": SUPABASE_URL + "/auth/v1/.well-known/jwks.json",
    "SUPABASE_JWT_VERIFY_MODE": "jwks",
    "VITA_AGENT_ENCLAVE_URL": AGENT_URL,
    "VITA_AGENT_CORS_ORIGINS": "https://staging-app.vitadao.com",
    "SENTRY_ENVIRONMENT": "staging",
    # This is a debug-only manifest. The runtime rejects .debug. under STRICT_PROD=1.
    "STRICT_PROD": "0",
    "VITA_AGENT_REQUIRE_SEALED_DEK": "1",
    "VITA_AGENT_ACCEPT_LEGACY_DEK_HEADERS": "0",
    "OPENAI_AGENTS_DISABLE_TRACING": "1",
    "VITA_AGENT_ENABLE_LEGACY_ROUTES": "0",
    "VITA_TURN_V1_POLICY": "disabled",
    "VITA_TURN_ENVELOPE_V2": "1",
    "VITA_CONTEXT_OWNER_BACKEND": "1",
    "VITA_SESSION_V2": "1",
    "VITA_HEALTH_RESOLVER_V2": "1",
    "VITA_CONTEXT_V2_CANARY_PERCENT": "100",
    "VITA_AGENT_PINNED_SAFETY": "1",
    "VITA_AGENT_INPUT_FILTER": "1",
    "AUBRAI_DEBUG": "0",
    "VITA_AGENT_MODEL_PROVIDER": "tinfoil",
    "VITA_AGENT_TINFOIL_TRANSPORT": "sdk",
}


class InvalidConfig(ValueError):
    pass


class UniqueLoader(yaml.SafeLoader):
    """Reject duplicate keys instead of silently taking the last value."""

    def construct_mapping(self, node, deep=False):
        result = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str) or key in result:
                raise InvalidConfig("YAML keys must be unique strings")
            result[key] = self.construct_object(value_node, deep=deep)
        return result


def require(condition, message):
    if not condition:
        raise InvalidConfig(message)


def load_config(text):
    try:
        return yaml.load(text, Loader=UniqueLoader)
    except yaml.YAMLError as exc:
        raise InvalidConfig("Invalid YAML") from exc


def environment(container):
    items = container.get("env")
    require(isinstance(items, list), "env must be a list")
    env = {}
    for item in items:
        require(isinstance(item, dict) and len(item) == 1, "env entries must contain one name")
        name, value = next(iter(item.items()))
        require(isinstance(name, str) and isinstance(value, str), "env names and values must be strings")
        require(name not in env, "Duplicate environment variable")
        env[name] = value
    return env


def validate(config):
    require(isinstance(config, dict), "Manifest must be a mapping")
    require(set(config) == {"cvm-version", "cpus", "memory", "containers", "shim"}, "Unexpected manifest fields")
    require(config["cvm-version"] == "0.7.5", "CVM changes require an explicit compatibility review")
    require(config["cpus"] == 4 and config["memory"] == 16384, "Unexpected resource change")
    containers = config["containers"]
    require(isinstance(containers, list) and len(containers) == 1, "Only the vita-agent workload is allowed")
    container = containers[0]
    require(isinstance(container, dict), "Container must be a mapping")
    require(set(container) == {"name", "image", "registry", "env", "secrets"}, "Unexpected container fields")
    require(container["name"] == "vita-agent", "Wrong workload name")
    require(container["registry"] == {"username": "DobrinAlexandru", "password_secret": "VITA_AGENT_GHCR_TOKEN"}, "Unexpected registry binding")
    image = container["image"]
    require(isinstance(image, str), "Image must be a string")
    match = re.fullmatch(r"ghcr\.io/vitadao/vita-agent:staging-([0-9a-f]{40})@sha256:[0-9a-f]{64}", image)
    require(match is not None, "Pin a staging image by source SHA and immutable digest")
    version = match.group(1)[:7]
    env = environment(container)
    for name, expected in REQUIRED_ENV.items():
        require(env.get(name) == expected, f"Incorrect or missing {name}")
    for name in ("VITA_AGENT_VERSION", "SENTRY_RELEASE"):
        require(env.get(name) == f"vita-agent@{version}", f"{name} must match the image source SHA")
    require(env.get("VITA_AGENT_DEPLOYMENT_ID") == f"staging-vita-agent-{version}", "Wrong staging deployment identity")
    permitted_supabase = {"SUPABASE_URL", "SUPABASE_JWKS_URL", "SUPABASE_JWT_VERIFY_MODE"}
    for name, value in env.items():
        require(not ("SUPABASE" in name and name not in permitted_supabase), "Supabase credentials must be staging secret bindings")
        require(not (re.search(r"(?:PASSWORD|PRIVATE_KEY|API_KEY|ANON_KEY|PUBLISHABLE_KEY|SECRET_KEY|HMAC_KEY|JWT_SECRET)$", name)), "Credential values cannot be stored in env")
        hosts = re.findall(r"[a-z0-9]+\.supabase\.co", value)
        require(all(host == f"{PROJECT}.supabase.co" for host in hosts), "A non-staging Supabase host is forbidden")
        require("vita-agent-prod" not in value, "Production Agent references are forbidden")
        require(not re.search(r"-----BEGIN .*PRIVATE KEY-----|\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.|\bsb_(?:secret|publishable)_", value), "Token-like values cannot be stored in env")
    for name in ("ALLOW_PLAINTEXT_DEK", "VITA_AGENT_DEBUG_ALLOW_SERVICE_ROLE_INTERNAL_CLIENT", "VITA_STAGING_SYNTHETIC_FIXTURES"):
        require(name not in env, "Debug authentication bypasses are forbidden")
    secrets = container["secrets"]
    require(isinstance(secrets, list) and all(isinstance(s, str) for s in secrets), "Secrets must be names only")
    require(len(secrets) == len(set(secrets)) and set(secrets) == SECRET_NAMES, "Unexpected or missing secret binding")
    shim = config["shim"]
    require(isinstance(shim, dict) and set(shim) == {"upstream-port", "paths"}, "Unexpected shim fields")
    require(shim["upstream-port"] == 8787, "Wrong upstream port")
    paths = shim["paths"]
    require(isinstance(paths, list) and all(isinstance(p, str) for p in paths), "Paths must be strings")
    require(len(paths) == len(set(paths)) and set(paths) == PATHS, "Unexpected exposed HTTP paths")
    return env


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", nargs="?", type=Path, default=ROOT / "tinfoil-config.yml")
    args = parser.parse_args()
    try:
        validate(load_config(args.manifest.read_text()))
    except (InvalidConfig, OSError) as exc:
        parser.exit(1, f"Configuration check failed: {exc}\n")
    print("PASS: staging manifest checks. This does not verify live secret scopes or authorize deployment.")


if __name__ == "__main__":
    main()
