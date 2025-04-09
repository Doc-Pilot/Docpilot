"""
User Model
==========

Represents a user of the application with authentication and profile information.
"""

import uuid
import datetime
from sqlalchemy import Column, String, DateTime, Boolean, Integer
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship
from passlib.hash import pbkdf2_sha256

from src.database import Base, JsonType

class User(Base):
    """
    Represents a user of the application.
    
    Stores authentication information, profile data, and relationships to other models.
    """
    __tablename__ = 'users'
    
    # Primary key and identification
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    
    # Authentication
    _password_hash = Column('password_hash', String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    verification_token = Column(String(100), nullable=True)
    reset_token = Column(String(100), nullable=True)
    reset_token_expires_at = Column(DateTime, nullable=True)
    
    # Profile information
    first_name = Column(String(50), nullable=True)
    last_name = Column(String(50), nullable=True)
    avatar_url = Column(String(255), nullable=True)
    timezone = Column(String(50), default='UTC', nullable=False)
    locale = Column(String(10), default='en_US', nullable=False)
    
    # Preferences and settings
    preferences = Column(JsonType, nullable=True)  # JSON storage for user preferences
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, 
                        onupdate=datetime.datetime.utcnow, nullable=False)
    
    # Relationships
    repositories = relationship('Repository', back_populates='user', 
                               cascade='all, delete-orphan')
    subscription = relationship('Subscription', back_populates='user', 
                               uselist=False, cascade='all, delete-orphan')
    usage_records = relationship('Usage', back_populates='user',
                                cascade='all, delete-orphan')
    usage_summaries = relationship('UsageSummary', back_populates='user',
                                   cascade='all, delete-orphan')
    installations = relationship('UserAccess', back_populates='user',
                               cascade='all, delete-orphan')
    
    # GitHub integration
    github_username = Column(String(100), nullable=True)
    
    # Password handling
    @hybrid_property
    def password(self):
        """Prevent password from being accessed"""
        raise AttributeError('password is not a readable attribute')
    
    @password.setter
    def password(self, password):
        """Set password hash"""
        self._password_hash = pbkdf2_sha256.hash(password)
    
    def verify_password(self, password):
        """Check if password matches the hash"""
        return pbkdf2_sha256.verify(password, self._password_hash)
    
    @property
    def full_name(self):
        """Return user's full name or username if not available"""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        return self.username
    
    def __repr__(self):
        return f'<User {self.username}>' 