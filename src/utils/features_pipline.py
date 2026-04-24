import os
import math
import sqlite3
import pandas as pd

pd.set_option('future.no_silent_downcasting', True)

_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data/ai_audit_db.sqlite")

# ─────────────────────────────────────────────────────────────────────────────
# Database Helper
# ─────────────────────────────────────────────────────────────────────────────
def get_data_from_db(query: str) -> pd.DataFrame:
    try:
        conn = sqlite3.connect(_DB_PATH, timeout=30)
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    except Exception as e:
        print(f"❌ DB error: {e}")
        return pd.DataFrame()


# ─────────────────────────────────────────────────────────────────────────────
# 1. Revenue Features
# ─────────────────────────────────────────────────────────────────────────────
def Revenue_Features() -> pd.DataFrame:
    """Monthly revenue with lags, rolling stats, and calendar encodings."""

    revenue_by_month = get_data_from_db("""
        SELECT SUM(total_amount) AS total,
               strftime('%Y-%m', invoice_date) AS month
        FROM invoices
        WHERE type = 'out_invoice'
        GROUP BY month
        ORDER BY month
    """)

    if revenue_by_month.empty:
        raise ValueError("Revenue_Features: No invoice data found.")

    revenue_by_month['month'] = pd.to_datetime(revenue_by_month['month'])
    revenue_by_month = revenue_by_month.sort_values('month').reset_index(drop=True)

    revenue_by_month['revenue_lag_1']      = revenue_by_month['total'].shift(1)
    revenue_by_month['revenue_lag_2']      = revenue_by_month['total'].shift(2)
    revenue_by_month['revenue_lag_3']      = revenue_by_month['total'].shift(3)
    revenue_by_month['revenue_growth_mom'] = revenue_by_month['total'].pct_change(1)
    revenue_by_month['revenue_ma_3']       = revenue_by_month['total'].rolling(3).mean()
    revenue_by_month['revenue_ma_6']       = revenue_by_month['total'].rolling(6).mean()
    revenue_by_month['revenue_std_3']      = revenue_by_month['total'].rolling(3).std()

    revenue_by_month['month_num']   = revenue_by_month['month'].dt.month
    revenue_by_month['quarter']     = revenue_by_month['month'].dt.quarter
    revenue_by_month['month_sin']   = (revenue_by_month['month_num'] * 2 * math.pi / 12).apply(math.sin)
    revenue_by_month['month_cos']   = (revenue_by_month['month_num'] * 2 * math.pi / 12).apply(math.cos)
    revenue_by_month['is_year_end'] = revenue_by_month['month_num'].isin([11, 12]).astype(int)

    revenue_by_month['month'] = revenue_by_month['month'].dt.strftime('%Y-%m')

    print("✅ Revenue Features:")
    print(revenue_by_month[['month', 'total', 'revenue_growth_mom', 'revenue_ma_3', 'revenue_std_3']].tail())
    return revenue_by_month


