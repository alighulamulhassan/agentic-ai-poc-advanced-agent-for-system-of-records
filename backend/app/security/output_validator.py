"""
Output Validator — validates LLM-generated tool call arguments before execution.

The LLM can hallucinate arguments. For example:
  - refund amount of $99999 for a $50 order
  - cancel_order on a delivered order
  - update_customer_profile with a SQL injection payload

This module sits between the LLM output and the tool executor,
acting as a schema + business-logic firewall.

Session for audience:
  - Knowledge fuel: why LLM outputs can't be trusted, hallucination taxonomy
  - Lab: add domain-specific validation rules for your SoR use case
        (e.g., "refund cannot exceed original order total")
"""
import re
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Validation result
# ---------------------------------------------------------------------------
@dataclass
class ValidationResult:
    is_valid: bool
    tool_name: str
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    sanitized_args: Optional[Dict[str, Any]] = None

    @property
    def summary(self) -> str:
        if self.is_valid:
            return f"✅ {self.tool_name}: valid"
        return f"❌ {self.tool_name}: {'; '.join(self.errors)}"


# ---------------------------------------------------------------------------
# Rule type
# ---------------------------------------------------------------------------
ValidatorFn = Callable[[Dict[str, Any]], Tuple[bool, str]]


@dataclass
class ValidationRule:
    name: str
    applies_to: List[str]  # tool names, or ["*"] for all
    validator: ValidatorFn
    is_hard_block: bool = True  # False → warning only


# ---------------------------------------------------------------------------
# Built-in validation rules
# ---------------------------------------------------------------------------
def _rule_positive_amount(args: Dict) -> Tuple[bool, str]:
    amount = args.get("amount", 0)
    if amount is None:
        return False, "amount is required"
    try:
        if float(amount) <= 0:
            return False, f"amount must be positive, got {amount}"
    except (TypeError, ValueError):
        return False, f"amount must be numeric, got {amount!r}"
    return True, ""


def _rule_refund_reason_required(args: Dict) -> Tuple[bool, str]:
    reason = args.get("reason", "").strip()
    if len(reason) < 5:
        return False, "reason must be at least 5 characters"
    return True, ""


def _rule_valid_order_status(args: Dict) -> Tuple[bool, str]:
    valid = {"processing", "shipped", "delivered", "cancelled", "on_hold", "returned"}
    status = args.get("new_status", "")
    if status not in valid:
        return False, f"invalid status '{status}'. Must be one of {sorted(valid)}"
    return True, ""


def _rule_valid_customer_field(args: Dict) -> Tuple[bool, str]:
    allowed = {"name", "email", "phone", "address"}
    field = args.get("field", "")
    if field not in allowed:
        return False, f"cannot update field '{field}'. Allowed: {sorted(allowed)}"
    return True, ""


def _rule_no_sql_injection(args: Dict) -> Tuple[bool, str]:
    sql_patterns = re.compile(
        r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|TRUNCATE|EXEC|UNION|OR\s+1=1)\b|--|;)",
        re.IGNORECASE,
    )
    for key, val in args.items():
        if isinstance(val, str) and sql_patterns.search(val):
            return False, f"potential SQL injection in argument '{key}'"
    return True, ""


def _rule_address_not_empty(args: Dict) -> Tuple[bool, str]:
    addr = args.get("new_address", "").strip()
    if len(addr) < 10:
        return False, f"address too short to be valid: {addr!r}"
    return True, ""


def _rule_points_positive(args: Dict) -> Tuple[bool, str]:
    points = args.get("points", 0)
    try:
        if int(points) <= 0:
            return False, f"points must be a positive integer, got {points}"
        if int(points) > 100_000:
            return False, f"points value {points} exceeds maximum single grant (100,000)"
    except (TypeError, ValueError):
        return False, f"points must be an integer, got {points!r}"
    return True, ""


def _rule_discount_code_format(args: Dict) -> Tuple[bool, str]:
    code = args.get("discount_code", "")
    if not re.match(r"^[A-Z0-9]{4,20}$", code.upper()):
        return False, f"discount code '{code}' has invalid format (4-20 alphanumeric chars)"
    return True, ""


