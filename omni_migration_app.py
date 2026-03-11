import streamlit as st
import requests
import json
from typing import Optional, Tuple
from dotenv import load_dotenv
import os
import time  # Add this import at the top of your file
from urllib.parse import quote

# Load environment variables
load_dotenv()

# Constants
SOURCE_ENV = "demodashboards.omniapp.co"  # For dashboard migration
SOURCE_API_KEY = os.getenv("SOURCE_API_KEY")
DOCUMENT_LABELS = ["Verified", "Homepage"]

SOURCE_BASE_URL = f"https://{SOURCE_ENV}"

SOURCE_HEADERS = {
    "Authorization": f"Bearer {SOURCE_API_KEY}",
    "Content-Type": "application/json"
}

REGION_CONFIG = {
    "North America": {
        "model_source_env": "source-model.omniapp.co",
        "origin_model_id": "ebd137f2-f00c-43eb-8120-6ca240c893aa",
    },
    "EMEA": {
        "model_source_env": "source-model-emea.omniapp.co",
        "origin_model_id": "7c0a6c0c-2c5f-4b9b-b29b-931e3659a8c0",
    },
}

def apply_label_to_document(document_id: str, label_name: str) -> bool:
    """Apply a single existing label to a document."""
    encoded_label = quote(label_name, safe="")
    label_url = f"{st.session_state.dest_env}/api/v1/documents/{document_id}/labels/{encoded_label}"
    response = requests.put(label_url, headers=st.session_state.dest_headers)

    # Omni returns 204 when label application succeeds.
    if response.status_code in [200, 204]:
        return True

    st.error(
        f"Failed to apply label '{label_name}' to document {document_id}: "
        f"{response.status_code} {response.text}"
    )
    return False

def list_document_ids_in_folder(base_url: str, headers: dict, folder_id: str) -> list[str]:
    """List all document IDs in a folder using GET /v1/documents (folderId filter)."""
    list_url = f"{base_url}/api/v1/documents"
    document_ids = []
    cursor = None

    while True:
        params = {
            "folderId": folder_id,
            "pageSize": 100
        }
        if cursor:
            params["cursor"] = cursor

        response = requests.get(list_url, headers=headers, params=params)
        if not response.ok:
            st.error(
                f"Failed to list documents in folder {folder_id}: "
                f"{response.status_code} {response.text}"
            )
            return []

        try:
            payload = response.json()
        except Exception:
            st.error(f"Failed to parse document list response for folder {folder_id}")
            return []

        records = payload.get("records", []) if isinstance(payload, dict) else []
        page_info = payload.get("pageInfo", {}) if isinstance(payload, dict) else {}

        for item in records:
            if isinstance(item, dict):
                # /v1/documents returns `identifier` as document ID for document endpoints.
                document_id = item.get("identifier") or item.get("id") or item.get("documentId")
                if isinstance(document_id, str) and document_id.strip():
                    document_ids.append(document_id)

        has_next_page = bool(page_info.get("hasNextPage")) if isinstance(page_info, dict) else False
        cursor = page_info.get("nextCursor") if isinstance(page_info, dict) else None
        if not has_next_page or not cursor:
            break

    unique_document_ids = list(dict.fromkeys(document_ids))
    if not unique_document_ids:
        st.warning(f"No documents found in folder {folder_id}.")
    else:
        st.info(f"Found {len(unique_document_ids)} documents in folder.")
    return unique_document_ids

def apply_labels_to_documents(document_ids: list[str]) -> None:
    """Apply all configured labels to each document ID provided."""
    for document_id in document_ids:
        for label_name in DOCUMENT_LABELS:
            if apply_label_to_document(document_id, label_name):
                st.success(f"Applied label '{label_name}' to document {document_id}")

