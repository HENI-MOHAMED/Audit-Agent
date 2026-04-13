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
# features_df = Unit_Economics_Features()

def Cash_Flow_Features(features_df=None):
    if features_df is None:
        features_df = Unit_Economics_Features()

    # 1. DSO Days (Collection efficiency)
    dso_query = """
    SELECT strftime('%Y-%m', i.invoice_date) AS month,
           AVG(julianday(p.payment_date) - julianday(i.invoice_date)) AS dso_days
    FROM invoices i
    JOIN payments p ON i.id = p.invoice_id
    WHERE i.type = 'out_invoice'
    GROUP BY month
    """
    dso_df = get_data_from_db(dso_query).dropna(subset=['month']).sort_values(by='month').reset_index(drop=True)

    # 2. Overdue Amount & Ratio
    # We define overdue if the payment was made after due_date or if unpaid and due_date has passed (relative to the invoice date, but let's just check payment vs due_date to simplify, or unpaid checking if today > due_date)
    # Using a simple aggregation: sum of total_amount where payment_date > due_date, divided by total_invoiced.
    overdue_query = """
    SELECT strftime('%Y-%m', i.invoice_date) AS month,
           SUM(CASE WHEN p.payment_date IS NULL OR julianday(p.payment_date) > julianday(i.due_date) THEN i.total_amount ELSE 0 END) AS overdue_amount,
           SUM(i.total_amount) AS total_invoiced
    FROM invoices i
    LEFT JOIN payments p ON i.id = p.invoice_id
    WHERE i.type = 'out_invoice'
    GROUP BY month
    """
    overdue_df = get_data_from_db(overdue_query).dropna(subset=['month']).sort_values(by='month').reset_index(drop=True)
    overdue_df['overdue_ratio'] = overdue_df['overdue_amount'] / overdue_df['total_invoiced'].replace(0, pd.NA)

    # 3. Cash collected vs billed gap
    billed_collected_query = """
    SELECT month, SUM(billed_this_month) AS billed_this_month, SUM(collected_this_month) AS collected_this_month
    FROM (
        SELECT strftime('%Y-%m', invoice_date) AS month, total_amount AS billed_this_month, 0 AS collected_this_month
        FROM invoices WHERE type = 'out_invoice'
        UNION ALL
        SELECT strftime('%Y-%m', p.payment_date) AS month, 0 AS billed_this_month, p.amount AS collected_this_month
        FROM payments p
        JOIN invoices i ON p.invoice_id = i.id WHERE i.type = 'out_invoice'
    ) 
    WHERE month IS NOT NULL
    GROUP BY month
    """
    billed_collected_df = get_data_from_db(billed_collected_query).dropna(subset=['month']).sort_values(by='month').reset_index(drop=True)
    billed_collected_df['collection_gap'] = billed_collected_df['billed_this_month'] - billed_collected_df['collected_this_month']
    billed_collected_df['collection_gap_lag_1'] = billed_collected_df['collection_gap'].shift(1)

    # 4. Payment method distribution
    payment_method_query = """
    SELECT strftime('%Y-%m', p.payment_date) AS month,
           SUM(CASE WHEN LOWER(p.payment_method) LIKE '%cash%' THEN p.amount ELSE 0 END) / NULLIF(SUM(p.amount), 0) AS pct_paid_cash,
           SUM(CASE WHEN LOWER(p.payment_method) LIKE '%credit%' OR LOWER(p.payment_method) LIKE '%card%' THEN p.amount ELSE 0 END) / NULLIF(SUM(p.amount), 0) AS pct_paid_credit
    FROM payments p
    JOIN invoices i ON p.invoice_id = i.id
    WHERE i.type = 'out_invoice'
    GROUP BY month
    """
    payment_method_df = get_data_from_db(payment_method_query).dropna(subset=['month']).sort_values(by='month').reset_index(drop=True)

    # Merge all into features_df
    features_df = features_df.merge(dso_df, on='month', how='left')\
                             .merge(overdue_df[['month', 'overdue_amount', 'overdue_ratio']], on='month', how='left')\
                             .merge(billed_collected_df, on='month', how='left')\
                             .merge(payment_method_df, on='month', how='left')

    print("\nCash Flow Features DataFrame:")
    print(features_df[['month', 'dso_days', 'overdue_ratio', 'collection_gap', 'pct_paid_cash']].tail())
    return features_df

def Volume_Activity_Features(features_df=None):
    if features_df is None:
        features_df = Cash_Flow_Features()

    # 1. Transaction volume
    tx_volume_query = """
    SELECT strftime('%Y-%m', invoice_date) AS month,
           COUNT(*) AS invoice_count,
           SUM(total_amount) / COUNT(*) AS avg_invoice_value,
           COUNT(DISTINCT supplier_id) AS unique_customers
    FROM invoices 
    WHERE type = 'out_invoice'
    GROUP BY month
    """
    tx_volume_df = get_data_from_db(tx_volume_query).dropna(subset=['month']).sort_values(by='month').reset_index(drop=True)

    # 2. Customer concentration risk
    concentration_query = """
    WITH MonthlyRevenue AS (
        SELECT strftime('%Y-%m', invoice_date) AS month, 
               supplier_id, 
               SUM(total_amount) AS customer_revenue
        FROM invoices 
        WHERE type = 'out_invoice'
        GROUP BY month, supplier_id
    ),
    RankedRevenue AS (
        SELECT month, 
               customer_revenue,
               SUM(customer_revenue) OVER(PARTITION BY month) AS total_revenue,
               ROW_NUMBER() OVER(PARTITION BY month ORDER BY customer_revenue DESC) as rank
        FROM MonthlyRevenue
    )
    SELECT month,
           SUM(CASE WHEN rank = 1 THEN customer_revenue ELSE 0 END) / total_revenue AS top1_customer_pct,
           SUM(CASE WHEN rank <= 3 THEN customer_revenue ELSE 0 END) / total_revenue AS top3_customers_pct
    FROM RankedRevenue
    GROUP BY month, total_revenue
    """
    concentration_df = get_data_from_db(concentration_query).dropna(subset=['month']).sort_values(by='month').reset_index(drop=True)

    # 3. Order pipeline
    po_query = """
    SELECT strftime('%Y-%m', order_date) AS month,
           COUNT(*) AS po_count,
           SUM(total_amount) AS po_total_value
    FROM purchase_orders 
    GROUP BY month
    """
    po_df = get_data_from_db(po_query).dropna(subset=['month']).sort_values(by='month').reset_index(drop=True)
    po_df['po_lag_1'] = po_df['po_total_value'].shift(1)

    # Merge all into features_df
    features_df = features_df.merge(tx_volume_df, on='month', how='left')\
                             .merge(concentration_df, on='month', how='left')\
                             .merge(po_df, on='month', how='left')

    print("\nVolume & Activity Features DataFrame:")
    print(features_df[['month', 'invoice_count', 'unique_customers', 'top1_customer_pct', 'po_total_value']].tail())
    return features_df

# Call the function
features_df = Volume_Activity_Features()



































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