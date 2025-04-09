"""
Database Initialization Script
=============================

This script initializes the database and populates it with sample data.
Run this script to set up a new database or reset an existing one.
"""

import os
import sys
import datetime
import uuid
import sqlite3
import subprocess

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.database import get_session, DATABASE_URL, Base, engine
from src.models.user import User
from src.models.installation import Installation, UserAccess
from src.models.repository import Repository, DocumentFile
from src.models.subscription import Subscription, SubscriptionPlan
from src.models.usage import Usage, UsageSummary

def reset_database():
    """Reset the database: Delete file (SQLite) or drop tables, then recreate schema directly"""
    print("Attempting to reset database...")
    
    # Determine project root relative to this script
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    db_path = os.path.join(project_root, 'docpilot.db')

    # 1. Clear Existing Schema/Data
    if DATABASE_URL.startswith('sqlite'):
        print(f"Detected SQLite database at {db_path}")
        if os.path.exists(db_path):
            print(f"Deleting existing SQLite database file: {db_path}")
            try:
                os.remove(db_path)
                print(f"Database file {db_path} deleted successfully.")
            except Exception as delete_err:
                print(f"Error deleting SQLite file: {delete_err}")
                print("Please ensure the database file is not locked and try again.")
                sys.exit(1)
        else:
            print("SQLite database file not found, proceeding.")
    else:
        # For non-SQLite databases, drop all tables
        print(f"Attempting to drop tables for non-SQLite database: {DATABASE_URL}")
        try:
            Base.metadata.drop_all(engine)
            print("Tables dropped successfully using SQLAlchemy drop_all.")
        except Exception as e:
            print(f"Error dropping tables using SQLAlchemy drop_all: {e}")
            print("Cannot proceed with reset for non-SQLite database due to drop error.")
            sys.exit(1)
            
    # 2. Recreate Schema using SQLAlchemy's init_db function
    print("Recreating schema using SQLAlchemy...")
    from src.database import init_db
    try:
        init_db()
        print("Database schema created successfully.")
    except Exception as e:
        print(f"Error recreating database schema: {e}")
        sys.exit(1)

