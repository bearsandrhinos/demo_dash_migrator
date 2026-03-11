# Demo Dashboard Migrator

This Streamlit app migrates our demo Omni assets to another Omni instance:

- Demo Snowflake connection
- Demo models (SCHEMA + SHARED)
- Demo dashboards/documents
- Document labels (`Verified` and `Homepage`)

## What you need

Before running the app, you only need one thing in the **target** Omni instance:

- An **Organization API Key**

You will paste that key into the app when prompted.

## What the script handles automatically

When you click **Create Connection**, the app handles the migration flow end-to-end:

1. Creates the destination Snowflake connection.
2. Ensures `peter@omni.co` exists in the target org.
3. Assigns Peter as `CONNECTION_ADMIN` on the new connection.
4. Creates SCHEMA and SHARED models.
5. Creates the destination folder.
6. Migrates demo dashboards/documents.
7. Lists documents in the new folder and applies labels:
   - `Verified`
   - `Homepage`
8. Triggers model code migration.

## Important post-run step (required)

After the script completes, go into Omni and **update Peter to Org Admin**.

If this is not done, Peter can be locked out.

## Run locally

1. Create and activate a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt python-dotenv
```

3. Start the app:

```bash
streamlit run streamlit_app.py
```

4. Open:

`http://localhost:8501`

## Required environment variables

Set these in your local environment (or `.env` for local development):

- `SOURCE_API_KEY`
- `MODEL_SOURCE_API_KEY`
- `SNOWFLAKE_ACCOUNT`
- `SNOWFLAKE_DATABASE`
- `SNOWFLAKE_USERNAME`
- `SNOWFLAKE_KEYPAIR`
- `SNOWFLAKE_WAREHOUSE`

Do not commit secrets to git.

## Deploy to Streamlit Cloud

**Python 3.14 causes a crash.** You must use **Python 3.11**. Streamlit Cloud does not let you change Python version after deployment—you must delete and recreate the app.

### First-time deploy

1. Go to [share.streamlit.io](https://share.streamlit.io/) → **Create app**
2. Enter repo: `bearsandrhinos/demo_dash_migrator`, branch: `main`, file: `streamlit_app.py`
3. Click **Advanced settings**
4. In the **Python version** dropdown, select **3.11**
5. Add secrets (API keys, Snowflake credentials) if needed
6. Click **Deploy**

### If the app is already deployed (and failing)

1. **Delete** the app: App menu (⋮) → **Delete app**
2. Note your secrets and custom subdomain (you can reuse them)
3. **Create app** again with the same repo/branch/file
4. In **Advanced settings**, select **Python 3.11** (this is required)
5. Re-enter secrets, set subdomain if desired
6. Click **Deploy**

