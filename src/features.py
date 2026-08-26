import pandas as pd
import numpy as np


def build_master_dataset(df_orders_delivered, df_payments, df_reviews, df_items, df_products, df_customers):
    """
    Merges all our cleaned tables together into one massive 'Fact Table'
    and creates new columns (features) for analysis.
    """
    df_master = df_orders_delivered.copy()

    # --- 1. FEATURE ENGINEERING (The Math) ---
    time_diff = df_master['order_delivered_customer_date'] - df_master['order_purchase_timestamp']
    df_master['delivery_days'] = time_diff.dt.days

    delay_diff = df_master['order_delivered_customer_date'] - df_master['order_estimated_delivery_date']
    df_master['delay_days'] = delay_diff.dt.days

    df_master['is_late'] = (df_master['delay_days'] > 0).astype(int)

    conditions = [
        (df_master['delay_days'] <= 0),
        (df_master['delay_days'] >= 1) & (df_master['delay_days'] <= 3),
        (df_master['delay_days'] >= 4) & (df_master['delay_days'] <= 7),
        (df_master['delay_days'] >= 8) & (df_master['delay_days'] <= 14),
        (df_master['delay_days'] > 14)
    ]
    choices = ['Early or On Time', '1-3 Days Late', '4-7 Days Late', '1-2 Weeks Late', 'Over 2 Weeks Late']
    df_master['delay_bucket'] = np.select(conditions, choices, default='Unknown')

    df_master['order_month'] = df_master['order_purchase_timestamp'].dt.month
    df_master['order_year'] = df_master['order_purchase_timestamp'].dt.year
    df_master['order_hour'] = df_master['order_purchase_timestamp'].dt.hour
    df_master['order_dayofweek'] = df_master['order_purchase_timestamp'].dt.dayofweek
    df_master['order_yearmonth'] = df_master['order_purchase_timestamp'].dt.to_period('M').astype(str)

    # --- 2. MERGING REQUIRED COLUMNS (The Fix) ---

    # Merge Payments (Revenue & Payment Type)
    df_master = df_master.merge(df_payments[['order_id', 'total_payment', 'primary_payment_type', 'max_installments']],
                                on='order_id', how='left')
    df_master = df_master.rename(columns={'total_payment': 'revenue_per_order'})

    # Merge Reviews (Review Score)
    df_master = df_master.merge(df_reviews[['order_id', 'review_score']], on='order_id', how='left')

    # Merge Customers (Customer State & Unique ID for retention calculations)
    df_master = df_master.merge(df_customers[['customer_id', 'customer_unique_id', 'customer_state']], on='customer_id', how='left')

    # Merge Items & Products (Product Category)
    # Why drop duplicates? If an order has 3 items, joining directly would create 3 rows for one order.
    # We want to keep our table at 1 row per order, so we grab the category of the first item in the cart.
    # NOTE: sort by order_item_id before deduping — without this, drop_duplicates(keep='first')
    # keeps whichever row happens to appear first in the DataFrame's current order, not
    # necessarily order_item_id == 1. Sorting first makes "first item" actually mean item #1.
    first_item = df_items.sort_values('order_item_id').drop_duplicates(subset=['order_id'], keep='first')
    first_item = first_item.merge(df_products[['product_id', 'product_category_name_english']], on='product_id', how='left')

    df_master = df_master.merge(first_item[['order_id', 'product_category_name_english']], on='order_id', how='left')

    # NOTE: clean_products() drops ~610-612 rows missing full metadata, so a first item
    # pointing at one of those dropped product_ids leaves this column NaN after the merge.
    # clean_products() already buckets unmapped/missing categories into 'other' rather
    # than leaving nulls — apply the same policy here so it stays consistent end to end.
    df_master['product_category_name_english'] = df_master['product_category_name_english'].fillna('other')

    return df_master