import yaml
import os
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_PATH = os.path.join(BASE_DIR, "config", "database.yaml")

def load_db_config():
    """Load database configuration"""
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def get_source_engine():
    """Get source database engine"""
    config = load_db_config()
    db_config = config['source_db']
    
    user = quote_plus(db_config['user'])
    password = quote_plus(db_config['password'])
    host = db_config['host']
    port = db_config['port']
    dbname = db_config['dbname']
    
    url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}"
    return create_engine(url, connect_args={"client_encoding": "utf8"})

def get_target_engine():
    """Get target database engine"""
    config = load_db_config()
    db_config = config['target_db']
    
    user = quote_plus(db_config['user'])
    password = quote_plus(db_config['password'])
    host = db_config['host']
    port = db_config['port']
    dbname = db_config['dbname']
    
    url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}"
    return create_engine(url, connect_args={"client_encoding": "utf8"})

def execute_sql(engine, query, params=None):
    """Execute SQL query with parameters"""
    with engine.connect() as conn:
        if params:
            # Use text() and named parameters
            result = conn.execute(text(query), params)
        else:
            result = conn.execute(text(query))
        conn.commit()
        return result