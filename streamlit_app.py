import streamlit as st
import pandas as pd

from data.model import (
    get_feature_importance,
    get_grouped_permutation_importance,
    get_permutation_importance,
    get_position_validation,
    predict_next_gameweek,
    train_and_evaluate,
    train_final_model,
)

from data.fixture_engine import (
    get_team_fixture_horizon,
    summarize_fixture_horizon,
    build_fixture_features,
    attach_fixture_features
)

from data.historical import (
    load_historical_data,
    load_team_mapping,
    create_team_mapping,
    prepare_historical_data,
    prepare_database_records
)

from data.db import (
    get_database_connection,
    save_players,
    save_historical_data,
    save_prediction_features
)

from data.fpl_api import get_fpl_data, get_fixtures
from data.fpl_data import get_players

from data.features import (
    build_team_gameweek_calendar,
    build_player_gameweek_data,
    build_form_features
)


HISTORICAL_2025_26_URL = (
    "https://raw.githubusercontent.com/"
    "imadeddine-belkat/Premier-League-Stats/"
    "main/fpl_scraper/fpl_stats/_merged/players/"
    "2025-26_all_players_gw.csv"
)

HISTORICAL_SEASON = "2025-26"


st.set_page_config(
    page_title="FPL AI Coach",
    page_icon="⚽",
    layout="wide"
)

st.title("⚽ FPL AI Coach")


# ============================================================
# FPL DATA
# ============================================================

st.subheader("FPL Data")

if st.button("🔄 Update Player Database"):
    try:

        with st.spinner("Downloading latest FPL data..."):
            data = get_fpl_data()

        players = get_players(data)

        with st.spinner("Saving players to database..."):
            save_players(players)

        st.success(
            f"Successfully updated {len(players)} players!"
        )

    except Exception as e:

        st.error(
            f"Something went wrong: {e}"
        )


# ============================================================
# DATABASE CHECK
# ============================================================

try:

    conn = get_database_connection()

    result = conn.query(
        "SELECT COUNT(*) AS player_count FROM players",
        ttl=0
    )

    player_count = result.iloc[0]["player_count"]

    st.metric(
        "Players in database",
        player_count
    )

except Exception as e:

    st.error(
        f"Could not read database: {e}"
    )


# ============================================================
# HISTORICAL DATA TEST
# ============================================================

if st.button("📚 Test Historical Data"):

    try:

        with st.spinner(
            "Downloading 2025/26 historical data..."
        ):

            historical = pd.read_csv(
                HISTORICAL_2025_26_URL
            )

        st.success(
            "Historical data downloaded successfully!"
        )

        st.write(
            "Rows:",
            len(historical)
        )

        st.write(
            "Columns:"
        )

        st.write(
            historical.columns.tolist()
        )

        st.dataframe(
            historical.head(10),
            use_container_width=True
        )

    except Exception as e:

        st.error(
            f"Historical data download failed: {e}"
        )


# ============================================================
# TEAM MAPPING TEST
# ============================================================

st.subheader("Team Mapping Test")

if st.button("🔎 Test Team Mapping"):

    try:

        with st.spinner(
            "Downloading team mapping..."
        ):

            team_data = load_team_mapping()

        teams = create_team_mapping(
            team_data
        )

        st.success(
            f"Successfully loaded {len(teams)} teams!"
        )

        st.dataframe(
            teams,
            use_container_width=True
        )

    except Exception as e:

        st.error(
            f"Team mapping failed: {e}"
        )


# ============================================================
# HISTORICAL DATA JOIN TEST
# ============================================================

st.subheader("Historical Data Join Test")

