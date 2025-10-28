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
                    "operator_no", "defect_comment", "repair_comment"
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
            "operator_no", "defect_comment", "repair_comment"
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
            
            # DEBUG: Check machine/operator data BEFORE transformation
            if 'machine_no' in df.columns:
                print(f"BEFORE TRANSFORM - machine_no sample: {df['machine_no'].head(5).tolist()}")
                print(f"BEFORE TRANSFORM - machine_no null count: {df['machine_no'].notna().sum()}")
            
            if 'operator_no' in df.columns:
                print(f"BEFORE TRANSFORM - operator_no sample: {df['operator_no'].head(5).tolist()}")
                print(f"BEFORE TRANSFORM - operator_no null count: {df['operator_no'].notna().sum()}")
            
            # 2. Select only target columns (if they exist)
            available_columns = [col for col in self.target_columns if col in df.columns]
            df = df[available_columns]
            
            # DEBUG: Check after column selection
            print(f"Columns after selection: {df.columns.tolist()}")
            
            # 3. Filter invalid part_numbers
            if 'part_number' in df.columns:
                before = len(df)
                df = df[df['part_number'].astype(str).str.len() >= 15]
                after = len(df)
                print(f"Filtered part numbers: {before} -> {after}")
            
            # 4. Standardize code_description
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
            
            # 5. Standardize disposition
            if 'disposition' in df.columns:
                df['disposition'] = (
                    df['disposition']
                    .astype(str)
                    .str.upper()
                    .str.strip()
                )

            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'], errors='coerce')
                # Drop rows with invalid dates
                df = df[df['date'].notna()]
            
            # DEBUG: Check machine/operator data AFTER transformation
            if 'machine_no' in df.columns:
                print(f"AFTER TRANSFORM - machine_no sample: {df['machine_no'].head(5).tolist()}")
                print(f"AFTER TRANSFORM - machine_no null count: {df['machine_no'].notna().sum()}")
            
            if 'operator_no' in df.columns:
                print(f"AFTER TRANSFORM - operator_no sample: {df['operator_no'].head(5).tolist()}")
                print(f"AFTER TRANSFORM - operator_no null count: {df['operator_no'].notna().sum()}")
            
            # 6. Add timestamps
            df['load_date'] = pd.to_datetime('today').date()
            df['load_timestamp'] = datetime.now()
            
            print(f"Transformation complete: {len(df)} records")
            
            return df.reset_index(drop=True)
            
        except Exception as e:
            print(f"Transformation failed: {e}")
            raise