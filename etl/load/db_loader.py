import pandas as pd
from datetime import datetime
from load.base_loader import BaseLoader
from utils.db_utils import get_target_engine, execute_sql
from utils.logger import logger

class DatabaseLoader(BaseLoader):
    """Load transformed data to target database"""
    
    def __init__(self):
        self.engine = get_target_engine()
    
    def update_etl_metadata(self, records_processed, status='COMPLETED', error_message=None):
        """Update ETL metadata table"""
        try:
            query = """
                INSERT INTO etl_metadata.etl_runs 
                (job_name, last_successful_extraction, records_processed, status, error_message, completed_at)
                VALUES (:job_name, :last_extraction, :records, :status, :error_msg, :completed_at)
            """
            params = {
                'job_name': 'quality_data_extraction',
                'last_extraction': datetime.now(),
                'records': records_processed,
                'status': status,
                'error_msg': error_message,
                'completed_at': datetime.now()
            }
            execute_sql(self.engine, query, params)
            logger.info("ETL metadata updated successfully")
        except Exception as e:
            logger.error(f"Failed to update ETL metadata: {e}")
    
    def load_to_staging(self, df):
        """Load raw data to staging table"""
        if df.empty:
            logger.warning("No data to load to staging")
            return 0
        
        try:
            # Load to staging table
            df.to_sql(
                'stg_quality_data', 
                self.engine, 
                schema='quality', 
                if_exists='append', 
                index=False
            )
            logger.info(f"Loaded {len(df)} records to staging table")
            return len(df)
        except Exception as e:
            logger.error(f"Failed to load to staging: {e}")
            raise
    
    def load_to_clean(self, df):
        """Load transformed data to clean table using pandas to_sql"""
        if df.empty:
            logger.warning("No data to load to clean table")
            return 0
        
        try:
            # DEBUG: Check what we're loading
            logger.info(f"Loading DataFrame with columns: {df.columns.tolist()}")
            logger.info(f"DataFrame shape: {df.shape}")
            
            # Use simple to_sql without method='multi'
            records_loaded = df.to_sql(
                'clean_quality_data', 
                self.engine, 
                schema='quality', 
                if_exists='append', 
                index=False
            )
            
            logger.info(f"Loaded {records_loaded} records to clean table")
            return records_loaded
            
        except Exception as e:
            logger.error(f"Failed to load to clean table: {e}")
            raise
        
    def mark_staging_processed(self, batch_id):
        """Mark staging records as processed"""
        try:
            query = """
                UPDATE quality.stg_quality_data 
                SET is_processed = TRUE 
                WHERE batch_id = :batch_id
            """
            execute_sql(self.engine, query, {'batch_id': batch_id})
            logger.info(f"Marked staging records with batch_id {batch_id} as processed")
        except Exception as e:
            logger.error(f"Failed to mark staging as processed: {e}")
    
    def load(self, df, load_type='clean'):
        """Main load method"""
        if df.empty:
            logger.warning("No data to load")
            return 0
        
        try:
            if load_type == 'staging':
                records_loaded = self.load_to_staging(df)
            else:
                records_loaded = self.load_to_clean(df)
            
            # Update ETL metadata
            self.update_etl_metadata(records_loaded, 'COMPLETED')
            
            return records_loaded
            
        except Exception as e:
            error_msg = f"Load operation failed: {e}"
            logger.error(error_msg)
            self.update_etl_metadata(0, 'FAILED', error_msg)
            raise