if st.button("🔗 Test Player + Fixture Join"):

    try:

        with st.spinner(
            "Downloading historical datasets..."
        ):

            players, fixtures = (
                load_historical_data()
            )

            team_data = load_team_mapping()

            teams = create_team_mapping(
                team_data
            )

        with st.spinner(
            "Joining player, fixture and team data..."
        ):

            historical = prepare_historical_data(
                players,
                fixtures,
                teams
            )

        st.success(
            "Historical data joined successfully!"
        )

        col1, col2, col3, col4 = st.columns(4)

        col1.metric(
            "Player rows",
            len(historical)
        )

        col2.metric(
            "Gameweeks",
            historical["gameweek"].nunique()
        )

        col3.metric(
            "Fixtures",
            historical["fixture_id"].nunique()
        )

        col4.metric(
            "Missing fixtures",
            historical["fixture_id"].isna().sum()
        )

        st.subheader(
            "Historical Data Preview"
        )

        preview_columns = [
            "season",
            "gameweek",
            "player_id",
            "player_name",
            "position",
            "team_id",
            "team_name",
            "fixture_id",
            "opponent_team_id",
            "was_home",
            "fixture_difficulty",
            "minutes",
            "total_points",
            "goals_scored",
            "assists",
            "expected_goals",
            "expected_assists"
        ]

        st.dataframe(
            historical[
                preview_columns
            ].head(20),
            use_container_width=True
        )

    except Exception as e:

        st.error(
            f"Historical join failed: {e}"
        )


# ============================================================
# TEAM × GAMEWEEK CALENDAR TEST
# ============================================================

st.subheader(
    "Team × Gameweek Calendar Test"
)

if st.button(
    "📅 Validate Team × Gameweek Calendar"
):

    try:

        with st.spinner(
            "Building Team × Gameweek calendar..."
        ):

            players, fixtures = (
                load_historical_data()
            )

            calendar = build_team_gameweek_calendar(
                fixtures,
                season=HISTORICAL_SEASON
            )

        st.success(
            "Team × Gameweek calendar created successfully!"
        )

        calendar_rows = len(calendar)
        gameweeks = calendar["gameweek"].nunique()
        teams = calendar["team_id"].nunique()

        bgw_rows = int(
            (
                calendar["gameweek_type"] == "BGW"
            ).sum()
        )

        dgw_rows = int(
            (
                calendar["gameweek_type"] == "DGW"
            ).sum()
        )

        col1, col2, col3, col4, col5 = st.columns(5)

        col1.metric(
            "Calendar rows",
            calendar_rows
        )

        col2.metric(
            "Gameweeks",
            gameweeks
        )

        col3.metric(
            "Teams",
            teams
        )

        col4.metric(
            "BGW team rows",
            bgw_rows
        )

        col5.metric(
            "DGW team rows",
            dgw_rows
        )

        st.subheader(
            "Gameweek Summary"
        )

        summary = (
            calendar
            .groupby(
                [
                    "season",
                    "gameweek",
                    "gameweek_type"
                ],
                as_index=False
            )
            .agg(
                team_count=(
                    "team_id",
                    "nunique"
                )
            )
            .sort_values(
                [
                    "gameweek",
                    "gameweek_type"
                ]
            )
        )

        st.dataframe(
            summary,
            use_container_width=True
        )

        st.subheader(
            "Calendar Preview"
        )

        st.dataframe(
            calendar.head(50),
            use_container_width=True
        )

    except Exception as e:

        st.error(
            f"Team × Gameweek calendar validation failed: {e}"
        )


# ============================================================
# PLAYER × GAMEWEEK CANONICALIZATION TEST
# ============================================================

st.subheader(
    "Player × Gameweek Canonicalization Test"
)