def create_connection(dest_base_url: str, dest_headers: dict) -> Tuple[Optional[str], Optional[str]]:
    """Create a Snowflake connection and return the connection ID."""
    connection_payload = {
        "dialect": "snowflake",
        "name": "Ecommerce Demo Data",
        "host": os.getenv("SNOWFLAKE_ACCOUNT"),
        "database": os.getenv("SNOWFLAKE_DATABASE"),
        "username": os.getenv("SNOWFLAKE_USERNAME"),
        "privateKey": os.getenv("SNOWFLAKE_KEYPAIR"),
        "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE"),
        "queryTimeoutSeconds": 900
    }
    
    response = requests.post(
        f"{dest_base_url}/api/unstable/connections",
        headers=dest_headers,
        json=connection_payload
    )
    
    if response.status_code == 201:
        try:
            response_data = response.json()
            if response_data.get("success"):
                connection_id = response_data.get("data")
                return connection_id, None
            else:
                st.error("Connection creation was not successful")
                st.write("Response data:", response_data)  # Debug output
        except Exception as e:
            st.error(f"Failed to parse connection response: {str(e)}")
            st.write("Raw response:", response.text)  # Debug output
    else:
        st.error(f"Failed to create connection: {response.status_code} {response.text}")
    
    return None, None

def create_folder(folder_name: str) -> Tuple[Optional[str], Optional[str]]:
    """Create a new folder in Omni and return the folder ID and path."""
    payload = {
        "name": folder_name,
        "scope": "organization"  # Setting organization-wide scope as per documentation
    }
    
    response = requests.post(
        f"{st.session_state.dest_env}/api/unstable/folders",
        headers=st.session_state.dest_headers,
        json=payload
    )
    
    if response.status_code in [200, 201]:  # Accept both 200 and 201 as success
        try:
            folder_data = response.json()
            if isinstance(folder_data, dict):
                created_folder_id = folder_data.get("id")
                folder_path = folder_data.get("path")
                if created_folder_id and folder_path:
                    st.info(f"Created folder '{folder_name}' with path: {folder_path}")
                    return created_folder_id, folder_path
            
            st.error("Folder response missing ID or path")
            st.write("Response data:", folder_data)  # Debug output
        except Exception as e:
            st.error(f"Failed to parse response: {str(e)}")
            st.write("Raw response:", response.text)
        return None, None
    else:
        st.error(f"Failed to create folder: {response.text}")
        return None, None

def get_folder_by_path(base_url: str, headers: dict, folder_path: str) -> Optional[str]:
    """Get folder ID by path using GET /v1/folders (docs.omni.co/api/folders/list-folders)."""
    folders_url = f"{base_url}/api/v1/folders"
    path_value = folder_path if folder_path.startswith("/") else f"/{folder_path}"
    path_normalized = path_value.strip("/").lower()

    def _match(folder: dict) -> bool:
        rec_path = (folder.get("path") or "").strip("/").lower()
        return rec_path == path_normalized or rec_path.endswith("/" + path_normalized)

    # Try path filter first (path supports wildcards: blob-sales/* or blob-sales/**)
    for path_param in [path_normalized, path_value, f"{path_normalized}/*"]:
        resp = requests.get(
            folders_url, headers=headers,
            params={"path": path_param, "pageSize": 100, "scope": "organization"}
        )
        if resp.ok:
            try:
                data = resp.json()
                records = data.get("records", []) if isinstance(data, dict) else []
                for folder in records:
                    if isinstance(folder, dict) and _match(folder):
                        return folder.get("id")
                if records and path_param == path_normalized:
                    return records[0].get("id")
            except Exception:
                pass

    cursor = None
    while True:
        params = {"pageSize": 100, "scope": "organization"}
        if cursor:
            params["cursor"] = cursor
        response = requests.get(folders_url, headers=headers, params=params)
        if not response.ok:
            st.error(f"Failed to list folders: {response.status_code} {response.text}")
            return None
        try:
            payload = response.json()
            records = payload.get("records", []) if isinstance(payload, dict) else []
            for folder in records:
                if isinstance(folder, dict) and _match(folder):
                    return folder.get("id")
            page_info = payload.get("pageInfo", {}) or {}
            cursor = page_info.get("nextCursor")
            if not page_info.get("hasNextPage") or not cursor:
                break
        except Exception:
            st.error("Failed to parse folders response")
            return None

    st.error(f"Folder not found: '{path_value}'")
    return None

