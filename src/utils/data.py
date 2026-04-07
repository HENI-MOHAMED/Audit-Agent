import os
import pandas as pd
import sqlite3

_DB_PATH = os.path.join(os.path.dirname(__file__), "../../data/ai_audit_db.sqlite")



def get_data_from_db(query: str) -> pd.DataFrame:

    try:
        conn = sqlite3.connect(_DB_PATH, timeout=30)
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    except Exception as e:
        print(f"Error reading from local database: {e}")
        return pd.DataFrame()
print(f"Data: {get_data_from_db('SELECT * FROM taxes').describe(include="all")} ")