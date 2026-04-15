import os
import pandas as pd
import sqlite3

_DB_PATH = os.path.join(os.path.dirname(__file__), "../../data/ai_audit_db.sqlite")


# ─────────────────────────────────────────────
# DB Helpers
# ─────────────────────────────────────────────

def get_data_from_db(query: str) -> pd.DataFrame:
    try:
        conn = sqlite3.connect(_DB_PATH, timeout=30)
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    except Exception as e:
        print(f"Error reading from database: {e}")
        return pd.DataFrame()


# ─────────────────────────────────────────────
# Feature Functions
# ─────────────────────────────────────────────

def Revenue_Features() -> pd.DataFrame:
    # FIX: use invoice_date (when revenue was earned), not due_date
    revenue_by_month = get_data_from_db("""
        SELECT SUM(total_amount) AS total,
               strftime('%Y-%m', invoice_date) AS month
        FROM invoices
        WHERE type = 'out_invoice'
        GROUP BY month
    """)

    assert not revenue_by_month.empty, "Revenue_Features: query returned no data"

    revenue_by_month['month'] = pd.to_datetime(revenue_by_month['month'])
    revenue_by_month = revenue_by_month.sort_values('month').reset_index(drop=True)

    revenue_by_month['revenue_lag_1']        = revenue_by_month['total'].shift(1)
    revenue_by_month['revenue_lag_3']        = revenue_by_month['total'].shift(3)
    revenue_by_month['revenue_lag_12']       = revenue_by_month['total'].shift(12)
    revenue_by_month['revenue_growth_mom']   = revenue_by_month['total'].pct_change(1)
    revenue_by_month['revenue_growth_yoy']   = revenue_by_month['total'].pct_change(12)
    revenue_by_month['revenue_ma_3']         = revenue_by_month['total'].rolling(3).mean()
    revenue_by_month['revenue_ma_6']         = revenue_by_month['total'].rolling(6).mean()
    revenue_by_month['revenue_std_3']        = revenue_by_month['total'].rolling(3).std()

    # Calendar encoding
    revenue_by_month['month_num']   = revenue_by_month['month'].dt.month
    revenue_by_month['quarter']     = revenue_by_month['month'].dt.quarter
    revenue_by_month['month_sin']   = (revenue_by_month['month_num'] * 2 * 3.14159 / 12).apply(__import__('math').sin)
    revenue_by_month['month_cos']   = (revenue_by_month['month_num'] * 2 * 3.14159 / 12).apply(__import__('math').cos)
    revenue_by_month['is_year_end'] = revenue_by_month['month_num'].isin([11, 12]).astype(int)

    revenue_by_month['month'] = revenue_by_month['month'].dt.strftime('%Y-%m')

    print("✓ Revenue Features:")
    print(revenue_by_month[['month', 'total', 'revenue_growth_mom', 'revenue_ma_3', 'revenue_std_3']].tail())
    return revenue_by_month


def cogs_expenses_features(features_df: pd.DataFrame = None) -> pd.DataFrame:
    if features_df is None:
        features_df = Revenue_Features()

    # FIX: only count purchase orders that were actually fulfilled
    monthly_cogs = get_data_from_db("""
        SELECT strftime('%Y-%m', order_date) AS month,
               SUM(total_amount) AS total_cogs
        FROM purchase_orders
        WHERE status = 'done'
        GROUP BY month
    """).dropna(subset=['month']).sort_values('month').reset_index(drop=True)

    # FIX: filter by account type so we don't include asset purchases, loans, etc.
    monthly_expenses = get_data_from_db("""
        SELECT strftime('%Y-%m', je.entry_date) AS month,
               SUM(jl.debit) AS total_expenses
        FROM journal_lines jl
        JOIN journal_entries je ON jl.journal_entry_id = je.id
        JOIN accounts a ON jl.account_id = a.id
        WHERE a.type IN ('expense', 'cost_of_revenue')
        GROUP BY month
    """).dropna(subset=['month']).sort_values('month').reset_index(drop=True)

    features_df = (
        features_df.rename(columns={'total': 'monthly_revenue'})
        .merge(monthly_cogs, on='month', how='left')
        .merge(monthly_expenses, on='month', how='left')
    )

    features_df['total_cogs']     = features_df['total_cogs'].fillna(0)
    features_df['total_expenses'] = features_df['total_expenses'].fillna(0)

    features_df['cogs_to_revenue_ratio'] = (
        features_df['total_cogs'] / features_df['monthly_revenue'].replace(0, pd.NA)
    )
    features_df['expense_ratio'] = (
        features_df['total_expenses'] / features_df['monthly_revenue'].replace(0, pd.NA)
    )

    features_df['cogs_lag_1']      = features_df['total_cogs'].shift(1)
    features_df['cogs_lag_3']      = features_df['total_cogs'].shift(3)
    features_df['expense_lag_1']   = features_df['total_expenses'].shift(1)
    features_df['cogs_growth_mom'] = features_df['total_cogs'].pct_change(1)

    print("\n✓ COGS & Expenses Features:")
    print(features_df[['month', 'monthly_revenue', 'total_cogs', 'cogs_to_revenue_ratio', 'expense_ratio']].tail())
    return features_df


