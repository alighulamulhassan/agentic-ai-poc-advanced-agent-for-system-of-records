"""
Database operations for the agent tools.
These are the actual implementations that tools call.
All operations are transactional and logged.
"""
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import uuid
import json

from app.db.database import get_db
from app.db.models import Customer, Order, Product, Refund, OrderItem, AuditLog, Discount


def log_action(db, action: str, entity_type: str, entity_id: str, 
               old_value: Any = None, new_value: Any = None, notes: str = None):
    """Log an action to the audit table."""
    audit = AuditLog(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        old_value=json.dumps(old_value) if old_value else None,
        new_value=json.dumps(new_value) if new_value else None,
        performed_by="ai_agent",
        notes=notes
    )
    db.add(audit)


def get_order(order_id: str) -> Dict[str, Any]:
    """Look up an order by ID."""
    with get_db() as db:
        order = db.query(Order).filter(Order.id == order_id).first()
        
        if not order:
            return {
                "error": f"Order {order_id} not found",
                "suggestion": "Please check the order ID and try again. Valid format: ORD-XXXXX"
            }
        
        # Get customer info
        customer = db.query(Customer).filter(Customer.id == order.customer_id).first()
        result = order.to_dict()
        result["customer_name"] = customer.name if customer else "Unknown"
        return result


def get_customer(customer_id: str) -> Dict[str, Any]:
    """Look up a customer by ID."""
    with get_db() as db:
        customer = db.query(Customer).filter(Customer.id == customer_id).first()
        
        if not customer:
            return {
                "error": f"Customer {customer_id} not found",
                "suggestion": "Please check the customer ID and try again"
            }
        
        # Get recent orders
        recent_orders = db.query(Order).filter(
            Order.customer_id == customer_id
        ).order_by(Order.created_at.desc()).limit(5).all()
        
        result = customer.to_dict()
        result["recent_orders"] = [
            {"order_id": o.id, "status": o.status, "total": o.total, "date": o.created_at.isoformat()}
            for o in recent_orders
        ]
        return result


def get_customer_by_email(email: str) -> Dict[str, Any]:
    """Look up a customer by email."""
    with get_db() as db:
        customer = db.query(Customer).filter(Customer.email == email).first()
        
        if not customer:
            return {
                "error": f"No customer found with email {email}",
                "suggestion": "Please verify the email address"
            }
        
        return get_customer(customer.id)


def create_refund(order_id: str, amount: float, reason: str) -> Dict[str, Any]:
    """Process a refund for an order."""
    with get_db() as db:
        order = db.query(Order).filter(Order.id == order_id).first()
        
        if not order:
            return {"error": f"Order {order_id} not found", "success": False}
        
        if order.status == "cancelled":
            return {"error": f"Order {order_id} is already cancelled", "success": False}
        
        if amount > order.total:
            return {
                "error": f"Refund amount ${amount:.2f} exceeds order total ${order.total:.2f}",
                "success": False
            }
        
        # Create refund
        refund_id = f"REF-{uuid.uuid4().hex[:8].upper()}"
        refund = Refund(
            id=refund_id,
            order_id=order_id,
            amount=amount,
            reason=reason,
            status="completed"  # Auto-complete for demo
        )
        db.add(refund)
        
        # Update order notes
        old_notes = order.notes
        order.notes = f"{order.notes or ''}\n[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Refund {refund_id}: ${amount:.2f} - {reason}"
        
        # Log the transaction
        log_action(db, "REFUND_ISSUED", "order", order_id,
                   old_value={"total": order.total},
                   new_value={"refund_amount": amount, "refund_id": refund_id},
                   notes=reason)
        
        # Add loyalty points as goodwill (10 points per $1 refunded)
        customer = db.query(Customer).filter(Customer.id == order.customer_id).first()
        if customer:
            bonus_points = int(amount * 10)
            customer.loyalty_points += bonus_points
        
        return {
            "success": True,
            "refund_id": refund_id,
            "order_id": order_id,
            "amount": amount,
            "status": "completed",
            "bonus_loyalty_points": bonus_points if customer else 0,
            "message": f"✅ Refund of ${amount:.2f} has been processed successfully. {bonus_points} bonus loyalty points added."
        }


