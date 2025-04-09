"""
Settings Model
============

Stores configuration settings for installations and repositories.
"""

from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, func, Boolean, JSON
from sqlalchemy.orm import relationship

from src.database import Base

class InstallationSettings(Base):
    """
    Stores configuration settings for a GitHub App installation.
    
    This allows for customization of DocPilot behavior at the organization/account level.
    
    Attributes:
        id: Primary key
        installation_id: Foreign key to the installation
        ai_model: AI model to use for generation (default or specific)
        doc_update_settings: Whether to auto-update documentation
        created_at: When this record was created
        updated_at: When this record was last updated
    """
    __tablename__ = "installation_settings"
    
    # Primary key
    id = Column(Integer, primary_key=True)
    
    # Installation relationship
    installation_id = Column(Integer, ForeignKey("installations.id"), nullable=False, unique=True)
    installation = relationship("Installation", back_populates="settings_obj")
    
    # AI Settings
    ai_model = Column(String(50), default="gpt-4o")
    
    # Automation settings
    auto_update_docs = Column(Boolean, default=False)
    auto_update_conditions = Column(JSON, default={
        "min_changes": 5,
        "file_patterns": ["*.md", "*.rst"]
    })
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<InstallationSettings for installation {self.installation_id}>"
    
    def to_dict(self):
        """Convert settings to dictionary"""
        return {
            "id": self.id,
            "installation_id": self.installation_id,
            "ai_model": self.ai_model,
            "auto_update_docs": self.auto_update_docs,
            "auto_update_conditions": self.auto_update_conditions,
        }


class RepositorySettings(Base):
    """
    Stores configuration settings for a specific repository.
    
    This allows for customization of DocPilot behavior at the repository level.
    
    Attributes:
        id: Primary key
        repository_id: Foreign key to the repository
        ai_model: AI model to use for generation (default or specific)
        doc_path_patterns: Patterns to identify doc files
        code_path_patterns: Patterns to identify code files
        ignore_patterns: Patterns to ignore
        auto_update: Whether to auto-update docs
        created_at: When this record was created
        updated_at: When this record was last updated
    """
    __tablename__ = "repository_settings"
    
    # Primary key
    id = Column(Integer, primary_key=True)
    
    # Repository relationship
    repository_id = Column(Integer, ForeignKey("repositories.id"), nullable=False, unique=True)
    repository = relationship("Repository", back_populates="settings_obj")
    
    # AI Settings
    ai_model = Column(String(50), nullable=True)  # Null means use installation default
    
    # Documentation settings
    doc_path_patterns = Column(JSON, default=["docs/**/*.md", "**/*.md"])
    code_path_patterns = Column(JSON, default=["**/*.py", "**/*.js", "**/*.java", "**/*.go", "**/*.ts"])
    ignore_patterns = Column(JSON, default=["**/node_modules/**", "**/.git/**", "**/dist/**", "**/build/**"])
    
    # Automation settings
    auto_update = Column(Boolean, default=False)
    
    # PR settings
    pr_creation = Column(JSON, default={
        "enabled": True,
        "title_template": "Update documentation for {files}",
        "body_template": "DocPilot has updated the documentation based on recent code changes.",
        "labels": ["documentation", "automated", "docpilot"]
    })
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<RepositorySettings for repository {self.repository_id}>"
    
    def to_dict(self):
        """Convert settings to dictionary"""
        return {
            "id": self.id,
            "repository_id": self.repository_id,
            "ai_model": self.ai_model,
            "doc_path_patterns": self.doc_path_patterns,
            "code_path_patterns": self.code_path_patterns,
            "ignore_patterns": self.ignore_patterns,
            "auto_update": self.auto_update,
            "pr_creation": self.pr_creation,
        } 