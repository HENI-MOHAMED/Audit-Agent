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
def Revenue_Features():
    revenue_by_month = get_data_from_db('SELECT SUM(total_amount) AS total, strftime("%Y-%m", due_date) AS month FROM invoices WHERE type = "out_invoice" GROUP BY month')

    # Convert month to datetime for proper sorting and rolling calculations
    revenue_by_month['month'] = pd.to_datetime(revenue_by_month['month'])
    revenue_by_month = revenue_by_month.sort_values(by='month').reset_index(drop=True)

    # Calculate features for each month
    revenue_by_month['revenue_growth_mom'] = revenue_by_month['total'].pct_change(periods=1)
    # Assuming sequential months, period=12 gives YoY growth
    revenue_by_month['revenue_growth_yoy'] = revenue_by_month['total'].pct_change(periods=12)

    revenue_by_month['revenue_month_3_mean'] = revenue_by_month['total'].rolling(window=3).mean()
    revenue_by_month['revenue_month_6_mean'] = revenue_by_month['total'].rolling(window=6).mean()
    revenue_by_month['revenue_std_3'] = revenue_by_month['total'].rolling(window=3).std()

    # Convert month back to string format
    revenue_by_month['month'] = revenue_by_month['month'].dt.strftime('%Y-%m')

    print("Feature DataFrame:")
    print(revenue_by_month.tail())


    return revenue_by_month


def cogs_expenses_features():
    revenue = Revenue_Features()
    monthly_cogs = get_data_from_db("SELECT strftime('%Y-%m', order_date) AS month, SUM(total_amount) AS total_cogs FROM purchase_orders GROUP BY month").dropna(subset=['month']).sort_values(by='month').reset_index(drop=True)
    monthly_expenses = get_data_from_db("SELECT strftime('%Y-%m', je.entry_date) AS month, SUM(jl.debit) AS total_expenses FROM journal_lines jl JOIN journal_entries je ON jl.journal_entry_id = je.id GROUP BY month").dropna(subset=['month']).sort_values(by='month').reset_index(drop=True)

    # Merge all features into a single DataFrame based on the month
    features_df = revenue.rename(columns={'total': 'monthly_revenue'}).merge(monthly_cogs, on='month', how='left').merge(monthly_expenses, on='month', how='left')

    # Fill missing values for COGS and expenses to 0
    features_df['total_cogs'] = features_df['total_cogs'].fillna(0)
    features_df['total_expenses'] = features_df['total_expenses'].fillna(0)

    # Ratios
    # use replace(0, pd.NA) to avoid division by zero
    features_df['cogs_to_revenue_ratio'] = features_df['total_cogs'] / features_df['monthly_revenue'].replace(0, pd.NA)
    features_df['expense_ratio'] = features_df['total_expenses'] / features_df['monthly_revenue'].replace(0, pd.NA)

    # Lag features
    features_df['cogs_lag_1'] = features_df['total_cogs'].shift(1)
    features_df['cogs_lag_3'] = features_df['total_cogs'].shift(3)
    features_df['expense_lag_1'] = features_df['total_expenses'].shift(1)

    # Cost growth
    features_df['cogs_growth_mom'] = features_df['total_cogs'].pct_change(periods=1)

    print("\nCOGS & Expenses Features:")
    print(features_df[['month', 'monthly_revenue', 'total_cogs', 'cogs_to_revenue_ratio', 'expense_ratio', 'cogs_lag_1', 'cogs_growth_mom']].tail())
    return features_df


def Unit_Economics_Features(features_df=None):
    if features_df is None:
        features_df = cogs_expenses_features()

    # Unit economics & Margins
    features_df['gross_margin'] = (features_df['monthly_revenue'] - features_df['total_cogs']) / features_df['monthly_revenue'].replace(0, pd.NA)
    features_df['gross_margin_lag_1'] = features_df['gross_margin'].shift(1)
    features_df['gross_margin_ma_3'] = features_df['gross_margin'].rolling(window=3).mean()
    features_df['margin_delta_mom'] = features_df['gross_margin'] - features_df['gross_margin_lag_1']

    # Retrieve weighted average margin per month from products and invoice_lines
    margin_query = """
    SELECT strftime('%Y-%m', inv.invoice_date) AS month, 
           SUM(il.quantity * (p.price - p.cost)) / NULLIF(SUM(il.quantity * p.price), 0) AS weighted_avg_margin
    FROM invoice_lines il
    JOIN invoices inv ON il.invoice_id = inv.id
    JOIN products p ON il.product_id = p.id
    WHERE inv.type = 'out_invoice'
    GROUP BY month
    """
    monthly_margin = get_data_from_db(margin_query).dropna(subset=['month']).sort_values(by='month').reset_index(drop=True)
    
    # Merge unit economics columns
    features_df = features_df.merge(monthly_margin, on='month', how='left')

    print("\nUnit Economics DataFrame:")
    print(features_df[['month', 'gross_margin', 'weighted_avg_margin', 'margin_delta_mom']].tail())
    return features_df


# Call the function
features_df = Unit_Economics_Features()




























def get_data_from_feature_db(query: str) -> pd.DataFrame:
    try:
        conn = sqlite3.connect("feature_db.sqlite", timeout=30)
        cursor = conn.cursor()
        
        # Execute multiple lines/statements
        statements = [stmt.strip() for stmt in query.split(';') if stmt.strip()]
        for statement in statements:
            cursor.execute(statement)
        
        # Fetch results from the last query
        df = pd.DataFrame(cursor.fetchall(), columns=[desc[0] for desc in cursor.description] if cursor.description else [])
        conn.commit()
        conn.close()
        return df
    except Exception as e:
        print(f"Error reading from local database: {e}")
        return pd.DataFrame()
    
# print(get_data_from_feature_db('CREATE TABLE IF NOT EXISTS revenue_features (id INTEGER PRIMARY KEY, month TEXT, total REAL);'))