from __future__ import annotations

import hashlib
import re

# Uppercase letters incl. Vietnamese (Đ, Â, Ă, Ê, Ô, Ơ, Ư and toned forms like Ấ, Ộ...)
_UPPER = "A-Z" + "".join(ch for ch in map(chr, range(0x00C0, 0x1F00)) if ch.isupper())
# One address component: a number ("12", "12/3", "5A") or a capitalized name ("Lê", "Bến")
_ADDR_TOKEN = rf"(?:\d+[\w/-]*|[{_UPPER}]\w*)"
_ADDR_KEYWORDS = (
    "số nhà|ngõ|ngách|hẻm|kiệt|đường|phố|phường|quận|huyện|xã|thị trấn|thị xã|thôn|ấp|tổ dân phố"
)

# Order matters: more specific patterns run first so a longer number is not
# partially redacted by a shorter pattern (e.g. card number vs CCCD vs phone).
PII_PATTERNS: dict[str, str] = {
    "email": r"[\w\.-]+@[\w\.-]+\.\w+",
    "credit_card": r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b",
    "cccd": r"\b\d{12}\b",
    "phone_vn": r"(?<!\d)(?:\+84|0)(?:[ .-]?\d){9}(?!\d)",
    # Vietnamese passport: 1 uppercase letter + 7 digits (e.g. C1234567).
    # Uppercase only so lowercase hex IDs like req-a1234567 are not redacted.
    "passport": r"\b[A-Z]\d{7}\b",
    # Address: "địa chỉ: ..." up to end of clause, or an admin keyword followed by
    # 1-5 components (e.g. "phường Bến Nghé", "quận 1", "đường Lê Lợi").
    "address": (
        r"(?i:địa chỉ)[^\n:]{0,20}?(?::|\blà\b)\s*[^\n;]{1,120}"
        rf"|\b(?i:{_ADDR_KEYWORDS})\s+{_ADDR_TOKEN}(?:\s+{_ADDR_TOKEN}){{0,4}}"
    ),
}

_COMPILED = {name: re.compile(pattern) for name, pattern in PII_PATTERNS.items()}


def scrub_text(text: str) -> str:
    safe = text
    for name, pattern in _COMPILED.items():
        safe = pattern.sub(f"[REDACTED_{name.upper()}]", safe)
    return safe


def summarize_text(text: str, max_len: int = 80) -> str:
    safe = scrub_text(text).strip().replace("\n", " ")
    return safe[:max_len] + ("..." if len(safe) > max_len else "")


def hash_user_id(user_id: str) -> str:
    return hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:12]
