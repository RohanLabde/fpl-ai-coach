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
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


TARGET_COLUMN = "next_gw_points"
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
    "previous_gw_starts", "rolling_3gw_starts", "rolling_5gw_starts", "rolling_10gw_starts",
    "rolling_3gw_start_rate", "rolling_5gw_start_rate", "rolling_10gw_start_rate",
    "next_1gw_fixture_count", "next_1gw_avg_fdr",
    "next_1gw_home_count", "next_1gw_away_count",
    "next_1gw_opponent_avg_5fixture_goals_conceded",
    "next_1gw_opponent_avg_5fixture_clean_sheet_rate",
] + ADDITIONAL_PLAYER_FEATURE_COLUMNS + TEAM_CONTEXT_FEATURE_COLUMNS
CATEGORICAL_FEATURE_COLUMNS = ["position"]
MODEL_FEATURE_COLUMNS = NUMERIC_FEATURE_COLUMNS + CATEGORICAL_FEATURE_COLUMNS


@dataclass(frozen=True)
class EvaluationResult:
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


def build_pipeline(random_state: int = 42) -> Pipeline:
    """Build a robust baseline suitable for modest historical datasets."""
    preprocessor = ColumnTransformer(
        transformers=[
            (
                "numeric",
                Pipeline(
                    steps=[("imputer", SimpleImputer(strategy="median"))]
                ),
                NUMERIC_FEATURE_COLUMNS,
            ),
            (
                "categorical",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("encoder", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                CATEGORICAL_FEATURE_COLUMNS,
            ),
        ],
        remainder="drop",
    )

    regressor = RandomForestRegressor(
        n_estimators=400,
        min_samples_leaf=5,
        max_features=0.8,
        n_jobs=-1,
        random_state=random_state,
    )

    return Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("regressor", regressor),
        ]
    )


def get_feature_importance(model: Pipeline) -> pd.DataFrame:
    """Return source-level Random Forest feature importance.

    One-hot encoded position columns are aggregated back into one ``position``
    row, making the output suitable for comparison with numeric features.
    Importances describe model reliance, not causal effect.
    """
    if not isinstance(model, Pipeline):
        raise ValueError("Feature importance requires the fitted model pipeline.")

    try:
        preprocessor = model.named_steps["preprocessor"]
        regressor = model.named_steps["regressor"]
        transformed_names = preprocessor.get_feature_names_out()
        importances = regressor.feature_importances_
    except (AttributeError, KeyError) as error:
        raise ValueError(
            "Feature importance requires a fitted pipeline produced by "
            "build_pipeline()."
        ) from error

    if len(transformed_names) != len(importances):
        raise ValueError(
            "The fitted model's transformed feature names do not match its "
            "importance values."
        )

    source_features = []
    for name in transformed_names:
        if name.startswith("numeric__"):
            source_features.append(name.removeprefix("numeric__"))
        elif name.startswith("categorical__position_"):
            source_features.append("position")
        else:
            source_features.append(name)

    result = pd.DataFrame(
        {
            "feature": source_features,
            "importance": importances,
        }
    )

    result = (
        result.groupby("feature", as_index=False)["importance"]
        .sum()
        .sort_values("importance", ascending=False)
        .reset_index(drop=True)
    )
    result["importance_pct"] = result["importance"] * 100

    return result


def train_and_evaluate(
    feature_frame: pd.DataFrame,
    validation_gameweeks: int = 8,
    random_state: int = 42,
) -> tuple[Pipeline, EvaluationResult, pd.DataFrame]:
    """Train on past data and evaluate only on later gameweeks."""
    frame = prepare_feature_frame(feature_frame, include_target=True)
    train, validation, season, start_gameweek = temporal_split(
        frame,
        validation_gameweeks=validation_gameweeks,
    )

    model = build_pipeline(random_state=random_state)
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
        train_rows=len(train),
        validation_rows=len(validation),
        validation_season=season,
        validation_start_gameweek=start_gameweek,
        model_mae=float(mean_absolute_error(actual, predictions)),
        model_rmse=float(np.sqrt(mean_squared_error(actual, predictions))),
        baseline_mae=float(mean_absolute_error(actual, baseline_prediction)),
        baseline_rmse=float(np.sqrt(mean_squared_error(actual, baseline_prediction))),
    )

    validation_results = validation[
        IDENTIFIER_COLUMNS + [TARGET_COLUMN]
    ].copy()
    validation_results["predicted_next_gw_points"] = predictions
    validation_results["prediction_error"] = (
        validation_results["predicted_next_gw_points"]
        - validation_results[TARGET_COLUMN]
    )

    return model, evaluation, validation_results


def train_final_model(
    feature_frame: pd.DataFrame,
    random_state: int = 42,
) -> Pipeline:
    """Fit the selected model using every completed labelled row."""
    frame = prepare_feature_frame(feature_frame, include_target=True)
    model = build_pipeline(random_state=random_state)
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
    predictions = np.clip(
        model.predict(frame[MODEL_FEATURE_COLUMNS]),
        a_min=0,
        a_max=None,
    )

    results = frame[
        IDENTIFIER_COLUMNS
    ].copy()
    results["predicted_next_gw_points"] = predictions

    return results.sort_values(
        ["season", "gameweek", "predicted_next_gw_points"],
        ascending=[True, True, False],
    ).reset_index(drop=True)
