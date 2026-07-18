"""店舗名の正規化・類似度計算・ステータス分類（rapidfuzz）。"""

from __future__ import annotations

import unicodedata
from pathlib import Path
from typing import Dict, List, Mapping, Sequence

from rapidfuzz import fuzz, process

from .models import Candidate, MatchRow, Status

# しきい値の既定値（0〜100）。GUI 側から上書き可能。
DEFAULT_CONFIRM_THRESHOLD = 92.0
DEFAULT_AMBIGUOUS_THRESHOLD = 75.0


def normalize(text: object) -> str:
    """照合用に文字列を正規化する。

    - NFKC で全角/半角・互換文字を統一
    - 空白（半角・全角）を除去
    - 小文字化
    """
    if text is None:
        return ""
    normalized = unicodedata.normalize("NFKC", str(text))
    normalized = normalized.replace(" ", "").replace("　", "")
    return normalized.strip().lower()


def build_master_index(master_names: Sequence[str]) -> Dict[str, str]:
    """マスター名 → 正規化名 の辞書を作る（rapidfuzz の choices 用）。

    正規化後が空になる名前は除外する。
    """
    index: Dict[str, str] = {}
    for name in master_names:
        norm = normalize(name)
        if norm:
            index[name] = norm
    return index


def classify_name(
    extracted_name: str,
    master_index: Mapping[str, str],
    confirm_threshold: float = DEFAULT_CONFIRM_THRESHOLD,
    ambiguous_threshold: float = DEFAULT_AMBIGUOUS_THRESHOLD,
    top_n: int = 5,
) -> "tuple[Status, List[Candidate]]":
    """抽出名をマスターと照合し、ステータスと候補一覧を返す。"""
    query = normalize(extracted_name)
    if not query or not master_index:
        return Status.UNKNOWN, []

    # choices が Mapping の場合、結果は (value, score, key) のタプル。
    # value=正規化名, key=元のマスター名。
    results = process.extract(
        query, master_index, scorer=fuzz.WRatio, limit=top_n
    )
    candidates = [
        Candidate(master_name=key, score=float(score))
        for (_value, score, key) in results
    ]

    if not candidates:
        return Status.UNKNOWN, []

    top_score = candidates[0].score
    if top_score >= confirm_threshold:
        return Status.CONFIRMED, candidates
    if top_score >= ambiguous_threshold:
        return Status.AMBIGUOUS, candidates
    return Status.UNKNOWN, candidates


def build_rows(
    groups: Mapping[str, Sequence[Path]],
    master_names: Sequence[str],
    confirm_threshold: float = DEFAULT_CONFIRM_THRESHOLD,
    ambiguous_threshold: float = DEFAULT_AMBIGUOUS_THRESHOLD,
    top_n: int = 5,
) -> List[MatchRow]:
    """グルーピング済み画像とマスターから MatchRow の一覧を作る。"""
    master_index = build_master_index(master_names)
    rows: List[MatchRow] = []
    for extracted_name, files in groups.items():
        status, candidates = classify_name(
            extracted_name,
            master_index,
            confirm_threshold=confirm_threshold,
            ambiguous_threshold=ambiguous_threshold,
            top_n=top_n,
        )
        best = candidates[0] if candidates else None
        rows.append(
            MatchRow(
                extracted_name=extracted_name,
                files=list(files),
                status=status,
                best_master=best.master_name if status is not Status.UNKNOWN and best else None,
                score=best.score if best else 0.0,
                candidates=candidates,
            )
        )
    return rows