def update_order(order_id: str, new_status: str, notes: str = "") -> Dict[str, Any]:
    """Update an order's status."""
    valid_statuses = ["processing", "shipped", "delivered", "cancelled", "on_hold", "returned"]
    
    if new_status not in valid_statuses:
        return {
            "error": f"Invalid status '{new_status}'. Must be one of: {', '.join(valid_statuses)}",
            "success": False
        }
    
    with get_db() as db:
        order = db.query(Order).filter(Order.id == order_id).first()
        
        if not order:
            return {"error": f"Order {order_id} not found", "success": False}
        
        old_status = order.status
        
        # Business logic checks
        if old_status == "delivered" and new_status == "cancelled":
            return {
                "error": "Cannot cancel a delivered order. Please process a return instead.",
                "success": False,
                "suggestion": "Use the return process for delivered orders"
            }
        
        order.status = new_status
        order.updated_at = datetime.utcnow()
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
        order.notes = f"{order.notes or ''}\n[{timestamp}] Status: {old_status} → {new_status}. {notes}"
        
        # Log the transaction
        log_action(db, f"ORDER_{new_status.upper()}", "order", order_id,
                   old_value={"status": old_status},
                   new_value={"status": new_status},
                   notes=notes)
        
        # If cancelled, consider auto-refund
        refund_info = None
        if new_status == "cancelled" and old_status in ["processing", "on_hold"]:
            refund_id = f"REF-{uuid.uuid4().hex[:8].upper()}"
            refund = Refund(
                id=refund_id,
                order_id=order_id,
                amount=order.total,
                reason="Order cancelled - automatic refund",
                status="completed"
            )
            db.add(refund)
            refund_info = {"refund_id": refund_id, "amount": order.total}
        
        return {
            "success": True,
            "order_id": order_id,
            "old_status": old_status,
            "new_status": new_status,
            "refund": refund_info,
            "message": f"✅ Order {order_id} status updated from '{old_status}' to '{new_status}'" + 
                      (f". Automatic refund of ${order.total:.2f} issued." if refund_info else "")
        }


def update_shipping_address(order_id: str, new_address: str) -> Dict[str, Any]:
    """Update the shipping address for an order."""
    with get_db() as db:
        order = db.query(Order).filter(Order.id == order_id).first()
        
        if not order:
            return {"error": f"Order {order_id} not found", "success": False}
        
        if order.status in ["shipped", "delivered"]:
            return {
                "error": f"Cannot update address - order is already {order.status}",
                "success": False,
                "suggestion": "Contact shipping carrier directly for address changes on shipped orders"
            }
        
        old_address = order.shipping_address
        order.shipping_address = new_address
        order.updated_at = datetime.utcnow()
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
        order.notes = f"{order.notes or ''}\n[{timestamp}] Shipping address updated"
        
        log_action(db, "ADDRESS_UPDATED", "order", order_id,
                   old_value={"address": old_address},
                   new_value={"address": new_address})
        
        return {
            "success": True,
            "order_id": order_id,
            "old_address": old_address,
            "new_address": new_address,
            "message": f"✅ Shipping address updated successfully for order {order_id}"
        }


def apply_discount(order_id: str, discount_code: str) -> Dict[str, Any]:
    """Apply a discount code to an order."""
    with get_db() as db:
        order = db.query(Order).filter(Order.id == order_id).first()
        
        if not order:
            return {"error": f"Order {order_id} not found", "success": False}
        
        if order.status != "processing":
            return {
                "error": f"Cannot apply discount - order status is '{order.status}'",
                "success": False,
                "suggestion": "Discounts can only be applied to orders in 'processing' status"
            }
        
        discount = db.query(Discount).filter(
            Discount.code == discount_code.upper(),
            Discount.is_active == True
        ).first()
        
        if not discount:
            return {
                "error": f"Discount code '{discount_code}' is invalid or expired",
                "success": False
            }
        
        if order.total < discount.min_order_value:
            return {
                "error": f"Order total ${order.total:.2f} is below minimum ${discount.min_order_value:.2f}",
                "success": False
            }
        
        # Calculate discount
        old_total = order.total
        if discount.discount_type == "percentage":
            discount_amount = order.total * (discount.discount_value / 100)
        else:
            discount_amount = min(discount.discount_value, order.total)
        
        order.total = order.total - discount_amount
        order.updated_at = datetime.utcnow()
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
        order.notes = f"{order.notes or ''}\n[{timestamp}] Discount {discount_code}: -${discount_amount:.2f}"
        
        discount.current_uses += 1
        
        log_action(db, "DISCOUNT_APPLIED", "order", order_id,
                   old_value={"total": old_total},
                   new_value={"total": order.total, "discount": discount_amount, "code": discount_code})
        
        return {
            "success": True,
            "order_id": order_id,
            "discount_code": discount_code,
            "discount_amount": discount_amount,
            "original_total": old_total,
            "new_total": order.total,
            "message": f"✅ Discount applied! Saved ${discount_amount:.2f}. New total: ${order.total:.2f}"
        }