# ─────────────────────────────────────────────────────────────────────────────
# 2. COGS & Operating Expenses
# ─────────────────────────────────────────────────────────────────────────────
def cogs_expenses_features(features_df: pd.DataFrame) -> pd.DataFrame:
    """
    COGS & Expenses calculated using exact schema elements.
    COGS: invoice_lines × products.cost
    Expenses: journal_lines where account type = 'expense'
    """
    
    # ── COGS from invoice lines × product cost ───────────
    monthly_cogs = get_data_from_db("""
        SELECT strftime('%Y-%m', inv.invoice_date) AS month,
               SUM(il.quantity * COALESCE(p.cost, 0)) AS total_cogs
        FROM invoice_lines il
        JOIN invoices inv ON il.invoice_id = inv.id
        JOIN products p  ON il.product_id = p.id
        WHERE inv.type = 'out_invoice'
          AND p.cost > 0
        GROUP BY month
        ORDER BY month
    """)

    # ── Fallback 1: COGS from vendor bills (in_invoice) ──────────────────
    if monthly_cogs.empty or (not monthly_cogs.empty and monthly_cogs['total_cogs'].sum() == 0):
        print("⚠️  products.cost = 0 or missing. Falling back to vendor bill COGS.")
        monthly_cogs = get_data_from_db("""
            SELECT strftime('%Y-%m', invoice_date) AS month,
                   SUM(total_amount) AS total_cogs
            FROM invoices
            WHERE type = 'in_invoice'
              AND (source_id LIKE 'BILL/%' OR source_id LIKE '%BILL%' OR source_id IS NULL)
            GROUP BY month
            ORDER BY month
        """)
        # If no BILL filter results, use all in_invoices * 0.65
        if monthly_cogs.empty or monthly_cogs['total_cogs'].sum() == 0:
            monthly_cogs = get_data_from_db("""
                SELECT strftime('%Y-%m', invoice_date) AS month,
                       SUM(total_amount * 0.65) AS total_cogs
                FROM invoices
                WHERE type = 'in_invoice'
                GROUP BY month
                ORDER BY month
            """)

    # ── Expenses from journal_lines ───────────────────────────────────────
    monthly_expenses = get_data_from_db("""
        SELECT strftime('%Y-%m', je.entry_date) AS month,
               SUM(jl.debit) - SUM(jl.credit) AS total_expenses
        FROM journal_lines jl
        JOIN journal_entries je ON jl.journal_entry_id = je.id
        JOIN accounts a ON jl.account_id = a.id
        WHERE a.type = 'expense'
        GROUP BY month
        ORDER BY month
    """)

    # ── Fallback: opex from in_invoice vendor bills (EXP prefix) ─────────
    if monthly_expenses.empty or monthly_expenses['total_expenses'].sum() == 0:
        print("⚠️  No journal expense entries. Falling back to EXP vendor bills.")
        monthly_expenses = get_data_from_db("""
            SELECT strftime('%Y-%m', invoice_date) AS month,
                   SUM(total_amount) AS total_expenses
            FROM invoices
            WHERE type = 'in_invoice'
              AND source_id LIKE 'EXP/%'
            GROUP BY month
            ORDER BY month
        """)

        # Last resort: estimate expenses as 15% of in_invoice total
        if monthly_expenses.empty or monthly_expenses['total_expenses'].sum() == 0:
            print("⚠️  No EXP bills either. Estimating expenses as 15% of in_invoice total.")
            monthly_expenses = get_data_from_db("""
                SELECT strftime('%Y-%m', invoice_date) AS month,
                       SUM(total_amount * 0.15) AS total_expenses
                FROM invoices
                WHERE type = 'in_invoice'
                GROUP BY month
                ORDER BY month
            """)

    # ── Merge ─────────────────────────────────────────────────────────────
    features_df = (
        features_df.rename(columns={'total': 'monthly_revenue'})
        .merge(monthly_cogs,     on='month', how='left')
        .merge(monthly_expenses, on='month', how='left')
    )

    if features_df['total_cogs'].isna().any():
        missing = features_df.loc[features_df['total_cogs'].isna(), 'month'].tolist()
        print(f"⚠️  COGS missing for {len(missing)} months. Filling with 0.")
        
    features_df['total_cogs']     = features_df['total_cogs'].fillna(0).infer_objects(copy=False)
    features_df['total_expenses'] = features_df['total_expenses'].fillna(0).infer_objects(copy=False)

    features_df['cogs_to_revenue_ratio'] = (
        features_df['total_cogs'] / features_df['monthly_revenue'].replace(0, pd.NA)
    )
    features_df['expense_ratio'] = (
        features_df['total_expenses'] / features_df['monthly_revenue'].replace(0, pd.NA)
    )

    print("\n✅ COGS & Expenses Features:")
    print(features_df[['month', 'monthly_revenue', 'total_cogs', 'cogs_to_revenue_ratio', 'expense_ratio']].tail())
    return features_df


# ─────────────────────────────────────────────────────────────────────────────
# 3. Unit Economics
# ─────────────────────────────────────────────────────────────────────────────
def Unit_Economics_Features(features_df: pd.DataFrame) -> pd.DataFrame:

    features_df['gross_margin'] = (
        (features_df['monthly_revenue'] - features_df['total_cogs'])
        / features_df['monthly_revenue'].replace(0, pd.NA)
    )

    monthly_margin = get_data_from_db("""
        SELECT strftime('%Y-%m', inv.invoice_date) AS month,
               SUM(il.quantity * (il.unit_price - COALESCE(p.cost, 0)))
               / NULLIF(SUM(il.quantity * il.unit_price), 0) AS weighted_avg_margin
        FROM invoice_lines il
        JOIN invoices inv ON il.invoice_id = inv.id
        JOIN products p  ON il.product_id = p.id
        WHERE inv.type = 'out_invoice'
        GROUP BY month
        ORDER BY month
    """)

    if not monthly_margin.empty and 'weighted_avg_margin' in monthly_margin.columns:
        features_df = features_df.merge(monthly_margin, on='month', how='left')
    else:
        features_df['weighted_avg_margin'] = features_df['gross_margin']

    print("\n✅ Unit Economics Features:")
    print(features_df[['month', 'gross_margin', 'weighted_avg_margin']].tail())
    return features_df


