"""
Subscription Model
================

Tracks user subscription plans and billing information.
"""

import datetime
from sqlalchemy import Column, Integer, String, DateTime, Float, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from src.database import Base, JsonType

class Subscription(Base):
    """
    Represents a user subscription.
    
    Tracks the subscription status, plan, and billing details for users.
    
    Attributes:
        id: Primary key
        user_id: Foreign key to the user
        plan_id: Subscription plan identifier
        status: Subscription status
        current_period_start: Start of current billing period
        current_period_end: End of current billing period
        cancel_at_period_end: Whether the subscription will cancel at period end
        created_at: When this record was created
        updated_at: When this record was last updated
    """
    __tablename__ = "subscriptions"
    
    # Primary key
    id = Column(Integer, primary_key=True)
    
    # User relationship
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, unique=True)
    user = relationship("User", back_populates="subscription")
    
    # Plan relationship
    plan_id = Column(String(20), ForeignKey("subscription_plans.plan_id"), nullable=False)
    plan = relationship("SubscriptionPlan")
    
    # Subscription status
    status = Column(String(20), default="active")  # active, past_due, canceled, etc.
    
    # Billing period
    current_period_start = Column(DateTime, nullable=False)
    current_period_end = Column(DateTime, nullable=False)
    cancel_at_period_end = Column(Boolean, default=False)
    
    # Payment details
    payment_method = Column(String(255), nullable=True)
    payment_provider = Column(String(50), nullable=True)
    payment_provider_id = Column(String(255), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, 
                      onupdate=datetime.datetime.utcnow)
    
    def __repr__(self):
        return f"<Subscription {self.id} for user {self.user_id} on plan {self.plan_id}>"
    
    def to_dict(self):
        """Convert subscription to dictionary"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "plan_id": self.plan_id,
            "status": self.status,
            "current_period_start": self.current_period_start.isoformat() if self.current_period_start else None,
            "current_period_end": self.current_period_end.isoformat() if self.current_period_end else None,
            "cancel_at_period_end": self.cancel_at_period_end,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class SubscriptionPlan(Base):
    """
    Represents a subscription plan.
    
    Defines the available subscription plans with features and prices.
    
    Attributes:
        plan_id: Primary key and plan identifier
        name: Plan name
        description: Plan description
        price_monthly: Monthly price
        price_yearly: Yearly price
        features: Plan features and limits
        is_public: Whether this plan is publicly available
        created_at: When this record was created
        updated_at: When this record was last updated
    """
    __tablename__ = "subscription_plans"
    
    # Primary key
    plan_id = Column(String(20), primary_key=True)
    
    # Plan details
    name = Column(String(50), nullable=False)
    description = Column(String(255), nullable=True)
    price_monthly = Column(Float, nullable=False, default=0)
    price_yearly = Column(Float, nullable=False, default=0)
    
    # Features and limits
    token_limit = Column(Integer, nullable=False, default=100000)
    features = Column(JsonType, nullable=True)
    
    # Status and display
    is_active = Column(Boolean, default=True)
    is_public = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, 
                      onupdate=datetime.datetime.utcnow)
    
    def __repr__(self):
        return f"<SubscriptionPlan {self.plan_id}: {self.name}>"
    
    def to_dict(self):
        """Convert subscription plan to dictionary"""
        return {
            "plan_id": self.plan_id,
            "name": self.name,
            "description": self.description,
            "price_monthly": self.price_monthly,
            "price_yearly": self.price_yearly,
            "token_limit": self.token_limit,
            "features": self.features,
            "is_active": self.is_active,
            "is_public": self.is_public,
        } 