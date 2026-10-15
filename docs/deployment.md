# Deploy the interactive app using free tiers

Use **Render Free** for the app and **Neon Free** for PostgreSQL. The checked-in `render.yaml` selects `plan: free` and creates no paid instance, persistent disk, or managed database. Keep both accounts on their free plans. Usage limits apply; the app and database can sleep when idle, so the first request may be slow. AI classification is an optional paid API integration and is not required or enabled by this deployment.

## 1. Create the free database

1. Create or sign in to your [Neon account](https://console.neon.tech/signup).
2. Create a project on the **Free** plan. Choose a region near Render's Oregon region if available.
3. Open the project's **Connect** dialog. Copy the PostgreSQL connection string. It starts with `postgresql://` and includes credentials and TLS options such as `sslmode=require`. Copy the URL only, without a `psql` command or surrounding quotes. A pooled connection URL is supported.
4. Keep this connection string private. Paste it only into Render's secure configuration in the next step, never into chat or GitHub.

## 2. Create the free web service

1. Create or sign in to your [Render account](https://dashboard.render.com/register).
2. Open [Deploy Signal on Render](https://render.com/deploy?repo=https://github.com/kanhao-bytedance/bytedance).
3. Connect GitHub and grant Render access to `kanhao-bytedance/bytedance`. If it is private, allow access only to that repository. Review the Blueprint from `render.yaml` on `main`.
4. When asked for **DATABASE_URL**, paste the connection string from Neon. The app chooses the installed psycopg driver automatically while preserving TLS options.
5. Confirm that the service uses **Free**, with **no persistent disk or paid database**, then create the Blueprint resources. If Render asks you to upgrade, stop rather than accept a paid plan. A manual Free web service can use the same build/start commands and environment settings from `render.yaml` if Blueprint creation is unavailable for your account.
6. Wait for `signal-voc` to deploy. Open the actual HTTPS website URL displayed on its service page.
7. Sign in with username `admin`. Reveal the generated **DASHBOARD_PASSWORD** in Render's Environment settings for the password. Do not send that password in chat or screenshots.

There is no live website until these accounts and resources exist. The deployment button loads configuration; it is not the interactive website itself. This workspace has no Render or Neon account access and cannot create those accounts for you.

If you already created the earlier paid Blueprint, switching the repository's YAML does not cancel charges or delete old resources. Back up any existing feedback and remove the paid service/disk in Render, or review a supported change to Free. Do not delete stored data without a backup. Create this free deployment with the new Neon database separately if needed; existing SQLite records are not transferred automatically.

## How feedback persists

The free web service's local files are temporary. The app therefore stores feedback in Neon, not in a local SQLite file. Deployments, idle restarts, and app restarts reconnect to that database. Keep the Neon project and connection URL; deleting the database deletes its feedback. Database backups and exports are separate from Git backups.

The app uses connection pre-ping to replace stale pooled connections after database idle periods. A database outage or an exhausted free-tier allowance can still prevent the service from becoming ready.

## What gets deployed

- `render.yaml`: a free Python 3.12 web service and `/health` readiness check. `DATABASE_URL` is entered securely during service creation.
- `requirements.lock.txt`: exact runtime dependency versions, including psycopg 3.
- `scripts/start.sh`: one Uvicorn worker on Render's assigned `PORT`.
- `REQUIRE_DASHBOARD_AUTH=true`: refuses to start without a password. The dashboard, API, documentation, and assets require authentication. `/health` remains available to the provider.

This is a shared-workspace login for a small MVP, not a multi-user account system. Use Render's HTTPS URL. API clients use HTTP Basic authentication. Browser writes from other origins are rejected.

Manual entry, search, source evidence, and dashboard counts work without AI or Reddit credentials. If you later enable an integration, configure credentials only in Render's secure Environment settings and check that provider's pricing separately. Neither integration is needed for the free workflow.

## Verify after launch

1. Open the service URL and sign in.
2. Add feedback with a unique source reference. Without AI, it should be marked unclassified.
3. Search for its text and open the original evidence.
4. Restart the Render service and confirm the record remains in the inbox.
5. Check `/health` returns `ok: true`. A successful build alone does not verify the live app.

## Troubleshooting

- **Repository not found:** grant Render's GitHub integration access to this repository.
- **Missing password:** configure `DASHBOARD_PASSWORD` in Render and redeploy; keep authentication required.
- **Database connection error:** use the complete Neon URL, retain its TLS options, and check the project is active and within its free allowance. Do not print the URL in logs or chat.
- **First load is slow:** allow the free web service and database time to wake up.
- **Schema mismatch on an existing database:** preserve it and plan a migration. Do not delete feedback to make startup pass.

## Local validation

```bash
python -m pytest -q
python scripts/check_deployment.py
```

The production startup check uses a temporary SQLite database. It verifies password access, ingestion, search, persistence across a process restart, and missing-password refusal without changing real feedback. PostgreSQL URL normalization is covered by tests. A temporary PostgreSQL 16 integration check also passed schema creation, authenticated ingestion, deduplication, search, evidence retrieval, summaries, themes, and persistence after reconnecting. This local integration check is distinct from a live Neon connection: live provider provisioning and end-to-end public URL validation still require your free accounts.
