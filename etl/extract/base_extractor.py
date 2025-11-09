from abc import ABC, abstractmethod
import pandas as pd
from utils.logger import logger

class BaseExtractor(ABC):
    """Base class for data extraction"""
    
    @abstractmethod
    def extract(self, **kwargs):
        """Extract data from source"""
        pass
    
    def validate_data(self, df):
        """Validate extracted data"""
        if df.empty:
            logger.warning("No data extracted")
            return False
        
        required_columns = ['part_number', 'date', 'code_description']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            logger.error(f"Missing required columns: {missing_columns}")
            return False
            
        return True