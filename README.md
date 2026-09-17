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
