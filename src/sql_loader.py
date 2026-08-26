import pandas as pd
from sqlalchemy import create_engine
import urllib
import sys
import os

# Dynamically find the root project folder based on this file's exact location
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from src.data_loader import load_all_tables
from src.cleaning import clean_products, clean_strings, clean_reviews


def load_to_sql():
    print("--- Starting SQL Server Data Load ---")

    # 1. DEFINE YOUR SERVER CONNECTION
    # server = '.'
    # database = 'olist_db'

    # params = urllib.parse.quote_plus(
    #     f"DRIVER={{ODBC Driver 17 for SQL Server}};"
    #     f"SERVER={server};"
    #     f"DATABASE={database};"
    #     f"Trusted_Connection=yes;"
    # )
    server = r'DESKTOP-A39MPDE\SQLEXPRESS'
    database = 'olist_db'
    
    params = urllib.parse.quote_plus(
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={server};"
        f"DATABASE={database};"
        f"Trusted_Connection=yes;"
    )
    engine = create_engine(f"mssql+pyodbc:///?odbc_connect={params}")

    # 2. LOAD RAW DATA & MASTER ORDERS
    raw_path = os.path.join(parent_dir, 'data', 'raw')
    print("Loading tables...")
    tables = load_all_tables(raw_path)

    print("\nLoading Master Orders (Fact Table)...")
    master_csv_path = os.path.join(parent_dir, 'data', 'processed', 'master_orders.csv')
    df_master = pd.read_csv(master_csv_path)

    # Convert ALL date columns for SQL compatibility.
    # NOTE: master_orders.csv also carries order_approved_at and
    # order_delivered_carrier_date (they're part of df_orders_delivered,
    # just not used in delivery_days/delay_days math). The previous
    # version only formatted 3 of the 5 date columns, leaving these two
    # as whatever raw string format pandas happened to read them in as --
    # inconsistent with the properly formatted columns once in SQL Server.
    date_cols = [
        'order_purchase_timestamp', 'order_approved_at',
        'order_delivered_carrier_date', 'order_delivered_customer_date',
        'order_estimated_delivery_date'
    ]
    for col in date_cols:
        df_master[col] = pd.to_datetime(df_master[col]).dt.strftime('%Y-%m-%d %H:%M:%S')

    # 3. PREPARE DIMENSION TABLES
    print("Preparing Dimension Tables...")
    df_products = clean_products(tables['olist_products_dataset'], tables['product_category_name_translation'])
    df_customers = clean_strings(tables['olist_customers_dataset'], state_cols=['customer_state'])
    df_sellers = clean_strings(tables['olist_sellers_dataset'], state_cols=['seller_state'])

    # WHY: previously this called .drop_duplicates(subset=['review_id'])
    # directly on the raw table -- that's the same fan-out bug we already
    # fixed in cleaning.py's clean_reviews(): review_id being unique
    # doesn't guarantee order_id is unique, so some orders still end up
    # with 2+ review rows and any join to fact_orders on order_id fans
    # out. Using the real clean_reviews() here keeps dim_reviews at
    # exactly one row per order, matching the master table it's meant
    # to sit alongside.
    df_reviews = clean_reviews(tables['olist_order_reviews_dataset'])

    # 4. PUSH TO SQL SERVER
    push_dict = {
        'fact_orders': df_master,
        'dim_products': df_products,
        'dim_customers': df_customers,
        'dim_sellers': df_sellers,
        'dim_reviews': df_reviews
    }

    for table_name, df in push_dict.items():
        print(f"Pushing {table_name} ({len(df):,} rows) to SQL Server...")
        df.to_sql(name=table_name, con=engine, if_exists='replace', index=False, chunksize=10000)
        print(f"✅ {table_name} loaded successfully.")

    print("\n🎉 ALL DATA LOADED SUCCESSFULLY TO OLIST_DB!")


if __name__ == "__main__":
    load_to_sql()