if st.button(
    "🧩 Test Player × Gameweek Canonicalization"
):

    try:

        with st.spinner(
            "Preparing historical data and calendar..."
        ):

            players, fixtures = (
                load_historical_data()
            )

            team_data = load_team_mapping()

            teams = create_team_mapping(
                team_data
            )

            historical = prepare_historical_data(
                players,
                fixtures,
                teams
            )

            calendar = build_team_gameweek_calendar(
                fixtures,
                season=HISTORICAL_SEASON
            )

        with st.spinner(
            "Building canonical Player × Gameweek dataset..."
        ):

            canonical = build_player_gameweek_data(
                historical,
                calendar
            )

        duplicate_count = int(
            canonical
            .duplicated(
                subset=[
                    "season",
                    "gameweek",
                    "player_id"
                ]
            )
            .sum()
        )

        dgw_player_rows = int(
            canonical[
                "is_double_gameweek"
            ].sum()
        )

        bgw_player_rows = int(
            canonical[
                "is_blank_gameweek"
            ].sum()
        )

        if duplicate_count > 0:

            st.error(
                "Player × Gameweek canonicalization "
                f"failed: {duplicate_count} duplicate keys."
            )

        else:

            st.success(
                "Player × Gameweek aggregation "
                "passed successfully!"
            )

        col1, col2, col3, col4 = st.columns(4)

        col1.metric(
            "Player × GW rows",
            len(canonical)
        )

        col2.metric(
            "Unique Player × GW",
            canonical[
                [
                    "season",
                    "gameweek",
                    "player_id"
                ]
            ]
            .drop_duplicates()
            .shape[0]
        )

        col3.metric(
            "BGW Player rows",
            bgw_player_rows
        )

        col4.metric(
            "DGW Player rows",
            dgw_player_rows
        )

        st.subheader(
            "Double Gameweek Summary"
        )

        dgw_summary = (
            canonical[
                canonical["is_double_gameweek"]
            ]
            .groupby(
                "gameweek",
                as_index=False
            )
            .agg(
                player_rows=(
                    "player_id",
                    "size"
                ),
                players=(
                    "player_id",
                    "nunique"
                )
            )
            .sort_values(
                "gameweek"
            )
        )

        st.dataframe(
            dgw_summary,
            use_container_width=True
        )

        st.subheader(
            "Player × Gameweek Preview"
        )

        preview_columns = [
            "season",
            "gameweek",
            "player_id",
            "player_name",
            "team_id",
            "team_name",
            "fixture_count",
            "minutes",
            "starts",
            "total_points",
            "expected_goals",
            "expected_assists",
            "expected_goal_involvements",
            "is_blank_gameweek",
            "is_double_gameweek"
        ]

        st.dataframe(
            canonical[
                preview_columns
            ].head(30),
            use_container_width=True
        )

        st.info(
            "This test validates the canonical Player × "
            "Gameweek layer. BGW rows are explicitly present "
            "with fixture_count = 0, while ordinary non-playing "
            "rows retain the distinction that a fixture existed."
        )

    except Exception as e:

        st.error(
            f"Player × Gameweek canonicalization failed: {e}"
        )


# ============================================================
# HISTORICAL DATABASE IMPORT
# ============================================================

st.subheader(
    "Historical Database Import"
)

if st.button(
    "💾 Import 2025/26 into Supabase"
):

    try:

        with st.spinner(
            "Downloading historical data..."
        ):

            players, fixtures = (
                load_historical_data()
            )

            team_data = load_team_mapping()

            teams = create_team_mapping(
                team_data
            )

        with st.spinner(
            "Preparing historical records..."
        ):

            historical = (
                prepare_historical_data(
                    players,
                    fixtures,
                    teams
                )
            )

            records = (
                prepare_database_records(
                    historical
                )
            )

        st.info(
            f"Ready to import {len(records):,} records."
        )

        with st.spinner(
            "Importing records into Supabase..."
        ):

            imported = save_historical_data(
                records
            )

        st.success(
            f"Successfully imported "
            f"{imported:,} historical records!"
        )

    except Exception as e:

        st.error(
            f"Historical import failed: {e}"
        )


# ============================================================
# PREDICTION FEATURE TEST
# ============================================================

st.subheader(
    "Prediction Feature Test"
)

