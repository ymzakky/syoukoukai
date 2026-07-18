from pathlib import Path

from store_sorter import file_ops
from store_sorter.models import MatchRow, Status


def test_sanitize_folder_name():
    assert file_ops.sanitize_folder_name("A/B:C") == "A_B_C"
    assert file_ops.sanitize_folder_name("  .店舗.  ") == "店舗"
    assert file_ops.sanitize_folder_name("") == "未分類"


def test_unique_destination(tmp_path):
    (tmp_path / "a.jpg").write_bytes(b"x")
    dest = file_ops.unique_destination(tmp_path, "a.jpg")
    assert dest.name == "a_1.jpg"


def _make_row(tmp_path, name, files):
    paths = []
    for f in files:
        p = tmp_path / f
        p.write_bytes(b"img")
        paths.append(p)
    return MatchRow(
        extracted_name=name, files=paths, status=Status.CONFIRMED, resolved_name=name
    )


def test_move_files(tmp_path):
    row = _make_row(tmp_path, "山田商店", ["山田商店_1.jpg", "山田商店_2.jpg"])
    summary = file_ops.move_files([row], tmp_path)

    assert summary["moved"] == 2
    assert summary["failed"] == []
    dest_dir = tmp_path / "山田商店"
    assert dest_dir.is_dir()
    assert (dest_dir / "山田商店_1.jpg").exists()
    assert (dest_dir / "山田商店_2.jpg").exists()


def test_move_files_skips_excluded(tmp_path):
    row = _make_row(tmp_path, "除外店", ["除外店_1.jpg"])
    row.included = False
    summary = file_ops.move_files([row], tmp_path)
    assert summary["moved"] == 0
    assert not (tmp_path / "除外店").exists()


def test_move_files_name_collision(tmp_path):
    # 別々のサブフォルダにある同名ファイルが、同じフォルダ名に解決される場合は連番付与
    src_a = tmp_path / "a"
    src_b = tmp_path / "b"
    src_a.mkdir()
    src_b.mkdir()
    (src_a / "写真.jpg").write_bytes(b"img-a")
    (src_b / "写真.jpg").write_bytes(b"img-b")

    a = MatchRow(
        extracted_name="店A",
        files=[src_a / "写真.jpg"],
        status=Status.CONFIRMED,
        resolved_name="共通",
    )
    b = MatchRow(
        extracted_name="店B",
        files=[src_b / "写真.jpg"],
        status=Status.CONFIRMED,
        resolved_name="共通",
    )
    summary = file_ops.move_files([a, b], tmp_path)
    assert summary["moved"] == 2
    dest = tmp_path / "共通"
    assert (dest / "写真.jpg").exists()
    assert (dest / "写真_1.jpg").exists()
