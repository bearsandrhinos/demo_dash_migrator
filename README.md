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

