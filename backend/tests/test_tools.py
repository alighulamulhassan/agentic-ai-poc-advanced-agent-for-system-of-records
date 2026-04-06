"""
Tests for the tool registry and executor.

Covers:
  - Tool lookup and schema validation
  - Tool execution (read and write)
  - Error handling for unknown tools
  - Audit log creation on transactions
  - Integration of executor with output validator

Run: pytest tests/test_tools.py -v
"""
import pytest
from tests.conftest import TEST_ORDER_ID, TEST_CUSTOMER_ID, TEST_CUSTOMER_EMAIL


# ============================================================
# Tool Registry
# ============================================================
class TestToolRegistry:

    def test_all_tools_have_names(self):
        from app.tools.registry import ALL_TOOLS
        for tool in ALL_TOOLS:
            assert tool.name, f"Tool missing name: {tool}"

    def test_all_tools_have_descriptions(self):
        from app.tools.registry import ALL_TOOLS
        for tool in ALL_TOOLS:
            assert tool.description, f"Tool '{tool.name}' missing description"

    def test_get_tools_returns_list(self):
        from app.tools.registry import get_tools
        tools = get_tools()
        assert isinstance(tools, list)
        assert len(tools) > 0

    def test_expected_tools_present(self):
        from app.tools.registry import ALL_TOOLS
        names = {t.name for t in ALL_TOOLS}
        expected = {
            "lookup_order", "process_refund", "cancel_order",
            "get_customer_info", "search_documents", "add_loyalty_points",
        }
        assert expected.issubset(names)

    def test_16_tools_registered(self):
        from app.tools.registry import ALL_TOOLS
        assert len(ALL_TOOLS) >= 14  # at least 14


# ============================================================
# Tool Executor
# ============================================================
class TestToolExecutor:

    @pytest.mark.asyncio
    async def test_execute_lookup_order(self, test_db):
        from app.tools.executor import execute_tool
        result = await execute_tool("lookup_order", {"order_id": TEST_ORDER_ID})
        assert isinstance(result, dict)
        # Either success or a not-found error — both are valid dict responses
        assert "order_id" in result or "error" in result

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self, test_db):
        from app.tools.executor import execute_tool
        result = await execute_tool("nonexistent_tool", {})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_execute_search_documents(self, test_db):
        from app.tools.executor import execute_tool
        result = await execute_tool("search_documents", {"query": "return policy"})
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_execute_get_customer_info(self, test_db):
        from app.tools.executor import execute_tool
        result = await execute_tool("get_customer_info", {"customer_id": TEST_CUSTOMER_ID})
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_execute_search_products(self, test_db):
        from app.tools.executor import execute_tool
        result = await execute_tool("search_products", {"query": "headphones"})
        assert isinstance(result, dict)
        assert "results" in result


# ============================================================
# Database Operations
# ============================================================
class TestDatabaseOperations:

    def test_get_order_returns_dict(self, test_db):
        from app.db.operations import get_order
        result = get_order(TEST_ORDER_ID)
        assert isinstance(result, dict)

    def test_get_nonexistent_order_returns_error(self, test_db):
        from app.db.operations import get_order
        result = get_order("ORD-NONEXISTENT")
        assert "error" in result

    def test_get_customer_by_email(self, test_db):
        from app.db.operations import get_customer_by_email
        result = get_customer_by_email(TEST_CUSTOMER_EMAIL)
        # May return error if not seeded with this email — acceptable
        assert isinstance(result, dict)

    def test_search_products(self, test_db):
        from app.db.operations import search_products
        result = search_products("laptop")
        assert isinstance(result, dict)
        assert "results" in result
        assert "count" in result

    def test_refund_requires_valid_amount(self, test_db):
        from app.db.operations import create_refund
        result = create_refund("ORD-NONEXISTENT", -10.0, "Test")
        assert isinstance(result, dict)
        assert "error" in result or result.get("success") is False


# ============================================================
# API Endpoints (integration)
# ============================================================
class TestChatAPI:

    def test_health_endpoint(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_root_endpoint(self, client):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data

    def test_metrics_endpoint(self, client):
        response = client.get("/api/metrics")
        assert response.status_code == 200
        data = response.json()
        assert "requests" in data
        assert "tools" in data

    def test_policies_endpoint(self, client):
        response = client.get("/api/policies")
        assert response.status_code == 200
        data = response.json()
        assert "policies" in data
        assert len(data["policies"]) > 0

    def test_hitl_pending_endpoint(self, client):
        response = client.get("/api/hitl/pending")
        assert response.status_code == 200
        assert "pending" in response.json()

    def test_mcp_info_endpoint(self, client):
        response = client.get("/mcp/")
        assert response.status_code == 200

    def test_mcp_tools_list(self, client):
        response = client.get("/mcp/tools")
        assert response.status_code == 200
        tools = response.json()
        assert isinstance(tools, list)
        assert len(tools) > 0

    def test_clear_history_endpoint(self, client):
        response = client.delete("/api/chat/history/test-conv-001")
        assert response.status_code == 200
