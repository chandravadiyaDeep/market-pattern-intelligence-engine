# Deployment guide — Vercel + Render + Supabase

This repository currently contains a **FastAPI research API**, not a finished web dashboard. Deploying it on Render makes the API reachable; Vercel should host a separate frontend project when one exists.

## Important database status (read before deploying)

The current code in `src/market_engine/db.py` uses Python's built-in `sqlite3` and creates a local SQLite file. Adding Supabase environment variables does **not** migrate this code to PostgreSQL. Do not deploy this API expecting Supabase to store its research data until the database layer has been ported and tested against PostgreSQL.

For the initial stack, the intended roles are:

- **Vercel:** frontend/dashboard (deploy the frontend project or repository that contains the actual frontend; this repository currently does not contain a Vercel-ready frontend project).
- **Render:** long-running FastAPI API service, built from this repository's Dockerfile.
- **Supabase:** managed PostgreSQL database, and optionally Supabase Auth for user accounts in a later phase.

If you need to deploy the current SQLite-based API before the PostgreSQL migration, use a Render persistent disk mounted at `/data` and set `MPIE_DATABASE_PATH=/data/mpie.sqlite3`. Render's filesystem is ephemeral unless persistent storage is configured. This temporary route uses Render storage, not Supabase Postgres.

## A. Create Supabase project

1. Open https://supabase.com/dashboard and create a project.
2. Save the database password securely. Never commit it to GitHub or put it in browser code.
3. Open **Connect** in the Supabase dashboard and copy the connection string that matches your network. Render services may be on IPv4-only networks, so if the direct connection does not work, select the **Session pooler** connection string in Supabase rather than constructing a hostname manually. Follow Supabase's current connection instructions: https://supabase.com/docs/guides/database/connecting-to-postgres.
4. Keep the connection string private. A frontend must never receive the database password or a privileged server key.

**Note:** this step creates the managed database, but the current SQLite schema and queries have not yet been converted to PostgreSQL. Do not set an unused `DATABASE_URL` and assume the application is using it.

## B. Deploy the API on Render

The repository already has a Dockerfile and binds Uvicorn to the platform-provided `PORT`.

1. Open https://render.com and sign in.
2. Choose **New → Web Service**, connect GitHub, and select `chandravadiyaDeep/market-pattern-intelligence-engine`.
3. Choose **Docker** as the runtime/build method and use the root `Dockerfile`.
4. Set the health check path to `/health`.
5. For the current SQLite-based version, attach a persistent disk mounted at `/data`. Check current pricing first; persistent disks may require a paid Render service. Render disk docs: https://render.com/docs/disks.
6. Under **Environment**, set:
   - `MPIE_MODE=production`
   - `MPIE_DATABASE_PATH=/data/mpie.sqlite3`
   - `MPIE_API_KEY` = a generated secret of at least 32 characters
7. Generate the secret on your Windows computer in PowerShell:

   ```powershell
   # Generate a cryptographically strong API key; do not commit it.
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```

8. Copy the printed key directly into Render's environment variables. Do not send it in chat, commit it, or put it in frontend JavaScript.
9. Deploy and wait for Render to report that the service is live.

### Verify the Render API

Replace the placeholder with your actual Render service URL:

```powershell
# Public health check; expected JSON includes status = ok.
Invoke-RestMethod "https://YOUR-RENDER-SERVICE.onrender.com/health"

# Example authenticated request. Keep the key local and private.
$headers = @{ "X-API-Key" = "PASTE-YOUR-KEY-LOCALLY" }
Invoke-RestMethod "https://YOUR-RENDER-SERVICE.onrender.com/research-sources" -Headers $headers
```

Open `https://YOUR-RENDER-SERVICE.onrender.com/docs`, select **Authorize**, and enter the same API key to try protected routes. Treat the API key as a personal-access gate, not full user authentication.

## C. Deploy a frontend on Vercel

There is no Vercel-ready frontend in this repository at the moment. Do not import this Python-only repository as a Next.js project expecting a dashboard to appear.

When the frontend project is ready:

1. Open https://vercel.com and choose **Add New → Project**.
2. Import the GitHub repository that contains the actual frontend.
3. Select its framework preset and set the **Root Directory** to the frontend app directory (for example, `web` or `frontend`, only if that directory really exists in that repository).
4. Add a frontend environment variable such as `NEXT_PUBLIC_API_BASE_URL` with the Render API base URL, for example `https://YOUR-RENDER-SERVICE.onrender.com`.
5. Configure frontend requests to send `X-API-Key` only for a private personal prototype. **Do not bake a permanent private API key into `NEXT_PUBLIC_*` variables or browser JavaScript.** For a multi-user application, add server-side authentication/authorization and a secure server-side API proxy instead.
6. Deploy and test a read-only route from the deployed frontend.

Vercel's Git-connected deployments are documented at https://vercel.com/docs/deployments.

## D. Connect the API to Supabase — required migration work

The API currently uses SQLite-specific SQL and `sqlite3`. Before Supabase can be the actual database, the code needs a dedicated PostgreSQL migration, including:

- Add a PostgreSQL driver and environment setting for the Supabase connection string.
- Replace the SQLite connection/initialization layer with a PostgreSQL-compatible repository or database abstraction.
- Migrate SQLite-specific schema details such as `INTEGER PRIMARY KEY AUTOINCREMENT`, placeholder syntax, and SQLite-specific query behavior.
- Add and test schema migrations; do not rely on `init_db()` running SQLite DDL against Postgres.
- Run tests against both the local test database and a temporary/isolated Postgres database before changing production.
- Import existing approved research records explicitly; creating a Supabase project does not copy the local SQLite file into Postgres.
- Keep the database password and any service-role key on the server only. If Supabase Auth is later enabled for users, enforce authorization on the backend and database rather than trusting a client-supplied user ID.

Until this work is complete, **the deployed application uses SQLite on Render's disk** and Supabase is created but not used by the API data layer.

## E. What is and is not ready

Ready in the repository: FastAPI API, health endpoint, `/docs`, API-key check, Docker image, test/lint workflow.

Not automatically supplied by deployment: Vercel dashboard UI, PostgreSQL-compatible database layer, historical market prices, verified historical Nifty 50 membership, corporate event imports, scheduled ingestion, multi-user authentication, automated backups, or evidence of a profitable trading strategy.

Keep the Render service to one instance while using SQLite. Back up the database separately; a persistent disk is not a backup. The service is for research and paper simulation only and does not place live trades.
