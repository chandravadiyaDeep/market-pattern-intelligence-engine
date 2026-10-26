# Deployment guide (personal research API)

This repository is a **FastAPI backend**, not a finished public website. Deploy the API service first; its interactive API interface is served at `/docs`.

## Recommended first host: Railway

Railway can deploy this repository from GitHub and supports persistent volumes. The Docker image is configured to store SQLite at `/data/mpie.sqlite3`; without a volume, database changes can disappear on redeploy. See the current Railway guide: https://docs.railway.com/guides/fastapi and volume guide: https://docs.railway.com/volumes.

### 1. Before deploying

- Push the latest `main` branch to GitHub.
- Confirm the GitHub Actions test workflow passes.
- Have source-permitted price data and verified constituent membership ready for import later. Do not put licensed data dumps or a local SQLite database into Git.

### 2. Create the service

1. Sign in to Railway and create a new project.
2. Choose **Deploy from GitHub repo** and select `chandravadiyaDeep/market-pattern-intelligence-engine`.
3. Let Railway build using the repository's `Dockerfile`.
4. In the service's **Volumes** settings, create a volume mounted at `/data`.
5. In service variables, set:
   - `MPIE_MODE=production`
   - `MPIE_DATABASE_PATH=/data/mpie.sqlite3`
   - `MPIE_API_KEY` to a randomly generated secret with at least 32 characters.
6. Generate a public domain from the service's networking settings.
7. Redeploy if the platform does not automatically apply the variables/volume changes.

Generate a strong API key locally in PowerShell; do not commit or send it in chat:

```powershell
# Generate a cryptographically random 32-byte key and print it once.
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Store the result only in Railway's service variables. Never put it in GitHub source code, screenshots, or a committed `.env` file.

### 3. Verify deployment

Replace `YOUR-RAILWAY-DOMAIN` with the domain Railway generated.

```powershell
# Public health check does not require the API key.
Invoke-RestMethod "https://YOUR-RAILWAY-DOMAIN/health"

# Protected endpoints require the X-API-Key header.
$headers = @{ "X-API-Key" = "PASTE-YOUR-KEY-LOCALLY" }
Invoke-RestMethod "https://YOUR-RAILWAY-DOMAIN/research-sources" -Headers $headers
```

Open `https://YOUR-RAILWAY-DOMAIN/docs`, select **Authorize**, enter the same API key, and test a read-only endpoint. The key is required for all API routes except `/health` and the documentation assets when configured.

### 4. Data and operating notes

- SQLite is suitable for a single-instance personal research service at this stage. Keep the Railway service to one instance when using a mounted volume.
- Back up the database and test restoring it before relying on the service. A volume is persistence, not a complete backup strategy.
- Do not use a public deployment without setting `MPIE_API_KEY`; production mode refuses to start if a key of at least 32 characters is missing.
- API-key authentication is a basic personal-access gate, not multi-user authentication or role-based access control. Do not expose this API to untrusted users as a commercial service without a stronger security review.
- No live trading or broker connection is included.
- Feed ingestion is not automatically scheduled by deployment. Run it manually or add a separate scheduled worker only after validating source terms and failure handling.
- The API currently stores research records locally in SQLite. This is not yet a multi-user, high-availability architecture.

## Alternative: Render

Render can also deploy the Docker image, but its filesystem is ephemeral by default. SQLite requires a persistent disk attached at `/data`, and Render documents persistent disks as available for paid web services. Review current plan pricing and storage terms before selecting it: https://render.com/docs/disks.

## What is not included

- A frontend dashboard or custom domain.
- A verified historical Nifty 50 membership dataset.
- A licensed historical market-data subscription.
- Scheduled ingestion, monitoring alerts, managed database migrations or automated backups.
- Proof of predictive edge or a production trading strategy.
