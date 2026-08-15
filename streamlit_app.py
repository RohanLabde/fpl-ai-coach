import streamlit as st

st.set_page_config(
    page_title="FPL AI Coach",
    page_icon="⚽",
    layout="wide"
)

st.title("⚽ FPL AI Coach")

st.subheader("Your personal FPL decision engine")

st.write(
    "This application will analyse my FPL team "
    "and recommend the best transfers."
)

st.success("Application is running!")
