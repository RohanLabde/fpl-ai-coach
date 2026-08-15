import streamlit as st


st.set_page_config(
    page_title="FPL AI Coach",
    page_icon="⚽",
    layout="wide"
)

st.title("⚽ FPL AI Coach")

st.subheader("Database Connection")


try:

    conn = st.connection(
        "fpl_db",
        type="sql"
    )

    result = conn.query(
        "SELECT COUNT(*) AS player_count FROM players",
        ttl=0
    )

    player_count = result.iloc[0]["player_count"]

    st.success("Successfully connected to Supabase!")

    st.metric(
        "Players in database",
        player_count
    )


except Exception as e:

    st.error(
        f"Database connection failed: {e}"
    )
