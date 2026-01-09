"""
SQLAlchemy database models for e-commerce demo.
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime

Base = declarative_base()


class Customer(Base):
    """Customer model."""
    __tablename__ = "customers"
    
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    phone = Column(String)
    address = Column(Text)
    loyalty_points = Column(Integer, default=0)
    membership_tier = Column(String, default="bronze")  # bronze, silver, gold, platinum
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    orders = relationship("Order", back_populates="customer")
    
    def to_dict(self):
        return {
            "customer_id": self.id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "address": self.address,
            "loyalty_points": self.loyalty_points,
            "membership_tier": self.membership_tier,
            "member_since": self.created_at.isoformat() if self.created_at else None
        }


class Order(Base):
    """Order model."""
    __tablename__ = "orders"
    
    id = Column(String, primary_key=True)
    customer_id = Column(String, ForeignKey("customers.id"), nullable=False)
    status = Column(String, default="processing")  # processing, shipped, delivered, cancelled
    total = Column(Float, nullable=False)
    shipping_address = Column(Text)
    tracking_number = Column(String)
    carrier = Column(String)
    estimated_delivery = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    notes = Column(Text)
    
    # Relationships
    customer = relationship("Customer", back_populates="orders")
    items = relationship("OrderItem", back_populates="order")
    refunds = relationship("Refund", back_populates="order")
    
    def to_dict(self):
        return {
            "order_id": self.id,
            "customer_id": self.customer_id,
            "status": self.status,
            "total": self.total,
            "items": [item.to_dict() for item in self.items],
            "shipping": {
                "address": self.shipping_address,
                "carrier": self.carrier,
                "tracking_number": self.tracking_number,
                "estimated_delivery": self.estimated_delivery.isoformat() if self.estimated_delivery else None
            },
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "notes": self.notes
        }


class OrderItem(Base):
    """Order item model."""
    __tablename__ = "order_items"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(String, ForeignKey("orders.id"), nullable=False)
    product_id = Column(String, ForeignKey("products.id"), nullable=False)
    product_name = Column(String, nullable=False)
    quantity = Column(Integer, default=1)
    price = Column(Float, nullable=False)
    
    # Relationships
    order = relationship("Order", back_populates="items")
    product = relationship("Product")
    
    def to_dict(self):
        return {
            "product_id": self.product_id,
            "name": self.product_name,
            "quantity": self.quantity,
            "price": self.price,
            "subtotal": self.quantity * self.price
        }


class Product(Base):
    """Product model."""
    __tablename__ = "products"
    
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    price = Column(Float, nullable=False)
    category = Column(String)
    in_stock = Column(Boolean, default=True)
    
    def to_dict(self):
        return {
            "product_id": self.id,
            "name": self.name,
            "description": self.description,
            "price": self.price,
            "category": self.category,
            "in_stock": self.in_stock
        }


class Refund(Base):
    """Refund model."""
    __tablename__ = "refunds"
    
    id = Column(String, primary_key=True)
    order_id = Column(String, ForeignKey("orders.id"), nullable=False)
    amount = Column(Float, nullable=False)
    reason = Column(Text, nullable=False)
    status = Column(String, default="processing")  # processing, completed, failed
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime)
    
    # Relationships
    order = relationship("Order", back_populates="refunds")
    
    def to_dict(self):
        return {
            "refund_id": self.id,
            "order_id": self.order_id,
            "amount": self.amount,
            "reason": self.reason,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class AuditLog(Base):
    """Audit log to track all system transactions."""
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    action = Column(String, nullable=False)  # e.g., "ORDER_CANCELLED", "REFUND_ISSUED"
    entity_type = Column(String, nullable=False)  # e.g., "order", "customer"
    entity_id = Column(String, nullable=False)
    old_value = Column(Text)  # JSON of old state
    new_value = Column(Text)  # JSON of new state
    performed_by = Column(String, default="ai_agent")
    timestamp = Column(DateTime, default=datetime.utcnow)
    notes = Column(Text)
    
    def to_dict(self):
        return {
            "id": self.id,
            "action": self.action,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "performed_by": self.performed_by,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "notes": self.notes
        }


class Discount(Base):
    """Discount/coupon model."""
    __tablename__ = "discounts"
    
    id = Column(String, primary_key=True)
    code = Column(String, unique=True, nullable=False)
    description = Column(String)
    discount_type = Column(String, default="percentage")  # percentage, fixed
    discount_value = Column(Float, nullable=False)  # 10 for 10% or $10
    min_order_value = Column(Float, default=0)
    max_uses = Column(Integer, default=1)
    current_uses = Column(Integer, default=0)
    valid_from = Column(DateTime, default=datetime.utcnow)
    valid_until = Column(DateTime)
    is_active = Column(Boolean, default=True)
    
    def to_dict(self):
        return {
            "discount_id": self.id,
            "code": self.code,
            "description": self.description,
            "discount_type": self.discount_type,
            "discount_value": self.discount_value,
            "min_order_value": self.min_order_value,
            "is_active": self.is_active
        }

