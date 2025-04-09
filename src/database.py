"""
Database Module
==============

Handles database connection, session management, and initialization.
"""

import os
from sqlalchemy import create_engine, JSON, Text, event, MetaData, Table, inspect
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.ext.declarative import declarative_base
from contextlib import contextmanager
from src.utils import logger
from sqlalchemy.exc import SQLAlchemyError
import logging

# Get database URL from environment or use SQLite as default
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///docpilot.db')

# Create engine based on URL
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith('sqlite') else {},
    echo=os.environ.get('SQL_ECHO', 'false').lower() == 'true'
)

# Create session factory
SessionFactory = sessionmaker(bind=engine)
Session = scoped_session(SessionFactory)

# Base class for models
Base = declarative_base()

# Check if using PostgreSQL
is_postgres = DATABASE_URL.startswith('postgresql')

def get_json_type():
    """
    Returns the appropriate JSON column type based on the database engine.
    For PostgreSQL, returns JSONB. For other engines, returns JSON or Text.
    """
    if is_postgres:
        from sqlalchemy.dialects.postgresql import JSONB
        return JSONB
    else:
        # SQLite and other engines
        return JSON

# Use this in models
JsonType = get_json_type()

@contextmanager
def get_session():
    """
    Provide a transactional scope around a series of operations.
    
    Usage:
        with get_session() as session:
            user = session.query(User).get(1)
    """
    session = Session()
    try:
        yield session
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()

# For SQLite: Enable foreign key constraints
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Enable foreign key constraints for SQLite"""
    if DATABASE_URL.startswith('sqlite'):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

def init_db():
    """
    Initialize the database by creating all tables in the correct order based on dependencies.
    
    This function creates tables in phases to ensure foreign key constraints are satisfied:
    1. First tables with no dependencies
    2. Then tables that depend on the first group
    3. Finally tables that depend on the second group
    """
    try:
        # Import models here to avoid circular imports
        from src.models import (
            User, Installation, SubscriptionPlan, Repository, 
            DocumentFile, UserAccess, Subscription, Usage, UsageSummary,
            InstallationSettings, RepositorySettings
        )
        
        # Create engine with configured URL
        engine = create_engine(DATABASE_URL)
        
        logger = logging.getLogger(__name__)
        logger.info("Initializing database tables...")
        
        # Phase 1: Create tables with no dependencies
        Base.metadata.create_all(
            engine, 
            tables=[
                User.__table__,
                Installation.__table__,
                SubscriptionPlan.__table__
            ]
        )
        
        # Phase 2: Create tables with dependencies on first group
        Base.metadata.create_all(
            engine, 
            tables=[
                Repository.__table__,
                UserAccess.__table__,
                Subscription.__table__,
                InstallationSettings.__table__
            ]
        )
        
        # Phase 3: Create tables with dependencies on second group
        Base.metadata.create_all(
            engine, 
            tables=[
                DocumentFile.__table__,
                RepositorySettings.__table__,
                Usage.__table__
            ]
        )
        
        # Phase 4: Create remaining tables
        Base.metadata.create_all(
            engine, 
            tables=[
                UsageSummary.__table__
            ]
        )
        
        logger.info("Database initialization completed successfully")
        create_default_data()
    except SQLAlchemyError as e:
        logger.error(f"Database initialization failed: {str(e)}")
        raise

def create_default_data():
    """Initialize the database with default data needed for the application to run."""
    # Import here to avoid circular imports
    with get_session() as session:
        # Import SubscriptionPlan here to avoid circular imports
        from src.models.subscription import SubscriptionPlan
        
        plan_count = session.query(SubscriptionPlan).count()
        
        if plan_count == 0:
            # Create default subscription plans
            free_plan = SubscriptionPlan(
                plan_id="free",
                name="Free Plan",
                description="Basic documentation generation with limited features.",
                price_monthly=0,
                price_yearly=0,
                features={
                    "repositories": 1,
                    "tokens_per_month": 100000,
                    "priority_support": False,
                    "advanced_features": False
                }
            )
            
            pro_plan = SubscriptionPlan(
                plan_id="pro",
                name="Pro Plan",
                description="Enhanced documentation features for professionals.",
                price_monthly=9.99,
                price_yearly=99.99,
                features={
                    "repositories": 5,
                    "tokens_per_month": 500000,
                    "priority_support": True,
                    "advanced_features": True
                }
            )
            
            enterprise_plan = SubscriptionPlan(
                plan_id="enterprise",
                name="Enterprise Plan",
                description="Full-featured documentation solution for teams.",
                price_monthly=29.99,
                price_yearly=299.99,
                features={
                    "repositories": -1,  # Unlimited
                    "tokens_per_month": 2000000,
                    "priority_support": True,
                    "advanced_features": True
                }
            )
            
            session.add_all([free_plan, pro_plan, enterprise_plan])
            logger.info("Created default subscription plans")

# Create a convenience function to get models by import
def get_models():
    """Return a dictionary of all models for easy access"""
    # Import models directly
    from src.models import (
        User, Installation, UserAccess, InstallationSettings, 
        RepositorySettings, Repository, DocumentFile, 
        Subscription, SubscriptionPlan, Usage, UsageSummary
    )
    
    return {
        'User': User,
        'Installation': Installation,
        'UserAccess': UserAccess,
        'InstallationSettings': InstallationSettings,
        'RepositorySettings': RepositorySettings,
        'Repository': Repository,
        'DocumentFile': DocumentFile,
        'Subscription': Subscription,
        'SubscriptionPlan': SubscriptionPlan,
        'Usage': Usage,
        'UsageSummary': UsageSummary
    }

def get_connection():
    """Get a connection to the database."""
    try:
        return engine.connect()
    except SQLAlchemyError as e:
        logger.error(f"Database connection error: {e}")
        raise

@contextmanager
def session_scope():
    """Provide a transactional scope around a series of operations."""
    session = get_session()
    try:
        yield session
        session.commit()
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Database session error: {e}")
        raise
    finally:
        session.close() 