# ─────────────────────────────────────────────────────────────────────────────
# 4. Cash Flow & Collection Metrics
# ─────────────────────────────────────────────────────────────────────────────
def Cash_Flow_Features(features_df: pd.DataFrame) -> pd.DataFrame:

    # ── DSO ───────────────────────────────────────────────────────────────
    dso_df = get_data_from_db("""
        SELECT strftime('%Y-%m', i.invoice_date) AS month,
               AVG(julianday(p.payment_date) - julianday(i.invoice_date)) AS dso_days
        FROM invoices i
        JOIN payments p ON i.id = p.invoice_id
        WHERE i.type = 'out_invoice'
          AND p.payment_date IS NOT NULL
        GROUP BY month
        ORDER BY month
    """)

    # ── Overdue ───────────────────────────────────────────────────────────
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
        ORDER BY month
    """)
    if not overdue_df.empty:
        overdue_df['overdue_ratio'] = (
            overdue_df['overdue_amount']
            / overdue_df['total_invoiced'].replace(0, pd.NA)
        )

    # ── Billed vs Collected ───────────────────────────────────────────────
    billed_collected_df = get_data_from_db("""
        SELECT month,
               SUM(billed_this_month)    AS billed_this_month,
               SUM(collected_this_month) AS collected_this_month
        FROM (
            SELECT strftime('%Y-%m', invoice_date) AS month,
                   total_amount AS billed_this_month,
                   0 AS collected_this_month
            FROM invoices
            WHERE type = 'out_invoice'

            UNION ALL

            SELECT strftime('%Y-%m', p.payment_date) AS month,
                   0 AS billed_this_month,
                   p.amount AS collected_this_month
            FROM payments p
            JOIN invoices i ON i.id = p.invoice_id
            WHERE i.type = 'out_invoice'
              AND p.payment_date IS NOT NULL
        )
        WHERE month IS NOT NULL
        GROUP BY month
        ORDER BY month
    """)

    # ── Payment method split ──────────────────────────────────────────────
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
        JOIN invoices i ON i.id = p.invoice_id
        WHERE i.type = 'out_invoice'
          AND p.payment_date IS NOT NULL
        GROUP BY month
        ORDER BY month
    """)

    # ── Merge ─────────────────────────────────────────────────────────────
    if not dso_df.empty:
        features_df = features_df.merge(dso_df, on='month', how='left')
    else:
        features_df['dso_days'] = pd.NA

    if not overdue_df.empty:
        features_df = features_df.merge(
            overdue_df[['month', 'overdue_amount', 'overdue_ratio']], on='month', how='left'
        )
    else:
        features_df['overdue_amount'] = 0.0
        features_df['overdue_ratio']  = 0.0

    if not billed_collected_df.empty:
        features_df = features_df.merge(billed_collected_df, on='month', how='left')
        features_df['collection_gap']       = (
            features_df['billed_this_month'] - features_df['collected_this_month']
        )
        features_df['collection_gap_lag_1'] = features_df['collection_gap'].shift(1)
    else:
        features_df['billed_this_month']    = features_df['monthly_revenue']
        features_df['collected_this_month'] = pd.NA
        features_df['collection_gap']       = pd.NA
        features_df['collection_gap_lag_1'] = pd.NA

    if not payment_method_df.empty:
        features_df = features_df.merge(payment_method_df, on='month', how='left')
    else:
        features_df['pct_paid_cash']   = pd.NA
        features_df['pct_paid_credit'] = pd.NA

    print("\n✅ Cash Flow Features:")
    cols = [c for c in ['month', 'dso_days', 'overdue_ratio', 'collection_gap', 'pct_paid_cash']
            if c in features_df.columns]
    print(features_df[cols].tail())
    return features_df


