from etl.extract.db_extractor import DatabaseExtractor
from etl.transform.quality_transformer import QualityTransformer
from etl.load.db_loader import DatabaseLoader
from etl.utils.logger import logger

class ETLOrchestrator:
    """Orchestrate the complete ETL process"""
    
    def __init__(self):
        self.extractor = DatabaseExtractor()
        self.transformer = QualityTransformer()
        self.loader = DatabaseLoader()
    
    def run(self, incremental=True):
        """Run the complete ETL process"""
        logger.info("=== Starting ETL Pipeline ===")
        
        try:
            # Extraction
            logger.info("Phase 1: Extraction")
            raw_data = self.extractor.extract(incremental=incremental)
            
            if raw_data.empty:
                logger.info("No new data to process")
                return {
                    'status': 'success',
                    'records_processed': 0,
                    'message': 'No new data'
                }
            
            # Transformation
            logger.info("Phase 2: Transformation")
            clean_data = self.transformer.transform(raw_data)
            
            # Loading
            logger.info("Phase 3: Loading")
            records_loaded = self.loader.load(clean_data, load_type='clean')
            
            # Mark staging as processed if needed
            if hasattr(self.extractor, 'batch_id'):
                self.loader.mark_staging_processed(self.extractor.batch_id)
            
            logger.info(" ETL Pipeline completed successfully!")
            
            return {
                'status': 'success',
                'records_processed': records_loaded,
                'message': f'Processed {records_loaded} records'
            }
            
        except Exception as e:
            logger.error(f" ETL Pipeline failed: {e}")
            return {
                'status': 'error',
                'records_processed': 0,
                'message': str(e)
            }

def main():
    """Main ETL execution function"""
    orchestrator = ETLOrchestrator()
    result = orchestrator.run(incremental=True)
    return result

if __name__ == "__main__":
    main()