def list_source_folder_document_ids(folder_slug: str) -> list[str]:
    """List all document IDs in a source folder. Uses GET /v1/folders then GET /v1/documents."""
    folder_id = get_folder_by_path(SOURCE_BASE_URL, SOURCE_HEADERS, folder_slug)
    if not folder_id:
        st.error(f"Could not find source folder '{folder_slug}'.")
        return []
    return list_document_ids_in_folder(SOURCE_BASE_URL, SOURCE_HEADERS, folder_id)

def migrate_dashboards(folder_id: str, folder_path: str, target_model_id: str):
    """Download dashboards from source omni-examples folder and migrate them to destination."""
    with st.spinner("Fetching document list from source folder 'omni-examples'..."):
        document_ids = list_source_folder_document_ids("omni-examples")

    if not document_ids:
        st.error("No documents found in source folder — skipping dashboard migration.")
        return

    for doc_id in document_ids:
        get_url = f"{SOURCE_BASE_URL}/api/unstable/documents/{doc_id}/export"
        response = requests.get(get_url, headers=SOURCE_HEADERS)
        
        if not response.ok:
            st.error(f"Failed to fetch document {doc_id}: {response.text}")  # Log the response text
            continue
        
        try:
            export_data = response.json()
            import_payload = {
                "baseModelId": target_model_id,
                "dashboard": export_data.get("dashboard"),
                "document": export_data.get("document"),
                "workbookModel": export_data.get("workbookModel"),
                "exportVersion": "0.1",
                "folderPath": folder_path
            }
            
            missing_objects = [key for key in ["dashboard", "document", "workbookModel"] if not import_payload[key]]
            if missing_objects:
                st.error(f"Missing required objects in export data for document {doc_id}: {missing_objects}")
                continue
            
        except Exception as e:
            st.error(f"Failed to parse document {doc_id}: {str(e)}")
            continue
        
        import_url = f"{st.session_state.dest_env}/api/unstable/documents/import"
        dest_response = requests.post(import_url, headers=st.session_state.dest_headers, json=import_payload)
        
        if dest_response.ok:
            st.success(f"Successfully migrated document {doc_id}")
        else:
            st.error(f"Failed to migrate document {doc_id}: {dest_response.text}")  # Log the response text

def copy_model_code(target_model_id: str):
    """Copy model code from source to destination using the migration endpoint."""
    try:
        model_source_base_url = f"https://{st.session_state.model_source_env}"
        origin_model_id = st.session_state.model_origin_id
        model_source_headers = st.session_state.model_source_headers

        migration_url = f"{model_source_base_url}/api/unstable/model/{origin_model_id}/migrate"
        payload = {
            "gitRef": "origin/main",
            "targetModelId": target_model_id,
            "targetEnvironment": st.session_state.dest_env.replace("https://", "")
        }

        st.write("Migration URL:", migration_url)
        st.write("Payload:", payload)

        response = requests.post(migration_url, headers=model_source_headers, json=payload, timeout=30)
        
        if response.ok:
            st.success("✅ Model code migration completed successfully")
        else:
            st.warning(f"Migration endpoint failed: {response.text}")
            st.info("⚠️ Model code migration skipped - you may need to manually copy the model code")
            
    except Exception as e:
        st.error(f"Error during model migration: {str(e)}")
        st.info("⚠️ Model code migration skipped - you may need to manually copy the model code")

def create_model(dest_base_url: str, dest_headers: dict, model_name: str, connection_id: str, model_kind: str) -> Optional[str]:
    """Create a new model and return the model ID."""
    model_payload = {
        "connectionId": connection_id,
        "modelKind": model_kind,
        "modelName": model_name
    }

    # Log the curl request for debugging
    curl_command = (
        f"curl -L -X POST '{dest_base_url}/api/unstable/models' "
        f"-H 'Content-Type: application/json' "
        f"-H 'Authorization: {dest_headers['Authorization']}' "  # Ensure the full header is used
        f"--data-raw '{json.dumps(model_payload)}'"
    )
    st.write("Curl Request for Shared Model Creation:")
    st.code(curl_command)

    st.write("Endpoint URL:", f"{dest_base_url}/api/unstable/models")

    response = requests.post(
        f"{dest_base_url}/api/unstable/models",
        headers=dest_headers,
        json=model_payload
    )
    
    if response.status_code == 200:
        try:
            response_data = response.json()
            model_id = response_data.get("model", {}).get("id")
            return model_id
        except Exception as e:
            st.error(f"Failed to parse model creation response: {str(e)}")
            st.write("Raw response:", response.text)
    else:
        st.error(f"Failed to create model: {response.status_code} {response.text}")
        st.write("Request payload:", model_payload)  # Log the payload for debugging
    
    return None

