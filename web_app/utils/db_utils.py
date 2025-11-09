import yaml
from sqlalchemy import create_engine
import os

def load_db_config():
    """Load YAML config."""
    config_path = os.path.join(os.path.dirname(__file__), "../config/database.yaml")
    with open(config_path, "r") as f:
        return yaml.safe_load(f)

def get_target_engine():
    """Create SQLAlchemy engine for target_db."""
    cfg = load_db_config()["target_db"]
    connection_url = (
        f"postgresql+psycopg2://{cfg['user']}:{cfg['password']}"
        f"@{cfg['host']}:{cfg['port']}/{cfg['dbname']}"
    )
    engine = create_engine(connection_url)
    return engine
