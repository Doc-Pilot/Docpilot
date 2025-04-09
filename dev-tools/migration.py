#!/usr/bin/env python
"""
Migration Management Script
==========================

This script provides a command-line interface for managing database migrations
using Alembic. It supports creating, upgrading, downgrading, and checking
migration status.
"""

import os
import sys
import argparse
import subprocess
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

def run_alembic_command(command, *args):
    """Run an Alembic command with arguments."""
    cmd = ["alembic", command]
    cmd.extend(args)
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd)

def create_migration(message):
    """Create a new migration with autogenerate."""
    run_alembic_command("revision", "--autogenerate", "-m", message)

def create_initial_schema():
    """Create the initial schema migration without connecting to a database.
    This is useful for new projects that don't have a database yet.
    """
    print("Creating initial schema migration...")
    print("This will create a migration based on current SQLAlchemy models.")
    
    # Import models to ensure they're loaded
    from src.models.base import Base
    
    # Import all models to ensure they're registered with Base
    try:
        from src.models import (
            User, Installation, SubscriptionPlan, Repository, 
            DocumentFile, UserAccess, Subscription, Usage, UsageSummary,
            InstallationSettings, RepositorySettings
        )
        print("Models imported successfully")
    except ImportError as e:
        print(f"Warning: Could not import all models: {e}")
        print("Migration may be incomplete")
    
    # Create migration
    run_alembic_command("revision", "--autogenerate", "-m", "Initial schema")
    print("Initial schema migration created.")
    print("You can now run 'python dev-tools/migration.py upgrade' to apply it.")

def upgrade(revision="head"):
    """Upgrade to a revision."""
    run_alembic_command("upgrade", revision)

def downgrade(revision="-1"):
    """Downgrade to a revision."""
    run_alembic_command("downgrade", revision)

def show_history():
    """Show migration history."""
    run_alembic_command("history")

def show_current():
    """Show current revision."""
    run_alembic_command("current")

def init_db():
    """Initialize database with Alembic and populate default data."""
    # First upgrade to latest migration
    upgrade()
    
    # Then populate with default data
    print("Populating database with default data...")
    from src.database import create_default_data
    create_default_data()
    print("Database initialized successfully")

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Database migration management")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Create migration
    create_parser = subparsers.add_parser("create", help="Create a new migration")
    create_parser.add_argument("message", help="Migration message")
    
    # Create initial schema
    subparsers.add_parser("init-schema", help="Create initial schema migration")
    
    # Initialize database
    subparsers.add_parser("init-db", help="Initialize database with migrations and default data")
    
    # Upgrade
    upgrade_parser = subparsers.add_parser("upgrade", help="Upgrade to a revision")
    upgrade_parser.add_argument("revision", nargs="?", default="head", help="Revision to upgrade to")
    
    # Downgrade
    downgrade_parser = subparsers.add_parser("downgrade", help="Downgrade to a revision")
    downgrade_parser.add_argument("revision", nargs="?", default="-1", help="Revision to downgrade to")
    
    # History
    subparsers.add_parser("history", help="Show migration history")
    
    # Current
    subparsers.add_parser("current", help="Show current revision")
    
    # Environment selection for all commands
    parser.add_argument("--env", "-e", choices=["development", "testing", "production"], 
                        default="development", help="Environment to use")
    
    args = parser.parse_args()
    
    # Set environment variable
    os.environ["APP_ENV"] = args.env
    print(f"Using environment: {args.env}")
    
    # Load environment variables
    load_dotenv()
    
    # Run command
    if args.command == "create":
        create_migration(args.message)
    elif args.command == "init-schema":
        create_initial_schema()
    elif args.command == "init-db":
        init_db()
    elif args.command == "upgrade":
        upgrade(args.revision)
    elif args.command == "downgrade":
        downgrade(args.revision)
    elif args.command == "history":
        show_history()
    elif args.command == "current":
        show_current()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()