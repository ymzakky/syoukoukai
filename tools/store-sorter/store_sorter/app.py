"""Tkinter GUI 本体（非同期処理・進捗表示つき）。"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import List, Optional

from . import excel_loader, file_ops, file_scanner, matching
from .models import MatchRow, Status
from .thumbnails import ThumbnailCache
from .widgets import RowWidget, ScrollableFrame

POLL_INTERVAL_MS = 80


class SorterApp(tk.Tk):
    """店舗名マッチング・画像振り分けアプリのメインウィンドウ。"""

    def __init__(self) -> None:
        super().__init__()
        self.title("店舗名マッチング・画像振り分けツール")
        self.geometry("1000x720")
        self.minsize(820, 560)

        # 状態
        self.excel_path: Optional[Path] = None
        self.base_dir: Optional[Path] = None
        self.master_names: List[str] = []
        self.rows: List[MatchRow] = []
        self.row_widgets: List[RowWidget] = []
        self.cache = ThumbnailCache()

        # スレッド間通信
        self._queue: "queue.Queue[tuple]" = queue.Queue()
        self._worker: Optional[threading.Thread] = None
        self._cancel = threading.Event()

        self._build_ui()
        self.after(POLL_INTERVAL_MS, self._poll_queue)

    # ------------------------------------------------------------------
    # UI 構築
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        pad = {"padx": 6, "pady": 4}

        # --- ツールバー ---
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", **pad)

        ttk.Button(toolbar, text="Excel を開く", command=self.open_excel).pack(
            side="left"
        )
        ttk.Label(toolbar, text="シート:").pack(side="left", padx=(12, 2))
        self.sheet_var = tk.StringVar()
        self.sheet_combo = ttk.Combobox(
            toolbar, textvariable=self.sheet_var, width=16, state="readonly"
        )
        self.sheet_combo.pack(side="left")
        self.sheet_combo.bind("<<ComboboxSelected>>", lambda _e: self._reload_headers())

        ttk.Label(toolbar, text="照合する列:").pack(side="left", padx=(12, 2))
        self.column_var = tk.StringVar()
        self.column_combo = ttk.Combobox(
            toolbar, textvariable=self.column_var, width=28, state="readonly"
        )
        self.column_combo.pack(side="left")

        self.analyze_btn = ttk.Button(
            toolbar, text="解析開始", command=self.analyze, state="disabled"
        )
        self.analyze_btn.pack(side="left", padx=(12, 0))

        # --- しきい値 ---
        thr = ttk.Frame(self)
        thr.pack(fill="x", **pad)
        ttk.Label(thr, text="確定しきい値:").pack(side="left")
        self.confirm_var = tk.DoubleVar(value=matching.DEFAULT_CONFIRM_THRESHOLD)
        ttk.Scale(
            thr, from_=50, to=100, variable=self.confirm_var, length=160,
            command=lambda _v: self._update_thr_labels(),
        ).pack(side="left", padx=4)
        self.confirm_lbl = ttk.Label(thr, text="")
        self.confirm_lbl.pack(side="left")

        ttk.Label(thr, text="　曖昧しきい値:").pack(side="left")
        self.ambiguous_var = tk.DoubleVar(value=matching.DEFAULT_AMBIGUOUS_THRESHOLD)
        ttk.Scale(
            thr, from_=30, to=100, variable=self.ambiguous_var, length=160,
            command=lambda _v: self._update_thr_labels(),
        ).pack(side="left", padx=4)
        self.ambiguous_lbl = ttk.Label(thr, text="")
        self.ambiguous_lbl.pack(side="left")

        self.reclassify_btn = ttk.Button(
            thr, text="再分類", command=self.reclassify, state="disabled"
        )
        self.reclassify_btn.pack(side="left", padx=(12, 0))
        self._update_thr_labels()

        # --- 進捗 ---
        prog = ttk.Frame(self)
        prog.pack(fill="x", **pad)
        self.progress = ttk.Progressbar(prog, mode="determinate", length=300)
        self.progress.pack(side="left")
        self.status_lbl = ttk.Label(prog, text="Excel を開いてください。")
        self.status_lbl.pack(side="left", padx=8)

        # --- 結果一覧 ---
        self.list_area = ScrollableFrame(self)
        self.list_area.pack(fill="both", expand=True, padx=6, pady=4)

        # --- 実行ボタン ---
        action = ttk.Frame(self)
        action.pack(fill="x", **pad)
        self.execute_btn = ttk.Button(
            action, text="振り分け実行（OK）", command=self.execute_move, state="disabled"
        )
        self.execute_btn.pack(side="left")
        self.cancel_btn = ttk.Button(
            action, text="キャンセル", command=self.cancel, state="disabled"
        )
        self.cancel_btn.pack(side="left", padx=6)
        self.summary_lbl = ttk.Label(action, text="")
        self.summary_lbl.pack(side="left", padx=8)

    def _update_thr_labels(self) -> None:
        self.confirm_lbl.configure(text=f"{self.confirm_var.get():.0f}")
        self.ambiguous_lbl.configure(text=f"{self.ambiguous_var.get():.0f}")

    # ------------------------------------------------------------------
    # Excel 読み込み
    # ------------------------------------------------------------------
    def open_excel(self) -> None:
        path = filedialog.askopenfilename(
            title="店舗名マスターの Excel を選択",
            filetypes=[("Excel", "*.xlsx *.xlsm"), ("すべて", "*.*")],
        )
        if not path:
            return
        self.excel_path = Path(path)
        self.base_dir = self.excel_path.parent
        try:
            sheets = excel_loader.sheet_names(self.excel_path)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("エラー", f"Excel を開けませんでした:\n{exc}")
            return
        self.sheet_combo.configure(values=sheets)
        if sheets:
            self.sheet_var.set(sheets[0])
        self._reload_headers()
        self.status_lbl.configure(
            text=f"対象フォルダ: {self.base_dir}　列を選んで「解析開始」を押してください。"
        )

    def _reload_headers(self) -> None:
        if not self.excel_path:
            return
        try:
            headers = excel_loader.read_headers(
                self.excel_path, self.sheet_var.get() or None
            )
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("エラー", f"ヘッダーを読み込めませんでした:\n{exc}")
            return
        labels = [
            f"{i + 1}: {h}" if h else f"{i + 1}: (無題列)"
            for i, h in enumerate(headers)
        ]
        self.column_combo.configure(values=labels)
        if labels:
            self.column_var.set(labels[0])
            self.analyze_btn.configure(state="normal")

    def _selected_column_index(self) -> Optional[int]:
        value = self.column_var.get()
        if not value or ":" not in value:
            return None
        try:
            return int(value.split(":", 1)[0]) - 1
        except ValueError:
            return None

    # ------------------------------------------------------------------
    # 解析（バックグラウンド）
    # ------------------------------------------------------------------
    def analyze(self) -> None:
        if self._worker and self._worker.is_alive():
            return
        col = self._selected_column_index()
        if col is None or not self.excel_path or not self.base_dir:
            messagebox.showwarning("確認", "照合する列を選んでください。")
            return

        self._set_busy(True)
        self._cancel.clear()
        self.summary_lbl.configure(text="")
        self.list_area.clear()
        self.row_widgets = []

        sheet = self.sheet_var.get() or None
        confirm = self.confirm_var.get()
        ambiguous = self.ambiguous_var.get()

        def work() -> None:
            try:
                master = excel_loader.read_column(self.excel_path, col, sheet)
                self._queue.put(("status", f"{len(master)} 件のマスターを読み込みました。"))
                groups = file_scanner.scan_and_group(self.base_dir)
                total_files = sum(len(v) for v in groups.values())
                self._queue.put(
                    ("status", f"{len(groups)} 店舗 / {total_files} 枚の画像を検出。サムネイル生成中…")
                )
                # サムネイルを先読み（重い処理をワーカーで）
                done = 0
                for files in groups.values():
                    for f in files:
                        if self._cancel.is_set():
                            self._queue.put(("cancelled", None))
                            return
                        self.cache.get(f)
                        done += 1
                        self._queue.put(("progress", (done, total_files)))
                rows = matching.build_rows(
                    groups, master,
                    confirm_threshold=confirm,
                    ambiguous_threshold=ambiguous,
                )
                self._queue.put(("analyze_done", (rows, master)))
            except Exception as exc:  # noqa: BLE001
                self._queue.put(("error", str(exc)))

        self._worker = threading.Thread(target=work, daemon=True)
        self._worker.start()

    def reclassify(self) -> None:
        """しきい値変更後に、既存グループを再分類して一覧を作り直す。"""
        if not self.rows:
            return
        # 既存 rows から groups を復元
        groups = {r.extracted_name: r.files for r in self.rows}
        rows = matching.build_rows(
            groups, self.master_names,
            confirm_threshold=self.confirm_var.get(),
            ambiguous_threshold=self.ambiguous_var.get(),
        )
        self._render_rows(rows)

    # ------------------------------------------------------------------
    # 移動実行（バックグラウンド）
    # ------------------------------------------------------------------
    def execute_move(self) -> None:
        if self._worker and self._worker.is_alive():
            return
        for w in self.row_widgets:
            w.commit()
        targets = [r for r in self.rows if r.included and r.resolved_name]
        if not targets:
            messagebox.showinfo("確認", "振り分け対象がありません。")
            return
        total = sum(len(r.files) for r in targets)
        if not messagebox.askyesno(
            "確認",
            f"{len(targets)} フォルダ・{total} 枚の画像を移動します。よろしいですか？",
        ):
            return

        self._set_busy(True)
        self._cancel.clear()
        base_dir = self.base_dir
        rows = list(self.rows)

        def work() -> None:
            def cb(cur: int, tot: int, msg: str) -> None:
                self._queue.put(("progress", (cur, tot)))
                self._queue.put(("status", msg))

            summary = file_ops.move_files(
                rows, base_dir, progress_cb=cb, cancel_event=self._cancel
            )
            self._queue.put(("move_done", summary))

        self._worker = threading.Thread(target=work, daemon=True)
        self._worker.start()

    def cancel(self) -> None:
        self._cancel.set()
        self.status_lbl.configure(text="キャンセル中…")

    # ------------------------------------------------------------------
    # キュー処理（メインスレッド）
    # ------------------------------------------------------------------
    def _poll_queue(self) -> None:
        try:
            while True:
                kind, payload = self._queue.get_nowait()
                self._handle_message(kind, payload)
        except queue.Empty:
            pass
        self.after(POLL_INTERVAL_MS, self._poll_queue)

    def _handle_message(self, kind: str, payload: object) -> None:
        if kind == "status":
            self.status_lbl.configure(text=str(payload))
        elif kind == "progress":
            current, total = payload  # type: ignore[misc]
            self.progress.configure(maximum=max(total, 1), value=current)
        elif kind == "analyze_done":
            rows, master = payload  # type: ignore[misc]
            self.master_names = master
            self._render_rows(rows)
            self._set_busy(False)
            self.reclassify_btn.configure(state="normal")
            self.execute_btn.configure(state="normal")
            self._report_counts()
        elif kind == "move_done":
            self._set_busy(False)
            self._show_summary(payload)  # type: ignore[arg-type]
        elif kind == "cancelled":
            self._set_busy(False)
            self.status_lbl.configure(text="キャンセルしました。")
        elif kind == "error":
            self._set_busy(False)
            messagebox.showerror("エラー", str(payload))
            self.status_lbl.configure(text="エラーが発生しました。")

    def _render_rows(self, rows: List[MatchRow]) -> None:
        self.rows = rows
        self.list_area.clear()
        self.row_widgets = []
        for row in rows:
            w = RowWidget(self.list_area.inner, row, self.cache, self.master_names)
            w.pack(fill="x", expand=True, padx=2, pady=2)
            self.row_widgets.append(w)
        self._report_counts()

    def _report_counts(self) -> None:
        counts = {s: 0 for s in Status}
        for r in self.rows:
            counts[r.status] += 1
        self.summary_lbl.configure(
            text=(
                f"確定済み {counts[Status.CONFIRMED]} / "
                f"曖昧 {counts[Status.AMBIGUOUS]} / "
                f"不明 {counts[Status.UNKNOWN]}"
            )
        )

    def _show_summary(self, summary: dict) -> None:
        failed = summary.get("failed", [])
        msg = (
            f"移動完了: {summary['moved']} 枚\n"
            f"スキップ: {summary['skipped']} 枚\n"
            f"失敗: {len(failed)} 枚"
        )
        if summary.get("cancelled"):
            msg += "\n（途中キャンセルされました）"
        self.status_lbl.configure(text="振り分けが完了しました。")
        if failed:
            detail = "\n".join(f"- {p}: {e}" for p, e in failed[:20])
            messagebox.showwarning("完了（一部失敗）", msg + "\n\n" + detail)
        else:
            messagebox.showinfo("完了", msg)

    def _set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        self.analyze_btn.configure(state=state)
        self.execute_btn.configure(
            state="disabled" if busy or not self.rows else "normal"
        )
        self.cancel_btn.configure(state="normal" if busy else "disabled")
        if not busy:
            self.progress.configure(value=0)


def main() -> None:
    app = SorterApp()
    app.mainloop()


if __name__ == "__main__":
    main()
