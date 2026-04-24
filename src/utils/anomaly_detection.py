from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import RobustScaler
from sklearn.model_selection import train_test_split
from sklearn.decomposition import PCA
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import sqlite3
import os

_DB_PATH = os.path.join(os.path.dirname(__file__), "../../data/ai_audit_db.sqlite")

def get_data_from_db(query: str) -> pd.DataFrame:
    try:
        conn = sqlite3.connect(_DB_PATH, timeout=30)
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    except Exception as e:
        print(f"Error reading from database: {e}")
        return pd.DataFrame()

def detect_anomalies(query: str) -> list:
    data = get_data_from_db(query)
    if data.empty:
        return []

    id_col = None
    for col in data.columns:
        if col.lower() == 'id':
            id_col = col
            break

    # Drop ID columns and non-informative numerics
    id_cols = [c for c in data.columns if 'id' in c.lower()]
    X = data.select_dtypes(include=[np.number]).drop(columns=id_cols, errors='ignore').fillna(0)

    if X.empty:
        return []

    print("Features used:", X.columns.tolist())

    # Scale — RobustScaler handles financial outliers better than StandardScaler
    scaler = RobustScaler()
    X_scaled = scaler.fit_transform(X)

    # Train
    model = IsolationForest(contamination=0.05, random_state=42)
    model.fit(X_scaled)

    y_pred = model.predict(X_scaled)

    anomaly_indices = np.where(y_pred == -1)[0]
    
    if id_col is not None:
        anomaly_ids = data.iloc[anomaly_indices][id_col].tolist()
    else:
        # Fallback to returning DataFrame indices if no 'id' column is found
        anomaly_ids = data.iloc[anomaly_indices].index.tolist()

    return anomaly_ids


print(detect_anomalies("SELECT * FROM invoices"))