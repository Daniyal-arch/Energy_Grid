# Setup — accounts & credentials

Step-by-step for the two Phase-1 credentials. Everything goes into `.env` (copy from [.env.example](../.env.example)).

## 1. Supabase project

1. Create a project at https://supabase.com/dashboard (any name, region `eu-central-1` recommended — data + users are German).
2. Dashboard → **Settings → API**: copy
   - Project URL → `SUPABASE_URL`
   - `service_role` secret → `SUPABASE_SERVICE_ROLE_KEY` (server-side only, never in the frontend)
   - `anon` public key → `SUPABASE_ANON_KEY` (and later `VITE_SUPABASE_ANON_KEY` in `frontend/.env.local`)
3. Install the Supabase CLI (https://supabase.com/docs/guides/cli), then from the repo root:
   ```sh
   supabase login
   supabase link --project-ref YOUR_PROJECT_REF
   supabase db push          # applies supabase/migrations/*.sql
   ```
4. Dashboard → **Storage**: create a **private** bucket named `chips` (image chips; the backend serves signed URLs).

## 2. Google Earth Engine service account

You already have a GEE account. To let pipelines run headless:

1. Go to https://console.cloud.google.com → select (or create) the Google Cloud project that is **registered for Earth Engine** (check at https://code.earthengine.google.com → settings, or https://console.cloud.google.com/earth-engine).
2. **IAM & Admin → Service Accounts → Create service account.** Name e.g. `gridwatch-pipeline`.
3. Grant it the role **Earth Engine Resource Viewer** (`roles/earthengine.viewer`) — enough for reading collections and computing reductions. Also ensure the **Earth Engine API** is enabled for the project (APIs & Services → Enable APIs → "Google Earth Engine API").
4. On the service account → **Keys → Add key → JSON**. Download the file, store it OUTSIDE the repo or in `./secrets/` (gitignored).
5. Register the service account for Earth Engine use at https://code.earthengine.google.com/register (choose the same cloud project, noncommercial/testing tier is fine for the prototype).
6. Fill `.env`:
   ```
   GEE_SERVICE_ACCOUNT_EMAIL=gridwatch-pipeline@YOUR_PROJECT.iam.gserviceaccount.com
   GEE_SERVICE_ACCOUNT_KEY_FILE=E:\secrets\gee-key.json
   ```
7. Verify: `uv run python -c "import ee; from app.config import get_settings; s=get_settings(); ee.Initialize(ee.ServiceAccountCredentials(s.gee_service_account_email, s.gee_service_account_key_file)); print(ee.String('gee ok').getInfo())"`

## Phase 2 (later, not needed yet)

- **ENTSO-E**: register free at https://transparency.entsoe.eu, then email transparency@entsoe.eu with subject "Restful API access" → token appears under account settings → `ENTSOE_API_KEY`.
- **Anthropic**: https://console.anthropic.com → API keys → `ANTHROPIC_API_KEY`.
- Bright Sky (DWD) and SMARD need no keys.

## After credentials exist

```sh
uv sync                                   # install workspace
uv run pytest                             # should pass
uv run python scripts/probe_mastr.py     # probe MaStR (multi-GB download, one-time)
```
