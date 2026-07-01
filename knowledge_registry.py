"""
knowledge_registry.py
Creator Intelligence Sprint 2(Task3+4)— knowledge_libraryの重複排除ロジック。

【2026-07-05: Trend Score → Research Candidate Scoreへのリネームに追従】
trend_score.pyがresearch_candidate_score.pyへリネームされたことに伴い、
_format_achievement/_extract_score_numberが読み書きする「実績」列のラベルを
「Trend Score N点」から「Research Candidate Score N点」に変更した。重複判定・
信頼度計算などのロジックは変更していない。以下の【2026-07-04】の履歴は
リネーム前の「Trend Score」という名称だった時点の記録であり、当時の意思決定の
経緯を正確に残すため名称を書き換えずに保存している。

【2026-07-04(4回目)新設】
ユーザー要望「knowledge_libraryを会社の知識DBとして強化してほしい(成功パターン/
心理トリガー/CTAパターン/フック/再利用可能な構成/参考記事/参考URL/信頼度/
初回発見日/最後に確認した日/使用回数/実績)。知識が重複しない設計を希望する」
(Task3)、「AIが『初めて見るパターン』だけを登録する仕組みを追加してほしい。
同じ成功要因は重複登録しないでください」(Task4)に対応する。

設計方針:
- 新規のOpenAI呼び出しは追加しない(コスト増ゼロ)。すでに生成済みの
  idea["投稿カテゴリ"](main.pyのAIが付ける投稿案の切り口ラベル。例:
  「ビフォーアフター型」)と、success_factors["心理トリガー"](AIが生成した
  心理トリガーのテキスト。例:「社会的証明・限定性」)から、決定論的
  (deterministic)に「成功パターン名」を組み立てる。
- 重複判定は、この組み立てた「成功パターン名」の完全一致でのみ行う
  (= OpenAIに「これは既存パターンと同じか」を判断させない。コストゼロ・
  常に同じ入力なら同じ判定になる再現性を優先した)。
- 既存パターンと一致した場合(Task4「同じ成功要因は重複登録しない」):
  新規行を追加せず、既存行を更新する。使用回数を+1し、最後に確認した日を
  今日に更新し、信頼度を使用回数から再計算する(1件=低、2〜3件=中、4件以上
  =高、というユーザーとの相談なしの仮しきい値。運用しながら調整する前提)。
  「実績」列には、これまでに見た中で最も高いResearch Candidate Scoreを保持する
  (後退させない)。
- 一致しなかった場合(Task4「初めて見るパターン」):新規行を1件追加する
  (使用回数=1、初回発見日=最後に確認した日=今日)。

このファイルはGoogle Sheetsへの実際の読み書きを直接行わない。2026-07-04(6回目)、
Sprint2設計レビュー②に基づき、sheets_writer.pyへの直接依存を
creator_intelligence.knowledge.KnowledgeStore抽象(all/append/update)経由に変更した。
本ファイルが知っているのは「成功パターン名で重複判定し、無ければ追加・あれば更新する」
というビジネスロジックだけであり、保存先がSheetsかDBかは_store(KnowledgeStoreの
具象実装)が吸収する。将来SQLite等のDBへ移行する場合は、下の
`_store = SheetsKnowledgeStore()` の1行を新しいストア実装に差し替えるだけでよく、
本ファイルの重複判定・更新ロジックには手を入れない。
"""

import datetime
import re

from creator_intelligence.knowledge.sheets_store import SheetsKnowledgeStore

# 2026-07-04(6回目): 保存先の実体はここでのみ決定する。将来DBへ移行する場合は
# この1行を差し替えるだけでよい(下記の重複判定ロジックは変更不要)。
_store = SheetsKnowledgeStore()

# success_factors["心理トリガー"]のテキストから検出する既知の心理トリガー名
# (prompts.SUCCESS_FACTOR_SYSTEM_PROMPTが列挙を指示している技法名と揃えてある。
# north_star_index._score_psychologyとは別の用途だが、語彙は共通)。
_KNOWN_PSYCHOLOGY_TRIGGERS = [
    "社会的証明",
    "限定性",
    "緊急性",
    "権威",
    "ザイガニク効果",
    "FOMO",
    "損失回避",
    "共感",
    "ビフォーアフター",
]


def _today_str() -> str:
    return datetime.date.today().strftime("%Y-%m-%d")


def _detect_psychology_triggers(text: str) -> list:
    """success_factors["心理トリガー"]のテキストから既知のトリガー名を検出する。"""
    text = text or ""
    return [trigger for trigger in _KNOWN_PSYCHOLOGY_TRIGGERS if trigger in text]


