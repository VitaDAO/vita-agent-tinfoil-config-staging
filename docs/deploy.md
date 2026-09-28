# Prepare a staging deployment

This repository is not a deployed or runtime-verified fix. Complete the checks
below before using its manifest. Do not update production, shared secret
values, the existing config repository, or the source repository as part of
this setup.

## Review the secret bindings

In Tinfoil, inspect each name's scope and consumers without displaying its
value. Provisioning or rotating credentials is a separate, explicitly approved
operation. Do not copy credentials from the production container.

| Secret name | Required review |
| --- | --- |
| `STAGING_SUPABASE_ANON_KEY` | Existing anon or publishable key for `onqhfjiymokeljclyqdu` |
| `STAGING_SUPABASE_INTERNAL_AUTH_EMAIL` | Dedicated staging machine account |
| `STAGING_SUPABASE_INTERNAL_AUTH_PASSWORD` | Existing password for that same staging machine account |
| `VITA_PROTOCOL_TICKET_HMAC_KEY` | Staging-only signing key, not the production value |
| `VITA_AGENT_GHCR_TOKEN` | Approved read access to the pinned image |
| `TINFOIL_API_KEY` | Approved inference account, usage, and billing |
| `OPEN_JEV_API_KEY` | Approved downstream model access |
| `SENTRY_DSN` | Approved telemetry destination, with environment `staging` |

The pinned Agent supports `STAGING_SUPABASE_ANON_KEY` and the complete
`STAGING_SUPABASE_INTERNAL_AUTH_*` pair. It prefers unprefixed credentials when
they are also present. Do not attach `SUPABASE_URL`, `SUPABASE_ANON_KEY`, or
`SUPABASE_INTERNAL_AUTH_*` as additional secrets. The URL is already fixed in
the manifest.

The protocol-ticket code reads only `VITA_PROTOCOL_TICKET_HMAC_KEY`. Do not
invent a `STAGING_` alias for it. Tinfoil does not allow an organization secret
and a repository secret with the same name. If this name exists at organization
scope, stop. Do not delete or overwrite it. Resolve isolation separately,
through an approved staging-capable runtime binding or a separate Tinfoil
organization. The current repository does not solve that live binding issue.

No `X402_WALLET_PRIVATE_KEY`, `AUBRAI_HPKE_PUBLIC_KEY`, or unused
`REDPILL_API_KEY` is declared. Do not add a production wallet to restore research
functionality during a chat test.

## Review shared infrastructure

The manifest retains the existing `vita-agent-model` endpoint and its
attestation repository. Confirm whether staging may share its capacity before
deployment. For complete infrastructure isolation, provide a separately
verified staging model endpoint and update the matching attestation settings.
Do not substitute a guessed endpoint or disable verification.

The new configuration repository also changes the application's attestation
source. Inspect the staging frontend's expected repository and release before
cutover. Do not change production frontend settings. Debug mode is not an
attested production enclave.

## Publish an attested configuration

1. Run the local checks from the README and confirm that GitHub CI passes.
2. Review the pinned image digest and its source revision.
3. Create a lightweight `vMAJOR.MINOR.PATCH` tag in this repository only.
4. Manually run `Attest staging configuration manually` against that tag.
5. Inspect the generated attestation and prerelease. Publishing does not deploy
   the container, and this workflow never marks a release as latest.

The measurement action is pinned to the version used by the existing production
configuration workflow. No attestation run has been verified for this new repo
yet. Treat action success, Tinfoil acceptance, and browser verification as
separate checks.

## Deploy and verify separately

1. Confirm all secret-scope and shared-model checks above are complete.
2. Resolve the exact staging container ID, repository, tag, and selected SSH
   keys in Tinfoil. Record the current settings for rollback.
3. Confirm whether Tinfoil permits changing that container's source repository.
   If a replacement is required, agree on the cutover before creating it. Do not
   delete the existing container to free its name without approval.
4. Deploy only the approved staging instance with this repository's release.
   Do not use a repository-wide update or enable release promotion.
5. Inspect the effective Supabase hostname, JWKS endpoint, staging identity,
   and credential source without printing secret values.
6. Test health, capabilities, and authenticated chat with the dedicated
   synthetic account. A successful health check alone is not chat verification.
7. Save browser evidence and confirm that no production configuration changed.

## References

- [Tinfoil secret scopes and measured variables](https://docs.tinfoil.sh/containers/secrets-and-env-vars)
- [Tinfoil per-instance lifecycle operations](https://docs.tinfoil.sh/containers/cli)
- [Agent credential selection at the pinned revision](https://github.com/VitaDAO/vita-agent/blob/36833999830a8e42b0a58c54fdbe027cfcab7720/py/src/vita_agent/config.py)
- [Agent strict-production checks](https://github.com/VitaDAO/vita-agent/blob/36833999830a8e42b0a58c54fdbe027cfcab7720/py/src/vita_agent/boot.py)
