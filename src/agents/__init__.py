"""
DocPilot Agents
=============

This module provides the core agents for documentation generation following the Diátaxis framework.
"""

from .base import BaseAgent, AgentConfig, AgentResult
from .api_doc_agent import ApiDocAgent, ApiDocDependency, ApiDocumentation


__all__ = [
    # Base classes
    'BaseAgent',
    'AgentConfig',
    'AgentResult',
    
    # API Documentation Agent
    'ApiDocAgent',
    'ApiDocDependency',
    'ApiDocumentation'
]