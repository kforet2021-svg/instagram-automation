"""
thumbnail_analyzer.py

CORE HARI FACE — リール サムネイル分析モジュール

処理フロー:
  1. reels シートから投稿URLを取得（直近20日・高再生数優先）
  2. OGPスクレイピングでサムネイル画像URLを取得
  3. 画像をダウンロードしてbase64化
  4. GPT-4o（vision）で各投稿を個別分析
  5. 全体傾向を集計・パターン分類
  6. CORE HARI FACE用サムネイル案を3案生成
  7. thumbnail_analysis シートに保存
  8. Markdownレポートを出力

エントリポイント:
  python3 main.py --thumbnail          # 通常実行（最大10件）
  python3 main.py --thumbnail --test   # テスト実行（3件）

【2026-07-15(1回目): 新規作成。OGP+GPT-4o visionによるサムネイル分析。】
"""

from __future__ import annotations

import base64
import datetime
import json
import os
import re
import sys
import time
from typing import Optional

import requests

# ── 定数 ─────────────────────────────────────────────────────────────────────

THUMBNAIL_MODEL = "gpt-4o"         # vision 分析には gpt-4o を使用
MAX_POSTS_TEST  = 3
MAX_POSTS_FULL  = 10
RECENT_DAYS     = 20               # 直近N日以内の投稿を優先
MIN_VIEWS       = 100_000          # 再生数フィルタ（緩和時は外す）
REQUEST_DELAY   = 1.5              # OGPスクレイピング間隔（秒）

OGP_USER_AGENT  = (
    "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)"
)

# ── システムプロンプト ─────────────────────────────────────────────────────────

_THUMBNAIL_SYSTEM = """
あなたはInstagramリールのサムネイル分析の専門家です。
サムネイル画像を見て、以下のJSON形式で分析結果を返してください。
画像から判断できない項目は必ず "判定不可" としてください（推測で埋めない）。

出力は必ずJSON形式のみ。説明文は含めない。
"""

_THUMBNAIL_ANALYSIS_PROMPT = """
以下のInstagramリール投稿のサムネイル画像を分析してください。

【投稿情報】
- URL: {url}
- 再生数: {views}
- いいね数: {likes}
- キャプション冒頭: {caption_head}

以下のJSON形式で返してください（不明な項目は "判定不可"）:

{{
  "thumbnail_text": "サムネイル内の全テキスト（改行は / で区切る）",
  "main_text": "最も大きく目立つテキスト",
  "sub_text": "サブテキスト（なければ空文字）",
  "text_length": "文字数（数字）",
  "text_lines": "行数（数字）",
  "emphasized_words": "強調されている単語（カンマ区切り）",
  "text_position": "テキストの位置（例: 上部中央 / 下部左 / 全体）",
  "text_size": "テキストの大きさ（大 / 中 / 小）",
  "font_impression": "フォントの印象（例: 手書き風 / ゴシック / 明朝 / 太字）",
  "background_color": "背景色（例: 白 / 黒 / ピンク / 肌色）",
  "text_color": "文字色",
  "accent_color": "強調色（使われていなければ 判定不可）",
  "color_count": "使用色数（数字）",
  "person_present": "人物あり / 人物なし",
  "face_size": "顔の大きさ（大 / 中 / 小 / 判定不可）",
  "face_direction": "顔の向き（正面 / 斜め / 横向き / 判定不可）",
  "facial_expression": "表情（笑顔 / 真顔 / 驚き / 真剣 / 判定不可）",
  "pose": "手の動き・ポーズ（例: 顔に手を当てる / 指差し / 腕組み / 判定不可）",
  "pointing": "指差しあり / 指差しなし / 判定不可",
  "decoration": "矢印・丸・線などの装飾（例: 矢印 / 丸囲み / なし）",
  "before_after": "ビフォーアフター表現あり / なし",
  "whitespace": "余白の多さ（多い / 普通 / 少ない）",
  "self_explanatory": "サムネイルだけで内容が伝わるか（はい / いいえ / 判定不可）",
  "scroll_stop_reason": "スクロールを止める要素（50字以内）",
  "curiosity_reason": "続きを見たくなる要素（50字以内）",
  "psychological_trigger": "心理トリガー（不安 / 共感 / 意外性 / 結果提示 / 疑問 / 数字 / カンマ区切り）",
  "thumbnail_type": "サムネイルの型（悩み共感型 / 意外性型 / 勘違い否定型 / 結果提示型 / 数字型 / 質問型 / ビフォーアフター型 / 専門視点型 / NG行動指摘型 / セルフケア提示型 / その他）",
  "scroll_stop_analysis": "このサムネイルが止まりやすい理由（100字以内）",
  "first_gaze": "視線が最初に向く場所（30字以内）",
  "strongest_word": "最も強い言葉",
  "reader_emotion": "想定される読者の感情（50字以内）",
  "content_match": "動画内容とサムネイルが一致しているか（一致 / 不一致 / 判定不可）",
  "applicable_points": "CORE HARI FACEで応用できる点（100字以内）",
  "caution_points": "そのまま真似すると危険な点（100字以内）",
  "core_hari_thumbnail_idea": "CORE HARIらしく置き換えたサムネイル案（100字以内）",
  "confidence": "分析の信頼度（高 / 中 / 低）",
  "analysis_notes": "補足・注意事項（なければ空文字）"
}}
"""

