"""
Database seeding script - creates sample e-commerce data.
Run this to populate the database with demo data for testing transactions.
"""
from datetime import datetime, timedelta
import random

from app.db.database import init_db, get_db
from app.db.models import Customer, Order, OrderItem, Product, Refund, Discount


def seed_products():
    """Create sample products."""
    products = [
        Product(
            id="PROD-001",
            name="Wireless Noise-Canceling Headphones",
            description="Premium over-ear headphones with active noise cancellation, 30-hour battery life, and premium sound quality.",
            price=249.99,
            category="Electronics",
            in_stock=True
        ),
        Product(
            id="PROD-002",
            name="Smart Fitness Watch",
            description="Track your health with heart rate monitoring, GPS, sleep tracking, and 7-day battery life.",
            price=199.99,
            category="Electronics",
            in_stock=True
        ),
        Product(
            id="PROD-003",
            name="Portable Bluetooth Speaker",
            description="Waterproof speaker with 360° sound, 20-hour playtime, and built-in microphone.",
            price=79.99,
            category="Electronics",
            in_stock=True
        ),
        Product(
            id="PROD-004",
            name="Ergonomic Office Chair",
            description="Adjustable lumbar support, breathable mesh back, and armrests. Perfect for long work sessions.",
            price=349.99,
            category="Furniture",
            in_stock=True
        ),
        Product(
            id="PROD-005",
            name="Mechanical Gaming Keyboard",
            description="RGB backlit keys, Cherry MX switches, programmable macros, and aluminum frame.",
            price=149.99,
            category="Electronics",
            in_stock=False
        ),
        Product(
            id="PROD-006",
            name="Wireless Charging Pad",
            description="Fast 15W wireless charging for phones and earbuds. Slim design with LED indicator.",
            price=29.99,
            category="Accessories",
            in_stock=True
        ),
        Product(
            id="PROD-007",
            name="Premium Coffee Maker",
            description="12-cup programmable coffee maker with thermal carafe and strength control.",
            price=129.99,
            category="Kitchen",
            in_stock=True
        ),
        Product(
            id="PROD-008",
            name="4K Webcam",
            description="Ultra HD webcam with autofocus, built-in microphone, and privacy cover.",
            price=99.99,
            category="Electronics",
            in_stock=True
        ),
        Product(
            id="PROD-009",
            name="Standing Desk Converter",
            description="Adjustable height desk converter. Fits monitors up to 32 inches. Easy assembly.",
            price=279.99,
            category="Furniture",
            in_stock=True
        ),
        Product(
            id="PROD-010",
            name="Wireless Mouse",
            description="Ergonomic wireless mouse with programmable buttons and long battery life.",
            price=49.99,
            category="Electronics",
            in_stock=True
        ),
    ]
    return products


def seed_customers():
    """Create sample customers with varied profiles."""
    customers = [
        Customer(
            id="CUST-1001",
            name="John Smith",
            email="john.smith@email.com",
            phone="+1-555-0101",
            address="123 Oak Avenue, San Francisco, CA 94102",
            loyalty_points=2500,
            membership_tier="silver",
            created_at=datetime.now() - timedelta(days=365)
        ),
        Customer(
            id="CUST-1002",
            name="Sarah Johnson",
            email="sarah.j@email.com",
            phone="+1-555-0102",
            address="456 Pine Street, Seattle, WA 98101",
            loyalty_points=8500,
            membership_tier="gold",
            created_at=datetime.now() - timedelta(days=180)
        ),
        Customer(
            id="CUST-1003",
            name="Michael Chen",
            email="m.chen@email.com",
            phone="+1-555-0103",
            address="789 Maple Drive, Austin, TX 78701",
            loyalty_points=500,
            membership_tier="bronze",
            created_at=datetime.now() - timedelta(days=90)
        ),
        Customer(
            id="CUST-1004",
            name="Emily Davis",
            email="emily.d@email.com",
            phone="+1-555-0104",
            address="321 Cedar Lane, Boston, MA 02101",
            loyalty_points=12000,
            membership_tier="platinum",
            created_at=datetime.now() - timedelta(days=400)
        ),
        Customer(
            id="CUST-1005",
            name="Robert Wilson",
            email="r.wilson@email.com",
            phone="+1-555-0105",
            address="654 Birch Road, Denver, CO 80201",
            loyalty_points=100,
            membership_tier="bronze",
            created_at=datetime.now() - timedelta(days=7)
        ),
        Customer(
            id="CUST-1006",
            name="Jennifer Martinez",
            email="j.martinez@email.com",
            phone="+1-555-0106",
            address="987 Elm Street, Chicago, IL 60601",
            loyalty_points=4500,
            membership_tier="silver",
            created_at=datetime.now() - timedelta(days=200)
        ),
    ]
    return customers