# ─────────────────────────────────────────────────────────────────────────────
# 5. Volume, Customer Concentration & Purchase Order Activity
# ─────────────────────────────────────────────────────────────────────────────
def Volume_Activity_Features(features_df: pd.DataFrame) -> pd.DataFrame:

    # ── Invoice volume ────────────────────────────────────────────────────
    tx_volume_df = get_data_from_db("""
        SELECT strftime('%Y-%m', invoice_date) AS month,
               COUNT(*) AS invoice_count,
               AVG(total_amount) AS avg_invoice_value,
               COUNT(DISTINCT customer_id) AS unique_customers
        FROM invoices
        WHERE type = 'out_invoice'
        GROUP BY month
        ORDER BY month
    """)

    # ── Customer concentration ────────────────────────────────────────────
    concentration_df = get_data_from_db("""
        WITH MonthlyRevenue AS (
            SELECT strftime('%Y-%m', invoice_date) AS month,
                   customer_id,
                   SUM(total_amount) AS customer_revenue
            FROM invoices
            WHERE type = 'out_invoice'
            GROUP BY month, customer_id
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
                   ROW_NUMBER() OVER (
                       PARTITION BY m.month ORDER BY m.customer_revenue DESC
                   ) AS rnk
            FROM MonthlyRevenue m
            JOIN TotalPerMonth t ON m.month = t.month
        )
        SELECT month,
               SUM(CASE WHEN rnk = 1  THEN customer_revenue ELSE 0 END)
               / NULLIF(MAX(total_revenue), 0) AS top1_customer_pct,
               SUM(CASE WHEN rnk <= 3 THEN customer_revenue ELSE 0 END)
               / NULLIF(MAX(total_revenue), 0) AS top3_customers_pct
        FROM RankedRevenue
        GROUP BY month
        ORDER BY month
    """)

    # ── Purchase orders ───────────────────────────────────────────────────
    po_df = get_data_from_db("""
        SELECT strftime('%Y-%m', order_date) AS month,
               COUNT(*) AS po_count,
               SUM(total_amount) AS po_total_value
        FROM purchase_orders
        WHERE status IN ('purchase', 'done', 'confirmed')
        GROUP BY month
        ORDER BY month
    """)

    # ── Merge ─────────────────────────────────────────────────────────────
    if not tx_volume_df.empty:
        features_df = features_df.merge(tx_volume_df, on='month', how='left')
    if not concentration_df.empty:
        features_df = features_df.merge(concentration_df, on='month', how='left')
    if not po_df.empty:
        features_df = features_df.merge(po_df, on='month', how='left')
        features_df['po_lag_1'] = features_df['po_total_value'].shift(1)
    else:
        features_df['po_count']       = pd.NA
        features_df['po_total_value'] = pd.NA
        features_df['po_lag_1']       = pd.NA

    # ── Lagged features (computed on full merged df for correct alignment) ─
    features_df['gross_margin_lag_1'] = features_df['gross_margin'].shift(1)
    features_df['gross_margin_ma_3']  = features_df['gross_margin'].rolling(3).mean()
    features_df['margin_delta_mom']   = features_df['gross_margin'].diff(1)

    features_df['cogs_lag_1']      = features_df['total_cogs'].shift(1)
    features_df['cogs_lag_3']      = features_df['total_cogs'].shift(3)
    features_df['expense_lag_1']   = features_df['total_expenses'].shift(1)
    features_df['cogs_growth_mom'] = (
        features_df['total_cogs']
        / features_df['total_cogs'].shift(1).replace(0, pd.NA)
    ) - 1

    # ── Target ────────────────────────────────────────────────────────────
    features_df['net_profit']    = (
        features_df['monthly_revenue']
        - features_df['total_cogs']
        - features_df['total_expenses']
    )
    features_df['target_profit'] = features_df['net_profit'].shift(-1)
    features_df = features_df.dropna(subset=['target_profit'])

    print("\n✅ Volume & Activity Features:")
    cols_to_print = [c for c in ['month', 'invoice_count', 'unique_customers', 'top1_customer_pct', 'po_total_value'] if c in features_df.columns]
    print(features_df[cols_to_print].tail())
    return features_df


# ─────────────────────────────────────────────────────────────────────────────
# Orchestrator
# ─────────────────────────────────────────────────────────────────────────────
def build_feature_pipeline() -> pd.DataFrame:
    print("=" * 60)
    print("🚀 Running feature engineering pipeline...")
    print("=" * 60)

    revenue_df  = Revenue_Features()
    features_df = cogs_expenses_features(revenue_df)
    features_df = Unit_Economics_Features(features_df)
    features_df = Cash_Flow_Features(features_df)
    features_df = Volume_Activity_Features(features_df)

    print("\n" + "=" * 60)
    print(f"✅ Pipeline complete. Shape: {features_df.shape}")
    print(f"📊 Columns ({len(features_df.columns)}): {list(features_df.columns)}")
    print("=" * 60)

    for col in features_df.columns:
        if col != 'month':
            features_df[col] = pd.to_numeric(features_df[col], errors='coerce')

    return features_df