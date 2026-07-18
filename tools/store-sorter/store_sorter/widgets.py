"""再利用 GUI ウィジェット（Tkinter）。"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import Callable, Dict, List, Optional

from PIL import ImageTk

from .models import MatchRow, Status
from .thumbnails import ThumbnailCache, load_preview

# ステータス別の色
STATUS_COLORS: Dict[Status, str] = {
    Status.CONFIRMED: "#e6f4ea",  # 緑系
    Status.AMBIGUOUS: "#fff4d6",  # 黄系
    Status.UNKNOWN: "#fde7e7",    # 赤系
}
STATUS_ACCENT: Dict[Status, str] = {
    Status.CONFIRMED: "#137333",
    Status.AMBIGUOUS: "#b06000",
    Status.UNKNOWN: "#c5221f",
}

THUMB_SIZE = (96, 96)


class ScrollableFrame(ttk.Frame):
    """縦スクロール可能な内部フレームを持つコンテナ。"""

    def __init__(self, parent: tk.Misc, **kwargs) -> None:
        super().__init__(parent, **kwargs)
        self.canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(
            self, orient="vertical", command=self.canvas.yview
        )
        self.inner = ttk.Frame(self.canvas)

        self._window = self.canvas.create_window(
            (0, 0), window=self.inner, anchor="nw"
        )
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        # マウスホイール（Windows / Linux）
        self.canvas.bind("<Enter>", self._bind_wheel)
        self.canvas.bind("<Leave>", self._unbind_wheel)

    def _on_inner_configure(self, _event: object) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event: tk.Event) -> None:
        self.canvas.itemconfigure(self._window, width=event.width)

    def _bind_wheel(self, _event: object) -> None:
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", self._on_mousewheel)
        self.canvas.bind_all("<Button-5>", self._on_mousewheel)

    def _unbind_wheel(self, _event: object) -> None:
        self.canvas.unbind_all("<MouseWheel>")
        self.canvas.unbind_all("<Button-4>")
        self.canvas.unbind_all("<Button-5>")

    def _on_mousewheel(self, event: tk.Event) -> None:
        if getattr(event, "num", None) == 4:
            delta = -1
        elif getattr(event, "num", None) == 5:
            delta = 1
        else:
            delta = -1 if event.delta > 0 else 1
        self.canvas.yview_scroll(delta, "units")

    def clear(self) -> None:
        for child in list(self.inner.winfo_children()):
            child.destroy()


def show_preview(parent: tk.Misc, path: Path) -> None:
    """画像を別ウィンドウで拡大表示する。"""
    image = load_preview(path)
    win = tk.Toplevel(parent)
    win.title(Path(path).name)
    if image is None:
        ttk.Label(win, text="画像を読み込めませんでした:\n" + str(path)).pack(
            padx=20, pady=20
        )
        return
    photo = ImageTk.PhotoImage(image)
    label = ttk.Label(win, image=photo)
    label.image = photo  # GC 防止
    label.pack(padx=8, pady=8)
    ttk.Label(win, text=Path(path).name).pack(pady=(0, 8))
    win.bind("<Escape>", lambda _e: win.destroy())


class RowWidget(ttk.Frame):
    """1 店舗（MatchRow）を表す行ウィジェット。

    確定名の編集、曖昧行の採否、不明行の店舗名入力、サムネイル表示を担う。
    ユーザーの入力は commit() で MatchRow に書き戻される。
    """

    def __init__(
        self,
        parent: tk.Misc,
        row: MatchRow,
        cache: ThumbnailCache,
        master_names: List[str],
    ) -> None:
        super().__init__(parent, relief="ridge", borderwidth=1)
        self.row = row
        self.cache = cache
        self._thumb_refs: List[ImageTk.PhotoImage] = []

        color = STATUS_COLORS.get(row.status, "#ffffff")
        accent = STATUS_ACCENT.get(row.status, "#333333")

        container = tk.Frame(self, bg=color)
        container.pack(fill="x", expand=True)

        # 左：ステータス・情報・入力
        left = tk.Frame(container, bg=color)
        left.pack(side="left", fill="both", expand=True, padx=8, pady=6)

        header = tk.Frame(left, bg=color)
        header.pack(fill="x")
        tk.Label(
            header,
            text=f"● {row.status.value}",
            fg=accent,
            bg=color,
            font=("", 10, "bold"),
        ).pack(side="left")
        tk.Label(
            header,
            text=f"　ファイル名: 「{row.extracted_name}」　（{len(row.files)} 枚）",
            bg=color,
        ).pack(side="left")

        self.included_var = tk.BooleanVar(value=row.included)
        self.name_var = tk.StringVar(value=row.resolved_name)

        self._build_status_body(left, color, accent, master_names)

        # 右：サムネイル
        right = tk.Frame(container, bg=color)
        right.pack(side="right", padx=8, pady=6)
        self._build_thumbnails(right, color)

    # ------------------------------------------------------------------
    def _build_status_body(
        self, parent: tk.Misc, color: str, accent: str, master_names: List[str]
    ) -> None:
        row = self.row

        if row.status is Status.CONFIRMED:
            body = tk.Frame(parent, bg=color)
            body.pack(fill="x", pady=(4, 0))
            tk.Label(body, text="フォルダ名:", bg=color).pack(side="left")
            entry = ttk.Combobox(
                body, textvariable=self.name_var, values=master_names, width=32
            )
            entry.pack(side="left", padx=4)
            tk.Label(
                body, text=f"（一致度 {row.score:.0f}）", bg=color, fg=accent
            ).pack(side="left")

        elif row.status is Status.AMBIGUOUS:
            body = tk.Frame(parent, bg=color)
            body.pack(fill="x", pady=(4, 0))
            candidate = row.best_master or row.extracted_name
            tk.Label(
                body,
                text=f"ファイル名「{row.extracted_name}」 → マスター候補「{candidate}」（一致度 {row.score:.0f}）",
                bg=color,
            ).pack(anchor="w")

            choice = tk.Frame(parent, bg=color)
            choice.pack(fill="x", pady=(2, 0))
            # accept=True: 候補を採用 / False: 手入力
            self.accept_var = tk.BooleanVar(value=True)
            ttk.Radiobutton(
                choice,
                text="はい（この候補で確定）",
                variable=self.accept_var,
                value=True,
                command=self._sync_ambiguous,
            ).pack(side="left")
            ttk.Radiobutton(
                choice,
                text="いいえ（手入力）",
                variable=self.accept_var,
                value=False,
                command=self._sync_ambiguous,
            ).pack(side="left", padx=(8, 0))

            entry_frame = tk.Frame(parent, bg=color)
            entry_frame.pack(fill="x", pady=(2, 0))
            tk.Label(entry_frame, text="フォルダ名:", bg=color).pack(side="left")
            self.amb_entry = ttk.Combobox(
                entry_frame, textvariable=self.name_var, values=master_names, width=32
            )
            self.amb_entry.pack(side="left", padx=4)
            self.name_var.set(candidate)
            self._sync_ambiguous()

        else:  # UNKNOWN
            body = tk.Frame(parent, bg=color)
            body.pack(fill="x", pady=(4, 0))
            tk.Label(
                body, text="該当マスターなし。フォルダ名を入力:", bg=color
            ).pack(side="left")
            entry = ttk.Combobox(
                body, textvariable=self.name_var, values=master_names, width=32
            )
            entry.pack(side="left", padx=4)
            # 不明は既定で対象外（入力後にチェックを促す）
            self.included_var.set(True)

        # 共通：移動対象チェック
        incl = tk.Frame(parent, bg=color)
        incl.pack(fill="x", pady=(4, 0))
        ttk.Checkbutton(
            incl, text="このグループを振り分け対象にする", variable=self.included_var
        ).pack(side="left")

    def _sync_ambiguous(self) -> None:
        """曖昧行のラジオに応じて入力欄の有効/無効を切り替える。"""
        if not hasattr(self, "amb_entry"):
            return
        if self.accept_var.get():
            self.name_var.set(self.row.best_master or self.row.extracted_name)
            self.amb_entry.configure(state="disabled")
        else:
            self.amb_entry.configure(state="normal")

    def _build_thumbnails(self, parent: tk.Misc, color: str) -> None:
        for path in self.row.files:
            image = self.cache.get(path)
            if image is None:
                tk.Label(
                    parent, text="×", width=6, height=3, bg="#dddddd"
                ).pack(side="left", padx=2)
                continue
            photo = ImageTk.PhotoImage(image)
            self._thumb_refs.append(photo)
            btn = tk.Label(parent, image=photo, bg=color, cursor="hand2")
            btn.pack(side="left", padx=2)
            btn.bind("<Button-1>", lambda _e, p=path: show_preview(self, p))

    # ------------------------------------------------------------------
    def commit(self) -> None:
        """ウィジェットの状態を MatchRow に書き戻す。"""
        self.row.resolved_name = self.name_var.get().strip()
        self.row.included = bool(self.included_var.get()) and bool(
            self.row.resolved_name
        )
