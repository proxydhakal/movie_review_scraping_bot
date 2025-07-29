import csv
import os
import logging
from pathlib import Path
from datetime import datetime
import psycopg
from dotenv import load_dotenv

# === Load environment variables ===
load_dotenv()

DB_CONFIG = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", 5432),
}

# === Logging Setup ===
def setup_logger():
    today = datetime.now()
    log_dir = Path("output") / str(today.year) / today.strftime("%Y-%m") 
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{today.strftime('%Y%m%d')}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logger()


def fetch_existing_reviews(app_id: int) -> set:
    """
    Return a set of existing review texts from DB for deduplication.
    """
    existing = set()
    try:
        with psycopg.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT review FROM steam_reviews WHERE app_id = %s", (app_id,))
                existing = {row[0] for row in cur.fetchall()}
        logger.info(f"Fetched {len(existing)} existing reviews from DB.")
    except Exception as e:
        logger.error(f"❌ Error fetching existing reviews: {e}")
    return existing


def insert_reviews_into_db_incremental(data, app_id):
    """
    Insert new reviews into DB with deduplication.
    """
    try:
        with psycopg.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:
                insert_query = """
                    INSERT INTO steam_reviews (app_id, username, hours, review_date, review, helpful, funny)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING;
                """
                for review in data:
                    cur.execute(insert_query, (
                        app_id,
                        review["Username"],
                        review["Hours"],
                        review["Date"],
                        review["Review"],
                        review["Helpful"],
                        review["Funny"]
                    ))
            conn.commit()
        logger.info(f"✅ Incremental insert of {len(data)} new reviews into DB.")
    except Exception as e:
        logger.error(f"❌ DB insert error (incremental): {e}")


def save_reviews_to_csv_incremental(data, app_id=220):
    """
    Append reviews to CSV (if not already written).
    """
    output_dir = Path(os.getenv("ROBOT_ARTIFACTS", "output"))
    output_dir.mkdir(parents=True, exist_ok=True)
    output_csv = output_dir / f"steam_reviews_app_{app_id}.csv"

    try:
        already_seen = set()
        if output_csv.exists():
            with open(output_csv, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    already_seen.add(row["Review"])

        with open(output_csv, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["Username", "Hours", "Date", "Review", "Helpful", "Funny"])
            if not output_csv.exists() or output_csv.stat().st_size == 0:
                writer.writeheader()
            for row in data:
                if row["Review"] not in already_seen:
                    writer.writerow(row)
        logger.info(f"✅ Appended {len(data)} new reviews to CSV.")
    except Exception as e:
        logger.error(f"❌ CSV append error: {e}")

def create_reviews_table():
    """
    Create PostgreSQL table for reviews if it doesn't exist.
    """
    try:
        with psycopg.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS steam_reviews (
                        id SERIAL PRIMARY KEY,
                        app_id INTEGER,
                        username TEXT,
                        hours TEXT,
                        date TEXT,
                        review TEXT,
                        helpful INTEGER,
                        funny INTEGER
                    );
                """)
            conn.commit()
        logger.info("✅ PostgreSQL table 'steam_reviews' checked/created.")
    except Exception as e:
        logger.error(f"❌ Failed to create table: {e}")

def insert_reviews_into_db(data, app_id):
    """
    Insert scraped reviews into PostgreSQL database.
    """
    try:
        with psycopg.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:
                insert_query = """
                    INSERT INTO steam_reviews (app_id, username, hours, review_date, review, helpful, funny)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """

                for review in data:
                    cur.execute(insert_query, (
                        app_id,
                        review["Username"],
                        review["Hours"],
                        review["Date"],
                        review["Review"],
                        review["Helpful"],
                        review["Funny"]
                    ))

            conn.commit()
        logger.info(f"✅ Inserted {len(data)} reviews into PostgreSQL.")
    except Exception as e:
        logger.error(f"❌ DB insert error: {e}")
