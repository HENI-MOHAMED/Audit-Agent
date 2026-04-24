from src.utils.predictions_fucntions import build_feature_pipeline, train_and_predict_xgboost
try:
    df_features = build_feature_pipeline()
    feature_cols = ['revenue_lag_1','revenue_lag_2','cogs_lag_1','gross_margin_ma_3']
    results_xgb = train_and_predict_xgboost(df=df_features, target_column='target_profit', feature_cols=feature_cols, n_months=3)
    print(results_xgb)
except Exception as e:
    print("Error:", e)
