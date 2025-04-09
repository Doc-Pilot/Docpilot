"""
Database Models
=============

This package contains SQLAlchemy ORM models for the application.
"""

from src.database import Base

from .user import User
from .repository import Repository, DocumentFile
from .installation import Installation, UserAccess
from .settings import InstallationSettings, RepositorySettings
from .subscription import Subscription, SubscriptionPlan
from .usage import Usage, UsageSummary

# Define __all__ to control what's imported with wildcard imports
__all__ = [
    'User',
    'Repository',
    'DocumentFile',
    'Installation',
    'UserAccess',
    'InstallationSettings', 
    'RepositorySettings',
    'Subscription',
    'SubscriptionPlan',
    'Usage',
    'UsageSummary',
]

# Create a function to import all models and avoid circular imports
def register_models():
    """Import all models to ensure they're registered with SQLAlchemy"""
    global User, Repository, DocumentFile, Installation
    global InstallationSettings, RepositorySettings
    global Subscription, SubscriptionPlan
    global Usage, UsageSummary
    
    from .user import User
    from .repository import Repository, DocumentFile
    from .installation import Installation
    from .settings import InstallationSettings, RepositorySettings
    from .subscription import Subscription, SubscriptionPlan
    from .usage import Usage, UsageSummary 