if st.button(
    "🧠 Build Form Features"
):

    try:

        with st.spinner(
            "Preparing historical data..."
        ):

            players, fixtures = (
                load_historical_data()
            )

            team_data = load_team_mapping()

            teams = create_team_mapping(
                team_data
            )

            historical = (
                prepare_historical_data(
                    players,
                    fixtures,
                    teams
                )
            )

        with st.spinner(
            "Building Team × Gameweek calendar..."
        ):

            calendar = build_team_gameweek_calendar(
                fixtures,
                season=HISTORICAL_SEASON
            )

        with st.spinner(
            "Calculating form and fixture features..."
        ):

            features = build_form_features(
                historical,
                calendar
            )

            fixture_features = build_fixture_features(
                fixtures,
                season=HISTORICAL_SEASON,
            )

            features = attach_fixture_features(
                features,
                fixture_features,
            )

        # Do not allow a successful-looking rebuild to save empty new fields.
        # This is displayed before the database write for direct diagnosis.
        new_feature_columns = [
            "previous_gw_goals_scored",
            "rolling_3gw_goals_scored",
            "previous_gw_clean_sheets",
            "rolling_3gw_clean_sheets",
            "previous_gw_threat",
            "rolling_3gw_creativity",
            "rolling_3gw_xgi_per_90",
            "rolling_3gw_defensive_contribution",
            "next_1gw_team_avg_5fixture_goals_conceded",
            "next_1gw_opponent_avg_5fixture_goals_scored",
        ]

        missing_new_columns = [
            column
            for column in new_feature_columns
            if column not in features.columns
        ]
        if missing_new_columns:
            raise ValueError(
                "Feature build did not return required new columns: "
                f"{missing_new_columns}"
            )

        feature_population = pd.DataFrame(
            {
                "feature": new_feature_columns,
                "populated_rows": [
                    int(features[column].notna().sum())
                    for column in new_feature_columns
                ],
            }
        )

        st.subheader("New Feature Build Validation")
        st.dataframe(
            feature_population,
            use_container_width=True,
            hide_index=True,
        )

        empty_features = feature_population.loc[
            feature_population["populated_rows"].eq(0),
            "feature",
        ].tolist()
        if empty_features:
            raise ValueError(
                "New features are empty before database saving: "
                f"{empty_features}"
            )

        with st.spinner(
            "Saving prediction features to Supabase..."
        ):

            saved = save_prediction_features(
                features
            )

        st.success(
            f"Form features created and "
            f"{saved:,} rows saved to Supabase!"
        )

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Feature rows",
            len(features)
        )

        col2.metric(
            "Players",
            features["player_id"].nunique()
        )

        col3.metric(
            "Gameweeks",
            features["gameweek"].nunique()
        )

        st.subheader(
            "Prediction Feature Preview"
        )

        feature_preview_columns = [
            "gameweek",
            "player_name",
            "team_name",

            # Form
            "rolling_3gw_points",
            "rolling_5gw_points",

            # Underlying performance
            "rolling_3gw_xg",
            "rolling_3gw_xa",
            "rolling_3gw_xgi",

            # Playing time
            "previous_gw_minutes",
            "rolling_3gw_minutes",
            "rolling_5gw_minutes",

            "previous_gw_starts",
            "rolling_3gw_starts",
            "rolling_5gw_starts",

            "rolling_3gw_start_rate",
            "rolling_5gw_start_rate",

            # Target
            "next_gw_points"
        ]

        st.dataframe(
            features[
                feature_preview_columns
            ].head(30),
            use_container_width=True
        )

    except Exception as e:

        st.error(
            f"Feature engineering failed: {e}"
        )

st.divider()
st.header("Model Training & Backtesting")

st.caption(
    "The model predicts next calendar-gameweek points from information "
    "available at the end of the current gameweek. Evaluation uses only "
    "later gameweeks; it is never randomly split."
)

validation_gameweeks = st.slider(
    "Validation gameweeks",
    min_value=4,
    max_value=12,
    value=8,
    help=(
        "The latest completed gameweeks are held out for evaluation. "
        "Earlier rows are used for training."
    ),
)

if st.button("Train and evaluate next-GW model", type="primary"):
    try:
        with st.spinner("Loading validated prediction features..."):
            conn = get_database_connection()
            training_features = conn.query(
                "SELECT * FROM public.prediction_features",
                ttl=0,
            )

        with st.spinner("Training on earlier gameweeks and evaluating later ones..."):
            evaluation_model, evaluation, validation_results = (
                train_and_evaluate(
                    training_features,
                    validation_gameweeks=validation_gameweeks,
                )
            )
            feature_importance = get_feature_importance(evaluation_model)
            permutation_results = get_permutation_importance(
                evaluation_model,
                validation_results,
            )
            grouped_permutation_results = get_grouped_permutation_importance(
                evaluation_model,
                validation_results,
            )
            production_model = train_final_model(training_features)
            position_validation = get_position_validation(validation_results)

        st.session_state["fpl_production_model"] = production_model
        st.session_state["fpl_validation_results"] = validation_results
        st.session_state["fpl_model_evaluation"] = evaluation.to_dict()
        st.session_state["fpl_feature_importance"] = feature_importance
        st.session_state["fpl_permutation_importance"] = permutation_results
        st.session_state["fpl_grouped_permutation_importance"] = (
            grouped_permutation_results
        )
        st.session_state["fpl_position_validation"] = position_validation
        st.session_state["fpl_training_features"] = training_features

        st.success("Global Random Forest trained and temporally evaluated.")

    except Exception as error:
        st.error(f"Model training failed: {error}")


