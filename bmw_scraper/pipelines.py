import re
import sqlite3
import logging

from scrapy.exceptions import DropItem

logger = logging.getLogger(__name__)


class ValidationAndCleaningPipeline:
    REQUIRED_FIELDS = ("model", "name", "registration")

    def process_item(self, item):
        for field in self.REQUIRED_FIELDS:
            if not item.get(field):
                logger.warning(
                    f"[ValidationPipeline] Dropping item — missing '{field}': "
                    f"{item.get('registration')}"
                )
                raise DropItem(f"Missing required field: {field}")

        mileage_raw = item.get("mileage")
        if mileage_raw:
            digits = re.sub(r"[^\d]", "", str(mileage_raw))
            item["mileage"] = int(digits) if digits else None
        else:
            item["mileage"] = None

        if item.get("fuel"):
            item["fuel"] = item["fuel"].strip().lower()

        return item


class SQLitePipeline:
    COMMIT_EVERY = 10

    _CREATE_TABLE_SQL = """
        CREATE TABLE IF NOT EXISTS bmw_cars (
            registration TEXT UNIQUE NOT NULL,
            model TEXT NOT NULL,
            name TEXT NOT NULL,
            mileage INTEGER,
            registered TEXT,
            engine TEXT,
            "range" TEXT,
            exterior TEXT,
            fuel TEXT,
            transmission TEXT,
            upholstery TEXT
        )
    """

    _INSERT_SQL = """
        INSERT OR IGNORE INTO bmw_cars
            (registration, model, name, mileage, registered, engine,
             "range", exterior, fuel, transmission, upholstery)
        VALUES
            (:registration, :model, :name, :mileage, :registered, :engine,
             :range, :exterior, :fuel, :transmission, :upholstery)
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self._insert_count = 0

    @classmethod
    def from_crawler(cls, crawler):
        return cls(db_path=crawler.settings.get("SQLITE_DB_PATH", "bmw_cars.db"))

    def open_spider(self):
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.cursor = self.conn.cursor()
            self._create_table()
            logger.info(f"[SQLitePipeline] Connected: {self.db_path}")
        except sqlite3.Error as e:
            logger.error(f"[SQLitePipeline] Failed to connect: {e}")
            raise

    def close_spider(self):
        if self.conn:
            try:
                self.conn.commit()
                logger.info(
                    f"[SQLitePipeline] Closed. Total inserted: {self._insert_count}"
                )
            except sqlite3.Error as e:
                logger.error(f"[SQLitePipeline] Commit failed: {e}")
                self.conn.rollback()
            finally:
                self.conn.close()

    def _create_table(self):
        self.cursor.execute(self._CREATE_TABLE_SQL)
        self.conn.commit()

    def process_item(self, item):
        try:
            self.cursor.execute(self._INSERT_SQL, dict(item))

            if self.cursor.rowcount > 0:
                self._insert_count += 1
                logger.debug(
                    f"[SQLitePipeline] Inserted: {item.get('registration')} — {item.get('name')}"
                )
                if self._insert_count % self.COMMIT_EVERY == 0:
                    self.conn.commit()
            else:
                logger.debug(
                    f"[SQLitePipeline] Duplicate skipped: {item.get('registration')}"
                )

        except sqlite3.Error as e:
            logger.error(f"[SQLitePipeline] DB error {item.get('registration')}: {e}")

        return item