_SUMMARY_SYSTEM = """
あなたはInstagramリールのサムネイル分析の専門家です。
複数の投稿分析結果から全体傾向をまとめ、CORE HARI FACE向けの提案を生成してください。
出力はJSON形式のみ。
"""

_SUMMARY_PROMPT = """
以下は {n} 件のInstagramリールサムネイル分析結果です。

{analyses_json}

【CORE HARI FACEについて】
- 顔専門エステ（小顔矯正・顔筋・たるみ）
- 札幌 / オーナー: 森このみ
- 対象: 30〜40代女性
- やさしい・専門的・押し付けない
- セルフケア中心（道具不要・30秒以内）
- CORE HARI視点: 咬筋/噛み癖/舌/姿勢/首/呼吸/表情グセ/左右差 など
- 禁止: 医学的断定 / 施術前提 / 誇張ビフォーアフター / 「プロが教えます」

以下のJSON形式で全体分析を返してください:

{{
  "common_patterns": {{
    "popular_composition": "よく使われているサムネイル構成（3点箇条書き）",
    "popular_text_length": "よく使われている文字数",
    "popular_colors": "よく使われている配色",
    "person_usage": "人物の見せ方の傾向",
    "popular_expression": "よく使われている表情",
    "popular_hook_types": "よく使われているHookの型（3点）",
    "popular_keywords": "よく使われている強調語（5語）",
    "difference_analysis": "伸びた投稿と伸びなかった投稿の違い",
    "beauty_specific": "美容ジャンル特有の傾向",
    "recent_trends": "直近の新しい傾向"
  }},
  "type_counts": {{
    "悩み共感型": 0,
    "意外性型": 0,
    "勘違い否定型": 0,
    "結果提示型": 0,
    "数字型": 0,
    "質問型": 0,
    "ビフォーアフター型": 0,
    "専門視点型": 0,
    "NG行動指摘型": 0,
    "セルフケア提示型": 0,
    "その他": 0
  }},
  "core_hari_elements": "CORE HARI FACEで使える要素（5点箇条書き）",
  "reel_ideas": [
    {{
      "theme": "投稿テーマ",
      "purpose": "投稿目的（共感 / 保存 / 信頼 / 行動）",
      "hook": "冒頭Hook（15字以内）",
      "terop_3sec": "3秒以内のテロップ",
      "thumbnail_main": "サムネイルのメインテキスト",
      "thumbnail_sub": "サムネイルのサブテキスト",
      "composition": "写真または動画の構図",
      "expression": "森このみの表情",
      "pose": "手の位置やポーズ",
      "text_position": "文字の位置",
      "colors": "推奨配色",
      "emphasis_word": "強調する単語",
      "canva_instruction": "Canvaで再現するための具体的な配置指示",
      "reason": "この案を選んだ理由",
      "reference": "参考にした伸び投稿の共通点"
    }}
  ],
  "thumbnail_proposals": [
    {{
      "type": "共感重視",
      "main_text": "メインテキスト",
      "sub_text": "サブテキスト",
      "composition": "写真構図",
      "expression": "表情",
      "pose": "ポーズ",
      "text_layout": "文字配置",
      "colors": "配色",
      "psychological_trigger": "想定する心理トリガー",
      "best_purpose": "どのような投稿目的に向いているか"
    }},
    {{
      "type": "意外性重視",
      "main_text": "メインテキスト",
      "sub_text": "サブテキスト",
      "composition": "写真構図",
      "expression": "表情",
      "pose": "ポーズ",
      "text_layout": "文字配置",
      "colors": "配色",
      "psychological_trigger": "想定する心理トリガー",
      "best_purpose": "どのような投稿目的に向いているか"
    }},
    {{
      "type": "保存・実用性重視",
      "main_text": "メインテキスト",
      "sub_text": "サブテキスト",
      "composition": "写真構図",
      "expression": "表情",
      "pose": "ポーズ",
      "text_layout": "文字配置",
      "colors": "配色",
      "psychological_trigger": "想定する心理トリガー",
      "best_purpose": "どのような投稿目的に向いているか"
    }}
  ]
}}
"""

