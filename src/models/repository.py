"""
Repository Model
=============

Represents a GitHub repository tracked by Docpilot.
"""

from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Boolean, func
from sqlalchemy.orm import relationship

from src.database import Base

class Repository(Base):
    """
    Represents a GitHub repository.
    
    Tracks repositories connected to the DocPilot application, including metadata
    and documentation files.
    
    Attributes:
        id: Primary key
        user_id: Owner of the repository connection
        installation_id: GitHub App installation that manages this repo
        github_id: GitHub's repository ID
        name: Repository name
        full_name: Full repository name (owner/name)
        default_branch: Default branch (usually main or master)
        is_private: Whether repository is private
        clone_url: URL to clone the repository
        last_scanned_at: When docs were last analyzed
        created_at: When this record was created
        updated_at: When this record was last updated
    """
    __tablename__ = "repositories"
    
    # Primary key
    id = Column(Integer, primary_key=True)
    
    # User relationship
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    user = relationship("User", back_populates="repositories")
    
    # GitHub App installation (if connected via app)
    installation_id = Column(Integer, ForeignKey("installations.id"), nullable=True)
    installation = relationship("Installation", back_populates="repositories")
    
    # GitHub repository details  
    github_id = Column(Integer, nullable=False, unique=True)
    name = Column(String(100), nullable=False)
    full_name = Column(String(200), nullable=False)
    default_branch = Column(String(100), default="main")
    is_private = Column(Boolean, default=False)
    clone_url = Column(String(255))
    
    # Status tracking
    last_scanned_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    document_files = relationship("DocumentFile", back_populates="repository", 
                                 cascade="all, delete-orphan")
    settings_obj = relationship("RepositorySettings", back_populates="repository",
                           uselist=False, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Repository {self.full_name}>"
    
    def to_dict(self):
        """Convert repository to dictionary"""
        return {
            "id": self.id,
            "github_id": self.github_id,
            "name": self.name,
            "full_name": self.full_name,
            "default_branch": self.default_branch,
            "is_private": self.is_private,
            "clone_url": self.clone_url,
            "last_scanned_at": self.last_scanned_at.isoformat() if self.last_scanned_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class DocumentFile(Base):
    """
    Represents a documentation file within a repository.
    
    Tracks documentation files found in repositories, their content,
    and metadata about when they were last updated.
    
    Attributes:
        id: Primary key
        repository_id: Repository this file belongs to
        path: Path to the file within the repository
        title: Document title extracted from content
        last_commit_sha: SHA of the commit that last changed this file
        last_updated_at: When the file was last changed in the repo
        content_updated_at: When DocPilot last updated the content
        created_at: When this record was created
        updated_at: When this record was last updated
    """
    __tablename__ = "document_files"
    
    # Primary key
    id = Column(Integer, primary_key=True)
    
    # Repository relationship
    repository_id = Column(Integer, ForeignKey("repositories.id"), nullable=False)
    repository = relationship("Repository", back_populates="document_files")
    
    # File details
    path = Column(String(255), nullable=False)
    title = Column(String(255), nullable=True)
    
    # Git tracking
    last_commit_sha = Column(String(40), nullable=True)
    last_updated_at = Column(DateTime, nullable=True)
    content_updated_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<DocumentFile {self.path} in {self.repository_id}>" 