if "fpl_model_evaluation" in st.session_state:
    evaluation = st.session_state["fpl_model_evaluation"]

    st.subheader("Temporal Validation")
    st.caption(
        f"Held out {evaluation['validation_rows']:,} rows from "
        f"{evaluation['validation_season']} gameweek "
        f"{evaluation['validation_start_gameweek']} onward."
    )

    metric_1, metric_2, metric_3, metric_4 = st.columns(4)

    metric_1.metric("Model MAE", f"{evaluation['model_mae']:.3f}")
    metric_2.metric("Baseline MAE", f"{evaluation['baseline_mae']:.3f}")
    metric_3.metric("Model RMSE", f"{evaluation['model_rmse']:.3f}")
    metric_4.metric("Baseline RMSE", f"{evaluation['baseline_rmse']:.3f}")

    if evaluation["model_mae"] < evaluation["baseline_mae"]:
        st.success("The model beats the simple historical-mean baseline on the holdout period.")
    else:
        st.warning(
            "The model does not yet beat the baseline. Do not use it for "
            "transfer decisions until features or model selection improve."
        )

    if "fpl_feature_importance" in st.session_state:
        st.subheader("Model Feature Importance")
        st.caption(
            "This split-based Random Forest view can overstate correlated "
            "continuous features such as minutes. Use the held-out "
            "permutation results below as the primary comparison."
        )

        feature_importance = st.session_state["fpl_feature_importance"].copy()
        top_feature_importance = feature_importance.head(15)

        st.bar_chart(
            top_feature_importance.set_index("feature")["importance"],
            horizontal=True,
        )

        st.dataframe(
            top_feature_importance,
            use_container_width=True,
            hide_index=True,
            column_config={
                "importance": st.column_config.NumberColumn(
                    "Importance",
                    format="%.4f",
                ),
                "importance_pct": st.column_config.NumberColumn(
                    "Share of model importance (%)",
                    format="%.2f%%",
                ),
            },
        )

    if "fpl_permutation_importance" in st.session_state:
        st.subheader("Held-out Permutation Importance")
        st.caption(
            "Each feature is shuffled on unseen gameweeks. A larger positive "
            "MAE increase means the model loses more accuracy without it."
        )
        permutation_results = st.session_state[
            "fpl_permutation_importance"
        ].copy()
        top_permutation_results = permutation_results.head(20)
        st.bar_chart(
            top_permutation_results.set_index("feature")["mae_increase"],
            horizontal=True,
        )
        st.dataframe(
            top_permutation_results,
            use_container_width=True,
            hide_index=True,
            column_config={
                "mae_increase": st.column_config.NumberColumn(
                    "Held-out MAE increase",
                    format="%.4f",
                ),
                "mae_increase_std": st.column_config.NumberColumn(
                    "Variation across shuffles",
                    format="%.4f",
                ),
            },
        )

    if "fpl_grouped_permutation_importance" in st.session_state:
        st.subheader("Feature Group Impact")
        st.caption(
            "Related features are shuffled together. This shows whether "
            "availability, attacking data, defensive data, or fixture context "
            "matters most on the holdout period."
        )
        grouped_results = st.session_state[
            "fpl_grouped_permutation_importance"
        ].copy()
        st.bar_chart(
            grouped_results.set_index("feature_group")["mae_increase"],
            horizontal=True,
        )
        st.dataframe(
            grouped_results,
            use_container_width=True,
            hide_index=True,
            column_config={
                "mae_increase": st.column_config.NumberColumn(
                    "Held-out MAE increase",
                    format="%.4f",
                ),
                "mae_increase_std": st.column_config.NumberColumn(
                    "Variation across shuffles",
                    format="%.4f",
                ),
            },
        )

    if "fpl_position_validation" in st.session_state:
        st.subheader("Position-by-Position Validation")
        st.caption(
            "Accuracy is reported separately for each FPL position, so a good "
            "overall score cannot hide weaker defender or attacker predictions."
        )
        st.dataframe(
            st.session_state["fpl_position_validation"],
            use_container_width=True,
            hide_index=True,
            column_config={
                "mae": st.column_config.NumberColumn("MAE", format="%.3f"),
                "rmse": st.column_config.NumberColumn("RMSE", format="%.3f"),
                "actual_points_per_gw": st.column_config.NumberColumn(
                    "Actual points / GW",
                    format="%.3f",
                ),
                "predicted_points_per_gw": st.column_config.NumberColumn(
                    "Predicted points / GW",
                    format="%.3f",
                ),
            },
        )

    st.subheader("Held-out Predictions")

    validation_results = st.session_state["fpl_validation_results"].copy()
    validation_results["absolute_error"] = validation_results[
        "prediction_error"
    ].abs()

    held_out_display_columns = [
        "season",
        "gameweek",
        "player_id",
        "player_name",
        "position",
        "team_id",
        "team_name",
        "next_gw_points",
        "predicted_next_gw_points",
        "prediction_error",
        "absolute_error",
    ]

    st.dataframe(
        validation_results[held_out_display_columns].sort_values(
            "absolute_error",
            ascending=False,
        ),
        use_container_width=True,
        hide_index=True,
    )


