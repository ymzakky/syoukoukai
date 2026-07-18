"""フォルダ作成とファイル移動。"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Callable, List, Optional, Sequence, Union

from .models import MatchRow

PathLike = Union[str, Path]

# Windows で使用できないファイル名文字＋制御文字
_INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

# 進捗コールバック: (current, total, message) -> None
ProgressCallback = Callable[[int, int, str], None]

# キャンセルフラグ: is_set() を持つオブジェクト（threading.Event など）
class _CancelLike:  # pragma: no cover - 型ヒント用
    def is_set(self) -> bool:  # noqa: D401
        ...


def sanitize_folder_name(name: str) -> str:
    """フォルダ名として安全な文字列に整える。"""
    cleaned = _INVALID_CHARS.sub("_", name or "").strip().strip(".")
    return cleaned or "未分類"


def unique_destination(dest_dir: Path, filename: str) -> Path:
    """移動先で同名衝突する場合に連番を付けた一意なパスを返す。"""
    target = dest_dir / filename
    if not target.exists():
        return target
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    i = 1
    while True:
        candidate = dest_dir / f"{stem}_{i}{suffix}"
        if not candidate.exists():
            return candidate
        i += 1


def move_files(
    rows: Sequence[MatchRow],
    base_dir: PathLike,
    progress_cb: Optional[ProgressCallback] = None,
    cancel_event: Optional[_CancelLike] = None,
) -> dict:
    """確定した行の画像を店舗名フォルダへ移動する。

    Returns
    -------
    dict
        ``{"moved", "skipped", "failed", "total", "cancelled"}`` を含むサマリ。
        ``failed`` は ``(ファイルパス, エラーメッセージ)`` のリスト。
    """
    base = Path(base_dir)

    # 移動タスクを平坦化（フォルダ名, 元ファイル）
    tasks: List[tuple] = []
    for row in rows:
        if not row.included:
            continue
        folder = sanitize_folder_name(row.resolved_name)
        for src in row.files:
            tasks.append((folder, Path(src)))

    total = len(tasks)
    moved = 0
    skipped = 0
    failed: List[tuple] = []
    cancelled = False

    for i, (folder, src) in enumerate(tasks, start=1):
        if cancel_event is not None and cancel_event.is_set():
            cancelled = True
            break
        try:
            if not src.exists():
                skipped += 1
            else:
                dest_dir = base / folder
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest = unique_destination(dest_dir, src.name)
                shutil.move(str(src), str(dest))
                moved += 1
        except Exception as exc:  # noqa: BLE001 - 個々の失敗は握って続行
            failed.append((str(src), str(exc)))
        if progress_cb is not None:
            progress_cb(i, total, f"{i}/{total} 枚を移動中… （{folder}）")

    return {
        "moved": moved,
        "skipped": skipped,
        "failed": failed,
        "total": total,
        "cancelled": cancelled,
    }