def seed_discounts():
    """Create sample discount codes."""
    discounts = [
        Discount(
            id="DISC-001",
            code="WELCOME10",
            description="10% off for new customers",
            discount_type="percentage",
            discount_value=10,
            min_order_value=50,
            max_uses=100,
            current_uses=45,
            is_active=True
        ),
        Discount(
            id="DISC-002",
            code="SAVE20",
            description="$20 off orders over $100",
            discount_type="fixed",
            discount_value=20,
            min_order_value=100,
            max_uses=50,
            current_uses=12,
            is_active=True
        ),
        Discount(
            id="DISC-003",
            code="VIP25",
            description="25% off for VIP customers",
            discount_type="percentage",
            discount_value=25,
            min_order_value=0,
            max_uses=20,
            current_uses=5,
            is_active=True
        ),
        Discount(
            id="DISC-004",
            code="FREESHIP",
            description="Free shipping (simulated as $15 off)",
            discount_type="fixed",
            discount_value=15,
            min_order_value=75,
            max_uses=200,
            current_uses=89,
            is_active=True
        ),
        Discount(
            id="DISC-005",
            code="HOLIDAY30",
            description="30% holiday special",
            discount_type="percentage",
            discount_value=30,
            min_order_value=150,
            max_uses=100,
            current_uses=0,
            is_active=True
        ),
    ]
    return discounts


def seed_orders(customers, products):
    """Create sample orders with various statuses for testing."""
    carriers = ["FedEx", "UPS", "USPS", "DHL"]
    
    orders = []
    order_items = []
    
    order_data = [
        # John Smith's orders - CUST-1001
        {
            "id": "ORD-10001",
            "customer_id": "CUST-1001",
            "status": "delivered",
            "products": ["PROD-001"],
            "days_ago": 30,
            "address": "123 Oak Avenue, San Francisco, CA 94102"
        },
        {
            "id": "ORD-10002",
            "customer_id": "CUST-1001",
            "status": "shipped",
            "products": ["PROD-003", "PROD-006"],
            "days_ago": 3,
            "address": "123 Oak Avenue, San Francisco, CA 94102"
        },
        # Sarah Johnson's orders - CUST-1002 (Gold member with issues)
        {
            "id": "ORD-10003",
            "customer_id": "CUST-1002",
            "status": "processing",
            "products": ["PROD-002", "PROD-010"],
            "days_ago": 1,
            "address": "456 Pine Street, Seattle, WA 98101",
            "notes": "Customer requested gift wrapping"
        },
        {
            "id": "ORD-10004",
            "customer_id": "CUST-1002",
            "status": "on_hold",
            "products": ["PROD-004"],
            "days_ago": 5,
            "address": "456 Pine Street, Seattle, WA 98101",
            "notes": "Payment verification needed"
        },
        # Michael Chen's orders - CUST-1003
        {
            "id": "ORD-10005",
            "customer_id": "CUST-1003",
            "status": "delivered",
            "products": ["PROD-004"],
            "days_ago": 45,
            "address": "789 Maple Drive, Austin, TX 78701"
        },
        {
            "id": "ORD-10006",
            "customer_id": "CUST-1003",
            "status": "shipped",
            "products": ["PROD-007", "PROD-008"],
            "days_ago": 2,
            "address": "789 Maple Drive, Austin, TX 78701"
        },
        # Emily Davis's orders - CUST-1004 (Platinum member)
        {
            "id": "ORD-10007",
            "customer_id": "CUST-1004",
            "status": "processing",
            "products": ["PROD-001", "PROD-002"],
            "days_ago": 0,
            "address": "321 Cedar Lane, Boston, MA 02101"
        },
        {
            "id": "ORD-10008",
            "customer_id": "CUST-1004",
            "status": "delivered",
            "products": ["PROD-009"],
            "days_ago": 60,
            "address": "321 Cedar Lane, Boston, MA 02101"
        },
        # Robert Wilson's order - CUST-1005 (New customer, processing)
        {
            "id": "ORD-10009",
            "customer_id": "CUST-1005",
            "status": "processing",
            "products": ["PROD-005", "PROD-006"],
            "days_ago": 0,
            "address": "654 Birch Road, Denver, CO 80201",
            "notes": "First order - new customer"
        },
        # Jennifer Martinez's orders - CUST-1006
        {
            "id": "ORD-10010",
            "customer_id": "CUST-1006",
            "status": "processing",
            "products": ["PROD-001", "PROD-003", "PROD-006"],
            "days_ago": 1,
            "address": "987 Elm Street, Chicago, IL 60601"
        },
        {
            "id": "ORD-10011",
            "customer_id": "CUST-1006",
            "status": "delivered",
            "products": ["PROD-007"],
            "days_ago": 20,
            "address": "987 Elm Street, Chicago, IL 60601",
            "notes": "Delivered successfully"
        },
    ]
    
    product_map = {p.id: p for p in products}
    
    for od in order_data:
        # Calculate total
        total = sum(product_map[pid].price for pid in od["products"])
        
        # Create order
        created = datetime.now() - timedelta(days=od["days_ago"])
        order = Order(
            id=od["id"],
            customer_id=od["customer_id"],
            status=od["status"],
            total=total,
            shipping_address=od["address"],
            carrier=random.choice(carriers),
            tracking_number=f"TRK{random.randint(100000000, 999999999)}",
            estimated_delivery=created + timedelta(days=5),
            created_at=created,
            updated_at=created,
            notes=od.get("notes", "")
        )
        orders.append(order)
        
        # Create order items
        for pid in od["products"]:
            product = product_map[pid]
            item = OrderItem(
                order_id=od["id"],
                product_id=pid,
                product_name=product.name,
                quantity=1,
                price=product.price
            )
            order_items.append(item)
    
    return orders, order_items


