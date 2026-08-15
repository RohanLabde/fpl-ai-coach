import streamlit as st


def get_database_connection():

    return st.connection(
        "fpl_db",
        type="sql"
    )
