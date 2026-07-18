from openpyxl import Workbook

from store_sorter import excel_loader


def _make_excel(path):
    wb = Workbook()
    ws = wb.active
    ws.title = "店舗一覧"
    ws.append(["No", "店舗名", "備考"])
    ws.append([1, "たこ焼き山田", "A"])
    ws.append([2, "鈴木酒店", "B"])
    ws.append([3, None, "空欄行"])       # 店舗名が空
    ws.append([4, "鈴木酒店", "重複"])   # 重複
    ws.append([5, "  カフェ Sunny  ", "C"])  # 前後空白
    wb.save(path)


def test_sheet_names(tmp_path):
    path = tmp_path / "master.xlsx"
    _make_excel(path)
    assert excel_loader.sheet_names(path) == ["店舗一覧"]


def test_read_headers(tmp_path):
    path = tmp_path / "master.xlsx"
    _make_excel(path)
    assert excel_loader.read_headers(path) == ["No", "店舗名", "備考"]


def test_read_column_dedup_and_strip(tmp_path):
    path = tmp_path / "master.xlsx"
    _make_excel(path)
    # 店舗名列は index 1
    values = excel_loader.read_column(path, 1)
    assert values == ["たこ焼き山田", "鈴木酒店", "カフェ Sunny"]
