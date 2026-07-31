from scraper.parsers import extract_phones, extract_emails, match_pic


def test_extract_phones_indonesian_mobile():
    assert extract_phones("Hubungi 0812-3456-7890 sekarang") == ["081234567890"]


def test_extract_phones_international():
    assert extract_phones("Call +62 812 3456 7890") == ["+6281234567890"]


def test_extract_phones_with_parens_area_code():
    assert extract_phones("Phone (021) 123-4567") == ["0211234567"]


def test_extract_phones_filters_short_noise():
    assert extract_phones("id #42 done") == []


def test_extract_phones_dedup():
    phones = extract_phones("081234567890 or 0812 3456 7890")
    assert phones == ["081234567890"]


def test_extract_emails_basic():
    assert extract_emails("Contact: info@pt-maju.co.id please") == ["info@pt-maju.co.id"]


def test_extract_emails_multiple():
    assert extract_emails("a@b.com and c@d.org") == ["a@b.com", "c@d.org"]


def test_extract_emails_dedup_preserves_order():
    assert extract_emails("a@b.com a@b.com c@d.org") == ["a@b.com", "c@d.org"]


def test_extract_emails_filters_invalid():
    assert extract_emails("no at sign here") == []


def test_match_pic_tier1_hse_english():
    m = match_pic("Budi Santoso", "Budi Santoso - HSE Manager")
    assert m is not None
    assert m.tier == 1
    assert m.name == "Budi Santoso"


def test_match_pic_tier1_hse_indonesian():
    m = match_pic("Siti", "Siti - Kepala Bagian K3")
    assert m is not None
    assert m.tier == 1


def test_match_pic_tier2_environmental():
    m = match_pic("Andi", "Andi Wijaya - Environmental Manager")
    assert m is not None
    assert m.tier == 2


def test_match_pic_tier3_general_manager():
    m = match_pic("Rini", "Rini - General Manager")
    assert m is not None
    assert m.tier == 3


def test_match_pic_no_match():
    assert match_pic("Budi", "Budi - Marketing Staff") is None


def test_match_pic_tier1_wins_over_tier3():
    m = match_pic("Hendra", "Hendra - HSE Officer & Acting General Manager")
    assert m.tier == 1