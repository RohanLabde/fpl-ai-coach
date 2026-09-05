"""Training and inference for the FPL next-gameweek-points model.

The input is the canonical public.prediction_features table.  Every feature
is known at the end of its row's gameweek; next_gw_points is the label.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


TARGET_COLUMN = "next_gw_points"
GRADIENT_BOOSTING_MODEL_NAME = "Gradient Boosting"
IDENTIFIER_COLUMNS = ["season", "gameweek", "player_id", "player_name", "team_id", "team_name"]
ADDITIONAL_PLAYER_METRICS = [
    "goals_scored",
    "assists",
    "clean_sheets",
    "bonus",
    "threat",
    "creativity",
    "defensive_contribution",
]
ADDITIONAL_PLAYER_FEATURE_COLUMNS = [
    f"previous_gw_{metric}"
    for metric in ADDITIONAL_PLAYER_METRICS
] + [
    f"rolling_{window}gw_{metric}"
    for metric in ADDITIONAL_PLAYER_METRICS
    for window in (3, 5, 10)
] + [
    f"rolling_{window}gw_{metric}_per_90"
    for window in (3, 5)
    for metric in (
        "xgi",
        "goals_scored",
        "assists",
        "threat",
        "creativity",
        "defensive_contribution",
    )
]
TEAM_CONTEXT_FEATURE_COLUMNS = [
    "next_1gw_team_avg_5fixture_goals_conceded",
    "next_1gw_team_avg_5fixture_clean_sheet_rate",
    "next_1gw_opponent_avg_5fixture_goals_scored",
]
NUMERIC_FEATURE_COLUMNS = [
    "previous_gw_points", "rolling_3gw_points", "rolling_5gw_points", "rolling_10gw_points",
    "previous_gw_xg", "rolling_3gw_xg", "rolling_5gw_xg", "rolling_10gw_xg",
    "previous_gw_xa", "rolling_3gw_xa", "rolling_5gw_xa", "rolling_10gw_xa",
    "previous_gw_xgi", "rolling_3gw_xgi", "rolling_5gw_xgi", "rolling_10gw_xgi",
    "previous_gw_minutes", "rolling_3gw_minutes", "rolling_5gw_minutes", "rolling_10gw_minutes",
    "previous_gw_played", "previous_gw_60_minute_appearance",
    "previous_gw_starts", "rolling_3gw_starts", "rolling_5gw_starts", "rolling_10gw_starts",
    "rolling_3gw_start_rate", "rolling_5gw_start_rate", "rolling_10gw_start_rate",
    "rolling_3gw_minutes_per_fixture", "rolling_5gw_minutes_per_fixture",
    "rolling_10gw_minutes_per_fixture", "rolling_3gw_play_rate",
    "rolling_5gw_play_rate", "rolling_10gw_play_rate",
    "rolling_3gw_60_minute_appearance_rate",
    "rolling_5gw_60_minute_appearance_rate",
    "rolling_10gw_60_minute_appearance_rate",
    "minutes_trend_3gw_vs_10gw", "start_rate_trend_3gw_vs_10gw",
    "expected_minutes_per_fixture", "expected_minutes_next_gw",
    "next_1gw_fixture_count", "next_1gw_avg_fdr",
    "next_1gw_home_count", "next_1gw_away_count",
    "next_1gw_opponent_avg_5fixture_goals_conceded",
    "next_1gw_opponent_avg_5fixture_clean_sheet_rate",
] + ADDITIONAL_PLAYER_FEATURE_COLUMNS + TEAM_CONTEXT_FEATURE_COLUMNS
CATEGORICAL_FEATURE_COLUMNS = ["position"]
MODEL_FEATURE_COLUMNS = NUMERIC_FEATURE_COLUMNS + CATEGORICAL_FEATURE_COLUMNS

AVAILABILITY_FEATURE_COLUMNS = [
    column
    for column in NUMERIC_FEATURE_COLUMNS
    if any(
        token in column
        for token in (
            "minutes", "starts", "start_rate", "play_rate",
            "appearance_rate", "played",
        )
    )
]
CORE_FORM_FEATURE_COLUMNS = [
    column
    for column in NUMERIC_FEATURE_COLUMNS
    if any(token in column for token in ("points", "_xg", "_xa", "_xgi"))
]
ATTACKING_FEATURE_COLUMNS = [
    column
    for column in ADDITIONAL_PLAYER_FEATURE_COLUMNS
    if any(
        token in column
        for token in ("goals_scored", "assists", "bonus", "threat", "creativity")
    )
]
DEFENSIVE_FEATURE_COLUMNS = [
    column
    for column in ADDITIONAL_PLAYER_FEATURE_COLUMNS
    if "clean_sheets" in column or "defensive_contribution" in column
]
FIXTURE_FEATURE_COLUMNS = [
    column
    for column in NUMERIC_FEATURE_COLUMNS
    if column.startswith("next_1gw_")
]
FEATURE_GROUPS = {
    "Availability and starts": AVAILABILITY_FEATURE_COLUMNS,
    "Points and expected output": CORE_FORM_FEATURE_COLUMNS,
    "Attacking underlying data": ATTACKING_FEATURE_COLUMNS,
    "Defensive underlying data": DEFENSIVE_FEATURE_COLUMNS,
    "Fixture context": FIXTURE_FEATURE_COLUMNS,
    "Position": CATEGORICAL_FEATURE_COLUMNS,
}


@dataclass(frozen=True)
class EvaluationResult:
    model_name: str
    train_rows: int
    validation_rows: int
    validation_season: str
    validation_start_gameweek: int
    model_mae: float
    model_rmse: float
    baseline_mae: float
    baseline_rmse: float

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def _validate_columns(frame: pd.DataFrame, include_target: bool) -> None:
    required = MODEL_FEATURE_COLUMNS.copy()
    if include_target:
        required.append(TARGET_COLUMN)
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"Feature table is missing required columns: {missing}")


def prepare_feature_frame(frame: pd.DataFrame, include_target: bool = True) -> pd.DataFrame:
    """Return a typed, sorted copy suitable for training or inference."""
    _validate_columns(frame, include_target=include_target)
    result = frame.copy()

    for column in NUMERIC_FEATURE_COLUMNS:
        result[column] = pd.to_numeric(result[column], errors="coerce")

    if include_target:
        result[TARGET_COLUMN] = pd.to_numeric(result[TARGET_COLUMN], errors="coerce")
        result = result.dropna(subset=[TARGET_COLUMN]).copy()

    result["position"] = result["position"].fillna("Unknown").astype(str)

    return result.sort_values(
        ["season", "gameweek", "player_id"]
    ).reset_index(drop=True)


def temporal_split(
    frame: pd.DataFrame,
    validation_gameweeks: int = 8,
) -> tuple[pd.DataFrame, pd.DataFrame, str, int]:
    """Hold out the final N gameweeks of the latest season.

    This prevents future gameweeks from influencing model evaluation.
    """
    if validation_gameweeks < 1:
        raise ValueError("validation_gameweeks must be at least 1")

    seasons = sorted(frame["season"].dropna().astype(str).unique())
    if not seasons:
        raise ValueError("No season values are available for temporal splitting")

    validation_season = seasons[-1]
    latest_season = frame[frame["season"].astype(str) == validation_season]
    gameweeks = sorted(latest_season["gameweek"].dropna().unique())

    if len(gameweeks) <= validation_gameweeks:
        raise ValueError(
            "Not enough gameweeks for a temporal split. "
            "Load more completed gameweeks or reduce validation_gameweeks."
        )

    validation_start_gameweek = int(gameweeks[-validation_gameweeks])
    validation_mask = (
        frame["season"].astype(str).eq(validation_season)
        & frame["gameweek"].ge(validation_start_gameweek)
    )

    validation = frame.loc[validation_mask].copy()
    train = frame.loc[~validation_mask].copy()

    if train.empty or validation.empty:
        raise ValueError("Temporal split produced an empty train or validation set")

    return train, validation, validation_season, validation_start_gameweek


def build_gradient_boosting_pipeline(random_state: int = 42) -> Pipeline:
    """Build a dense-input Histogram Gradient Boosting candidate.

    Gradient boosting learns sequentially: each tree focuses on errors left by
    the earlier trees. Its preprocessing produces dense input, as required by
    HistGradientBoosting.
    """
    preprocessor = ColumnTransformer(
        transformers=[
            (
                "numeric",
                Pipeline(steps=[("imputer", SimpleImputer(strategy="median"))]),
                NUMERIC_FEATURE_COLUMNS,
            ),
            (
                "categorical",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        (
                            "encoder",
                            OneHotEncoder(
                                handle_unknown="ignore",
                                sparse_output=False,
                            ),
                        ),
                    ]
                ),
                CATEGORICAL_FEATURE_COLUMNS,
            ),
        ],
        remainder="drop",
        sparse_threshold=0,
    )
    regressor = HistGradientBoostingRegressor(
        # FPL scores can be negative after deductions, so Poisson loss is not
        # valid. Squared-error regression supports the complete point range.
        loss="squared_error",
        learning_rate=0.05,
        max_iter=300,
        max_leaf_nodes=15,
        min_samples_leaf=20,
        l2_regularization=1.0,
        random_state=random_state,
    )
    return Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("regressor", regressor),
        ]
    )


def get_permutation_importance(
    model: Pipeline,
    validation_frame: pd.DataFrame,
    repeats: int = 3,
    random_state: int = 42,
) -> pd.DataFrame:
    """Measure held-out feature value using MAE degradation when shuffled.

    This is evaluated on data the model did not train on and measures the MAE
    cost of disrupting one input at a time.
    """
    if repeats < 1:
        raise ValueError("Permutation repeats must be at least 1")

    _validate_columns(validation_frame, include_target=True)
    result = permutation_importance(
        model,
        validation_frame[MODEL_FEATURE_COLUMNS],
        validation_frame[TARGET_COLUMN],
        scoring="neg_mean_absolute_error",
        n_repeats=repeats,
        random_state=random_state,
        # The fitted forest already uses all available workers.  Avoid nested
        # parallelism in constrained Streamlit deployment environments.
        n_jobs=1,
    )
    importance = pd.DataFrame(
        {
            "feature": MODEL_FEATURE_COLUMNS,
            "mae_increase": result.importances_mean,
            "mae_increase_std": result.importances_std,
        }
    ).sort_values("mae_increase", ascending=False).reset_index(drop=True)
    return importance


def get_grouped_permutation_importance(
    model: Pipeline,
    validation_frame: pd.DataFrame,
    repeats: int = 3,
    random_state: int = 42,
) -> pd.DataFrame:
    """Measure the held-out MAE cost of jointly shuffling related features."""
    if repeats < 1:
        raise ValueError("Permutation repeats must be at least 1")

    _validate_columns(validation_frame, include_target=True)
    features = validation_frame[MODEL_FEATURE_COLUMNS].copy()
    actual = validation_frame[TARGET_COLUMN].to_numpy()
    baseline_predictions = np.clip(model.predict(features), a_min=0, a_max=None)
    baseline_mae = mean_absolute_error(actual, baseline_predictions)
    random_generator = np.random.default_rng(random_state)
    rows = []

    for group_name, columns in FEATURE_GROUPS.items():
        increases = []
        for _ in range(repeats):
            shuffled = features.copy()
            permutation = random_generator.permutation(len(shuffled))
            shuffled.loc[:, columns] = shuffled.loc[:, columns].iloc[
                permutation
            ].to_numpy()
            predictions = np.clip(model.predict(shuffled), a_min=0, a_max=None)
            increases.append(mean_absolute_error(actual, predictions) - baseline_mae)
        rows.append(
            {
                "feature_group": group_name,
                "mae_increase": float(np.mean(increases)),
                "mae_increase_std": float(np.std(increases)),
            }
        )

    return pd.DataFrame(rows).sort_values(
        "mae_increase", ascending=False
    ).reset_index(drop=True)


def get_position_validation(validation_results: pd.DataFrame) -> pd.DataFrame:
    """Return held-out accuracy by FPL position for model health checks."""
    required = {"position", TARGET_COLUMN, "predicted_next_gw_points"}
    missing = sorted(required.difference(validation_results.columns))
    if missing:
        raise ValueError(f"Position validation is missing columns: {missing}")

    rows = []
    for position, group in validation_results.groupby("position", dropna=False):
        actual = group[TARGET_COLUMN].to_numpy()
        predicted = group["predicted_next_gw_points"].to_numpy()
        rows.append(
            {
                "position": "Unknown" if pd.isna(position) else str(position),
                "held_out_rows": len(group),
                "mae": float(mean_absolute_error(actual, predicted)),
                "rmse": float(np.sqrt(mean_squared_error(actual, predicted))),
                "actual_points_per_gw": float(np.mean(actual)),
                "predicted_points_per_gw": float(np.mean(predicted)),
            }
        )
    return pd.DataFrame(rows).sort_values("position").reset_index(drop=True)


def _fit_and_evaluate(
    feature_frame: pd.DataFrame,
    model: Pipeline,
    model_name: str,
    validation_gameweeks: int = 8,
) -> tuple[Pipeline, EvaluationResult, pd.DataFrame]:
    """Fit a candidate and evaluate it only on later gameweeks."""
    frame = prepare_feature_frame(feature_frame, include_target=True)
    train, validation, season, start_gameweek = temporal_split(
        frame,
        validation_gameweeks=validation_gameweeks,
    )

    model.fit(train[MODEL_FEATURE_COLUMNS], train[TARGET_COLUMN])

    predictions = np.clip(
        model.predict(validation[MODEL_FEATURE_COLUMNS]),
        a_min=0,
        a_max=None,
    )

    actual = validation[TARGET_COLUMN].to_numpy()
    baseline_prediction = np.full(
        shape=len(validation),
        fill_value=train[TARGET_COLUMN].mean(),
    )

    evaluation = EvaluationResult(
        model_name=model_name,
        train_rows=len(train),
        validation_rows=len(validation),
        validation_season=season,
        validation_start_gameweek=start_gameweek,
        model_mae=float(mean_absolute_error(actual, predictions)),
        model_rmse=float(np.sqrt(mean_squared_error(actual, predictions))),
        baseline_mae=float(mean_absolute_error(actual, baseline_prediction)),
        baseline_rmse=float(np.sqrt(mean_squared_error(actual, baseline_prediction))),
    )

    # Keep the feature columns in the held-out frame.  The Streamlit layer uses
    # them for permutation diagnostics, while it selects a compact subset for
    # the prediction table shown to users.
    validation_results = validation.copy()
    validation_results["predicted_next_gw_points"] = predictions
    validation_results["prediction_error"] = (
        validation_results["predicted_next_gw_points"]
        - validation_results[TARGET_COLUMN]
    )

    return model, evaluation, validation_results


def train_and_evaluate(
    feature_frame: pd.DataFrame,
    validation_gameweeks: int = 8,
    random_state: int = 42,
) -> tuple[Pipeline, EvaluationResult, pd.DataFrame]:
    """Train and temporally evaluate the production Gradient Boosting model."""
    return _fit_and_evaluate(
        feature_frame,
        model=build_gradient_boosting_pipeline(random_state=random_state),
        model_name=GRADIENT_BOOSTING_MODEL_NAME,
        validation_gameweeks=validation_gameweeks,
    )


def train_final_model(
    feature_frame: pd.DataFrame,
    random_state: int = 42,
) -> Pipeline:
    """Fit the production Gradient Boosting model using every labelled row."""
    frame = prepare_feature_frame(feature_frame, include_target=True)
    model = build_gradient_boosting_pipeline(random_state=random_state)
    model.fit(frame[MODEL_FEATURE_COLUMNS], frame[TARGET_COLUMN])
    return model


def save_model(
    model: Pipeline,
    path: str | Path,
    evaluation: EvaluationResult,
) -> None:
    """Persist the fitted pipeline and its evaluation metadata together."""
    artifact_path = Path(path)
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "model": model,
            "feature_columns": MODEL_FEATURE_COLUMNS,
            "target_column": TARGET_COLUMN,
            "evaluation": evaluation.to_dict(),
        },
        artifact_path,
    )


def load_model(path: str | Path) -> dict[str, Any]:
    artifact = joblib.load(path)
    required = {"model", "feature_columns", "target_column", "evaluation"}
    missing = required.difference(artifact)
    if missing:
        raise ValueError(f"Invalid model artifact; missing keys: {sorted(missing)}")
    return artifact


def predict_next_gameweek(
    model: Pipeline,
    feature_frame: pd.DataFrame,
) -> pd.DataFrame:
    """Score feature rows without using their known historical target."""
    frame = prepare_feature_frame(feature_frame, include_target=False)
    predictions = np.clip(model.predict(frame[MODEL_FEATURE_COLUMNS]), a_min=0, a_max=None)

    results = frame[
        IDENTIFIER_COLUMNS
    ].copy()
    results["predicted_next_gw_points"] = predictions

    return results.sort_values(
        ["season", "gameweek", "predicted_next_gw_points"],
        ascending=[True, True, False],
    ).reset_index(drop=True)
