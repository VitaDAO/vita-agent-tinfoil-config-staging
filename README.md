# Vita Agent staging configuration

Public Tinfoil configuration for `staging-vita-agent`. Application source stays
in [VitaDAO/vita-agent](https://github.com/VitaDAO/vita-agent). This repository
does not build or fork the application.

**Status: configuration prepared, not deployed.** No Tinfoil secrets are stored
here. Creating this repository does not change a running container.

## Environment

| Setting | Target |
| --- | --- |
| Supabase project | `onqhfjiymokeljclyqdu` |
| Frontend | `https://staging-app.vitadao.com` |
| Agent | `https://staging-vita-agent.debug.vitality-now.containers.tinfoil.dev` |
| Telemetry environment | `staging` |
| Application source revision | `36833999830a8e42b0a58c54fdbe027cfcab7720` |

The image reference matches the production configuration at
[`3cffa435`](https://github.com/VitaDAO/vita-agent-tinfoil-config/tree/3cffa435ccad1831a169d2b838cfb5afc1478b87).
This is a configuration comparison, not proof of the image currently running
on production.

The manifest was derived from the existing
[`staging` configuration at `7559c38c`](https://github.com/VitaDAO/vita-agent-tinfoil-config/tree/7559c38cc92f2d7dbfdb717c3c31f2f7f355f6f4).
Application feature settings match the production manifest. Differences are
limited to the debug environment, staging URLs and identity, credentials,
and the unconfigured paid-research integration described below.

## Isolation and limits

- Supabase URL and JWKS point only to staging. Shared, unprefixed Supabase
  credential bindings are not allowed.
- `STRICT_PROD=0` matches the existing debug-staging configuration. It skips
  production-only boot checks, including rejection of a `.debug.` URL. JWKS
  verification, sealed DEKs, disabled legacy routes, and disabled tracing remain
  explicit. This manifest must never serve production or real health data.
- No wallet private key or Aubrai research-key binding is requested. Paid
  research is not configured in this initial manifest. Do not claim research
  parity until a staging-only credential setup is approved and verified.
- The model endpoint is still shared infrastructure. This repository does not
  establish isolated model capacity, billing, or downstream services.
- Protocol-ticket signing and other non-Supabase secret scopes require a live
  Tinfoil review before deployment. A secret name alone does not prove isolation.
- CI checks configuration. Releases are manual and never deploy a container or
  promote another repository's release.
- The dashboard starts `tinfoil-release.yml` with a version. That workflow
  creates the tag and starts `tinfoil-release-publish.yml` to attest and publish.

## Check locally

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-checks.txt
.venv/bin/python scripts/validate_config.py
.venv/bin/python -m unittest discover -s tests -v
```

See [deployment prerequisites](docs/deploy.md) before creating a release or
changing the staging container. Production configuration and secrets must stay
untouched.
