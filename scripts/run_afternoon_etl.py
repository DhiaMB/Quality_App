#!/usr/bin/env python3
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from etl.main import main
from etl.utils.logger import logger

if __name__ == "__main__":
    logger.info("=== Starting Afternoon ETL Run ===")
    result = main()
    logger.info(f"Afternoon ETL completed: {result}")