def _build_success_pattern_name(idea: dict, success_factors: dict) -> str:
    """
    「投稿カテゴリ × 検出された心理トリガー」を、決定論的な成功パターン名として
    組み立てる(これが重複判定のキーになる)。

    例: idea["投稿カテゴリ"]="ビフォーアフター型"、success_factors["心理トリガー"]=
    "社会的証明・限定性が使われている" -> "ビフォーアフター型×社会的証明・限定性"
    """
    idea = idea or {}
    success_factors = success_factors or {}
    category = idea.get("投稿カテゴリ", "") or "カテゴリ不明"
    triggers = _detect_psychology_triggers(success_factors.get("心理トリガー", ""))
    trigger_part = "・".join(triggers) if triggers else "心理トリガー不明"
    return f"{category}×{trigger_part}"


def _compute_confidence(usage_count: int) -> str:
    """
    使用回数(同じ成功パターン名で何回確認されたか)から信頼度を仮決めする。
    1件=低、2〜3件=中、4件以上=高(ユーザー未確認の仮しきい値。運用しながら
    調整することを前提にしている。north_star_index.pyのWEIGHTSと同じ思想)。
    """
    if usage_count >= 4:
        return "高"
    if usage_count >= 2:
        return "中"
    return "低"


def _extract_score_number(text: str) -> float:
    """「実績」列の文字列(例: "Research Candidate Score 82点")から数値部分だけを取り出す。"""
    if not text:
        return -1.0
    match = re.search(r"[\d.]+", str(text))
    return float(match.group()) if match else -1.0


def _format_achievement(post: dict) -> str:
    """投稿のResearch Candidate Score合計を「実績」列用のテキストに整形する。"""
    score = (post or {}).get("research_candidate_score") or {}
    total = score.get("total")
    if total is None:
        return ""
    return f"Research Candidate Score {total}点"


def upsert_knowledge_for_entry(entry: dict) -> None:
    """
    1投稿分のentry({"post":..., "idea":..., "success_factors":...})から、
    knowledge_libraryシートに重複なく登録/更新する。

    既存の成功パターン(成功パターン名が完全一致)が見つかった場合は更新のみ
    行い、新規行は追加しない(Task4「同じ成功要因は重複登録しない」)。
    見つからなかった場合のみ新規登録する(Task4「初めて見るパターンだけを
    登録する」)。

    Google Sheetsへの読み書きに失敗しても例外を外に伝播させない
    (呼び出し元main.pyのtry/exceptパターンに合わせ、本関数内でも1件の
    失敗が他の処理を止めないようにする)。
    """
    entry = entry or {}
    post = entry.get("post") or {}
    idea = entry.get("idea") or {}
    success_factors = entry.get("success_factors") or {}

    pattern_name = _build_success_pattern_name(idea, success_factors)
    triggers = _detect_psychology_triggers(success_factors.get("心理トリガー", ""))
    today = _today_str()
    new_achievement = _format_achievement(post)

    try:
        existing_rows = _store.all()
    except Exception as e:
        print(f"  ⚠️ knowledge_library読み込みに失敗したためスキップします: {e}")
        return

    match = next(
        (r for r in existing_rows if r["values"].get("成功パターン") == pattern_name),
        None,
    )

    try:
        if match:
            values = dict(match["values"])
            usage_count = int(values.get("使用回数") or 0) + 1
            values["使用回数"] = usage_count
            values["最後に確認した日"] = today
            values["信頼度"] = _compute_confidence(usage_count)

            existing_achievement = values.get("実績", "")
            if new_achievement and _extract_score_number(new_achievement) > _extract_score_number(
                existing_achievement
            ):
                values["実績"] = new_achievement

            if not values.get("参考記事"):
                values["参考記事"] = idea.get("タイトル", "") or post.get("url", "")
            if not values.get("参考URL"):
                values["参考URL"] = post.get("url", "")

            _store.update(match["id"], values)
        else:
            values = {
                "成功パターン": pattern_name,
                "心理トリガー": "・".join(triggers),
                "CTAパターン": success_factors.get("CTA", ""),
                "フック": success_factors.get("冒頭3秒のフック", ""),
                "再利用可能な構成": success_factors.get("構成", ""),
                "参考記事": idea.get("タイトル", "") or post.get("url", ""),
                "参考URL": post.get("url", ""),
                "信頼度": _compute_confidence(1),
                "初回発見日": today,
                "最後に確認した日": today,
                "使用回数": 1,
                "実績": new_achievement,
            }
            _store.append(values)
    except Exception as e:
        print(f"  ⚠️ knowledge_library更新に失敗しました(パターン: {pattern_name}): {e}")


def upsert_knowledge_for_entries(entries: list) -> None:
    """upsert_knowledge_for_entryをentries全件に適用する(main.pyから呼ぶ想定)。"""
    for entry in entries or []:
        upsert_knowledge_for_entry(entry)
