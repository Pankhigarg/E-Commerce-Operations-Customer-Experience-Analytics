import os
from urllib.parse import quote_plus

from dotenv import load_dotenv


# --------------------------------------------------
# 1. Find project root
# --------------------------------------------------
PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)


# --------------------------------------------------
# 2. Load .env from project root
# --------------------------------------------------
ENV_PATH = os.path.join(PROJECT_ROOT, ".env")

load_dotenv(ENV_PATH)


# --------------------------------------------------
# 3. Read environment variables
# --------------------------------------------------
DB_CONFIG = {
    "server": os.getenv("SQL_SERVER"),
    "database": os.getenv("SQL_DATABASE"),
    "driver": os.getenv("SQL_DRIVER"),
}


# --------------------------------------------------
# 4. Validate SQL configuration
# --------------------------------------------------
missing_db_config = [
    key
    for key, value in DB_CONFIG.items()
    if not value
]

if missing_db_config:
    raise ValueError(
        f"Missing database environment variables: "
        f"{', '.join(missing_db_config)}"
    )


# --------------------------------------------------
# 5. Build SQL Server connection string
# --------------------------------------------------
odbc_connection_string = (
    f"DRIVER={{{DB_CONFIG['driver']}}};"
    f"SERVER={DB_CONFIG['server']};"
    f"DATABASE={DB_CONFIG['database']};"
    "Trusted_Connection=yes;"
)

CONNECTION_STRING = (
    "mssql+pyodbc:///?odbc_connect="
    + quote_plus(odbc_connection_string)
)


# --------------------------------------------------
# 6. Groq API key
# --------------------------------------------------
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise ValueError(
        "GROQ_API_KEY is missing from the .env file."
    )