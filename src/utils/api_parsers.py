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

    if not name or not file_path:
        return False

    # Common base classes
    common_bases = ['BaseModel', 'Model', 'Schema', 'Serializer', 'Entity']
    if any(base in common_bases for base in base_classes):
            return True
            
    # Framework-specific checks
    if framework == 'fastapi' and 'BaseModel' in base_classes:
        return True
    if framework == 'django' and 'models.Model' in base_classes:
        return True
    if framework in ['express', 'nestjs'] and 'Schema' in name: # Heuristic
             return True
             
    # Decorator checks (e.g., @dataclass, @Entity)
    common_decorators = ['dataclass', 'entity']
    if any(dec.lower() in common_decorators for dec in decorators):
        return True

    # Filename conventions
    if any(pattern in file_path.lower() for pattern in ['models/', 'schemas/', 'dtos/', 'entities/']):
        return True

    logger.debug(f"Class '{name}' in {file_path} not identified as a primary data model.")
    return False 