def Unit_Economics_Features(features_df: pd.DataFrame = None) -> pd.DataFrame:
    if features_df is None:
        features_df = cogs_expenses_features()

    features_df['gross_margin']      = (
        (features_df['monthly_revenue'] - features_df['total_cogs'])
        / features_df['monthly_revenue'].replace(0, pd.NA)
    )
    features_df['gross_margin_lag_1'] = features_df['gross_margin'].shift(1)
    features_df['gross_margin_ma_3']  = features_df['gross_margin'].rolling(3).mean()
    features_df['margin_delta_mom']   = features_df['gross_margin'].diff(1)

    monthly_margin = get_data_from_db("""
        SELECT strftime('%Y-%m', inv.invoice_date) AS month,
               SUM(il.quantity * (il.unit_price - p.cost))
               / NULLIF(SUM(il.quantity * il.unit_price), 0) AS weighted_avg_margin
        FROM invoice_lines il
        JOIN invoices inv ON il.invoice_id = inv.id
        JOIN products p   ON il.product_id = p.id
        WHERE inv.type = 'out_invoice'
        GROUP BY month
    """).dropna(subset=['month']).sort_values('month').reset_index(drop=True)

    features_df = features_df.merge(monthly_margin, on='month', how='left')

    print("\n✓ Unit Economics Features:")
    print(features_df[['month', 'gross_margin', 'weighted_avg_margin', 'margin_delta_mom']].tail())
    return features_df


def Cash_Flow_Features(features_df: pd.DataFrame = None) -> pd.DataFrame:
    if features_df is None:
        features_df = Unit_Economics_Features()

    dso_df = get_data_from_db("""
        SELECT strftime('%Y-%m', i.invoice_date) AS month,
               AVG(julianday(p.payment_date) - julianday(i.invoice_date)) AS dso_days
        FROM invoices i
        JOIN payments p ON i.id = p.invoice_id
        WHERE i.type = 'out_invoice'
        GROUP BY month
    """).dropna(subset=['month']).sort_values('month').reset_index(drop=True)

    overdue_df = get_data_from_db("""
        SELECT strftime('%Y-%m', i.invoice_date) AS month,
               SUM(CASE
                    WHEN p.payment_date IS NULL
                      OR julianday(p.payment_date) > julianday(i.due_date)
                    THEN i.total_amount ELSE 0
               END) AS overdue_amount,
               SUM(i.total_amount) AS total_invoiced
        FROM invoices i
        LEFT JOIN payments p ON i.id = p.invoice_id
        WHERE i.type = 'out_invoice'
        GROUP BY month
    """).dropna(subset=['month']).sort_values('month').reset_index(drop=True)

    overdue_df['overdue_ratio'] = (
        overdue_df['overdue_amount'] / overdue_df['total_invoiced'].replace(0, pd.NA)
    )

    billed_collected_df = get_data_from_db("""
        SELECT month,
               SUM(billed_this_month)    AS billed_this_month,
               SUM(collected_this_month) AS collected_this_month
        FROM (
            SELECT strftime('%Y-%m', invoice_date) AS month,
                   total_amount AS billed_this_month,
                   0            AS collected_this_month
            FROM invoices
            WHERE type = 'out_invoice'

            UNION ALL

            SELECT strftime('%Y-%m', p.payment_date) AS month,
                   0         AS billed_this_month,
                   p.amount  AS collected_this_month
            FROM payments p
            JOIN invoices i ON p.invoice_id = i.id
            WHERE i.type = 'out_invoice'
        )
        WHERE month IS NOT NULL
        GROUP BY month
    """).dropna(subset=['month']).sort_values('month').reset_index(drop=True)

    billed_collected_df['collection_gap']      = (
        billed_collected_df['billed_this_month'] - billed_collected_df['collected_this_month']
    )
    billed_collected_df['collection_gap_lag_1'] = billed_collected_df['collection_gap'].shift(1)

    payment_method_df = get_data_from_db("""
        SELECT strftime('%Y-%m', p.payment_date) AS month,
               SUM(CASE WHEN LOWER(p.payment_method) LIKE '%cash%'
                        THEN p.amount ELSE 0 END)
               / NULLIF(SUM(p.amount), 0) AS pct_paid_cash,
               SUM(CASE WHEN LOWER(p.payment_method) LIKE '%credit%'
                          OR LOWER(p.payment_method) LIKE '%card%'
                        THEN p.amount ELSE 0 END)
               / NULLIF(SUM(p.amount), 0) AS pct_paid_credit
        FROM payments p
        JOIN invoices i ON p.invoice_id = i.id
        WHERE i.type = 'out_invoice'
        GROUP BY month
    """).dropna(subset=['month']).sort_values('month').reset_index(drop=True)

    features_df = (
        features_df
        .merge(dso_df, on='month', how='left')
        .merge(overdue_df[['month', 'overdue_amount', 'overdue_ratio']], on='month', how='left')
        .merge(billed_collected_df, on='month', how='left')
        .merge(payment_method_df, on='month', how='left')
    )

    print("\n✓ Cash Flow Features:")
    print(features_df[['month', 'dso_days', 'overdue_ratio', 'collection_gap', 'pct_paid_cash']].tail())
    return features_df