def refresh_schema(dest_base_url: str, dest_headers: dict, model_id: str) -> bool:
    """Refresh the schema of the specified model."""
    refresh_url = f"{dest_base_url}/api/v0/model/{model_id}/refresh"
    response = requests.post(refresh_url, headers=dest_headers)
    
    if response.status_code == 200:
        st.success(f"✅ Schema refresh started for model ID: {model_id}")
        return True
    else:
        st.error(f"Failed to refresh schema for model ID {model_id}: {response.text}")
        return False

def build_destination_env(destination_input: str) -> str:
    """Build destination base URL with fixed omniapp.co domain."""
    cleaned = destination_input.strip().replace("https://", "").replace("http://", "")

    if cleaned.endswith(".omniapp.co"):
        cleaned = cleaned[:-len(".omniapp.co")]
    elif cleaned.endswith(".playground.exploreomni.dev"):
        cleaned = cleaned[:-len(".playground.exploreomni.dev")]

    return f"https://{cleaned}.omniapp.co"

def main():
    st.title("Omni Migration Tool")

    # --- Session state initialisation ---
    for key, default in [
        ("region", None),
        ("model_source_env", None),
        ("model_origin_id", None),
        ("model_source_api_key", None),
        ("model_source_headers", None),
        ("api_key_created", None),
        ("setup_complete", False),
        ("connection_created", False),
        ("migration_started", False),
        ("dest_env", None),
        ("dest_headers", None),
        ("shared_model_id", None),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default

    # ── Step 1: Region ────────────────────────────────────────────────────────
    if not st.session_state.region:
        st.subheader("Step 1: Select your region")
        region = st.radio(
            "Is the target Omni instance in North America or EMEA?",
            options=list(REGION_CONFIG.keys()),
            index=None,
        )
        if region:
            cfg = REGION_CONFIG[region]
            st.session_state.region = region
            st.session_state.model_source_env = cfg["model_source_env"]
            st.session_state.model_origin_id = cfg["origin_model_id"]
            st.rerun()
        return

    # ── Step 2: Source model API key ─────────────────────────────────────────
    if not st.session_state.setup_complete:
        env_host = st.session_state.model_source_env
        env_url = f"https://{env_host}"
        api_keys_url = f"{env_url}/keys/organization"

        st.subheader("Step 2: Source model API key")
        st.caption(f"Region: **{st.session_state.region}** · Source environment: `{env_host}`")

        # 2a: Have you created an API key yet?
        if st.session_state.api_key_created is None:
            st.write(f"Have you already created an API key in **{env_host}**?")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Yes, I have one"):
                    st.session_state.api_key_created = True
                    st.rerun()
            with col2:
                if st.button("❌ No, not yet"):
                    st.session_state.api_key_created = False
                    st.rerun()
            return

        # 2b: If they haven't created one, point them there first
        if not st.session_state.api_key_created:
            st.warning(
                f"You'll need to create an API key in **{env_host}** before continuing."
            )
            st.markdown(
                f"👉 [Open API key settings in {env_host}]({api_keys_url})"
            )
            st.write("Once you've created the key, paste it below.")

        # 2c: Input field for the key (shown regardless of yes/no path)
        api_key_input = st.text_input(
            f"API key for `{env_host}`",
            type="password",
            key="model_source_api_key_input",
        )

        if api_key_input:
            if st.button("Save & continue →"):
                st.session_state.model_source_api_key = api_key_input
                st.session_state.model_source_headers = {
                    "Authorization": f"Bearer {api_key_input}",
                    "Content-Type": "application/json",
                }
                st.session_state.setup_complete = True
                st.rerun()
            else:
                st.info("⚠️ Make sure you've saved your API key somewhere safe — you won't be able to see it again after leaving that page!")
        return

    # ── Step 3: Destination subdomain + API key ───────────────────────────────
    st.subheader("Step 3: Destination environment")
    st.caption(
        f"Region: **{st.session_state.region}** · "
        f"Source model: `{st.session_state.model_source_env}`"
    )

    col1, col2 = st.columns(2)
    with col1:
        destination_subdomain = st.text_input("Destination Subdomain")
    with col2:
        destination_api_key = st.text_input("Destination API Key", type="password")

    if destination_subdomain and destination_api_key:
        if not st.session_state.dest_env:
            st.session_state.dest_env = build_destination_env(destination_subdomain)
            st.session_state.dest_headers = {
                "Authorization": f"Bearer {destination_api_key}",
                "Content-Type": "application/json",
            }

        if not st.session_state.connection_created:
            if st.button("Create Connection"):
                # Step 0: Create connection
                with st.spinner("Creating connection..."):
                    connection_id, _ = create_connection(st.session_state.dest_env, st.session_state.dest_headers)
                    if connection_id:
                        st.session_state.connection_created = True
                        st.success("✅ Connection created successfully")

                        # Step 1: Create model with modelKind SCHEMA
                        with st.spinner("Creating SCHEMA model..."):
                            schema_model_id = create_model(st.session_state.dest_env, st.session_state.dest_headers, "My Schema Model", connection_id, model_kind="SCHEMA")
                            if schema_model_id:
                                st.success(f"✅ SCHEMA model created successfully with ID: {schema_model_id}")
                                
                                # Step 2: Refresh the schema for the SCHEMA model
                                if refresh_schema(st.session_state.dest_env, st.session_state.dest_headers, schema_model_id):
                                    # Wait for 20 seconds before creating the SHARED model
                                    st.spinner("Waiting for 20 seconds before creating SHARED model...")
                                    time.sleep(20)  # Wait for 20 seconds
                                    
                                    # Step 3: Create model with modelKind SHARED
                                    with st.spinner("Creating SHARED model..."):
                                        shared_model_id = create_model(
                                            st.session_state.dest_env,
                                            st.session_state.dest_headers,
                                            "My New Model",
                                            connection_id,
                                            model_kind="SHARED"
                                        )
                                        if shared_model_id:
                                            st.session_state.shared_model_id = shared_model_id  # Store shared model ID in session state
                                            st.success(f"✅ SHARED model created successfully with ID: {shared_model_id}")
                                            
                                            # Automatically start migration after model creation
                                            st.spinner("Creating folder...")
                                            folder_id, folder_path = create_folder("Omni Examples")
                                            if not folder_id or not folder_path:
                                                st.error("Failed to create folder")
                                                return
                                            st.success("✅ Folder created successfully")
                                            
                                            # Migrate dashboards
                                            st.spinner("Migrating dashboards...")
                                            migrate_dashboards(folder_id, folder_path, shared_model_id)  # Use shared model ID

                                            # List folder documents and apply labels after migration.
                                            st.spinner("Listing folder documents for labeling...")
                                            folder_document_ids = list_document_ids_in_folder(
                                                st.session_state.dest_env,
                                                st.session_state.dest_headers,
                                                folder_id
                                            )
                                            if folder_document_ids:
                                                st.spinner("Applying labels to folder documents...")
                                                apply_labels_to_documents(folder_document_ids)
                                            
                                            # Migrate model code
                                            st.spinner("Migrating model code...")
                                            copy_model_code(shared_model_id)  # Use shared model ID
                                            
                                            st.success("🎉 Migration process completed!")
                                            st.balloons()
                                            st.info(
                                                "Please dont forget to go back into Omni and update Peter to an Org Admin"
                                            )
                                        else:
                                            st.error("Failed to create SHARED model")
                                            return
                            else:
                                st.error("Failed to create SCHEMA model")
                                return
                    else:
                        st.error("Failed to create connection")
                        return
        
        # Show these elements if connection is created
        if st.session_state.connection_created:
            st.success("✅ Connection active")
            if st.session_state.shared_model_id:
                st.write(f"Using SHARED Model ID: {st.session_state.shared_model_id}")
            else:
                st.text_input("Target Model ID", 
                                          help="The ID of the model in the destination environment",
                                          key="model_id_input")
    else:
        st.info("Please enter both the destination subdomain and API key to continue.")

if __name__ == "__main__":
    main() 