def create_sample_data():
    """Create sample data for testing"""
    with get_session() as session:
        # Import models here to avoid circular imports
        from src.models.subscription import SubscriptionPlan
        from src.models.user import User
        from src.models.installation import Installation
        from src.models.repository import Repository
        
        # Check for existing users first
        existing_users = session.query(User.username).all()
        existing_usernames = [user[0] for user in existing_users]
        
        users_to_add = []
        if 'admin' not in existing_usernames:
            admin_user = User(
                id=str(uuid.uuid4()),
                username='admin',
                email='admin@docpilot.ai',
                first_name='Admin',
                last_name='User',
                is_active=True,
                is_verified=True,
                preferences={
                    'theme': 'dark',
                    'email_notifications': True
                }
            )
            admin_user.password = 'adminpassword'
            users_to_add.append(admin_user)
            
        if 'testuser' not in existing_usernames:
            free_user = User(
                id=str(uuid.uuid4()),
                username='testuser',
                email='testuser@example.com',
                first_name='Test',
                last_name='User',
                is_active=True,
                is_verified=True,
                preferences={
                    'theme': 'light',
                    'email_notifications': True
                }
            )
            free_user.password = 'testpassword'
            users_to_add.append(free_user)
            
        if 'prouser' not in existing_usernames:
            pro_user = User(
                id=str(uuid.uuid4()),
                username='prouser',
                email='prouser@example.com',
                first_name='Pro',
                last_name='User',
                is_active=True,
                is_verified=True,
                preferences={
                    'theme': 'system',
                    'email_notifications': False
                }
            )
            pro_user.password = 'propassword'
            users_to_add.append(pro_user)
            
        if users_to_add:
            session.add_all(users_to_add)
            session.flush()
            print(f"Added {len(users_to_add)} new users")
        else:
            print("Users already exist, skipping")
            
        # Check if subscription plans already exist
        existing_plans = session.query(SubscriptionPlan.plan_id).all()
        existing_plan_ids = [plan[0] for plan in existing_plans]
        
        # Create subscription plans if they don't exist
        print("Creating subscription plans...")
        plans_to_add = []
        
        if 'free' not in existing_plan_ids:
            free_plan = SubscriptionPlan(
                plan_id='free',
                name='Free',
                description='Basic plan for individual developers',
                price_monthly=0,
                price_yearly=0,
                token_limit=100000,
                is_public=True,
                sort_order=10
            )
            plans_to_add.append(free_plan)
            
        if 'pro' not in existing_plan_ids:
            pro_plan = SubscriptionPlan(
                plan_id='pro',
                name='Pro',
                description='Advanced features for professional developers',
                price_monthly=9.99,
                price_yearly=99.00,
                token_limit=1000000,
                is_public=True,
                sort_order=20
            )
            plans_to_add.append(pro_plan)
            
        if 'team' not in existing_plan_ids:
            team_plan = SubscriptionPlan(
                plan_id='team',
                name='Team',
                description='Collaboration features for development teams',
                price_monthly=29.99,
                price_yearly=299.00,
                token_limit=5000000,
                is_public=True,
                sort_order=30
            )
            plans_to_add.append(team_plan)
        
        if plans_to_add:
            session.add_all(plans_to_add)
            session.flush()
            print(f"Added {len(plans_to_add)} new subscription plans")
        else:
            print("Subscription plans already exist, skipping")
        
        # Get all plans for later use
        all_plans = {plan.plan_id: plan for plan in session.query(SubscriptionPlan).all()}
        
        # Check for existing installations
        existing_installations = session.query(Installation.github_id).all()
        existing_installation_ids = [inst[0] for inst in existing_installations]
        
        # Create installations if they don't exist
        print("Creating GitHub App installations...")
        installations_to_add = []
        
        if 123456 not in existing_installation_ids:
            test_installation = Installation(
                github_id=123456,
                account_id=7890123,
                account_type="Organization",
                account_name="TestOrg",
                account_login="testorg",
                access_token="ghs_test123456",
                token_expires_at=datetime.datetime.now() + datetime.timedelta(hours=1),
                is_active=True
            )
            installations_to_add.append(test_installation)
            
        if 234567 not in existing_installation_ids:
            admin_installation = Installation(
                github_id=234567,
                account_id=8901234,
                account_type="User",
                account_name="Admin",
                account_login="admin-user",
                access_token="ghs_admin234567",
                token_expires_at=datetime.datetime.now() + datetime.timedelta(hours=1),
                is_active=True
            )
            installations_to_add.append(admin_installation)
            
        if installations_to_add:
            session.add_all(installations_to_add)
            session.flush()
            print(f"Added {len(installations_to_add)} new installations")
        else:
            print("Installations already exist, skipping")
            
        # Get all installations and users for later use
        installations = {inst.github_id: inst for inst in session.query(Installation).all()}
        users = {user.username: user for user in session.query(User).all()}
        
        # Create user access records if needed
        print("Creating user access permissions...")
        access_records = []
        
        # Check existing access records
        existing_access = session.query(UserAccess.user_id, UserAccess.installation_id).all()
        existing_access_pairs = [(ua[0], ua[1]) for ua in existing_access]
        
        if users.get('testuser') and installations.get(123456):
            access_pair = (users['testuser'].id, installations[123456].id)
            if access_pair not in existing_access_pairs:
                free_access = UserAccess(
                    user_id=users['testuser'].id,
                    installation_id=installations[123456].id,
                    role="member",
                    permissions="read"
                )
                access_records.append(free_access)
                
        if users.get('prouser') and installations.get(123456):
            access_pair = (users['prouser'].id, installations[123456].id)
            if access_pair not in existing_access_pairs:
                pro_access = UserAccess(
                    user_id=users['prouser'].id,
                    installation_id=installations[123456].id,
                    role="member",
                    permissions="write"
                )
                access_records.append(pro_access)
                
        if users.get('admin') and installations.get(234567):
            access_pair = (users['admin'].id, installations[234567].id)
            if access_pair not in existing_access_pairs:
                admin_access = UserAccess(
                    user_id=users['admin'].id,
                    installation_id=installations[234567].id,
                    role="admin",
                    permissions="admin"
                )
                access_records.append(admin_access)
                
        if access_records:
            session.add_all(access_records)
            session.flush()
            print(f"Added {len(access_records)} new user access records")
        else:
            print("User access records already exist, skipping")
        
        # Create subscriptions
        print("Creating subscriptions...")
        from src.models.subscription import Subscription
        
        # Check existing subscriptions
        existing_subs = session.query(Subscription.user_id).all()
        existing_sub_user_ids = [sub[0] for sub in existing_subs]
        
        subscriptions_to_add = []
        
        # Free user subscription
        if users.get('testuser') and users['testuser'].id not in existing_sub_user_ids:
            free_sub = Subscription(
                user_id=users['testuser'].id,
                plan_id=all_plans['free'].plan_id,
                status='active',
                current_period_start=datetime.datetime.now(),
                current_period_end=datetime.datetime.now() + datetime.timedelta(days=30),
                cancel_at_period_end=False
            )
            subscriptions_to_add.append(free_sub)
            
        # Pro user subscription
        if users.get('prouser') and users['prouser'].id not in existing_sub_user_ids:
            pro_sub = Subscription(
                user_id=users['prouser'].id,
                plan_id=all_plans['pro'].plan_id,
                status='active',
                current_period_start=datetime.datetime.now(),
                current_period_end=datetime.datetime.now() + datetime.timedelta(days=30),
                cancel_at_period_end=False
            )
            subscriptions_to_add.append(pro_sub)
            
        # Admin user subscription (team plan)
        if users.get('admin') and users['admin'].id not in existing_sub_user_ids:
            admin_sub = Subscription(
                user_id=users['admin'].id,
                plan_id=all_plans['team'].plan_id,
                status='active',
                current_period_start=datetime.datetime.now(),
                current_period_end=datetime.datetime.now() + datetime.timedelta(days=30),
                cancel_at_period_end=False
            )
            subscriptions_to_add.append(admin_sub)
            
        if subscriptions_to_add:
            session.add_all(subscriptions_to_add)
            session.flush()
            print(f"Added {len(subscriptions_to_add)} new subscriptions")
        else:
            print("Subscriptions already exist, skipping")
            
        # Create repositories
        print("Creating repositories...")
        
        # Check existing repositories
        existing_repos = session.query(Repository.github_id).all()
        existing_repo_ids = [repo[0] for repo in existing_repos]
        
        repos_to_add = []
        
        # Test repository for the test installation
        if 987654321 not in existing_repo_ids and installations.get(123456):
            test_repo = Repository(
                user_id=users['testuser'].id if users.get('testuser') else None,
                installation_id=installations[123456].id,
                github_id=987654321,
                name='test-repo',
                full_name='testorg/test-repo',
                default_branch='main',
                is_private=False,
                clone_url='https://github.com/testorg/test-repo.git',
                last_scanned_at=datetime.datetime.now()
            )
            repos_to_add.append(test_repo)
            
        # Admin repository
        if 987654322 not in existing_repo_ids and installations.get(234567):
            admin_repo = Repository(
                user_id=users['admin'].id if users.get('admin') else None,
                installation_id=installations[234567].id,
                github_id=987654322,
                name='admin-repo',
                full_name='admin-user/admin-repo',
                default_branch='main',
                is_private=True,
                clone_url='https://github.com/admin-user/admin-repo.git',
                last_scanned_at=datetime.datetime.now()
            )
            repos_to_add.append(admin_repo)
            
        if repos_to_add:
            session.add_all(repos_to_add)
            session.flush()
            print(f"Added {len(repos_to_add)} new repositories")
        else:
            print("Repositories already exist, skipping")
            
        session.commit()
        print("Sample data creation completed successfully")

if __name__ == '__main__':
    # Check if we should reset the database
    if len(sys.argv) > 1 and sys.argv[1] == '--reset':
        reset_database() # Resets DB and runs alembic upgrade
        print("\nPopulating database with sample data...")
        create_sample_data() # Populate data AFTER schema is created
    else:
        # Default action: Ensure schema exists and populate data
        # This assumes schema might already exist, useful for just adding sample data
        print("Ensuring database schema is up-to-date using Alembic...")
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        alembic_ini_path = os.path.join(project_root, 'alembic.ini')
        alembic_command = [sys.executable, "-m", "alembic", "-c", alembic_ini_path, "upgrade", "head"]
        try:
            subprocess.run(alembic_command, cwd=project_root, check=True, capture_output=True, text=True)
            print("Alembic check/upgrade complete.")
        except Exception as e:
            print(f"Error running Alembic upgrade during default run: {e}")
            # Decide if you want to exit or just warn
        
        print("\nPopulating database with sample data...")
        create_sample_data()
    
    print("\nDatabase initialization and data population complete!") 