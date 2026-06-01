# Deploy TH-EVI on Vercel

TH-EVI can run on Vercel as a FastAPI Python app. Vercel uses `app.py` as the
entrypoint and `vercel.json` to trim development-only files from the function
bundle.

## Database

Local development uses SQLite at `data/th_evi.sqlite3`.

Production on Vercel should use Postgres. Add a Postgres provider from the
Vercel Marketplace, Neon, Supabase, or another managed provider, then set one
of these environment variables in the Vercel project:

- `DATABASE_URL`
- `POSTGRES_URL`
- `TH_EVI_DB_URL`

The app accepts regular `postgres://` or `postgresql://` connection strings and
converts them for the bundled psycopg SQLAlchemy driver.

## Dashboard Deploy

1. Open the Vercel dashboard.
2. Import the GitHub repository: `pongwaraj/TH-EVI`.
3. Keep the project root as the repository root.
4. Use the default Python/FastAPI detection.
5. Add the Postgres environment variable before production use.
6. Deploy.

## CLI Deploy

Install Vercel CLI, then run:

```powershell
vercel login
vercel link
vercel --prod
```

For a preview deploy, run:

```powershell
vercel
```

## Notes

- `requirements.txt` is intentionally production-focused for Vercel.
- Notebook, plotting, and analysis-only packages live in `requirements-dev.txt`.
- Excel and local SQLite files are excluded from Vercel bundles.
