"""Streamlit entry point for the FPL Copilot."""

import streamlit as st

from data.fpl_copilot import render_fpl_copilot


st.set_page_config(
    page_title="FPL Copilot",
    page_icon="⚽",
    layout="centered",
)

render_fpl_copilot()
