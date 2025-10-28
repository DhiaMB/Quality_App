from abc import ABC, abstractmethod
from etl.utils.logger import logger

class BaseLoader(ABC):
    """Base class for data loading"""
    
    @abstractmethod
    def load(self, df, **kwargs):
        """Load transformed data"""
        pass
    
    def validate_load(self, df_before, df_after):
        """Validate load operation"""
        if df_before.empty:
            return True
            
        # Basic validation - should have same or fewer records (due to deduplication)
        return len(df_after) <= len(df_before)