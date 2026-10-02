# Higress on Coolify

A minimal, Git-backed deployment of the official Higress All-in-One image.

## Endpoints

- Console: https://higress.discipline-agent.tech (container port 8001)
- Gateway: https://gateway.discipline-agent.tech (container port 8080)

## Deployment

Coolify reads `docker-compose.yml` from the `main` branch. Pushes to `main` automatically trigger a deployment through the repository-scoped GitHub App webhook. Manual deployment remains available from **Actions → Deploy** in Coolify.

Configuration is persisted in the `higress_data` Docker volume mounted at `/data`. Observability is disabled to keep resource usage appropriate for the current VPS.

## Important

Higress documents standalone mode as suitable mainly for development, testing, and proof-of-concept workloads. For large-scale production use, prefer the Kubernetes/Helm deployment model.

## Console password recovery

See [the scoped recovery procedure](docs/CONSOLE-PASSWORD-RECOVERY.md). It uses
the official password-change endpoint with operator-entered hidden input. It does
not clear gateway configuration or restart services. Never commit credentials
or the VPS-only Secret backup. Publishing documentation must not cause an
unnecessary `latest` image redeployment just to recover a password.

## Free GLM onboarding

See [the free GLM staged onboarding record](docs/GLM-FREE-ONBOARDING.md), including
the authorized switch from GLM-4.7-Flash to `glm-4-flash-250414`.
Provider registration alone is not evidence that a protected gateway route or
Agent Hub inference has been deployed or tested.
