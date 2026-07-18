"""サムネイル生成と LRU キャッシュ（Pillow）。

PIL の Image 生成はワーカースレッドから呼んでよいが、``ImageTk.PhotoImage`` は
Tk のメインスレッドから生成する必要がある。本モジュールは PIL.Image までを担当し、
PhotoImage 化は GUI 側（メインスレッド）で行う。
"""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from typing import Optional, Tuple, Union

from PIL import Image, ImageOps

PathLike = Union[str, Path]


class ThumbnailCache:
    """パス → PIL.Image の LRU キャッシュ。"""

    def __init__(self, size: Tuple[int, int] = (96, 96), max_items: int = 500) -> None:
        self.size = size
        self.max_items = max_items
        self._cache: "OrderedDict[str, Optional[Image.Image]]" = OrderedDict()

    def get(self, path: PathLike) -> Optional[Image.Image]:
        """サムネイル PIL.Image を返す。読み込み失敗時は None。"""
        key = str(path)
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]

        image = self._load(path)
        self._cache[key] = image
        if len(self._cache) > self.max_items:
            self._cache.popitem(last=False)
        return image

    def _load(self, path: PathLike) -> Optional[Image.Image]:
        try:
            with Image.open(path) as img:
                img = ImageOps.exif_transpose(img)
                img.thumbnail(self.size)
                return img.convert("RGB")
        except Exception:
            return None

    def clear(self) -> None:
        self._cache.clear()


def load_preview(path: PathLike, max_size: Tuple[int, int] = (800, 800)) -> Optional[Image.Image]:
    """拡大プレビュー用に、指定サイズに収まる PIL.Image を返す。"""
    try:
        with Image.open(path) as img:
            img = ImageOps.exif_transpose(img)
            img.thumbnail(max_size)
            return img.convert("RGB")
    except Exception:
        return None
