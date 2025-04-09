"""
Installation Model
================

Represents a GitHub App installation in an organization or user account.
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, func, ForeignKey
from sqlalchemy.orm import relationship

from src.database import Base

class Installation(Base):
    """
    Represents a GitHub App installation.
    
    This tracks installations of the DocPilot GitHub App in organizations or user accounts.
    
    Attributes:
        id: Primary key
        github_id: GitHub's installation ID
        account_id: GitHub account ID where installed
        account_type: Type of account (Organization or User)
        account_name: Name of the account
        account_login: Login/username of the account
        access_token: GitHub access token
        token_expires_at: When the token expires
        is_active: Whether this installation is active
        suspended_reason: Reason if installation is suspended
        created_at: When this record was created
        updated_at: When this record was last updated
    """
    __tablename__ = "installations"
    
    # Primary key
    id = Column(Integer, primary_key=True)
    
    # GitHub identifiers
    github_id = Column(Integer, nullable=False, unique=True)
    account_id = Column(Integer, nullable=False)
    account_type = Column(String(20), nullable=False)  # 'Organization' or 'User'
    account_name = Column(String(255), nullable=True)
    account_login = Column(String(100), nullable=False)
    
    # Authentication
    access_token = Column(String(255), nullable=True)
    token_expires_at = Column(DateTime, nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    suspended_reason = Column(String(255), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    repositories = relationship("Repository", back_populates="installation", cascade="all, delete-orphan")
    settings_obj = relationship("InstallationSettings", back_populates="installation", 
                           uselist=False, cascade="all, delete-orphan")
    users = relationship("UserAccess", back_populates="installation")
    
    def __repr__(self):
        return f"<Installation {self.github_id} for {self.account_login}>"
    
    def to_dict(self):
        """Convert installation to dictionary"""
        return {
            "id": self.id,
            "github_id": self.github_id,
            "account_id": self.account_id,
            "account_type": self.account_type,
            "account_name": self.account_name,
            "account_login": self.account_login,
            "is_active": self.is_active,
            "suspended_reason": self.suspended_reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
    
    def is_token_valid(self):
        """Check if the access token is still valid"""
        if not self.access_token or not self.token_expires_at:
            return False
        return self.token_expires_at > func.now()


class UserAccess(Base):
    """
    Represents a user's access to an installation.
    
    This tracks which users have access to which installations, including their permissions.
    
    Attributes:
        id: Primary key
        user_id: Foreign key to the user
        installation_id: Foreign key to the installation
        permissions: User's permissions for this installation
        created_at: When this record was created
        updated_at: When this record was last updated
    """
    __tablename__ = "user_access"
    
    # Primary key
    id = Column(Integer, primary_key=True)
    
    # Relationships
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    # Use string names
    user = relationship("User", back_populates="installations")
    
    installation_id = Column(Integer, ForeignKey("installations.id"), nullable=False)
    # Use string names
    installation = relationship("Installation", back_populates="users")
    
    # Access details
    role = Column(String(20), default="member")  # 'admin', 'member', etc.
    permissions = Column(String(50), default="read")  # 'read', 'write', 'admin'
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<UserAccess: User {self.user_id} to Installation {self.installation_id}>" 