def Volume_Activity_Features(features_df: pd.DataFrame = None) -> pd.DataFrame:
    if features_df is None:
        features_df = Cash_Flow_Features()

    # FIX: use supplier_id (kept as-is per your decision) but label correctly
    # NOTE: for out_invoices supplier_id actually holds the customer reference
    tx_volume_df = get_data_from_db("""
        SELECT strftime('%Y-%m', invoice_date) AS month,
               COUNT(*)                        AS invoice_count,
               SUM(total_amount) / COUNT(*)    AS avg_invoice_value,
               COUNT(DISTINCT supplier_id)     AS unique_customers
        FROM invoices
        WHERE type = 'out_invoice'
        GROUP BY month
    """).dropna(subset=['month']).sort_values('month').reset_index(drop=True)

    # FIX: use supplier_id consistently in concentration CTE (matches your schema)
    concentration_df = get_data_from_db("""
        WITH MonthlyRevenue AS (
            SELECT strftime('%Y-%m', invoice_date) AS month,
                   supplier_id,
                   SUM(total_amount) AS customer_revenue
            FROM invoices
            WHERE type = 'out_invoice'
            GROUP BY month, supplier_id
        ),
        TotalPerMonth AS (
            SELECT month, SUM(customer_revenue) AS total_revenue
            FROM MonthlyRevenue
            GROUP BY month
        ),
        RankedRevenue AS (
            SELECT m.month,
                   m.customer_revenue,
                   t.total_revenue,
                   ROW_NUMBER() OVER (PARTITION BY m.month ORDER BY m.customer_revenue DESC) AS rank
            FROM MonthlyRevenue m
            JOIN TotalPerMonth t ON m.month = t.month
        )
        SELECT month,
               SUM(CASE WHEN rank = 1  THEN customer_revenue ELSE 0 END)
               / NULLIF(MAX(total_revenue), 0) AS top1_customer_pct,
               SUM(CASE WHEN rank <= 3 THEN customer_revenue ELSE 0 END)
               / NULLIF(MAX(total_revenue), 0) AS top3_customers_pct
        FROM RankedRevenue
        GROUP BY month
    """).dropna(subset=['month']).sort_values('month').reset_index(drop=True)

    po_df = get_data_from_db("""
        SELECT strftime('%Y-%m', order_date) AS month,
               COUNT(*)           AS po_count,
               SUM(total_amount)  AS po_total_value
        FROM purchase_orders
        WHERE status = 'done'
        GROUP BY month
    """).dropna(subset=['month']).sort_values('month').reset_index(drop=True)

    po_df['po_lag_1'] = po_df['po_total_value'].shift(1)

    features_df = (
        features_df
        .merge(tx_volume_df, on='month', how='left')
        .merge(concentration_df, on='month', how='left')
        .merge(po_df, on='month', how='left')
    )

    print("\n✓ Volume & Activity Features:")
    print(features_df[['month', 'invoice_count', 'unique_customers', 'top1_customer_pct', 'po_total_value']].tail())
    return features_df


# ─────────────────────────────────────────────
# Orchestrator — run this, not the individuals
# ─────────────────────────────────────────────

def build_feature_pipeline() -> pd.DataFrame:
    print("=" * 50)
    print("Running feature pipeline...")
    print("=" * 50)

    revenue_df  = Revenue_Features()
    assert not revenue_df.empty, "Pipeline aborted: Revenue_Features returned no data"

    features_df = cogs_expenses_features(revenue_df)
    assert not features_df.empty, "Pipeline aborted: cogs_expenses_features returned no data"

    features_df = Unit_Economics_Features(features_df)
    features_df = Cash_Flow_Features(features_df)
    features_df = Volume_Activity_Features(features_df)

    print("\n" + "=" * 50)
    print(f"Pipeline complete. Shape: {features_df.shape}")
    print(f"Columns: {list(features_df.columns)}")
    print("=" * 50)

    return features_df




import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import xgboost as xgb

from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, confusion_matrix, classification_report
from xgboost import XGBClassifier

sns.set_style("whitegrid")


df = pd.read_csv("invoices.csv")

df.head()













# # ─────────────────────────────────────────────
# # Entry point
# # ─────────────────────────────────────────────

# if __name__ == "__main__":
#     features_df = build_feature_pipeline()