if "fpl_production_model" in st.session_state:
    st.subheader("Score Historical Feature Rows")
    st.caption(
        "This is an exploratory scoring view. Live recommendations require "
        "an unlabelled current-gameweek feature row, which is the next build step."
    )

    score_frame = st.session_state["fpl_training_features"].copy()

    seasons = sorted(score_frame["season"].dropna().astype(str).unique())
    selected_season = st.selectbox("Season", seasons, key="model_score_season")

    season_rows = score_frame[
        score_frame["season"].astype(str) == selected_season
    ]

    available_gameweeks = sorted(
        season_rows["gameweek"].dropna().astype(int).unique()
    )

    selected_gameweek = st.selectbox(
        "Feature gameweek",
        available_gameweeks,
        index=len(available_gameweeks) - 1,
        key="model_score_gameweek",
    )

    rows_to_score = season_rows[
        season_rows["gameweek"].eq(selected_gameweek)
    ].copy()

    scored_rows = predict_next_gameweek(
        st.session_state["fpl_production_model"],
        rows_to_score,
    )

    st.dataframe(
        scored_rows[
            [
                "player_name",
                "position",
                "team_name",
                "predicted_next_gw_points",
            ]
        ].sort_values(
            "predicted_next_gw_points",
            ascending=False,
        ),
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# FIXTURE HORIZON TEST
# ============================================================

st.divider()

st.header(
    "Fixture Horizon Test"
)

if st.button(
    "🔮 Test Arsenal Fixture Horizon"
):

    try:

        test_team_id = 1
        test_current_gameweek = 10

        fixtures = pd.DataFrame(
            get_fixtures()
        )

        fixture_horizon = get_team_fixture_horizon(
            fixtures,
            team_id=test_team_id,
            current_gameweek=test_current_gameweek,
            horizon=5
        )

        st.subheader(
            "Arsenal — Next 5 Gameweeks"
        )

        st.dataframe(
            fixture_horizon,
            use_container_width=True
        )

        summary = summarize_fixture_horizon(
            fixtures,
            team_id=test_team_id,
            current_gameweek=test_current_gameweek
        )

        st.subheader(
            "Fixture Summary"
        )

        st.json(
            summary
        )

    except Exception as e:

        st.error(
            f"Fixture horizon test failed: {e}"
        )


# ============================================================
# FIXTURE FEATURE TEST
# ============================================================

st.header(
    "Fixture Feature Test"
)

if st.button(
    "🧪 Build Fixture Features"
):

    try:

        fixtures = pd.DataFrame(
            get_fixtures()
        )

        fixture_features = build_fixture_features(
            fixtures
        )

        st.success(
            "Fixture features created successfully!"
        )

        st.write(
            f"Rows: {len(fixture_features)}"
        )

        st.dataframe(
            fixture_features.head(20),
            use_container_width=True
        )

    except Exception as e:

        st.error(
            f"Fixture feature engineering failed: {e}"
        )