def seed_database():
    """Seed the entire database with sample data."""
    print("🌱 Seeding database...")
    
    # Initialize database
    init_db()
    
    with get_db() as db:
        # Check if already seeded
        existing = db.query(Product).first()
        if existing:
            print("⚠️ Database already contains data. Skipping seed.")
            return
        
        # Create products
        products = seed_products()
        for p in products:
            db.add(p)
        print(f"  ✅ Created {len(products)} products")
        
        # Create customers
        customers = seed_customers()
        for c in customers:
            db.add(c)
        print(f"  ✅ Created {len(customers)} customers")
        
        # Create discounts
        discounts = seed_discounts()
        for d in discounts:
            db.add(d)
        print(f"  ✅ Created {len(discounts)} discount codes")
        
        # Create orders
        orders, order_items = seed_orders(customers, products)
        for o in orders:
            db.add(o)
        for oi in order_items:
            db.add(oi)
        print(f"  ✅ Created {len(orders)} orders with {len(order_items)} items")
    
    print("🎉 Database seeded successfully!")
    print("\n📋 Test Data Summary:")
    print("=" * 50)
    print("CUSTOMERS:")
    print("  CUST-1001 - John Smith (Silver, 2500 pts)")
    print("  CUST-1002 - Sarah Johnson (Gold, 8500 pts)")  
    print("  CUST-1003 - Michael Chen (Bronze, 500 pts)")
    print("  CUST-1004 - Emily Davis (Platinum, 12000 pts)")
    print("  CUST-1005 - Robert Wilson (Bronze, new customer)")
    print("  CUST-1006 - Jennifer Martinez (Silver, 4500 pts)")
    print("\nORDERS:")
    print("  ORD-10003 - Processing (good for testing changes)")
    print("  ORD-10004 - On Hold (payment verification)")
    print("  ORD-10007 - Processing (Platinum customer)")
    print("  ORD-10009 - Processing (new customer, has out-of-stock item)")
    print("  ORD-10010 - Processing (multiple items)")
    print("\nDISCOUNT CODES:")
    print("  WELCOME10 - 10% off (min $50)")
    print("  SAVE20 - $20 off (min $100)")
    print("  VIP25 - 25% off (VIP)")
    print("  FREESHIP - $15 off (min $75)")
    print("  HOLIDAY30 - 30% off (min $150)")
    print("=" * 50)


if __name__ == "__main__":
    seed_database()
