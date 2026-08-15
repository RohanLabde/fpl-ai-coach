import streamlit as st

from data.fpl_api import get_fpl_data


st.set_page_config(
    page_title="FPL AI Coach",
    page_icon="⚽",
    layout="wide"
)

st.title("⚽ FPL AI Coach")

st.subheader("FPL Data Connection")

try:
    data = get_fpl_data()

    st.success("Successfully connected to the FPL API!")

    st.write("Number of players:", len(data["elements"]))
    st.write("Number of teams:", len(data["teams"]))

except Exception as e:
    st.error(f"Something went wrong: {e}")
