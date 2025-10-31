import pandas as pd
import hashlib
from datetime import datetime
from etl.extract.base_extractor import BaseExtractor
from etl.utils.db_utils import get_source_engine, execute_sql,get_target_engine
from etl.utils.date_utils import parse_source_date, get_extraction_time_range
from etl.utils.logger import logger

class DatabaseExtractor(BaseExtractor):
    """Extract data from source database with incremental loading"""
    
    def __init__(self):
        self.engine = get_source_engine()
        self.batch_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    def get_last_extraction_time(self):
        """Get the last successful extraction time from metadata"""
        try:
            target_engine = get_target_engine()
            
            # Try different schema possibilities
            queries = [
                "SELECT last_successful_extraction FROM etl_metadata.etl_runs WHERE job_name = 'quality_data_extraction' AND status = 'COMPLETED' ORDER BY completed_at DESC LIMIT 1",
                "SELECT last_successful_extraction FROM public.etl_runs WHERE job_name = 'quality_data_extraction' AND status = 'COMPLETED' ORDER BY completed_at DESC LIMIT 1",
                "SELECT last_successful_extraction FROM quality.etl_runs WHERE job_name = 'quality_data_extraction' AND status = 'COMPLETED' ORDER BY completed_at DESC LIMIT 1"
            ]
            
            for query in queries:
                try:
                    result = execute_sql(target_engine, query)
                    row = result.fetchone()
                    if row:
                        return row[0]
                except:
                    continue
                    
            return None
            
        except Exception as e:
            logger.warning(f"Could not get last extraction time: {e}")
            return None
    
    def create_record_hash(self, row):
        """Create hash for record deduplication"""
        hash_string = f"{row.get('part_number', '')}_{row.get('serial_number', '')}_{row.get('date', '')}_{row.get('code_description', '')}"
        return hashlib.md5(hash_string.encode()).hexdigest()
    
    def extract(self, incremental=True):
        """Extract data from source database"""
        logger.info("Starting database extraction")
        
        if incremental:
            df = self._extract_incremental()
        else:
            df = self._extract_full()
        
        # DEBUG: Check machine_no and operator_no in SOURCE data
        if not df.empty and 'machine_no' in df.columns:
            logger.info(f"SOURCE machine_no sample: {df['machine_no'].head(10).tolist()}")
            logger.info(f"SOURCE machine_not null count: {df['machine_no'].notna().sum()}")
            
        if not df.empty and 'operator_no' in df.columns:
            logger.info(f"SOURCE operator_no sample: {df['operator_no'].head(10).tolist()}")
            logger.info(f"SOURCE operator_no null count: {df['operator_no'].notna().sum()}")
    
        return df
    
    def _extract_incremental(self):
        """Extract only new records since last extraction"""
        last_extraction = self.get_last_extraction_time()
        
        if last_extraction:
            query = """
                SELECT * FROM lpb_quality_data 
                WHERE date > %s
                ORDER BY date
            """
            params = (last_extraction,)
        else:
            # First run - extract last 7 days
            query = """
                SELECT * FROM lpb_quality_data 
                WHERE date >= CURRENT_DATE - INTERVAL '356 days'
                ORDER BY date
            """
            params = None
        
        logger.info(f"Executing incremental extraction query: {query}")
        df = pd.read_sql(query, self.engine, params=params)
        
        # DEBUG: Check ALL column names and samples
        if not df.empty:
            logger.info("=== SOURCE DATA COLUMN ANALYSIS ===")
            for col in df.columns:
                sample_values = df[col].dropna().head(3).tolist()
                unique_count = df[col].nunique()
                logger.info(f"Column '{col}': {unique_count} unique values, samples: {sample_values}")
        
        if not df.empty:
            # Add extraction metadata
            df['source_record_hash'] = df.apply(self.create_record_hash, axis=1)
            df['batch_id'] = self.batch_id
            df['extracted_at'] = datetime.now()
            
            # Parse date column
            df['date'] = df['date'].apply(parse_source_date)
            
            logger.info(f"Extracted {len(df)} new records")
        else:
            logger.info("No new records to extract")
        
        return df
    
    def _extract_full(self):
        """Extract all data (for initial load)"""
        query = "SELECT * FROM lpb_quality_data ORDER BY date"
        df = pd.read_sql(query, self.engine)
        
        if not df.empty:
            df['source_record_hash'] = df.apply(self.create_record_hash, axis=1)
            df['batch_id'] = self.batch_id
            df['extracted_at'] = datetime.now()
            df['date'] = df['date'].apply(parse_source_date)
        
        logger.info(f"Extracted {len(df)} records in full load")
        return df