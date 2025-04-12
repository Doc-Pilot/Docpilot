"""
API Parsing Utilities
=====================

Functions for parsing API endpoints and schemas from code structures,
primarily using AST analysis.
"""

from typing import Dict, Any, List, Optional

# Assuming logger is available or passed in, or create one
from .logging import core_logger 
logger = core_logger()

# Re-using Pydantic models for structure might be good, or just return dicts
# from ..agents.api_doc_agent import ApiEndpoint # Avoid circular dependency if possible

# FastAPI/Pydantic parsing logic moved to src/parsers/fastapi_parser.py

# --- Other Framework Parsers (Keep here for now) ---

def parse_flask_endpoint(file_path: str, file_structure: Dict[str, Any], repo_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Placeholder for Flask endpoint parsing."""
    logger.debug(f"Flask parser called for {file_path} (Not Implemented)")
    # TODO: Implement Flask parsing logic using AST
    return []

def parse_express_endpoint(file_path: str, file_structure: Dict[str, Any], repo_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Placeholder for Express endpoint parsing."""
    logger.debug(f"Express parser called for {file_path} (Not Implemented)")
    # TODO: Implement Express parsing logic (requires different AST or regex)
    return []

def parse_django_endpoint(file_path: str, file_structure: Dict[str, Any], repo_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Placeholder for Django endpoint parsing."""
    logger.debug(f"Django parser called for {file_path} (Not Implemented)")
    # TODO: Implement Django parsing logic (urls.py, views.py)
    return []

def parse_generic_endpoint(file_path: str, file_structure: Dict[str, Any], repo_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fallback generic endpoint parsing attempt."""
    logger.debug(f"Generic endpoint parser called for {file_path}")
    # TODO: Implement basic regex or comment-based parsing as a fallback
    return []

def parse_django_model(class_info: Dict[str, Any]) -> Dict[str, Any]:
    """Placeholder for Django model parsing."""
    logger.debug(f"Django model parser called for {class_info.get('name', 'N/A')} (Not Implemented)")
    # TODO: Implement Django model parsing (models.py)
    return {"name": class_info.get('name', 'Unknown'), "fields": [], "source_file": class_info.get('file_path')}

def parse_typescript_model(class_info: Dict[str, Any]) -> Dict[str, Any]:
    """Placeholder for TypeScript interface/class parsing."""
    logger.debug(f"TypeScript model parser called for {class_info.get('name', 'N/A')} (Not Implemented)")
    # TODO: Implement TypeScript parsing (requires TS parser)
    return {"name": class_info.get('name', 'Unknown'), "fields": [], "source_file": class_info.get('file_path')}

def parse_generic_model(class_info: Dict[str, Any]) -> Dict[str, Any]:
    """Fallback generic model parsing attempt."""
    logger.debug(f"Generic model parser called for {class_info.get('name', 'N/A')}")
    # TODO: Implement basic class parsing
    return {"name": class_info.get('name', 'Unknown'), "fields": [], "source_file": class_info.get('file_path')}

def is_data_model(cls: Dict[str, Any], framework: Optional[str]) -> bool:
    """Checks if a class definition is likely a data model based on framework conventions."""
    name = cls.get('name', '')
    base_classes = cls.get('bases', [])
    decorators = cls.get('decorators', [])
    file_path = cls.get('file_path', '')
    attributes = cls.get('attributes', [])

    if not name or not file_path:
        logger.debug(f"is_data_model({name}, {framework}): False (missing name or file_path)")
        return False

    # --- Exclusion Checks (SQLAlchemy specific) ---
    # Check for __tablename__ attribute which strongly indicates SQLAlchemy
    if any(attr.get('name') == '__tablename__' for attr in attributes):
        logger.debug(f"is_data_model({name}, {framework}): False (SQLAlchemy __tablename__ found)")
        return False
        
    # Add more specific SQLAlchemy base class checks if needed, e.g., if you use a custom Base
    # Example: if 'declarative_base' in file_content and 'Base' in base_classes: return False

    # --- Framework Specific Checks ---
    if framework == 'fastapi':
        # Primary check: Inherits directly from 'BaseModel' (most common case)
        if 'BaseModel' in base_classes:
            logger.debug(f"is_data_model({name}, {framework}): True (FastAPI/Pydantic BaseModel inheritance)")
            return True
        # Secondary check: Uses @dataclass decorator (often used with Pydantic)
        if 'dataclass' in [d.lower() for d in decorators]:
             logger.debug(f"is_data_model({name}, {framework}): True (FastAPI/Pydantic @dataclass decorator)")
             return True
        # Avoid relying solely on filename for FastAPI Pydantic models
        logger.debug(f"is_data_model({name}, {framework}): False (FastAPI check failed - not BaseModel or @dataclass)")
        return False # Be stricter for FastAPI - must meet criteria

    if framework == 'django':
        if 'models.Model' in base_classes:
            logger.debug(f"is_data_model({name}, {framework}): True (django Model)")
            return True
        # Add DRF Serializer checks if needed
        logger.debug(f"is_data_model({name}, {framework}): False (Django check failed)")
        return False

    # --- General Heuristics (Lower Confidence - Use after specific checks fail) ---
    
    # General base classes (Lower confidence than specific framework checks)
    # Consider removing 'Model' as it conflicts with Django/SQLAlchemy
    general_bases = ['Schema', 'Serializer', 'Entity', 'DTO'] # Removed 'BaseModel', 'Model'
    if any(base in general_bases for base in base_classes):
        logger.debug(f"is_data_model({name}, {framework}): True (General base class heuristic: {base_classes})")
        return True
            
    # Decorator checks (Lower confidence)
    general_decorators = ['entity'] # Removed 'dataclass' as handled by FastAPI specifically
    if any(dec.lower() in general_decorators for dec in decorators):
        logger.debug(f"is_data_model({name}, {framework}): True (General decorator heuristic: {decorators})")
        return True

    # Filename conventions (Lowest confidence - maybe remove or make very specific)
    # Avoid using this for FastAPI as we have better checks
    # if framework != 'fastapi' and any(pattern in file_path.lower() for pattern in ['/schemas/', '/dtos/', '/entities/']):
    #     logger.debug(f"is_data_model({name}, {framework}): True (Filename convention heuristic: {file_path})")
    #     return True

    logger.debug(f"Class '{name}' in {file_path} not identified as a data model by any rule.")
    return False 