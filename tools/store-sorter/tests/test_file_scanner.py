from pathlib import Path

from store_sorter import file_scanner


def test_extract_store_name_with_underscore():
    assert file_scanner.extract_store_name("たこ焼き山田_正面.jpg") == "たこ焼き山田"
    assert file_scanner.extract_store_name("ABC商店_01_裏.png") == "ABC商店"


def test_extract_store_name_without_underscore():
    assert file_scanner.extract_store_name("店舗名だけ.jpg") == "店舗名だけ"


def test_is_image():
    assert file_scanner.is_image(Path("a.JPG"))
    assert file_scanner.is_image(Path("a.png"))
    assert not file_scanner.is_image(Path("a.txt"))
    assert not file_scanner.is_image(Path("a.xlsx"))


def test_scan_and_group(tmp_path):
    for name in [
        "山田商店_1.jpg",
        "山田商店_2.png",
        "鈴木_a.jpeg",
        "メモ.txt",  # 非画像は除外
        "master.xlsx",
    ]:
        (tmp_path / name).write_bytes(b"x")

    groups = file_scanner.scan_and_group(tmp_path)
    assert set(groups.keys()) == {"山田商店", "鈴木"}
    assert len(groups["山田商店"]) == 2
    assert len(groups["鈴木"]) == 1
