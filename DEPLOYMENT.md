# Deployment guide — Vercel + optional Render (no Supabase Auth)

## First: what is currently in this repository?

This repository contains a Python FastAPI research API and its SQLite database layer. It does **not** currently contain a browser-ready frontend/dashboard that Vercel can deploy as a finished site.

Your preference is:
- **Browser-based site:** accessible in a normal browser, with no login/authentication for now.
- **Vercel:** host the frontend once a frontend project is in the repository.
- **Render:** host the Python API only if the browser site needs those API features.
- **Supabase:** do not configure it now. No Supabase Auth is needed. The current code uses SQLite, not Supabase/PostgreSQL.

Do not import this Python-only repository into Vercel expecting a dashboard to appear. Vercel is not a replacement runtime for this project's long-running Python API.

## Recommended path for a browser-only prototype

If the immediate goal is a browser-based site and you do not need data to be shared between browsers/devices:
1. Build/deploy the frontend as a separate Vercel project (or add the frontend to this repository and set Vercel's Root Directory to its real app folder).
2. Keep the initial version fully client-side where practical. Store temporary preferences in browser storage and let the user upload CSV files locally if needed.
3. Do not add Supabase, authentication, a database, or Render until a required feature genuinely needs them.
4. Be aware that browser-local data stays in that browser/device and may be cleared by the user; it is not shared cloud storage.

**Current blocker:** a frontend/dashboard has not yet been added to this repository. The current FastAPI API's research endpoints and SQLite persistence cannot magically work in a static frontend without a server/API and data import.

## Optional: deploy the current Python API on Render

Use this only when the browser site needs server-side research features. The API currently uses SQLite (`src/market_engine/db.py`), so it needs persistent storage on Render.

1. Open https://render.com and sign in.
2. Select **New → Web Service**, connect GitHub, and choose `chandravadiyaDeep/market-pattern-intelligence-engine`.
3. Choose Docker and use the repository-root `Dockerfile`.
4. Set the health-check path to `/health`.
5. Attach a persistent disk mounted at `/data` and check Render's current pricing before proceeding: https://render.com/docs/disks.
6. Add these environment variables:

   | Name | Value |
   |---|---|
   | `MPIE_MODE` | `production` |
   | `MPIE_DATABASE_PATH` | `/data/mpie.sqlite3` |
   | `MPIE_API_KEY` | Strong random secret, at least 32 characters |

   Generate a key in Windows PowerShell:

   ```powershell
   # Generate a private API key. Keep it out of GitHub and frontend code.
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```

7. Generate the service's public URL and wait until the deploy finishes.
8. Test the public health route:

   ```powershell
   # Replace this placeholder with your actual Render URL.
   Invoke-RestMethod "https://YOUR-RENDER-SERVICE.onrender.com/health"
   ```

   A successful response should include `"status": "ok"`.

9. API docs will be available at `https://YOUR-RENDER-SERVICE.onrender.com/docs`. Use Swagger's **Authorize** control for API-key-protected routes.

### Important browser security warning

Do **not** place `MPIE_API_KEY` in frontend JavaScript or a `NEXT_PUBLIC_*` / `VITE_*` variable. Anyone can inspect a browser bundle and copy a key. A personal browser prototype can call only public, read-only endpoints, or use a server-side proxy/authentication layer before exposing protected API operations. The current API key is a simple personal-access gate, not multi-user authentication or per-user authorization.

## Do we need Supabase?

**Not for the current code.** The database implementation imports Python's built-in `sqlite3`, and it has not been migrated to PostgreSQL. Creating a Supabase project or setting a `DATABASE_URL` would not cause the API to use it.

Consider Supabase later only if you need cloud PostgreSQL—for example, shared datasets or research records across deployments/devices. That would require a tested PostgreSQL migration and server-side credentials. Supabase Auth is optional and should remain disabled unless user accounts become a requirement. Never put database passwords or privileged Supabase keys in browser code.

## What deployment does not provide automatically

Deploying the API does not load historical price data, verified point-in-time Nifty 50 membership, or corporate events. It also does not create a dashboard, schedule feed ingestion, create backups, add multi-user authentication, validate a profitable strategy, or execute live trades.

Keep this SQLite API to one service instance. A persistent disk is not a backup; arrange separate backups if the database becomes valuable.

## Related links

- Vercel: https://vercel.com/
- Vercel deployment docs: https://vercel.com/docs/deployments
- Render: https://render.com/
- Render persistent disks: https://render.com/docs/disks
- Supabase is intentionally not part of the current deployment steps.
