from store_sorter import matching
from store_sorter.matching import build_master_index, classify_name, normalize
from store_sorter.models import Status

MASTER = ["たこ焼き山田", "鈴木酒店", "カフェ Sunny", "串カツ田中"]


def test_normalize_zenkaku_hankaku_and_space():
    # 全角英数→半角、空白除去、小文字化
    assert normalize("ＡＢＣ　商店 ") == "abc商店"
    assert normalize("カフェ Sunny") == "カフェsunny"


def test_exact_match_is_confirmed():
    index = build_master_index(MASTER)
    status, candidates = classify_name("たこ焼き山田", index)
    assert status is Status.CONFIRMED
    assert candidates[0].master_name == "たこ焼き山田"


def test_typo_within_range_is_confirmed_or_ambiguous():
    index = build_master_index(MASTER)
    # 1 文字違い（打ち間違いの範囲）
    status, candidates = classify_name("鈴木酒展", index)
    assert candidates[0].master_name == "鈴木酒店"
    assert status in (Status.CONFIRMED, Status.AMBIGUOUS)


def test_no_match_is_unknown():
    index = build_master_index(MASTER)
    status, _candidates = classify_name("全く関係ない名前XYZ", index)
    assert status is Status.UNKNOWN


def test_empty_query_is_unknown():
    index = build_master_index(MASTER)
    status, candidates = classify_name("", index)
    assert status is Status.UNKNOWN
    assert candidates == []


def test_build_rows(tmp_path):
    from pathlib import Path

    groups = {
        "たこ焼き山田": [Path("たこ焼き山田_1.jpg")],
        "全く不明な店XYZ": [Path("全く不明な店XYZ_1.jpg")],
    }
    rows = matching.build_rows(groups, MASTER)
    by_name = {r.extracted_name: r for r in rows}
    assert by_name["たこ焼き山田"].status is Status.CONFIRMED
    assert by_name["たこ焼き山田"].resolved_name == "たこ焼き山田"
    assert by_name["全く不明な店XYZ"].status is Status.UNKNOWN
    # 不明は best_master なし → resolved_name は抽出名のまま
    assert by_name["全く不明な店XYZ"].resolved_name == "全く不明な店XYZ"
