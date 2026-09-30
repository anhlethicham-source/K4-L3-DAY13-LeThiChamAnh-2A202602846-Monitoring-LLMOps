from app.pii import scrub_text


def test_scrub_email() -> None:
    out = scrub_text("Email me at student@vinuni.edu.vn")
    assert "student@" not in out
    assert "REDACTED_EMAIL" in out


def test_scrub_common_vietnamese_phone_formats() -> None:
    phone_numbers = (
        "0901234567",
        "090 123 4567",
        "090.123.4567",
        "090-123-4567",
        "+84 90 123 4567",
    )

    for phone_number in phone_numbers:
        out = scrub_text(f"Contact: {phone_number}")
        assert phone_number not in out
        assert "REDACTED_PHONE_VN" in out


def test_scrub_cccd_and_credit_card() -> None:
    out = scrub_text("CCCD 012345678901, card 4111 1111 1111 1111")
    assert "012345678901" not in out
    assert "4111" not in out
    assert "REDACTED_CCCD" in out
    assert "REDACTED_CREDIT_CARD" in out


def test_scrub_passport() -> None:
    out = scrub_text("Hộ chiếu của tôi là C1234567")
    assert "C1234567" not in out
    assert "REDACTED_PASSPORT" in out


def test_scrub_vietnamese_address() -> None:
    samples = (
        "Tôi ở phường Bến Nghé, quận 1",
        "Giao tới số nhà 12 đường Lê Lợi",
        "Địa chỉ: 25 Nguyễn Trãi, Thanh Xuân, Hà Nội",
    )
    for text in samples:
        out = scrub_text(text)
        assert "REDACTED_ADDRESS" in out
        for leaked in ("Bến Nghé", "Lê Lợi", "Nguyễn Trãi"):
            assert leaked not in out


def test_scrub_keeps_non_pii_text_intact() -> None:
    for text in (
        "response_sent",
        "req-a1234567",
        "2026-09-30T03:24:58.007651Z",
        "Explain why metrics traces and logs work together",
        "đường dẫn tới file log",
    ):
        assert scrub_text(text) == text