# ── OGP サムネイル取得 ─────────────────────────────────────────────────────────

def _get_thumbnail_url(post_url: str) -> Optional[str]:
    """Instagram投稿URLからOGPスクレイピングでサムネイルURLを取得する。"""
    try:
        r = requests.get(
            post_url,
            timeout=15,
            headers={"User-Agent": OGP_USER_AGENT},
        )
        if r.status_code != 200:
            print(f"  [OGP] HTTP {r.status_code}: {post_url}")
            return None
        # content-type がHTMLかつJSONでない場合のみパース
        if "json" in r.headers.get("content-type", ""):
            return None
        og_images = re.findall(
            r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', r.text
        )
        if not og_images:
            # name="thumbnail" フォールバック
            og_images = re.findall(
                r'<meta[^>]+name="thumbnail"[^>]+content="([^"]+)"', r.text
            )
        if og_images:
            url = og_images[0].replace("&amp;", "&")
            return url
        return None
    except Exception as e:
        print(f"  [OGP] error: {e}")
        return None


def _download_image_b64(image_url: str) -> Optional[str]:
    """画像URLをダウンロードしてbase64文字列を返す。"""
    try:
        r = requests.get(image_url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200:
            return None
        content_type = r.headers.get("content-type", "image/jpeg")
        b64 = base64.b64encode(r.content).decode()
        return f"data:{content_type};base64,{b64}"
    except Exception as e:
        print(f"  [IMG] download error: {e}")
        return None


# ── OpenAI vision 呼び出し ───────────────────────────────────────────────────

def _get_openai_client():
    from openai import OpenAI
    from config import OPENAI_API_KEY
    return OpenAI(api_key=OPENAI_API_KEY)


def _analyze_thumbnail_with_vision(
    post: dict,
    image_b64: str,
) -> dict:
    """GPT-4o visionでサムネイルを分析する。"""
    label = f"thumbnail vision ({post.get('url','')[-20:]})"
    print(f"  [API START] {label}")

    user_prompt = _THUMBNAIL_ANALYSIS_PROMPT.format(
        url=post.get("url", ""),
        views=post.get("views", "不明"),
        likes=post.get("likes", "不明"),
        caption_head=str(post.get("caption", ""))[:100],
    )

    client = _get_openai_client()
    response = client.chat.completions.create(
        model=THUMBNAIL_MODEL,
        messages=[
            {"role": "system", "content": _THUMBNAIL_SYSTEM},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": image_b64, "detail": "high"},
                    },
                ],
            },
        ],
        temperature=0.3,
        response_format={"type": "json_object"},
        timeout=90,
        max_tokens=2000,
    )
    print(f"  [API END] {label}")
    raw = response.choices[0].message.content or "{}"
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"analysis_notes": f"JSON parse error: {raw[:200]}", "confidence": "低"}


