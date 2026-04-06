"""
PII Detection & Masking — reference implementation.

Detects and redacts Personally Identifiable Information before it reaches
the LLM or appears in logs. Uses a layered approach:
  1. Regex patterns for structured PII (SSN, cards, emails, phones)
  2. NER-based detection for names and addresses (optional, requires spacy)

Why this matters for System of Records agents:
  - Customer data flows through the LLM context window
  - Logs must not contain raw PII (GDPR Article 25, HIPAA § 164.312)
  - LLM training pipelines must not ingest customer data

Session for audience:
  - Knowledge fuel: explain PII categories, regulatory requirements
  - Lab: extend _PATTERNS to cover your domain-specific PII
        (e.g., patient MRN, account numbers, passport numbers)
"""
import re
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# PII pattern definitions
# ---------------------------------------------------------------------------
@dataclass
class PIIPattern:
    name: str
    pattern: re.Pattern
    replacement: str
    risk_level: str  # low | medium | high | critical


_PATTERNS: List[PIIPattern] = [
    # Financial — critical
    PIIPattern(
        name="credit_card",
        pattern=re.compile(r"\b(?:\d[ -]?){13,16}\b"),
        replacement="[CARD-REDACTED]",
        risk_level="critical",
    ),
    PIIPattern(
        name="ssn",
        pattern=re.compile(r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b"),
        replacement="[SSN-REDACTED]",
        risk_level="critical",
    ),
    PIIPattern(
        name="bank_account",
        pattern=re.compile(r"\b\d{8,17}\b"),
        replacement="[ACCOUNT-REDACTED]",
        risk_level="critical",
    ),
    # Contact — high
    PIIPattern(
        name="email",
        pattern=re.compile(
            r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
        ),
        replacement="[EMAIL-REDACTED]",
        risk_level="high",
    ),
    PIIPattern(
        name="phone_us",
        pattern=re.compile(
            r"\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b"
        ),
        replacement="[PHONE-REDACTED]",
        risk_level="high",
    ),
    PIIPattern(
        name="phone_intl",
        pattern=re.compile(r"\+\d{1,3}[-.\s]?\d{6,14}"),
        replacement="[PHONE-REDACTED]",
        risk_level="high",
    ),
    # Location — medium
    PIIPattern(
        name="zip_code",
        pattern=re.compile(r"\b\d{5}(?:-\d{4})?\b"),
        replacement="[ZIP-REDACTED]",
        risk_level="medium",
    ),
    PIIPattern(
        name="ip_address",
        pattern=re.compile(
            r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"
        ),
        replacement="[IP-REDACTED]",
        risk_level="medium",
    ),
    # Tokens — critical
    PIIPattern(
        name="jwt_token",
        pattern=re.compile(r"\beyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\b"),
        replacement="[JWT-REDACTED]",
        risk_level="critical",
    ),
    PIIPattern(
        name="aws_key",
        pattern=re.compile(r"\b(?:AKIA|ASIA|AROA)[A-Z0-9]{16}\b"),
        replacement="[AWS-KEY-REDACTED]",
        risk_level="critical",
    ),
    PIIPattern(
        name="api_key_generic",
        pattern=re.compile(r"\b(?:sk|pk|api[-_]?key)[-_]?[A-Za-z0-9]{20,}\b", re.IGNORECASE),
        replacement="[API-KEY-REDACTED]",
        risk_level="critical",
    ),
]


# ---------------------------------------------------------------------------
# Detection result
# ---------------------------------------------------------------------------
@dataclass
class PIIDetectionResult:
    original: str
    masked: str
    detections: List[Dict] = field(default_factory=list)
    pii_found: bool = False
    risk_level: str = "none"  # none | low | medium | high | critical

    @property
    def summary(self) -> str:
        if not self.pii_found:
            return "No PII detected"
        types = [d["type"] for d in self.detections]
        return f"PII detected: {', '.join(set(types))}"


# ---------------------------------------------------------------------------
# PIIDetector class
# ---------------------------------------------------------------------------
class PIIDetector:
    """
    Regex-based PII detector with optional NER enhancement.

    Usage:
        detector = PIIDetector()
        result = detector.detect("Please refund John Doe at john@example.com")
        print(result.masked)   # "Please refund John Doe at [EMAIL-REDACTED]"
        print(result.pii_found)  # True
    """

    _RISK_RANK = {"none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
    _ner_available: bool = False

    def __init__(self, min_risk_level: str = "low", use_ner: bool = False):
        """
        Args:
            min_risk_level: Only detect PII at or above this risk level
            use_ner: Attempt to load spacy for name/address NER (optional)
        """
        self.min_risk = self._RISK_RANK.get(min_risk_level, 1)
        self._nlp = None

        if use_ner:
            self._load_ner()

    def _load_ner(self):
        """Attempt to load spacy NER model."""
        try:
            import spacy  # type: ignore
            self._nlp = spacy.load("en_core_web_sm")
            self._ner_available = True
            logger.info("spacy NER model loaded for PII detection")
        except Exception as e:
            logger.info(f"spacy not available — NER disabled: {e}")

    def detect(self, text: str) -> PIIDetectionResult:
        """
        Scan text for PII and return a masked version.

        Args:
            text: Raw input (user message, LLM output, log line, etc.)

        Returns:
            PIIDetectionResult with .masked text and .detections list
        """
        if not text or not isinstance(text, str):
            return PIIDetectionResult(original=text or "", masked=text or "")

        masked = text
        detections: List[Dict] = []
        max_risk = "none"

        for pat in _PATTERNS:
            if self._RISK_RANK[pat.risk_level] < self.min_risk:
                continue

            matches = list(pat.pattern.finditer(masked))
            for m in matches:
                detections.append({
                    "type": pat.name,
                    "value": m.group()[:4] + "****",  # partial for logging only
                    "start": m.start(),
                    "end": m.end(),
                    "risk_level": pat.risk_level,
                })
                if self._RISK_RANK[pat.risk_level] > self._RISK_RANK[max_risk]:
                    max_risk = pat.risk_level

            masked = pat.pattern.sub(pat.replacement, masked)

        # Optional NER pass for names and locations
        if self._nlp and masked:
            masked, ner_detections = self._ner_pass(masked)
            detections.extend(ner_detections)

        result = PIIDetectionResult(
            original=text,
            masked=masked,
            detections=detections,
            pii_found=len(detections) > 0,
            risk_level=max_risk,
        )

        if result.pii_found:
            logger.info(f"PII detected [{result.risk_level}]: {result.summary}")

        return result

    def _ner_pass(self, text: str) -> Tuple[str, List[Dict]]:
        """Apply spacy NER to detect names, locations, organisations."""
        doc = self._nlp(text)
        detections = []
        masked = text

        for ent in reversed(doc.ents):  # reverse to preserve offsets
            if ent.label_ in ("PERSON",):
                detections.append({
                    "type": "person_name",
                    "value": ent.text[:2] + "****",
                    "risk_level": "medium",
                })
                masked = masked[: ent.start_char] + "[NAME-REDACTED]" + masked[ent.end_char :]

        return masked, detections

    def is_safe(self, text: str, max_allowed_risk: str = "low") -> bool:
        """
        Quick safety check — returns False if PII above the threshold is found.

        TODO (Lab): Wire this into the chat endpoint to block messages
        that contain customer PII before they reach the LLM.
        """
        result = self.detect(text)
        return self._RISK_RANK[result.risk_level] <= self._RISK_RANK[max_allowed_risk]


# ---------------------------------------------------------------------------
# Module-level convenience function
# ---------------------------------------------------------------------------
_default_detector: Optional[PIIDetector] = None


def mask_pii(text: str) -> str:
    """
    Convenience function — mask PII in a string using the default detector.
    Suitable for wrapping log statements.

    Example:
        logger.info(mask_pii(f"Processing request for {user_email}"))
    """
    global _default_detector
    if _default_detector is None:
        _default_detector = PIIDetector(min_risk_level="medium")
    return _default_detector.detect(text).masked
