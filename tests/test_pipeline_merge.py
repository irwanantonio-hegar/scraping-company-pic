from scraper.pipeline import PartialRow, merge_rows, final_to_output_dict
from scraper.parsers import PICMatch


def make_row(**kw):
    base = dict(sources=[], pic_candidates=[])
    base.update(kw)
    return PartialRow(**base)


def test_merge_picks_highest_priority_pic():
    a = make_row(sources=["Google"], pic_candidates=[PICMatch(tier=3, name="GM Person", context="GM")])
    b = make_row(sources=["Website"], pic_candidates=[PICMatch(tier=1, name="HSE Person", context="HSE")])
    final = merge_rows([a, b])
    assert final.pic_name == "HSE Person"


def test_merge_first_non_empty_per_scalar_field():
    a = make_row(kabupaten_kota="Bandung", phone="111")
    b = make_row(kabupaten_kota="Bekasi", phone="222", email="x@y.com")
    final = merge_rows([a, b])
    assert final.kabupaten_kota == "Bandung"  # OSS / source A wins
    assert final.phone == "111"
    assert final.email == "x@y.com"  # filled by B


def test_merge_dedups_sources():
    a = make_row(sources=["OSS"])
    b = make_row(sources=["OSS", "Website"])
    final = merge_rows([a, b])
    assert sorted(final.sources) == ["OSS", "Website"]


def test_merge_kawasan_default_non():
    final = merge_rows([make_row()])
    assert final.kawasan == "Non Kawasan"


def test_final_to_output_dict_preserves_input_and_appends():
    src = {"Nama Perusahaan": "PT X", "Extra": "keepme"}
    final = merge_rows([make_row(kabupaten_kota="Jakarta")])
    out = final_to_output_dict(final, src)
    assert out["Nama Perusahaan"] == "PT X"
    assert out["Extra"] == "keepme"
    assert out["Kabupaten/Kota"] == "Jakarta"
    assert "Sumber data" in out


def test_final_to_output_dict_sumber_data_format():
    final = merge_rows([make_row(sources=["OSS", "Website"])])
    out = final_to_output_dict(final, {"Nama Perusahaan": "X"})
    assert out["Sumber data"] == "OSS; Website"