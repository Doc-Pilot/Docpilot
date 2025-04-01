"""
DocPilot Agent Module
=====================

This module provides AI agent classes for code analysis, documentation generation,
and quality checking of documentation.
"""

from .base import BaseAgent, AgentConfig
from .code_analyzer import CodeAnalyzer, CodeElement, CodeAnalysisResult, DocstringResult, ComplexityResult
from .doc_generator import DocGenerator, DocGeneratorInput, DocumentationResult, ExamplesResult, ImprovementsResult
from .quality_checker import QualityChecker, QualityCheckInput, QualityResult, QualityIssue, CompletenessResult, ConsistencyResult

__all__ = [
    'BaseAgent',
    'AgentConfig',
    'CodeAnalyzer',
    'CodeElement',
    'CodeAnalysisResult',
    'DocstringResult',
    'ComplexityResult',
    'DocGenerator',
    'DocGeneratorInput',
    'DocumentationResult',
    'ExamplesResult',
    'ImprovementsResult',
    'QualityChecker',
    'QualityCheckInput',
    'QualityResult',
    'QualityIssue',
    'CompletenessResult',
    'ConsistencyResult'
] 