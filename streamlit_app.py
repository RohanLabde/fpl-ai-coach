import streamlit as st
import pandas as pd

from data.fpl_api import get_fpl_data


st.set_page_config(
    page_title="FPL AI Coach",
    page_icon="⚽",
    layout="wide"
)

st.title("⚽ FPL AI Coach")

st.subheader("Player Database")


try:

    data = get_fpl_data()

    players = pd.DataFrame(data["elements"])

    st.success(
        f"Successfully loaded {len(players)} players."
    )

    columns = [
        "id",
        "first_name",
        "second_name",
        "now_cost",
        "total_points",
        "form",
        "selected_by_percent"
    ]

    st.dataframe(
        players[columns],
        use_container_width=True
    )


except Exception as e:

    st.error(
        f"Something went wrong: {e}"
    )
