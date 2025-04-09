"""
Usage Model
=========

Tracks API usage and token consumption.
"""

import uuid
import datetime
from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship

from src.database import Base, JsonType

class Usage(Base):
    """
    Tracks API usage and token consumption.
    
    Records each API operation, token usage, and cost for billing.
    
    Attributes:
        id: Primary key
        user_id: Foreign key to the user
        repository_id: Foreign key to the repository (optional)
        operation_type: Type of operation performed
        model_name: AI model used
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        cost: Cost calculation based on model and tokens
        usage_metadata: Additional metadata about the operation
        created_at: When this record was created
    """
    __tablename__ = 'usage'
    
    # Primary key
    id = Column(Integer, primary_key=True)
    
    # User relationship
    user_id = Column(String(36), ForeignKey('users.id'), nullable=False)
    user = relationship('User', back_populates='usage_records')
    
    # Repository relationship (optional)
    repository_id = Column(Integer, ForeignKey('repositories.id'), nullable=True)
    repository = relationship('Repository')
    
    # Operation details
    operation_id = Column(String(36), default=lambda: str(uuid.uuid4()))
    operation_type = Column(String(50), nullable=False)  # e.g., 'doc_generation', 'code_analysis'
    model_name = Column(String(50), nullable=False)  # e.g., 'gpt-4', 'claude-3'
    
    # Token usage
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    
    # Cost tracking
    cost = Column(Float, nullable=False, default=0.0)
    
    # Additional metadata
    usage_metadata = Column(JsonType, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f'<Usage {self.operation_id}: {self.operation_type}>'
    
    def calculate_cost(self, model_name: str = None):
        """
        Calculate the cost of this usage based on the model and tokens.
        
        Args:
            model_name: Override the model name if needed
        
        Returns:
            Calculated cost
        """
        from ..utils.metrics import ModelCosts
        model = model_name or self.model_name
        costs = ModelCosts.for_model(model)
        self.cost = costs.calculate_cost(self.input_tokens, self.output_tokens)
        return self.cost
        
    def add(self, other: "Usage"):
        """
        Add another usage record's tokens to this one.
        
        Args:
            other: Another usage record
            
        Returns:
            Self for method chaining
        """
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.cost += other.cost
        return self


class UsageSummary(Base):
    """
    Aggregates usage data for billing periods.
    
    Summarizes usage across operations for a billing period (usually monthly).
    
    Attributes:
        id: Primary key
        user_id: Foreign key to the user
        period_start: Start of the billing period
        period_end: End of the billing period
        total_operations: Total number of operations
        total_input_tokens: Total input tokens used
        total_output_tokens: Total output tokens used
        total_cost: Total cost for the period
        is_billed: Whether this period has been billed
        summary_metadata: Additional metadata about the billing
        created_at: When this record was created
        updated_at: When this record was last updated
    """
    __tablename__ = 'usage_summaries'
    
    # Primary key
    id = Column(Integer, primary_key=True)
    
    # User relationship
    user_id = Column(String(36), ForeignKey('users.id'), nullable=False)
    user = relationship('User', back_populates='usage_summaries')
    
    # Billing period
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    
    # Usage totals
    total_operations = Column(Integer, default=0)
    total_input_tokens = Column(Integer, default=0)
    total_output_tokens = Column(Integer, default=0)
    total_cost = Column(Float, default=0.0)
    
    # Billing status
    is_billed = Column(Integer, default=0)  # 0: not billed, 1: billed, 2: paid
    
    # Additional metadata
    summary_metadata = Column(JsonType, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, 
                        onupdate=datetime.datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f'<UsageSummary: {self.period_start} to {self.period_end}>' 