_SANITISE_STRIP_WHITESPACE = ["order_id", "customer_id", "email", "discount_code"]


# ---------------------------------------------------------------------------
# Rule registry
# ---------------------------------------------------------------------------
_RULES: List[ValidationRule] = [
    # Global rules
    ValidationRule("no_sql_injection", ["*"], _rule_no_sql_injection),
    # Tool-specific rules
    ValidationRule("positive_amount", ["process_refund"], _rule_positive_amount),
    ValidationRule("refund_reason", ["process_refund"], _rule_refund_reason_required),
    ValidationRule("valid_status", ["update_order_status"], _rule_valid_order_status),
    ValidationRule("valid_customer_field", ["update_customer_profile"], _rule_valid_customer_field),
    ValidationRule("address_not_empty", ["update_shipping_address"], _rule_address_not_empty),
    ValidationRule("points_positive", ["add_loyalty_points"], _rule_points_positive),
    ValidationRule("discount_format", ["apply_discount_code"], _rule_discount_code_format),
]


# ---------------------------------------------------------------------------
# OutputValidator class
# ---------------------------------------------------------------------------
class OutputValidator:
    """
    Validates LLM-generated tool call arguments before execution.

    Usage:
        validator = OutputValidator()
        result = validator.validate("process_refund", {"order_id": "ORD-1", "amount": -5})
        if not result.is_valid:
            raise ValueError(result.summary)
    """

    def __init__(self, strict: bool = True):
        """
        Args:
            strict: If True, warnings are treated as errors for write tools.
        """
        self.strict = strict
        self._rules = list(_RULES)

    def add_rule(self, rule: ValidationRule) -> None:
        """Register a custom validation rule."""
        self._rules.append(rule)

    def validate(self, tool_name: str, args: Dict[str, Any]) -> ValidationResult:
        """
        Run all applicable rules against the tool arguments.

        Args:
            tool_name: The LLM-chosen tool name
            args: The LLM-generated arguments dict

        Returns:
            ValidationResult — check .is_valid before calling execute_tool()

        TODO (Lab):
            Add a rule that fetches the current order total from the DB
            and validates that process_refund.amount <= order.total.
            This prevents the LLM from hallucinating a refund larger than
            the original purchase.
        """
        errors: List[str] = []
        warnings: List[str] = []

        # Sanitise common fields first
        sanitized = dict(args)
        for key in _SANITISE_STRIP_WHITESPACE:
            if key in sanitized and isinstance(sanitized[key], str):
                sanitized[key] = sanitized[key].strip()

        # Apply rules
        for rule in self._rules:
            applies = "*" in rule.applies_to or tool_name in rule.applies_to
            if not applies:
                continue

            try:
                ok, msg = rule.validator(sanitized)
            except Exception as exc:
                ok, msg = False, f"rule '{rule.name}' raised an exception: {exc}"

            if not ok:
                if rule.is_hard_block:
                    errors.append(f"[{rule.name}] {msg}")
                else:
                    warnings.append(f"[{rule.name}] {msg}")

        is_valid = len(errors) == 0

        result = ValidationResult(
            is_valid=is_valid,
            tool_name=tool_name,
            errors=errors,
            warnings=warnings,
            sanitized_args=sanitized if is_valid else None,
        )

        if not is_valid:
            logger.warning(f"Tool args validation failed | {result.summary}")
        elif warnings:
            logger.info(f"Tool args validation warnings | {tool_name}: {'; '.join(warnings)}")

        return result


# ---------------------------------------------------------------------------
# Module-level convenience
# ---------------------------------------------------------------------------
_default_validator: Optional[OutputValidator] = None


def validate_tool_args(tool_name: str, args: Dict[str, Any]) -> ValidationResult:
    """Convenience function using the default validator."""
    global _default_validator
    if _default_validator is None:
        _default_validator = OutputValidator(strict=True)
    return _default_validator.validate(tool_name, args)