def add_loyalty_points(customer_id: str, points: int, reason: str) -> Dict[str, Any]:
    """Add loyalty points to a customer's account."""
    with get_db() as db:
        customer = db.query(Customer).filter(Customer.id == customer_id).first()
        
        if not customer:
            return {"error": f"Customer {customer_id} not found", "success": False}
        
        old_points = customer.loyalty_points
        customer.loyalty_points += points
        new_points = customer.loyalty_points
        
        # Check for tier upgrade
        old_tier = customer.membership_tier
        if new_points >= 10000:
            customer.membership_tier = "platinum"
        elif new_points >= 5000:
            customer.membership_tier = "gold"
        elif new_points >= 1000:
            customer.membership_tier = "silver"
        
        tier_upgraded = customer.membership_tier != old_tier
        
        log_action(db, "LOYALTY_POINTS_ADDED", "customer", customer_id,
                   old_value={"points": old_points, "tier": old_tier},
                   new_value={"points": new_points, "tier": customer.membership_tier},
                   notes=reason)
        
        return {
            "success": True,
            "customer_id": customer_id,
            "points_added": points,
            "new_balance": new_points,
            "tier": customer.membership_tier,
            "tier_upgraded": tier_upgraded,
            "message": f"✅ Added {points} loyalty points. New balance: {new_points} points." +
                      (f" Congratulations! Upgraded to {customer.membership_tier} tier!" if tier_upgraded else "")
        }


def update_customer_info(customer_id: str, field: str, value: str) -> Dict[str, Any]:
    """Update a customer's information."""
    allowed_fields = ["name", "email", "phone", "address"]
    
    if field not in allowed_fields:
        return {
            "error": f"Cannot update field '{field}'. Allowed fields: {', '.join(allowed_fields)}",
            "success": False
        }
    
    with get_db() as db:
        customer = db.query(Customer).filter(Customer.id == customer_id).first()
        
        if not customer:
            return {"error": f"Customer {customer_id} not found", "success": False}
        
        old_value = getattr(customer, field)
        setattr(customer, field, value)
        
        log_action(db, "CUSTOMER_UPDATED", "customer", customer_id,
                   old_value={field: old_value},
                   new_value={field: value})
        
        return {
            "success": True,
            "customer_id": customer_id,
            "field": field,
            "old_value": old_value,
            "new_value": value,
            "message": f"✅ Customer {field} updated successfully"
        }


def expedite_shipping(order_id: str) -> Dict[str, Any]:
    """Upgrade shipping to express/expedited."""
    with get_db() as db:
        order = db.query(Order).filter(Order.id == order_id).first()
        
        if not order:
            return {"error": f"Order {order_id} not found", "success": False}
        
        if order.status not in ["processing", "on_hold"]:
            return {
                "error": f"Cannot expedite - order is already {order.status}",
                "success": False
            }
        
        old_carrier = order.carrier
        old_delivery = order.estimated_delivery
        
        order.carrier = "Express Shipping"
        order.estimated_delivery = datetime.utcnow() + timedelta(days=2)
        order.updated_at = datetime.utcnow()
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
        order.notes = f"{order.notes or ''}\n[{timestamp}] Shipping expedited - complimentary upgrade"
        
        log_action(db, "SHIPPING_EXPEDITED", "order", order_id,
                   old_value={"carrier": old_carrier},
                   new_value={"carrier": "Express Shipping"})
        
        return {
            "success": True,
            "order_id": order_id,
            "new_carrier": "Express Shipping",
            "estimated_delivery": order.estimated_delivery.strftime('%Y-%m-%d'),
            "message": f"✅ Shipping expedited! Order will arrive by {order.estimated_delivery.strftime('%B %d, %Y')}"
        }


def search_products(query: str) -> Dict[str, Any]:
    """Search products by name or description."""
    with get_db() as db:
        products = db.query(Product).filter(
            Product.name.ilike(f"%{query}%") | 
            Product.description.ilike(f"%{query}%") |
            Product.category.ilike(f"%{query}%")
        ).limit(10).all()
        
        return {
            "results": [p.to_dict() for p in products],
            "count": len(products)
        }


def get_order_history(customer_id: str, limit: int = 10) -> Dict[str, Any]:
    """Get order history for a customer."""
    with get_db() as db:
        customer = db.query(Customer).filter(Customer.id == customer_id).first()
        
        if not customer:
            return {"error": f"Customer {customer_id} not found", "success": False}
        
        orders = db.query(Order).filter(
            Order.customer_id == customer_id
        ).order_by(Order.created_at.desc()).limit(limit).all()
        
        return {
            "customer_id": customer_id,
            "customer_name": customer.name,
            "total_orders": len(orders),
            "orders": [o.to_dict() for o in orders]
        }


def get_audit_log(entity_type: str = None, entity_id: str = None, limit: int = 20) -> List[Dict]:
    """Get audit log entries."""
    with get_db() as db:
        query = db.query(AuditLog)
        
        if entity_type:
            query = query.filter(AuditLog.entity_type == entity_type)
        if entity_id:
            query = query.filter(AuditLog.entity_id == entity_id)
        
        logs = query.order_by(AuditLog.timestamp.desc()).limit(limit).all()
        
        return [log.to_dict() for log in logs]
