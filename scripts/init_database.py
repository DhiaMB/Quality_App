import os
import sys
from sqlalchemy import text
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from etl.utils.db_utils import get_target_engine
from etl.utils.logger import logger


def init_database():
    """Initialize the target database with required tables"""
    engine = get_target_engine()
    
    with engine.connect() as conn:
        # Create schemas
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS quality;"))
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS etl_metadata;"))

        # Staging table for raw data
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS quality.stg_quality_data (
                id BIGSERIAL PRIMARY KEY,
                part_number VARCHAR(100),
                serial_number VARCHAR(100),
                date TIMESTAMP,
                shift VARCHAR(10),
                disposition VARCHAR(50),
                code VARCHAR(50),
                code_description TEXT,
                category VARCHAR(100),
                type VARCHAR(100),
                who_made_it VARCHAR(100),
                registered_by VARCHAR(100),
                repaired_by VARCHAR(100),
                qua_auth VARCHAR(100),
                prod_auth VARCHAR(100),
                scrap_auth VARCHAR(100),
                machine_no VARCHAR(50),
                operator_no VARCHAR(50),
                defect_comment TEXT,
                repair_comment TEXT,
                source_record_hash VARCHAR(64),
                extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                batch_id VARCHAR(50),
                is_processed BOOLEAN DEFAULT FALSE
            );
        """))

        # Clean table for analysis
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS quality.clean_quality_data (
                id BIGSERIAL PRIMARY KEY,
                stg_id BIGINT,
                part_number VARCHAR(100),
                serial_number VARCHAR(100),
                date DATE,
                shift VARCHAR(10),
                disposition VARCHAR(20),
                code VARCHAR(50),
                code_description TEXT,
                category VARCHAR(100),
                type VARCHAR(100),
                machine_no VARCHAR(50),
                operator_no VARCHAR(50),
                defect_comment TEXT,
                repair_comment TEXT,
                data_quality_score INTEGER,
                load_date DATE,
                load_timestamp TIMESTAMP,
                record_fingerprint VARCHAR(64) UNIQUE,
                is_active BOOLEAN DEFAULT TRUE
            );
        """))

        # ETL metadata table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS etl_metadata.etl_runs (
                id BIGSERIAL PRIMARY KEY,
                job_name VARCHAR(100),
                last_successful_extraction TIMESTAMP,
                last_processed_date DATE,
                records_processed INTEGER,
                status VARCHAR(20),
                error_message TEXT,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            );
        """))

        # Create indexes
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_clean_date ON quality.clean_quality_data(date);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_clean_part_shift ON quality.clean_quality_data(part_number, shift, date);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_clean_disposition ON quality.clean_quality_data(disposition, date);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_stg_processed ON quality.stg_quality_data(is_processed);"))

        conn.commit()  # <-- Important: commit changes

        logger.info("✅ Database initialized successfully!")


if __name__ == "__main__":
    init_database()
