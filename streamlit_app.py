import streamlit as st

from data.fpl_api import get_fpl_data


st.set_page_config(
    page_title="FPL AI Coach",
    page_icon="⚽",
    layout="wide"
)

st.title("⚽ FPL AI Coach")

st.subheader("FPL API Structure")

try:

    data = get_fpl_data()

    st.success("Successfully connected to the FPL API!")

    st.write("Available data sections:")

    for key in data.keys():
        st.write(f"- {key}")

except Exception as e:

    st.error(f"Something went wrong: {e}")
