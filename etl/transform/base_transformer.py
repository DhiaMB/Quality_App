from abc import ABC, abstractmethod
import pandas as pd
from utils.logger import logger

class BaseTransformer(ABC):
    """Base class for data transformation"""
    
    @abstractmethod
    def transform(self, df):
        """Transform raw data"""
        pass
    
    def validate_transformation(self, df_before, df_after):
        """Validate transformation results"""
        if df_before.empty and df_after.empty:
            return True
        
        if len(df_after) == 0:
            logger.warning("All records were filtered out during transformation")
            return False
            
        return True