"""
Tool registry - defines all available tools for the agent.
Tools are defined using LangChain's @tool decorator.
These tools enable the agent to perform real transactions on the database.
"""
from typing import List, Dict, Any
from langchain_core.tools import tool


@tool
def lookup_order(order_id: str) -> Dict[str, Any]:
    """
    Look up an order by its ID to get status, items, tracking, and shipping info.
    Use this when a customer asks about their order status or tracking.
    
    Args:
        order_id: The order ID to look up (e.g., "ORD-10001")
    
    Returns:
        Order details including status, items, and shipping information
    """
    from app.db.operations import get_order
    return get_order(order_id)


@tool  
def search_documents(query: str) -> Dict[str, Any]:
    """
    Search product documentation, FAQs, policies, and knowledge base.
    Use this when you need to find information about products, return policies,
    shipping info, or answer general questions.
    
    Args:
        query: The search query describing what information you need
    
    Returns:
        Relevant document excerpts with sources
    """
    from app.rag.retriever import search
    return search(query)


@tool
def get_customer_info(customer_id: str) -> Dict[str, Any]:
    """
    Look up customer information by their ID.
    Use this to get customer details like name, email, loyalty points, and order history.
    
    Args:
        customer_id: The customer ID to look up (e.g., "CUST-1001")
    
    Returns:
        Customer details including name, email, loyalty points, and recent orders
    """
    from app.db.operations import get_customer
    return get_customer(customer_id)


@tool
def find_customer_by_email(email: str) -> Dict[str, Any]:
    """
    Find a customer by their email address.
    Use this when you need to look up a customer but only have their email.
    
    Args:
        email: The customer's email address
    
    Returns:
        Customer details if found
    """
    from app.db.operations import get_customer_by_email
    return get_customer_by_email(email)


@tool
def process_refund(order_id: str, amount: float, reason: str) -> Dict[str, Any]:
    """
    Process a refund for an order. This is a TRANSACTION that modifies the database.
    ALWAYS confirm with the customer before using this tool.
    
    Args:
        order_id: The order ID to refund
        amount: The refund amount in dollars (must not exceed order total)
        reason: The reason for the refund
    
    Returns:
        Refund confirmation with refund ID, status, and any bonus loyalty points added
    """
    from app.db.operations import create_refund
    return create_refund(order_id, amount, reason)


@tool
def cancel_order(order_id: str, reason: str) -> Dict[str, Any]:
    """
    Cancel an order. This is a TRANSACTION that modifies the database.
    This will automatically process a refund for orders that haven't shipped yet.
    ALWAYS confirm with the customer before cancelling.
    
    Args:
        order_id: The order ID to cancel
        reason: The reason for cancellation
    
    Returns:
        Confirmation of cancellation and any automatic refund issued
    """
    from app.db.operations import update_order
    return update_order(order_id, "cancelled", reason)


@tool
def update_order_status(order_id: str, new_status: str, notes: str = "") -> Dict[str, Any]:
    """
    Update the status of an order. This is a TRANSACTION that modifies the database.
    Valid statuses: processing, shipped, delivered, cancelled, on_hold, returned
    
    Args:
        order_id: The order ID to update
        new_status: New status value
        notes: Optional notes about the status change
    
    Returns:
        Confirmation of the status update
    """
    from app.db.operations import update_order
    return update_order(order_id, new_status, notes)


@tool
def update_shipping_address(order_id: str, new_address: str) -> Dict[str, Any]:
    """
    Update the shipping address for an order. This is a TRANSACTION.
    Can only be done for orders that haven't shipped yet.
    
    Args:
        order_id: The order ID to update
        new_address: The new shipping address (full address as a string)
    
    Returns:
        Confirmation of the address update
    """
    from app.db.operations import update_shipping_address
    return update_shipping_address(order_id, new_address)


@tool
def apply_discount_code(order_id: str, discount_code: str) -> Dict[str, Any]:
    """
    Apply a discount/coupon code to an order. This is a TRANSACTION.
    Can only be applied to orders in 'processing' status.
    
    Args:
        order_id: The order ID to apply discount to
        discount_code: The discount/coupon code (e.g., "SAVE20", "WELCOME10")
    
    Returns:
        Discount details including amount saved and new total
    """
    from app.db.operations import apply_discount
    return apply_discount(order_id, discount_code)


@tool
def add_loyalty_points(customer_id: str, points: int, reason: str) -> Dict[str, Any]:
    """
    Add loyalty points to a customer's account. This is a TRANSACTION.
    Use this for goodwill gestures or compensation.
    May trigger a membership tier upgrade.
    
    Args:
        customer_id: The customer ID
        points: Number of points to add
        reason: Reason for adding points
    
    Returns:
        New point balance and any tier upgrades
    """
    from app.db.operations import add_loyalty_points
    return add_loyalty_points(customer_id, points, reason)


@tool
def update_customer_profile(customer_id: str, field: str, new_value: str) -> Dict[str, Any]:
    """
    Update a customer's profile information. This is a TRANSACTION.
    Can update: name, email, phone, address
    
    Args:
        customer_id: The customer ID
        field: Field to update (name, email, phone, or address)
        new_value: New value for the field
    
    Returns:
        Confirmation of the update
    """
    from app.db.operations import update_customer_info
    return update_customer_info(customer_id, field, new_value)


@tool
def expedite_order_shipping(order_id: str) -> Dict[str, Any]:
    """
    Upgrade an order to express/expedited shipping at no extra cost.
    This is a TRANSACTION. Use as a goodwill gesture for customer issues.
    
    Args:
        order_id: The order ID to expedite
    
    Returns:
        New shipping details with updated delivery estimate
    """
    from app.db.operations import expedite_shipping
    return expedite_shipping(order_id)


@tool
def search_products(query: str) -> Dict[str, Any]:
    """
    Search for products in the catalog by name, description, or category.
    
    Args:
        query: Search query (e.g., "wireless headphones", "electronics")
    
    Returns:
        List of matching products with details
    """
    from app.db.operations import search_products
    return search_products(query)


@tool
def get_customer_order_history(customer_id: str) -> Dict[str, Any]:
    """
    Get the complete order history for a customer.
    
    Args:
        customer_id: The customer ID
    
    Returns:
        List of all orders with details
    """
    from app.db.operations import get_order_history
    return get_order_history(customer_id)


# List of all tools
ALL_TOOLS = [
    lookup_order,
    search_documents,
    get_customer_info,
    find_customer_by_email,
    process_refund,
    cancel_order,
    update_order_status,
    update_shipping_address,
    apply_discount_code,
    add_loyalty_points,
    update_customer_profile,
    expedite_order_shipping,
    search_products,
    get_customer_order_history,
]


def get_tools() -> List:
    """Get all registered tools."""
    return ALL_TOOLS


def get_tool_schemas() -> List[Dict]:
    """Get tool schemas in the format expected by LLMs."""
    return ALL_TOOLS


def get_tool_descriptions() -> str:
    """Get a formatted string of all tool descriptions for the system prompt."""
    descriptions = []
    for tool in ALL_TOOLS:
        descriptions.append(f"- **{tool.name}**: {tool.description.split(chr(10))[0]}")
    return "\n".join(descriptions)
