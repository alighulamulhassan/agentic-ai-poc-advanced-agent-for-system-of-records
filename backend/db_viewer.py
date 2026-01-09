#!/usr/bin/env python3
"""Simple CLI database viewer - run with: python db_viewer.py"""
from app.db.database import get_db
from app.db.models import Customer, Order, Refund, AuditLog, Discount

def view_all():
    with get_db() as db:
        print("\n" + "="*70)
        print("📊 DATABASE VIEWER")
        print("="*70)
        
        # Customers
        print("\n👤 CUSTOMERS:")
        print("-"*70)
        for c in db.query(Customer).all():
            print(f"  {c.id}: {c.name} | {c.membership_tier} | {c.loyalty_points} pts | {c.email}")
        
        # Orders
        print("\n📦 ORDERS:")
        print("-"*70)
        for o in db.query(Order).all():
            items = ", ".join([i.product_name[:20] for i in o.items])
            print(f"  {o.id}: {o.status:12} | ${o.total:>8.2f} | {o.customer_id} | {items[:40]}")
        
        # Refunds
        refunds = db.query(Refund).all()
        if refunds:
            print("\n💰 REFUNDS:")
            print("-"*70)
            for r in refunds:
                print(f"  {r.id}: {r.order_id} | ${r.amount:.2f} | {r.status} | {r.reason[:30]}")
        
        # Discounts
        print("\n🏷️  DISCOUNTS:")
        print("-"*70)
        for d in db.query(Discount).all():
            print(f"  {d.code}: {d.discount_value}{'%' if d.discount_type=='percentage' else '$'} off | uses: {d.current_uses}/{d.max_uses}")
        
        # Audit Log
        logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(10).all()
        if logs:
            print("\n📝 AUDIT LOG (last 10):")
            print("-"*70)
            for l in logs:
                print(f"  [{l.timestamp.strftime('%H:%M:%S')}] {l.action}: {l.entity_type}#{l.entity_id}")
        
        print("\n" + "="*70 + "\n")

if __name__ == "__main__":
    view_all()



