import pandas as pd


def clean_orders(df):
    """Cleans the orders table: handles timestamps, flags deliveries, and removes duplicates."""
    df_clean = df.copy()

    # WHY: Remove duplicate order IDs to ensure a 1:1 relationship in our fact table
    df_clean = df_clean.drop_duplicates(subset=['order_id'])

    # WHY: Convert strings to datetime objects so we can do time-based math (like delivery days).
    # errors='coerce' turns unparseable junk into NaT instead of crashing the pipeline.
    time_cols = [
        'order_purchase_timestamp', 'order_approved_at',
        'order_delivered_carrier_date', 'order_delivered_customer_date',
        'order_estimated_delivery_date'
    ]
    for col in time_cols:
        df_clean[col] = pd.to_datetime(df_clean[col], errors='coerce')

    # WHY: Create a boolean flag for delivered items.
    # Do not impute fake dates for undelivered items, just flag them.
    df_clean['is_delivered'] = df_clean['order_delivered_customer_date'].notna()

    # WHY: Create two versions for different analytical needs.
    # df_delivered is for speed/satisfaction analysis. df_all_statuses is for cancellation rates.
    df_delivered = df_clean[df_clean['order_status'] == 'delivered'].copy()
    df_all_statuses = df_clean.copy()

    # WHY: Some rows have order_status == 'delivered' but a null delivery date
    # (inconsistent source data). Any delivery-days math on these produces NaN,
    # so drop them from the speed/satisfaction dataset specifically.
    # df_all_statuses is left untouched since it's meant for cancellation-rate
    # analysis, where these rows are still valid.
    df_delivered = df_delivered.dropna(subset=['order_delivered_customer_date'])

    return df_delivered, df_all_statuses


def clean_geolocation(df):
    """Deduplicates the geolocation table and collapses it to one row per zip prefix."""
    # WHY: 261,831 of ~1M rows are exact duplicates (same zip/lat/lng/city/state
    # repeated). Drop those first before any aggregation.
    df_clean = df.drop_duplicates()

    # WHY: A single zip_code_prefix still maps to many different lat/lng pairs
    # (different addresses within the same zip) and occasionally inconsistent
    # city/state spellings for the same prefix. Downstream joins (customers/sellers
    # -> geolocation) are done on zip_code_prefix, not exact coordinates, so we
    # need exactly one row per prefix or the join will fan out and duplicate rows.
    df_grouped = df_clean.groupby('geolocation_zip_code_prefix').agg(
        geolocation_lat=('geolocation_lat', 'mean'),
        geolocation_lng=('geolocation_lng', 'mean'),
        # WHY: use the most frequent city/state for this prefix rather than the
        # first row encountered, since raw entries can be inconsistently spelled.
        geolocation_city=('geolocation_city', lambda x: x.mode().iloc[0] if not x.mode().empty else x.iloc[0]),
        geolocation_state=('geolocation_state', lambda x: x.mode().iloc[0] if not x.mode().empty else x.iloc[0])
    ).reset_index()

    return df_grouped


def clean_products(df_prod, df_trans):
    """Merges English translations, fills missing categories, and handles missing dimensions."""
    # WHY: Merge translation table so our dashboard is in English, not Portuguese.
    df_merged = df_prod.merge(df_trans, on='product_category_name', how='left')

    # WHY: Drop the original Portuguese column to save memory and avoid confusion.
    df_merged = df_merged.drop(columns=['product_category_name'])

    # WHY: Unmapped or missing categories should be bucketed into 'other' instead of remaining null.
    df_merged['product_category_name_english'] = df_merged['product_category_name_english'].fillna('other')

    # WHY: product_name_lenght / product_description_lenght / product_photos_qty are
    # missing together on the same ~610 rows as the category (products with no
    # listing content at all). No safe way to impute these, so drop them.
    content_cols = ['product_name_lenght', 'product_description_lenght', 'product_photos_qty']
    df_merged = df_merged.dropna(subset=content_cols)

    # WHY: product_weight_g/length_cm/height_cm/width_cm are missing on only ~2 rows.
    # These are needed for freight/shipping calculations, so drop rather than guess.
    dimension_cols = ['product_weight_g', 'product_length_cm', 'product_height_cm', 'product_width_cm']
    df_merged = df_merged.dropna(subset=dimension_cols)

    return df_merged


def aggregate_payments(df):
    """Aggregates multiple payment rows into a single row per order."""
    # WHY: Payments table has multiple rows if a customer used two cards or split payments.
    # We need exactly 1 row per order for our star schema fact table.

    # 1. Find the primary payment type (the one with the highest value per order)
    primary_type = df.sort_values('payment_value', ascending=False).drop_duplicates('order_id')[['order_id', 'payment_type']]
    primary_type = primary_type.rename(columns={'payment_type': 'primary_payment_type'})

    # 2. Aggregate the math
    agg_df = df.groupby('order_id').agg(
        total_payment=('payment_value', 'sum'),
        max_installments=('payment_installments', 'max')
    ).reset_index()

    # 3. Bring them together
    final_payments = agg_df.merge(primary_type, on='order_id', how='left')

    return final_payments


def clean_reviews(df):
    """Removes duplicate reviews and ensures exactly one review row per order."""
    # WHY: Multiple rows for the same review_id inflate/skew our average scores.
    df_clean = df.drop_duplicates(subset=['review_id'])

    # WHY: review_id being unique doesn't guarantee order_id is unique — some orders
    # have more than one distinct review (e.g. a follow-up review). Joining reviews
    # to orders on order_id when it isn't 1:1 fans out the join and double-counts
    # that order's delivery/delay data. Keep the most recently answered review so
    # every order contributes exactly one review row downstream.
    df_clean = df_clean.sort_values('review_answer_timestamp', ascending=False)
    df_clean = df_clean.drop_duplicates(subset=['order_id'])

    return df_clean


def clean_strings(df, state_cols=None):
    """Standardizes string formatting and capitalizes state codes."""
    df_clean = df.copy()

    # WHY: Clean up any accidental leading/trailing spaces.
    # NOTE: intentionally NOT using .astype(str) here — that would convert real
    # NaN values into the literal string "nan", making null checks downstream
    # silently return False on rows that are actually missing (this affects
    # review_comment_title/message, which are ~58-88% null in the raw data).
    # .str.strip() already works directly on object columns and preserves NaN.
    str_cols = df_clean.select_dtypes(include=['object']).columns
    for col in str_cols:
        df_clean[col] = df_clean[col].str.strip()

    # WHY: State codes must be perfectly matching uppercase for Power BI map visuals
    if state_cols:
        for col in state_cols:
            if col in df_clean.columns:
                df_clean[col] = df_clean[col].str.upper()

    return df_clean