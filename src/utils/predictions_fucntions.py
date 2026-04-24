import pandas as pd
import numpy as np
from sklearn.metrics import r2_score, mean_absolute_error
from sklearn.ensemble import RandomForestRegressor
import xgboost as xgb

from src.utils.features_pipline import build_feature_pipeline

# =====================================================================
# SMAPE — Symmetric Mean Absolute Percentage Error
# Handles zero and negative values gracefully.
# Returns a value in [0, 200]; we convert to accuracy as (1 - SMAPE/200)*100.
# =====================================================================
def _smape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Symmetric MAPE: handles negative/zero targets without exploding."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    denominator = (np.abs(y_true) + np.abs(y_pred))
    mask = denominator > 0
    if mask.sum() == 0:
        return 0.0
    return float(np.mean(2.0 * np.abs(y_true[mask] - y_pred[mask]) / denominator[mask]) * 100)


def _normalized_accuracy(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """
    Normalized MAE accuracy: 1 - MAE/range(y_true).
    More robust than SMAPE for highly volatile data with sign changes.
    Returns a percentage in [0, 100].
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    mae = np.mean(np.abs(y_true - y_pred))
    y_range = np.max(y_true) - np.min(y_true)
    if y_range == 0:
        return 100.0 if mae == 0 else 0.0
    return max(0.0, (1 - mae / y_range) * 100)


# =====================================================================
# LAG FEATURE SHIFT CONFIG
# =====================================================================
LAG_SHIFT_CONFIG = {
    'revenue_lag_2': 'revenue_lag_1',
    'revenue_lag_1': 'prediction',
    'revenue_lag_3': 'revenue_lag_2',
    'cogs_lag_1':    'revenue_lag_1',     # proxy
    'cogs_lag_3':    'cogs_lag_1',
    'gross_margin_ma_3': None,            # recomputed below
    'gross_margin_lag_1': 'gross_margin_ma_3',
    'po_lag_1': 'po_total_value',
    'expense_lag_1': 'expense_lag_1',     # frozen
    'collection_gap_lag_1': 'collection_gap',
}


def _roll_features_forward(features_row: pd.DataFrame, prediction: float) -> pd.DataFrame:
    """
    Given the current feature row and the model's prediction,
    construct the next month's feature row by shifting lag columns.
    """
    next_row = features_row.copy()

    for target_col, source in LAG_SHIFT_CONFIG.items():
        if target_col not in next_row.columns:
            continue
        if source == 'prediction':
            next_row[target_col] = prediction
        elif source is None:
            pass
        elif source in next_row.columns:
            next_row[target_col] = features_row[source].values[0]

    # Advance calendar features
    if 'month_num' in next_row.columns:
        import math
        cur = int(features_row['month_num'].values[0])
        nxt = (cur % 12) + 1
        next_row['month_num'] = nxt
        next_row['quarter'] = (nxt - 1) // 3 + 1
        next_row['month_sin'] = math.sin(nxt * 2 * math.pi / 12)
        next_row['month_cos'] = math.cos(nxt * 2 * math.pi / 12)
        next_row['is_year_end'] = int(nxt in [11, 12])

    # Recompute gross_margin_ma_3
    if all(c in next_row.columns for c in ['revenue_lag_1', 'revenue_lag_2', 'cogs_lag_1']):
        rev_pred  = prediction
        rev_lag1  = features_row['revenue_lag_1'].values[0]
        rev_lag2  = features_row['revenue_lag_2'].values[0]
        cogs_lag1 = features_row['cogs_lag_1'].values[0]

        def gm(rev, cogs):
            return (rev - cogs) / rev if rev != 0 else 0.0

        cogs_pred = features_row['cogs_lag_1'].values[0]
        cogs_lag2 = features_row['cogs_lag_3'].values[0] if 'cogs_lag_3' in features_row.columns else cogs_lag1
        ma3 = np.mean([gm(rev_pred, cogs_pred), gm(rev_lag1, cogs_lag1), gm(rev_lag2, cogs_lag2)])
        if 'gross_margin_ma_3' in next_row.columns:
            next_row['gross_margin_ma_3'] = ma3

    return next_row


def _validate_features_are_lags(feature_columns: list):
    """Refuse features that are current-month raw values."""
    forbidden = {'monthly_revenue', 'total_cogs', 'net_profit', 'gross_profit',
                 'total_expenses', 'monthly_expenses'}
    bad = [f for f in feature_columns if f in forbidden]
    if bad:
        raise ValueError(
            f"Feature columns {bad} are current-month raw values. "
            f"Replace them with lag versions: revenue_lag_1, cogs_lag_1, etc."
        )


# =====================================================================
# Walk-forward cross-validation
# =====================================================================
def _walk_forward_cv(model_class, model_params: dict, X: pd.DataFrame,
                     y: pd.Series, min_train_size: int = 12) -> tuple:
    """
    Expanding-window walk-forward CV for time series.
    Train on months [0..k], test on month k+1, repeat.
    """
    all_true = []
    all_pred = []

    for split_idx in range(min_train_size, len(X)):
        X_train = X.iloc[:split_idx]
        y_train = y.iloc[:split_idx]
        X_test  = X.iloc[split_idx:split_idx+1]
        y_test  = y.iloc[split_idx:split_idx+1]

        model = model_class(**model_params)
        model.fit(X_train, y_train)
        pred = model.predict(X_test)

        all_true.append(float(y_test.values[0]))
        all_pred.append(float(pred[0]))

    return np.array(all_true), np.array(all_pred)


def _print_eval(label: str, y_test: np.ndarray, test_preds: np.ndarray) -> float:
    """Print evaluation using both SMAPE and normalized MAE accuracy."""
    smape_val = _smape(y_test, test_preds)
    norm_acc = _normalized_accuracy(y_test, test_preds)
    mae = mean_absolute_error(y_test, test_preds)

    print(f"\n--- {label} Evaluation ---")
    print(f"SMAPE               : {smape_val:.2f}%")
    print(f"Normalized Accuracy : {norm_acc:.2f}%")
    print(f"MAE                 : {mae:,.2f}")
    if len(y_test) > 30:
        r2 = r2_score(y_test, test_preds)
        print(f"R² Score            : {r2:.4f}")
    else:
        print(f"R² Score            : N/A (sample too small for reliable R²)")
    print(f"CV Folds            : {len(y_test)}")
    return norm_acc


def _forecast_loop(model, X: pd.DataFrame, n_months: int, label: str) -> list:
    """Autoregressive forecast."""
    latest_features = X.iloc[-1:].copy()
    future_predictions = []

    print(f"\n--- {label} Forecast ---")
    for i in range(1, n_months + 1):
        pred_value = float(model.predict(latest_features)[0])
        future_predictions.append(pred_value)
        print(f"Month +{i}: {pred_value:,.2f}")
        latest_features = _roll_features_forward(latest_features, pred_value)

    return future_predictions


def _prepare_data(df: pd.DataFrame, feature_columns: list, target_column: str):
    """
    Prepare training data: fill NaN with column median instead of dropping rows.
    This preserves more data for small datasets.
    """
    df = df.replace({pd.NA: np.nan})
    work = df[feature_columns + [target_column]].copy()

    # Target must not be NaN — drop those rows
    work = work.dropna(subset=[target_column])

    # Fill feature NaN with column median (preserves rows for small datasets)
    for col in feature_columns:
        if col in work.columns and work[col].isna().any():
            median_val = work[col].median()
            work[col] = work[col].fillna(median_val if not pd.isna(median_val) else 0)

    return work[feature_columns], work[target_column]


def train_and_predict_future(
    df: pd.DataFrame,
    target_column: str,
    feature_columns: list,
    n_months: int
) -> dict:
    """
    Random Forest: walk-forward CV evaluation, then train on ALL data
    and forecast n_months ahead with autoregressive feature rolling.
    """
    _validate_features_are_lags(feature_columns)

    X, y = _prepare_data(df, feature_columns, target_column)

    if len(X) == 0:
        return {"error": "Not enough data"}

    # ── Walk-forward CV for evaluation ────────────────────────────────
    min_train = max(8, int(len(X) * 0.5))
    rf_params = {
        'n_estimators': 200,
        'max_depth': 3,
        'min_samples_leaf': 5,
        'max_features': 'sqrt',
        'random_state': 42,
    }

    y_true_cv, y_pred_cv = _walk_forward_cv(
        RandomForestRegressor, rf_params, X, y, min_train_size=min_train
    )
    accuracy_percent = _print_eval("Random Forest", y_true_cv, y_pred_cv)

    # ── Train final model on ALL data for forecasting ────────────────
    model = RandomForestRegressor(**rf_params)
    model.fit(X, y)

    future_predictions = _forecast_loop(model, X, n_months, "Random Forest")

    return {
        "accuracy_percent": accuracy_percent,
        "predictions": future_predictions
    }


def train_and_predict_xgboost(
    df: pd.DataFrame,
    target_column: str,
    feature_columns: list,
    n_months: int
) -> dict:
    """
    XGBoost: walk-forward CV + full-data training + forecast.
    """
    _validate_features_are_lags(feature_columns)

    X, y = _prepare_data(df, feature_columns, target_column)

    if len(X) == 0:
        return {"error": "Not enough data"}

    # ── Walk-forward CV for evaluation ────────────────────────────────
    min_train = max(8, int(len(X) * 0.5))
    xgb_params = {
        'n_estimators': 100,
        'learning_rate': 0.05,
        'booster': 'gblinear',
        'reg_alpha': 2.0,
        'reg_lambda': 5.0,
        'random_state': 42,
        'objective': 'reg:squarederror',
    }

    y_true_cv, y_pred_cv = _walk_forward_cv(
        xgb.XGBRegressor, xgb_params, X, y, min_train_size=min_train
    )
    accuracy_percent = _print_eval("XGBoost", y_true_cv, y_pred_cv)

    # ── Train final model on ALL data for forecasting ────────────────
    model = xgb.XGBRegressor(**xgb_params)
    model.fit(X, y)

    future_predictions = _forecast_loop(model, X, n_months, "XGBoost")

    return {
        "accuracy_percent": accuracy_percent,
        "predictions": future_predictions
    }


# =====================================================================
# Default feature set — curated for small datasets (~50 rows)
# Fewer features = less overfitting. Only the most informative lag features.
# =====================================================================
DEFAULT_FEATURE_COLS = [
    # Core revenue lags (most predictive)
    'revenue_lag_1',
    'revenue_lag_2',
    'revenue_ma_3',
    # Seasonality
    'month_sin',
    'month_cos',
    'quarter',
    # Cost signals
    'cogs_lag_1',
    'gross_margin_ma_3',
    # Cash flow
    'collection_gap_lag_1',
    # Volume
    'po_lag_1',
]


if __name__ == "__main__":
    df_features = build_feature_pipeline()

    # Filter to only columns that actually exist
    available = [c for c in DEFAULT_FEATURE_COLS if c in df_features.columns]
    print(f"\nUsing {len(available)} features: {available}")

    results_rf = train_and_predict_future(
        df=df_features,
        target_column='target_profit',
        feature_columns=available,
        n_months=3
    )

    results_xgb = train_and_predict_xgboost(
        df=df_features,
        target_column='target_profit',
        feature_columns=available,
        n_months=3
    )
