import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Import models
from src.models.base import Base
import src.models.user
import src.models.subscription
import src.models.repository
import src.models.installation
import src.models.usage
import src.models.settings

# Alembic config
config = context.config

# Set database URL based on environment
app_env = os.getenv("APP_ENV", "development")
if app_env == "production":
    db_url = os.getenv("PROD_DATABASE_URL")
elif app_env == "testing":
    db_url = os.getenv("TEST_DATABASE_URL")
else:
    db_url = os.getenv("DEV_DATABASE_URL")

# Override sqlalchemy.url
config.set_main_option("sqlalchemy.url", db_url)

# Interpret config file for Python logging
fileConfig(config.config_file_name)

# Set target metadata
target_metadata = Base.metadata

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    # Additional configuration options
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = db_url
    
    # Create engine
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, 
            target_metadata=target_metadata,
            # Enable transactional DDL
            transaction_per_migration=True,
            # Compare types
            compare_type=True,
            # Compare server defaults
            compare_server_default=True
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online() 