import streamlit as st

from data.database import DB_PATH, database_exists, initialize_database

st.set_page_config(
    page_title="資産形成ナビ",
    page_icon="📈",
    layout="wide",
)

if not database_exists(DB_PATH):
    initialize_database(DB_PATH)

# The app root is the Dashboard. Streamlit's multipage navigation remains in
# the sidebar, while opening the app always lands on the main overview.
st.switch_page("pages/1_Dashboard.py")
