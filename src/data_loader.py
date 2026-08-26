import os
import pandas as pd


def load_all_tables(raw_folder_path):
    """
    Load all CSV files from the raw data directory.

    Parameters
    ----------
    raw_folder_path : str
        Path to the folder containing raw CSV files.

    Returns
    -------
    dict
        Dictionary where:
        key   = table name
        value = pandas DataFrame
    """

    tables = {}

    print("=" * 70)
    print("LOADING RAW DATA")
    print("=" * 70)

    csv_files = sorted(
        file for file in os.listdir(raw_folder_path)
        if file.lower().endswith(".csv")
    )

    if not csv_files:
        raise FileNotFoundError(
            f"No CSV files found in: {raw_folder_path}"
        )

    for file in csv_files:

        file_path = os.path.join(
            raw_folder_path,
            file
        )

        table_name = os.path.splitext(file)[0]

        try:
            df = pd.read_csv(file_path)

            tables[table_name] = df

            print(
                f"✓ {table_name:<45} "
                f"{len(df):>10,} rows × "
                f"{len(df.columns):>3} columns"
            )

        except Exception as e:

            print(f"✗ Failed to load {file}")
            print(f"  Error: {e}")

    print("=" * 70)
    print(f"Successfully loaded {len(tables)} tables")
    print("=" * 70)

    return tables


def get_table_summary(tables):
    """
    Generate a high-level summary of all loaded tables.

    Returns
    -------
    pandas.DataFrame
    """

    summary = []

    for table_name, df in tables.items():

        summary.append({
            "table_name": table_name,
            "rows": len(df),
            "columns": len(df.columns),
            "memory_mb": round(
                df.memory_usage(deep=True).sum() / (1024 ** 2),
                2
            )
        })

    return pd.DataFrame(summary)


def audit_database(tables, output_path):
    """
    Perform a basic data-quality audit on all tables
    and save the results as a text report.

    Checks:
    - Number of rows
    - Number of columns
    - Duplicate rows
    - Missing values
    - Data types
    """

    print("=" * 70)
    print("GENERATING DATA QUALITY AUDIT")
    print("=" * 70)

    total_rows = 0
    total_nulls = 0
    total_duplicates = 0

    with open(output_path, "w", encoding="utf-8") as f:

        f.write(
            "E-COMMERCE OPERATIONS & CUSTOMER EXPERIENCE ANALYTICS\n"
        )
        f.write("DATA QUALITY AUDIT REPORT\n")
        f.write("=" * 80 + "\n\n")

        for table_name, df in tables.items():

            rows, columns = df.shape

            duplicate_rows = df.duplicated().sum()
            null_count = df.isnull().sum().sum()

            total_rows += rows
            total_nulls += null_count
            total_duplicates += duplicate_rows

            # -------------------------------------------------
            # Table Header
            # -------------------------------------------------

            f.write("=" * 80 + "\n")
            f.write(f"TABLE: {table_name}\n")
            f.write("=" * 80 + "\n")

            f.write(f"Rows: {rows:,}\n")
            f.write(f"Columns: {columns:,}\n")
            f.write(
                f"Duplicate Rows: {duplicate_rows:,}\n"
            )
            f.write(
                f"Total Null Values: {null_count:,}\n\n"
            )

            # -------------------------------------------------
            # Column Details
            # -------------------------------------------------

            f.write("COLUMN DETAILS\n")
            f.write("-" * 80 + "\n")

            for column in df.columns:

                dtype = str(df[column].dtype)
                nulls = df[column].isnull().sum()
                null_pct = (
                    nulls / len(df) * 100
                    if len(df) > 0
                    else 0
                )

                unique_values = df[column].nunique(
                    dropna=True
                )

                f.write(
                    f"{column}\n"
                    f"  Data Type       : {dtype}\n"
                    f"  Null Count      : {nulls:,}\n"
                    f"  Null Percentage : {null_pct:.2f}%\n"
                    f"  Unique Values   : {unique_values:,}\n\n"
                )

        # -----------------------------------------------------
        # Cross-table summary
        # -----------------------------------------------------

        f.write("=" * 80 + "\n")
        f.write("CROSS-TABLE SUMMARY\n")
        f.write("=" * 80 + "\n")

        f.write(
            f"Number of Tables       : {len(tables):,}\n"
        )

        f.write(
            f"Total Rows             : {total_rows:,}\n"
        )

        f.write(
            f"Total Null Values      : {total_nulls:,}\n"
        )

        f.write(
            f"Total Duplicate Rows   : {total_duplicates:,}\n"
        )

    print(f"✓ Audit report saved to:")
    print(f"  {output_path}")

    print("=" * 70)