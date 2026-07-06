"""
hook_library.py

Phase 1 Hook Library — 高評価Hookの保存・検索・リライト支援。

設計:
  ・Hookは資産。毎回ゼロから作らず、過去の良いHookを改善・再利用する。
  ・Google Sheets タブ「hook_library_phase1」に保存。
  ・生成時: ライブラリ上位N件をAIに渡し「リライト優先」で生成させる。
  ・選択後: 選んだHookをライブラリに自動保存（★5で初期登録）。

【2026-07-06(1回目): 新規作成。Phase1 Hook Library。】
"""

from __future__ import annotations

import datetime
from typing import Optional

# ── シート定義 ────────────────────────────────────────────────────────────────

SHEET_NAME = "hook_library_phase1"

HEADERS = [
    "登録日",       # YYYY-MM-DD
    "hook",         # Hook文
    "perspective",  # CORE HARI視点（咬筋/首 等）
    "angle",        # 切り口（〜な人へ/先にして 等）
    "post_type",    # 保存/共感/信頼/行動/Threads
    "stars",        # ユーザー評価 1〜5（初期: 5）
    "times_used",   # 使用回数
    "season",       # 登録時の季節（春/夏/秋/冬）
    "last_used",    # 最終使用日
    "source",       # new / rewrite
    "reason",       # 選定理由（AI生成）
]

# ── 読み込み ─────────────────────────────────────────────────────────────────

def load_hooks(top_n: int = 30) -> list[dict]:
    """
    Hook Libraryから上位Hookを読み込む。

    stars 降順 → last_used 降順でソートして top_n 件返す。
    失敗時は空リスト（ライブラリなしでも動作継続）。
    """
    try:
        from sheets_writer import _get_or_create_worksheet
        ws = _get_or_create_worksheet(SHEET_NAME, HEADERS)
        rows = ws.get_all_records()
        if not rows:
            return []

        def _sort_key(r: dict):
            stars = int(r.get("stars", 3) or 3)
            times = int(r.get("times_used", 0) or 0)
            return (stars, times)

        sorted_rows = sorted(rows, key=_sort_key, reverse=True)
        return sorted_rows[:top_n]
    except Exception as e:
        print(f"  ⚠️ Hook Library 読み込み失敗: {e}")
        return []


def format_library_for_prompt(hooks: list[dict], max_chars: int = 800) -> str:
    """
    ライブラリHookをAIプロンプト用テキストに変換する。

    AI はこのテキストを参照して「リライト優先」でHookを生成する。
    """
    if not hooks:
        return ""

    lines = ["【Hook Library — 過去の高評価Hook（リライト優先で使うこと）】"]
    total = 0
    for h in hooks:
        hook  = h.get("hook", "")
        stars = h.get("stars", "")
        persp = h.get("perspective", "")
        angle = h.get("angle", "")
        seas  = h.get("season", "")
        line = f"  ★{stars} [{persp}][{angle}] 「{hook}」（{seas}）"
        if total + len(line) > max_chars:
            break
        lines.append(line)
        total += len(line)

    lines.append("  ※ 季節・World Contextに合わせてリライトして使う。新規作成は最後の手段。")
    return "\n".join(lines)


# ── 保存 ─────────────────────────────────────────────────────────────────────

def save_hook(
    hook_dict: dict,
    season: str = "",
    source: str = "new",
    stars: int = 5,
) -> bool:
    """
    選択されたHookをライブラリに保存する。

    hook_dict: generate_topic_candidates_ai() が返す候補 dict
    season:    登録時の季節
    source:    "new"（新規）/ "rewrite"（リライト）
    stars:     初期評価（デフォルト5）
    """
    today = datetime.date.today().isoformat()
    row = [
        today,
        hook_dict.get("hook", ""),
        hook_dict.get("perspective", ""),
        hook_dict.get("angle", ""),
        hook_dict.get("post_type", ""),
        str(stars),
        "1",            # times_used
        season,
        today,          # last_used
        source,
        hook_dict.get("reason", ""),
    ]
    try:
        from sheets_writer import _get_or_create_worksheet
        ws = _get_or_create_worksheet(SHEET_NAME, HEADERS)
        ws.append_row(row, value_input_option="USER_ENTERED")
        return True
    except Exception as e:
        print(f"  ⚠️ Hook Library 保存失敗: {e}")
        return False


def increment_usage(hook_text: str) -> None:
    """
    既存Hook の times_used + 1 / last_used を更新する。
    見つからない場合は無視。
    """
    today = datetime.date.today().isoformat()
    try:
        from sheets_writer import _get_or_create_worksheet
        ws = _get_or_create_worksheet(SHEET_NAME, HEADERS)
        rows = ws.get_all_values()
        if not rows:
            return
        header = rows[0]
        try:
            hook_col   = header.index("hook") + 1
            times_col  = header.index("times_used") + 1
            last_col   = header.index("last_used") + 1
        except ValueError:
            return

        for i, row in enumerate(rows[1:], start=2):
            if len(row) >= hook_col and row[hook_col - 1] == hook_text:
                try:
                    current = int(row[times_col - 1] or 0)
                except ValueError:
                    current = 0
                ws.update_cell(i, times_col, str(current + 1))
                ws.update_cell(i, last_col,  today)
                break
    except Exception as e:
        print(f"  ⚠️ Hook Library usage更新失敗: {e}")
