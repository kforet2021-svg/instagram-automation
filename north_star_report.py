"""
north_star_report.py
North Star Daily Generator(2026-07-04新設)— レポート本文をMarkdownファイルとして
保存するモジュール。

ユーザー要望「North Star Daily Generatorを実装してほしい。Markdown形式で保存し、
north_star_dailyシートにも保存してください」に対応する。スプレッドシートへの保存
(sheets_writer.save_north_star_daily)とは別に、同じ結果(openai_analyzer.
generate_north_star_dailyの戻り値)を人間が読みやすいMarkdownファイルとしても
保存する。

設計判断(ユーザー指定ではないため、私の判断であることを明記する):
- 保存先は本リポジトリ直下の reports/north_star_daily/ ディレクトリ。
  YYYY-MM-DD.md という日付のみのファイル名にし、同じ日に複数回main.pyを実行した
  場合は最新の結果で上書きする(north_star_dailyシート側が「1日1件」設計である
  ことと揃えた)。過去日分のレポートはファイル名が異なるため上書きされず、
  reports/north_star_daily/配下に蓄積される。
- 新規のOpenAI呼び出しは発生しない。openai_analyzer.generate_north_star_dailyの
  戻り値(dict)をそのままMarkadownに整形するだけ。
- 既存のtrend_posts/post_analysis等の保存処理が失敗してもこの処理には影響しない
  ように、呼び出し側(main.py)でtry/exceptに包む(本モジュール自体はファイル
  書き込みエラー時に例外を投げる。失敗時の扱いは呼び出し側に委ねる)。

【2026-07-04(5回目): Creator Intelligence Sprint 2(Task6)— HTML出力を追加】
ユーザー要望「Markdownだけでなく、HTMLも生成してほしい。将来的にメール配信・
Web公開・Notion・PDF化を見据えた構造にしてほしい」に対応する。

- build_north_star_daily_html/save_north_star_daily_htmlを新設した。
  Markdown版(build_north_star_daily_markdown)と同じresult辞書を入力にする
  ため、生成ロジックの分岐は不要(NORTH_STAR_DAILY_TEXT_KEYSの並び順を
  そのまま使う1つのループ)。
- 「将来のメール配信・Web公開・Notion・PDF化を見据えた構造」という要望に対して、
  以下の判断をした:
  - メール配信を見据え、外部CSSファイルへの依存をゼロにし、すべてインライン
    style属性で装飾した(多くのメールクライアントは<style>タグ自体を除去する
    ため)。
  - Web公開・PDF化(印刷)を見据え、見出し(<h1>/<h2>)・本文(<p>)という
    セマンティックな構造にし、改行(\n\n)は段落(<p>)に、単純な改行(\n)は
    <br>に変換した。
  - Notion等への貼り付けを見据え、装飾は最小限(色は黒系のみ、派手な背景色は
    使わない)にし、貼り付け後にNotion側の見た目を壊さないようにした。
  - すべてのテキストはhtml.escapeでエスケープしている(AIが生成したテキストに
    たまたま<>&等が含まれていてもHTML構造が壊れないようにするため)。
- 保存先はMarkdown版と同じreports/north_star_daily/ディレクトリ内に
  YYYY-MM-DD.html として保存する(1日1ファイル。同日複数回実行時は上書き。
  Markdown版と運用ルールを揃えた)。
"""

import datetime
import html
import os

from prompts import NORTH_STAR_DAILY_TEXT_KEYS

_REPORT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports", "north_star_daily")


def _today_str() -> str:
    return datetime.date.today().strftime("%Y-%m-%d")


def build_north_star_daily_markdown(entries: list, result: dict) -> str:
    """
    North Star Dailyの結果(result。NORTH_STAR_DAILY_TEXT_KEYSの各キーを持つdict)を
    Markdown文字列に整形する。ファイルへの書き込みは行わない(save_north_star_
    daily_markdownが行う)。entriesは「対象投稿数」の表示にのみ使う。
    """
    entries = entries or []
    result = result or {}
    today = _today_str()

    lines = [
        f"# North Star Daily — {today}",
        "",
        f"対象投稿数: {len(entries)}件",
        "",
    ]
    for key in NORTH_STAR_DAILY_TEXT_KEYS:
        value = str(result.get(key, "")).strip() or "(なし)"
        lines.append(f"## {key}")
        lines.append("")
        lines.append(value)
        lines.append("")

    return "\n".join(lines)


def save_north_star_daily_markdown(entries: list, result: dict) -> str:
    """
    North Star Dailyの結果をMarkdownファイルとして
    reports/north_star_daily/YYYY-MM-DD.md に保存する(1日1ファイル。同日に
    複数回実行した場合は上書き)。

    戻り値: 保存したファイルの絶対パス。
    """
    os.makedirs(_REPORT_DIR, exist_ok=True)
    file_path = os.path.join(_REPORT_DIR, f"{_today_str()}.md")

    markdown_text = build_north_star_daily_markdown(entries, result)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(markdown_text)

    return file_path
