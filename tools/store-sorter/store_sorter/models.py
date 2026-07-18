"""データモデル（GUI 非依存）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional


class Status(Enum):
    """照合結果のステータス。"""

    CONFIRMED = "確定済み"
    AMBIGUOUS = "曖昧"
    UNKNOWN = "不明"


@dataclass
class Candidate:
    """マスターの照合候補。"""

    master_name: str
    score: float


@dataclass
class MatchRow:
    """1 店舗（＝同一の抽出名でまとまった画像群）の照合結果。

    ユーザーが GUI 上で確認・修正した最終フォルダ名は ``resolved_name`` に入る。
    """

    extracted_name: str
    files: List[Path]
    status: Status
    best_master: Optional[str] = None
    score: float = 0.0
    candidates: List[Candidate] = field(default_factory=list)
    # ユーザー確定後の最終フォルダ名（初期値は best_master or extracted_name）
    resolved_name: str = ""
    # このグループを移動対象に含めるか（曖昧で「いいえ」等を選んだ場合に False）
    included: bool = True

    def __post_init__(self) -> None:
        if not self.resolved_name:
            self.resolved_name = self.best_master or self.extracted_name
