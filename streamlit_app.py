import streamlit as st
from omni_migration_app import main

# Set page configuration
st.set_page_config(
    page_title="Omni Migration Tool",
    page_icon="🔄",
    layout="wide"
)

# Run the main application
main() 