def _generate_summary(analyses: list[dict]) -> dict:
    """全体傾向・提案をGPT-4o-miniで生成する（画像不使用）。"""
    print(f"  [API START] thumbnail summary ({len(analyses)} posts)")

    from openai import OpenAI
    from config import OPENAI_API_KEY

    # 各分析の要約だけを渡す（トークン節約）
    slim = []
    for a in analyses:
        slim.append({
            k: a.get(k, "")
            for k in [
                "post_url", "views", "thumbnail_type", "psychological_trigger",
                "scroll_stop_reason", "main_text", "sub_text", "emphasized_words",
                "background_color", "text_color", "person_present", "facial_expression",
                "pose", "applicable_points", "core_hari_thumbnail_idea",
            ]
        })

    prompt = _SUMMARY_PROMPT.format(
        n=len(analyses),
        analyses_json=json.dumps(slim, ensure_ascii=False, indent=2),
    )

    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": _SUMMARY_SYSTEM},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
        response_format={"type": "json_object"},
        timeout=90,
        max_tokens=3000,
    )
    print(f"  [API END] thumbnail summary")
    raw = response.choices[0].message.content or "{}"
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"analysis_notes": f"parse error: {raw[:200]}"}


# ── reels シートからデータ取得 ────────────────────────────────────────────────

