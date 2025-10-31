import os
import pandas as pd
import yaml
import hashlib
from datetime import datetime

# Simple path handling - config in same directory as this file
CONFIG_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'config')
CONFIG_PATH = os.path.join(CONFIG_DIR, 'etl_config.yaml')

class QualityTransformer:
    def __init__(self):
        try:
            # Create config directory if it doesn't exist
            if not os.path.exists(CONFIG_DIR):
                os.makedirs(CONFIG_DIR)
                
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
            
            self.code_mapping = self.config['transformation']['code_mapping']
            self.target_columns = self.config['transformation']['target_columns']
            
        except FileNotFoundError:
            print(f"Config file not found at: {CONFIG_PATH}")
            # Create a default config file
            self.create_default_config()
            self.setup_fallback_config()
    
    def create_default_config(self):
        """Create a default config file"""
        default_config = {
            'transformation': {
                'code_mapping': {
                    "manque port cable wire": "manque câble",
                    "manque cable wire": "manque câble",
                    "manque cable": "manque câble",
                    "point saute": "point sauté",
                    "point cassee": "point cassé"
                },
                'target_columns': [
                    "part_number", "serial_number", "date", "shift", "disposition",
                    "code", "code_description", "category", "type", "machine_no", 
                    "who_made_it", "defect_comment", "repair_comment"
                ]
            }
        }
        
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            yaml.dump(default_config, f, default_flow_style=False, allow_unicode=True)
        print(f"Created default config at: {CONFIG_PATH}")
    
    def setup_fallback_config(self):
        """Fallback config"""
        self.code_mapping = {
            "manque port cable wire": "manque câble",
            "manque cable wire": "manque câble",
            "manque cable": "manque câble",
            "point saute": "point sauté",
            "point cassee": "point cassé"
        }
        self.target_columns = [
            "part_number", "serial_number", "date", "shift", "disposition",
            "code", "code_description", "category", "type", "machine_no", 
            "who_made_it", "defect_comment", "repair_comment"
        ]
    
    def transform(self, df):
        """Transform raw quality data"""
        print("Starting data transformation")
        
        if df.empty:
            print("No data to transform")
            return df
        
        try:
            # 1. Clean column names
            df.columns = df.columns.str.lower().str.strip()
            print(f"Columns after cleaning: {df.columns.tolist()}")
            
            # DEBUG: Check who_made_it data before transformation
            if 'who_made_it' in df.columns:
                print(f"BEFORE TRANSFORM - who_made_it sample: {df['who_made_it'].head(5).tolist()}")
                print(f"BEFORE TRANSFORM - who_made_it null count: {df['who_made_it'].notna().sum()}")
            
            # DEBUG: Check machine data before transformation
            if 'machine_no' in df.columns:
                print(f"BEFORE TRANSFORM - machine_no sample: {df['machine_no'].head(5).tolist()}")
                print(f"BEFORE TRANSFORM - machine_no null count: {df['machine_no'].notna().sum()}")
            
            # 2. Ensure all target columns exist (add missing ones with null values)
            for column in self.target_columns:
                if column not in df.columns:
                    df[column] = None
                    print(f"Added missing column: {column}")
            
            # 3. Select only target columns (now they all exist)
            df = df[self.target_columns]
            print(f"Columns after selection: {df.columns.tolist()}")
            
            # 4. Filter invalid part_numbers
            if 'part_number' in df.columns:
                before = len(df)
                df = df[df['part_number'].astype(str).str.len() >= 15]
                after = len(df)
                print(f"Filtered part numbers: {before} -> {after}")
            
            # 5. Standardize code_description
            if 'code_description' in df.columns:
                df['code_description'] = (
                    df['code_description']
                    .astype(str)
                    .str.lower()
                    .str.strip()
                )
                # Apply mapping
                for old, new in self.code_mapping.items():
                    df['code_description'] = df['code_description'].str.replace(old, new, regex=False)
                print("Applied code_description standardization")
            
            # 6. Standardize disposition
            if 'disposition' in df.columns:
                df['disposition'] = (
                    df['disposition']
                    .astype(str)
                    .str.upper()
                    .str.strip()
                )
                print("Standardized disposition values")
            
            # 7. Handle date conversion
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'], errors='coerce')
                # Drop rows with invalid dates
                before_dates = len(df)
                df = df[df['date'].notna()]
                after_dates = len(df)
                print(f"Filtered invalid dates: {before_dates} -> {after_dates}")
            
            # 8. Standardize who_made_it (clean up the data)
            if 'who_made_it' in df.columns:
                df['who_made_it'] = df['who_made_it'].astype(str).str.strip()
                # Remove empty strings and replace with None
                df['who_made_it'] = df['who_made_it'].replace(['', 'nan', 'None'], None)
                print(f"Cleaned who_made_it values")
            
            # DEBUG: Check data after transformation
            if 'who_made_it' in df.columns:
                print(f"AFTER TRANSFORM - who_made_it sample: {df['who_made_it'].head(5).tolist()}")
                print(f"AFTER TRANSFORM - who_made_it null count: {df['who_made_it'].isna().sum()}")
                print(f"AFTER TRANSFORM - who_made_it unique values: {df['who_made_it'].nunique()}")
            
            if 'machine_no' in df.columns:
                print(f"AFTER TRANSFORM - machine_no sample: {df['machine_no'].head(5).tolist()}")
                print(f"AFTER TRANSFORM - machine_no null count: {df['machine_no'].isna().sum()}")
            
            # 9. Add timestamps
            df['load_date'] = pd.to_datetime('today').date()
            df['load_timestamp'] = datetime.now()
            
            print(f"Transformation complete: {len(df)} records")
            
            return df.reset_index(drop=True)
            
        except Exception as e:
            print(f"Transformation failed: {e}")
            raise