"""
Database Models Test Script
=========================

This script tests the database models by querying and displaying data.
It can be used to verify that the database structure is working correctly.
"""

import os
import sys
import datetime
from pprint import pprint

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.database import get_session
from src.models.user import User
from src.models.repository import Repository, DocumentFile
from src.models.subscription import Subscription, SubscriptionPlan
from src.models.usage import Usage, UsageSummary

def display_users():
    """Display all users in the database"""
    print("\n=== USERS ===")
    with get_session() as session:
        users = session.query(User).all()
        print(f"Found {len(users)} users:")
        for user in users:
            print(f"- {user.username} ({user.email})")
            print(f"  Full name: {user.full_name}")
            print(f"  Active: {user.is_active}, Verified: {user.is_verified}")
            print(f"  Created: {user.created_at}")
            if user.github_username:
                print(f"  GitHub: {user.github_username}")
            print()

def display_subscription_plans():
    """Display all subscription plans"""
    print("\n=== SUBSCRIPTION PLANS ===")
    with get_session() as session:
        plans = session.query(SubscriptionPlan).order_by(SubscriptionPlan.sort_order).all()
        print(f"Found {len(plans)} subscription plans:")
        for plan in plans:
            print(f"- {plan.name} (${plan.price_monthly}/mo or ${plan.price_yearly}/yr)")
            print(f"  Description: {plan.description}")
            print(f"  Token Limit: {plan.token_limit}")
            print(f"  Active: {plan.is_active}, Public: {plan.is_public}")
            print()

def display_user_subscriptions():
    """Display subscriptions for all users"""
    print("\n=== USER SUBSCRIPTIONS ===")
    with get_session() as session:
        subscriptions = session.query(Subscription).join(User).join(SubscriptionPlan).all()
        print(f"Found {len(subscriptions)} subscriptions:")
        for sub in subscriptions:
            print(f"- {sub.user.username} is on the {sub.plan.name} plan")
            print(f"  Status: {sub.status}")
            print(f"  Current period: {sub.current_period_start.strftime('%Y-%m-%d')} to {sub.current_period_end.strftime('%Y-%m-%d')}")
            print(f"  Cancel at period end: {sub.cancel_at_period_end}")
            print()

def display_repositories():
    """Display all repositories"""
    print("\n=== REPOSITORIES ===")
    with get_session() as session:
        repos = session.query(Repository).all()
        print(f"Found {len(repos)} repositories:")
        for repo in repos:
            print(f"- {repo.full_name} (GitHub ID: {repo.github_id})")
            print(f"  Private: {repo.is_private}, Branch: {repo.default_branch}")
            print(f"  Last scanned: {repo.last_scanned_at}")
            doc_count = session.query(DocumentFile).filter(DocumentFile.repository_id == repo.id).count()
            print(f"  Doc files: {doc_count}")
            print()

def display_document_files():
    """Display document files for repositories"""
    print("\n=== DOCUMENT FILES ===")
    with get_session() as session:
        docs = session.query(DocumentFile).join(Repository).all()
        print(f"Found {len(docs)} document files:")
        for doc in docs:
            print(f"- {doc.path} in {doc.repository.full_name}")
            print(f"  Title: {doc.title}")
            print(f"  Last commit: {doc.last_commit_sha}")
            print(f"  Last updated in repo: {doc.last_updated_at}")
            print(f"  Content updated by DocPilot: {doc.content_updated_at}")
            print()

def display_usage_records():
    """Display recent usage records"""
    print("\n=== USAGE RECORDS ===")
    with get_session() as session:
        # Get the 10 most recent usage records
        records = session.query(Usage).order_by(Usage.created_at.desc()).limit(10).all()
        print(f"Found {len(records)} recent usage records:")
        for record in records:
            print(f"- Operation: {record.operation_type}, Model: {record.model_name}")
            user = session.query(User).filter(User.id == record.user_id).first()
            print(f"  User: {user.username if user else record.user_id}")
            if record.repository_id:
                repo = session.query(Repository).filter(Repository.id == record.repository_id).first()
                print(f"  Repository: {repo.full_name if repo else record.repository_id}")
            print(f"  Tokens: {record.input_tokens} in, {record.output_tokens} out")
            print(f"  Cost: ${record.cost:.4f}")
            print(f"  Created: {record.created_at}")
            print()

def display_usage_summaries():
    """Display usage summaries"""
    print("\n=== USAGE SUMMARIES ===")
    with get_session() as session:
        summaries = session.query(UsageSummary).join(User).all()
        print(f"Found {len(summaries)} usage summaries:")
        for summary in summaries:
            period = f"{summary.period_start.strftime('%Y-%m-%d')} to {summary.period_end.strftime('%Y-%m-%d')}"
            print(f"- User: {summary.user.username}, Period: {period}")
            print(f"  Operations: {summary.total_operations}")
            print(f"  Tokens: {summary.total_input_tokens} in, {summary.total_output_tokens} out")
            print(f"  Cost: ${summary.total_cost:.2f}")
            print(f"  Billed: {summary.is_billed}")
            print()

def run_query_test():
    """Run a more complex query test"""
    print("\n=== COMPLEX QUERY TEST ===")
    with get_session() as session:
        # Find repositories with recent documentation updates
        one_week_ago = datetime.datetime.now() - datetime.timedelta(days=7)
        repos_with_recent_updates = session.query(Repository)\
            .join(DocumentFile)\
            .filter(DocumentFile.content_updated_at >= one_week_ago)\
            .distinct()\
            .all()
        
        print(f"Found {len(repos_with_recent_updates)} repositories with documentation updated in the last week:")
        for repo in repos_with_recent_updates:
            print(f"- {repo.full_name}")
            
            # Count recent doc updates in this repo
            recent_updates_count = session.query(DocumentFile)\
                .filter(DocumentFile.repository_id == repo.id)\
                .filter(DocumentFile.content_updated_at >= one_week_ago)\
                .count()
            
            print(f"  Recent doc updates: {recent_updates_count}")
            print()
        
        # Find users who have generated the most tokens
        print("\nTop users by token usage:")
        user_usage = session.query(User.username, UsageSummary.total_input_tokens + UsageSummary.total_output_tokens)\
            .join(UsageSummary, User.id == UsageSummary.user_id)\
            .order_by((UsageSummary.total_input_tokens + UsageSummary.total_output_tokens).desc())\
            .limit(3)\
            .all()
        
        for username, tokens in user_usage:
            print(f"- {username}: {tokens:,} tokens")

if __name__ == '__main__':
    display_users()
    display_subscription_plans()
    display_user_subscriptions()
    display_repositories()
    display_document_files()
    display_usage_records()
    display_usage_summaries()
    run_query_test()
    
    print("\nDatabase model tests completed successfully!") 