def _load_reels_from_sheet(max_posts: int = MAX_POSTS_FULL) -> list[dict]:
    """
    Google Sheets の reels シートから候補投稿を取得する。
    優先順: 直近20日かつ再生数10万以上 → 条件を満たせない場合は緩和。
    """
    import gspread
    from google.oauth2.service_account import Credentials

    from config import GOOGLE_SHEET_ID, GOOGLE_SERVICE_ACCOUNT_JSON

    creds = Credentials.from_service_account_file(
        GOOGLE_SERVICE_ACCOUNT_JSON,
        scopes=[
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(GOOGLE_SHEET_ID)
    ws = sh.worksheet("reels")
    rows = ws.get_all_values()
    headers = rows[0]

    def col(name: str) -> Optional[int]:
        try:
            return headers.index(name)
        except ValueError:
            return None

    url_i     = col("投稿URL")
    views_i   = col("再生数")
    likes_i   = col("いいね数")
    date_i    = col("投稿日")
    cap_i     = col("キャプション全文")
    follow_i  = col("フォロワー数")
    comments_i = col("コメント数")

    if url_i is None:
        raise ValueError("reels シートに '投稿URL' 列が見つかりません")

    now = datetime.datetime.now(tz=datetime.timezone.utc)
    cutoff = now - datetime.timedelta(days=RECENT_DAYS)

    posts = []
    for row in rows[1:]:
        if not row or not row[url_i]:
            continue
        url = row[url_i].strip()
        if not url:
            continue

        def _int(idx):
            if idx is None or idx >= len(row):
                return 0
            try:
                return int(str(row[idx]).replace(",", "").strip() or "0")
            except ValueError:
                return 0

        views    = _int(views_i)
        likes    = _int(likes_i)
        comments = _int(comments_i)
        followers = _int(follow_i)
        caption  = row[cap_i].strip() if cap_i is not None and cap_i < len(row) else ""

        # 投稿日パース
        posted_at = None
        if date_i is not None and date_i < len(row) and row[date_i]:
            try:
                posted_at = datetime.datetime.fromisoformat(row[date_i].replace("Z", "+00:00"))
                if posted_at.tzinfo is None:
                    posted_at = posted_at.replace(tzinfo=datetime.timezone.utc)
            except (ValueError, AttributeError):
                posted_at = None

        posts.append({
            "url": url,
            "views": views,
            "likes": likes,
            "comments": comments,
            "followers": followers,
            "posted_at": row[date_i] if date_i and date_i < len(row) else "",
            "posted_at_dt": posted_at,
            "caption": caption,
            "view_follower_ratio": round(views / followers, 2) if followers else None,
        })

    # 優先フィルタ: 直近20日 かつ 再生数10万以上
    strict = [
        p for p in posts
        if p["views"] >= MIN_VIEWS
        and p["posted_at_dt"] is not None
        and p["posted_at_dt"] >= cutoff
    ]

    relaxed = False
    if len(strict) >= max_posts:
        candidates = sorted(strict, key=lambda p: p["views"], reverse=True)[:max_posts * 2]
    else:
        # 条件緩和: 再生数のみ（日付制限外す）
        relaxed = True
        candidates = sorted(
            [p for p in posts if p["views"] >= MIN_VIEWS],
            key=lambda p: p["views"],
            reverse=True,
        )[: max_posts * 2]
        if not candidates:
            # さらに緩和: 再生数制限も外す
            candidates = sorted(posts, key=lambda p: p["views"], reverse=True)[: max_posts * 2]

    # 重複URL除去
    seen = set()
    result = []
    for p in candidates:
        if p["url"] not in seen:
            seen.add(p["url"])
            result.append(p)
        if len(result) >= max_posts:
            break

    print(f"[THUMBNAIL] reels シートから {len(posts)} 件読み込み → 候補 {len(result)} 件")
    if relaxed:
        print("[THUMBNAIL] 注意: 直近20日×10万再生の条件を満たす投稿が不足したため、条件を緩和しました")

    return result, relaxed


# ── 重複チェック ───────────────────────────────────────────────────────────────

def _load_analyzed_urls() -> set[str]:
    """thumbnail_analysis シートに既に保存済みのURLセットを返す。"""
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        from config import GOOGLE_SHEET_ID, GOOGLE_SERVICE_ACCOUNT_JSON

        creds = Credentials.from_service_account_file(
            GOOGLE_SERVICE_ACCOUNT_JSON,
            scopes=[
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/drive",
            ],
        )
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(GOOGLE_SHEET_ID)
        try:
            ws = sh.worksheet("thumbnail_analysis")
            rows = ws.get_all_values()
            if len(rows) < 2:
                return set()
            headers = rows[0]
            if "post_url" not in headers:
                return set()
            idx = headers.index("post_url")
            return {r[idx] for r in rows[1:] if len(r) > idx and r[idx]}
        except gspread.exceptions.WorksheetNotFound:
            return set()
    except Exception as e:
        print(f"[THUMBNAIL] 既存URL取得エラー（スキップ）: {e}")
        return set()


# ── メイン処理 ────────────────────────────────────────────────────────────────

def run_thumbnail_analysis(test_mode: bool = False) -> dict:
    """
    サムネイル分析のメインエントリポイント。

    Args:
        test_mode: True の場合 3 件のみ分析

    Returns:
        {
            "analyses": list[dict],       # 各投稿の分析結果
            "summary": dict,              # 全体集計・提案
            "report_md": str,             # Markdownレポート
            "fetched": int,               # 取得試行数
            "analyzed": int,              # 分析成功数
            "skipped_urls": list[str],    # サムネイル取得失敗URL
            "relaxed": bool,              # 条件緩和フラグ
        }
    """
    max_posts = MAX_POSTS_TEST if test_mode else MAX_POSTS_FULL
    mode_label = "テスト（3件）" if test_mode else f"通常（最大{max_posts}件）"
    print(f"\n{'='*60}")
    print(f"  CORE HARI サムネイル分析 [{mode_label}]")
    print(f"{'='*60}\n")

    analyzed_urls = _load_analyzed_urls()
    print(f"[THUMBNAIL] 既分析済みURL: {len(analyzed_urls)} 件（重複スキップ）\n")

    posts, relaxed = _load_reels_from_sheet(max_posts=max_posts)

    analyses: list[dict] = []
    skipped_urls: list[str] = []
    fetched = 0

    for i, post in enumerate(posts, 1):
        url = post["url"]
        print(f"\n── [{i}/{len(posts)}] {url}")

        if url in analyzed_urls:
            print("  → 分析済みのためスキップ")
            continue

        # Step 1: サムネイルURL取得
        print("  Step1: OGPスクレイピング...")
        time.sleep(REQUEST_DELAY)
        thumb_url = _get_thumbnail_url(url)
        if not thumb_url:
            print("  → サムネイルURL取得失敗: スキップ")
            skipped_urls.append(url)
            continue

        # Step 2: 画像ダウンロード
        print(f"  Step2: 画像ダウンロード ({thumb_url[:60]}...)")
        image_b64 = _download_image_b64(thumb_url)
        if not image_b64:
            print("  → 画像ダウンロード失敗: スキップ")
            skipped_urls.append(url)
            continue

        fetched += 1
        print(f"  → 画像取得OK ({len(image_b64)//1024}KB base64)")

        # Step 3: GPT-4o vision 分析
        try:
            analysis = _analyze_thumbnail_with_vision(post, image_b64)
        except Exception as e:
            print(f"  → vision API エラー: {e}")
            skipped_urls.append(url)
            continue

        # メタ情報を付加
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = {
            "analyzed_at":        now_str,
            "post_url":           url,
            "account_name":       post.get("caption", "")[:20],  # キャプションから仮
            "posted_at":          post.get("posted_at", ""),
            "views":              post.get("views", 0),
            "likes":              post.get("likes", 0),
            "comments":           post.get("comments", 0),
            "followers":          post.get("followers", 0),
            "view_follower_ratio": post.get("view_follower_ratio", ""),
            "thumbnail_image_url": thumb_url,
            "caption_head":       str(post.get("caption", ""))[:200],
        }
        entry.update(analysis)
        analyses.append(entry)
        print(f"  → 分析完了: type={analysis.get('thumbnail_type','?')}, trigger={analysis.get('psychological_trigger','?')}")

    print(f"\n[THUMBNAIL] 分析完了: {len(analyses)}/{len(posts)} 件成功")

    # Step 4: 全体集計・提案生成
    summary: dict = {}
    if analyses:
        print("\n[THUMBNAIL] 全体集計・提案生成中...")
        try:
            summary = _generate_summary(analyses)
        except Exception as e:
            print(f"[THUMBNAIL] 集計エラー: {e}")
            summary = {"error": str(e)}
    else:
        print("[THUMBNAIL] 分析成功件数が0件のため集計をスキップ")

    # Step 5: レポート生成
    report_md = _build_report(analyses, summary, relaxed, skipped_urls)

    return {
        "analyses":    analyses,
        "summary":     summary,
        "report_md":   report_md,
        "fetched":     fetched,
        "analyzed":    len(analyses),
        "skipped_urls": skipped_urls,
        "relaxed":     relaxed,
    }


# ── Markdownレポート生成 ──────────────────────────────────────────────────────

def _build_report(
    analyses: list[dict],
    summary: dict,
    relaxed: bool,
    skipped_urls: list[str],
) -> str:
    today = datetime.date.today().strftime("%Y-%m-%d")
    cp    = summary.get("common_patterns", {})
    tc    = summary.get("type_counts", {})
    ideas = summary.get("reel_ideas", [])
    props = summary.get("thumbnail_proposals", [])

    lines = [
        f"# CORE HARI サムネイル分析レポート — {today}",
        "",
        "---",
        "",
        f"## 1. 今日の分析件数",
        f"- 分析成功: **{len(analyses)} 件**",
        f"- サムネイル取得失敗: {len(skipped_urls)} 件",
        "",
    ]

    if relaxed:
        lines += [
            "## 2. 条件について",
            "> ⚠️ 直近20日かつ再生数10万以上の投稿が不足したため、条件を緩和して取得しました。",
            "",
        ]
    else:
        lines += [
            "## 2. 条件",
            "- 直近20日以内、再生数10万以上の投稿を対象",
            "",
        ]

    # TOP10
    lines += ["## 3. 伸びているサムネイル TOP", ""]
    for i, a in enumerate(
        sorted(analyses, key=lambda x: x.get("views", 0), reverse=True)[:10], 1
    ):
        lines += [
            f"### {i}. {a.get('post_url','')}",
            f"- 再生数: {a.get('views',0):,} / いいね: {a.get('likes',0):,}",
            f"- 型: {a.get('thumbnail_type','?')} / 心理トリガー: {a.get('psychological_trigger','?')}",
            f"- メインテキスト: {a.get('main_text','判定不可')}",
            f"- 止まる理由: {a.get('scroll_stop_analysis','?')}",
            f"- CORE HARI応用案: {a.get('core_hari_thumbnail_idea','?')}",
            "",
        ]

    # 共通傾向
    def _s(v) -> str:
        if isinstance(v, list):
            return " / ".join(str(x) for x in v)
        return str(v) if v else "-"

    lines += [
        "## 4. 共通傾向",
        f"- よく使われる構成: {_s(cp.get('popular_composition'))}",
        f"- よく使われる文字数: {_s(cp.get('popular_text_length'))}",
        f"- よく使われる配色: {_s(cp.get('popular_colors'))}",
        f"- 人物の見せ方: {_s(cp.get('person_usage'))}",
        f"- よく使われる表情: {_s(cp.get('popular_expression'))}",
        f"- Hookの型: {_s(cp.get('popular_hook_types'))}",
        f"- 強調語: {_s(cp.get('popular_keywords'))}",
        f"- 伸びた/伸びなかった違い: {_s(cp.get('difference_analysis'))}",
        f"- 美容ジャンル特有: {_s(cp.get('beauty_specific'))}",
        f"- 直近の新傾向: {_s(cp.get('recent_trends'))}",
        "",
    ]

    # 型別集計
    lines += ["## 5. サムネイルの型別集計", ""]
    for t, cnt in tc.items():
        if cnt:
            lines.append(f"- {t}: {cnt} 件")
    lines.append("")

    # CORE HARI要素
    lines += [
        "## 7. CORE HARI FACEで使える要素",
        _s(summary.get("core_hari_elements")),
        "",
    ]

    # リール案
    lines += ["## 8. 今日作るべきリール案", ""]
    for j, idea in enumerate(ideas, 1):
        lines += [
            f"### リール案 {j}: {_s(idea.get('theme'))}",
            f"- 投稿目的: {_s(idea.get('purpose'))}",
            f"- 冒頭Hook: **{_s(idea.get('hook'))}**",
            f"- 3秒テロップ: {_s(idea.get('terop_3sec'))}",
            f"- サムネイル メイン: {_s(idea.get('thumbnail_main'))}",
            f"- サムネイル サブ: {_s(idea.get('thumbnail_sub'))}",
            f"- 構図: {_s(idea.get('composition'))}",
            f"- 表情: {_s(idea.get('expression'))}",
            f"- ポーズ: {_s(idea.get('pose'))}",
            f"- 文字位置: {_s(idea.get('text_position'))}",
            f"- 推奨配色: {_s(idea.get('colors'))}",
            f"- 強調ワード: {_s(idea.get('emphasis_word'))}",
            f"- Canva指示: {_s(idea.get('canva_instruction'))}",
            f"- 選定理由: {_s(idea.get('reason'))}",
            "",
        ]

    # サムネイル3案
    lines += ["## 9. サムネイル3案", ""]
    for prop in props:
        lines += [
            f"### {_s(prop.get('type'))}",
            f"- メインテキスト: **{_s(prop.get('main_text'))}**",
            f"- サブテキスト: {_s(prop.get('sub_text'))}",
            f"- 構図: {_s(prop.get('composition'))}",
            f"- 表情: {_s(prop.get('expression'))}",
            f"- ポーズ: {_s(prop.get('pose'))}",
            f"- 文字配置: {_s(prop.get('text_layout'))}",
            f"- 配色: {_s(prop.get('colors'))}",
            f"- 心理トリガー: {_s(prop.get('psychological_trigger'))}",
            f"- 適した投稿目的: {_s(prop.get('best_purpose'))}",
            "",
        ]

    # Canva指示（サムネイル案から）
    lines += ["## 10. Canva用デザイン指示", ""]
    for j, idea in enumerate(ideas, 1):
        if idea.get("canva_instruction"):
            lines.append(f"**リール案{j}**: {_s(idea['canva_instruction'])}")
    lines.append("")

    # 注意点
    lines += ["## 12. データ不足・取得失敗", ""]
    if skipped_urls:
        lines.append(f"以下の {len(skipped_urls)} 件はサムネイル取得に失敗しました:")
        for u in skipped_urls:
            lines.append(f"- {u}")
    else:
        lines.append("取得失敗なし")
    lines.append("")

    return "\n".join(lines)


# ── レポートファイル保存 ──────────────────────────────────────────────────────

def save_report(report_md: str) -> str:
    """Markdownレポートを reports/thumbnail/ に保存する。"""
    report_dir = os.path.join(os.path.dirname(__file__), "reports", "thumbnail")
    os.makedirs(report_dir, exist_ok=True)
    today = datetime.date.today().strftime("%Y-%m-%d")
    path = os.path.join(report_dir, f"{today}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(report_md)
    print(f"[THUMBNAIL] レポート保存: {path}")
    return path
