import streamlit as st


def get_database_connection():

    return st.connection(
        "fpl_db",
        type="sql"
    )


def save_players(players):

    conn = get_database_connection()

    for _, player in players.iterrows():

        conn.session.execute(
            """
            INSERT INTO players (
                player_id,
                first_name,
                second_name,
                team_id,
                team_name,
                position,
                price,
                total_points,
                form,
                selected_by_percent
            )
            VALUES (
                :player_id,
                :first_name,
                :second_name,
                :team_id,
                :team_name,
                :position,
                :price,
                :total_points,
                :form,
                :selected_by_percent
            )
            ON CONFLICT (player_id)
            DO UPDATE SET
                first_name = EXCLUDED.first_name,
                second_name = EXCLUDED.second_name,
                team_id = EXCLUDED.team_id,
                team_name = EXCLUDED.team_name,
                position = EXCLUDED.position,
                price = EXCLUDED.price,
                total_points = EXCLUDED.total_points,
                form = EXCLUDED.form,
                selected_by_percent = EXCLUDED.selected_by_percent
            """,
            {
                "player_id": int(player["id"]),
                "first_name": player["first_name"],
                "second_name": player["second_name"],
                "team_id": int(player["team"]),
                "team_name": player["team_name"],
                "position": player["position"],
                "price": float(player["price"]),
                "total_points": int(player["total_points"]),
                "form": float(player["form"] or 0),
                "selected_by_percent": float(
                    player["selected_by_percent"] or 0
                )
            }
        )

    conn.session.commit()
