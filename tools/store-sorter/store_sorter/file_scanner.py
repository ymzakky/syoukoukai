"""画像ファイルの走査と、ファイル名からの店舗名抽出。"""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from typing import Dict, List, Union

PathLike = Union[str, Path]

# 対象とする画像拡張子（小文字比較）
IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".webp",
    ".tif",
    ".tiff",
}


def is_image(path: Path) -> bool:
    """画像拡張子かどうか。"""
    return path.suffix.lower() in IMAGE_EXTENSIONS


def extract_store_name(filename: str) -> str:
    """ファイル名（stem）の先頭 ``_`` より前を店舗名として返す。

    ``[店舗名]_[任意文字列].[拡張子]`` を想定。``_`` が無い場合は stem 全体を返す。
    """
    stem = Path(filename).stem
    if "_" in stem:
        return stem.split("_", 1)[0].strip()
    return stem.strip()


def scan_images(folder: PathLike) -> List[Path]:
    """フォルダ直下の画像ファイルを名前順で返す。"""
    folder = Path(folder)
    return sorted(
        (p for p in folder.iterdir() if p.is_file() and is_image(p)),
        key=lambda p: p.name,
    )


def group_by_store(files: List[Path]) -> "OrderedDict[str, List[Path]]":
    """抽出した店舗名ごとに画像ファイルをグルーピングする（出現順を維持）。"""
    groups: "OrderedDict[str, List[Path]]" = OrderedDict()
    for f in files:
        name = extract_store_name(f.name)
        groups.setdefault(name, []).append(f)
    return groups


def scan_and_group(folder: PathLike) -> "OrderedDict[str, List[Path]]":
    """走査とグルーピングをまとめて行うヘルパ。"""
    return group_by_store(scan_images(folder))
