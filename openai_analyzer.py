"""
openai_analyzer.py
プール対象(構造的に使えるリール群、bright_data_fetcher.build_post_pool)を
OpenAIで分析するモジュール。

analyze_category_trend(category_label, posts) を、
「Instagram全体トレンド」に対して1回だけ呼び出す(集約分析)。

【2026-07-05: Trend Score → Research Candidate Scoreへのリネームに追従】
ユーザー要望「Trend Scoreを廃止してResearch Candidate Scoreを追加してほしい」に
対応し、trend_score.pyがresearch_candidate_score.pyへリネームされたことに伴い、
各分析関数のdocstring中の表記を「Research Candidate Score」に更新した
(analyze_post_structure/analyze_success_factors/generate_north_star_daily参照)。
OpenAI呼び出し内容・回数・コストへの影響はない。以下の【2026-06-29(6回目)】〜
【2026-07-04】の履歴は、リネーム前の「Trend Score」という名称だった時点の記録
であり、当時の意思決定の経緯(ユーザーの発言内容を含む)を正確に残すため
名称を書き換えずに保存している。

【2026-06-29(6回目): 投稿単位の分析を3段階パイプラインに再設計】
集約分析に加えて、Trend Scoreが高い投稿については以下の2段階のAI呼び出しを
投稿ごとに行う(詳細はprompts.pyのdocstring参照)。
- analyze_post_structure(post): ②AI分析。CORE HARI FACEへの変換はまだ行わず、
  元投稿そのものの「なぜ伸びたか」を構造的に分析する(POST_ANALYSIS_SYSTEM_PROMPT)。
- generate_core_hari_idea(post, analysis): ③CORE HARI FACE変換+④投稿案生成。
  analyze_post_structureの結果を入力として、CORE HARI FACE向けの具体的な
  投稿案を生成する(CORE_HARI_IDEA_SYSTEM_PROMPT)。
旧analyze_single_post(1回の呼び出しで分析+投稿案を同時に出す方式)は廃止した。

【2026-07-01(2回目): 成功要因分析(analyze_success_factors)を追加】
ユーザー要望により、Trend Score(数値配点)とは別に、AIによる「成功要因分析」
(なぜ伸びたか・冒頭3秒のフック・構成・CTA・心理トリガー・CORE HARI FACEへの
応用方法)を追加した。既存のanalyze_post_structure(13項目)と内容は重複する部分
があるが、ユーザーが「既存は維持し、新しい分析として追加する」ことを選んだため、
analyze_post_structure/generate_core_hari_ideaとは独立した3つ目のAI呼び出しと
して実装している(詳細はprompts.pyのSUCCESS_FACTOR_*のdocstring参照)。

【2026-07-01(3回目): SNS Pattern Lab投稿素材生成(generate_pattern_lab_content)を追加】
ユーザー要望により、analyze_success_factorsの結果を入力として、匿名ブランド
「SNS Pattern Lab」として発信できる投稿素材(Instagramカルーセル10枚・リール
台本・Threads投稿・キャプション、計21項目)を1回のOpenAI呼び出しで生成する
generate_pattern_lab_contentを追加した(詳細はprompts.pyのPATTERN_LAB_*の
docstring参照)。投稿1件あたりのOpenAI呼び出しは3回→4回に増える。

【2026-07-03: Creator Intelligence Sprint 1(Task A)— generate_north_star_dailyを追加】
ユーザー要望「North Star Dailyを生成する処理を追加してほしい」に対応する。
他の関数(analyze_post_structure等)は投稿1件ごとに呼ばれるが、
generate_north_star_dailyは1回の実行(main.py._score_and_analyze_posts)で
その日のentries全体(複数投稿)を入力にして1回だけ呼ばれる点が異なる。
入力は新規分析を追加せず、各entryのsuccess_factors/idea["投稿カテゴリ"]を
再利用する(詳細はprompts.pyのNORTH_STAR_DAILY_*のdocstring参照)。

【2026-07-04: North Star Daily Generatorの出力項目を9項目に再設計】
ユーザー要望によりNORTH_STAR_DAILY_TEXT_KEYS(9項目)を置き換えた(詳細は
prompts.pyのdocstring2026-07-04の項目参照)。generate_north_star_dailyの
挙動変更点: OpenAIに生成させるのはNORTH_STAR_DAILY_AI_KEYS(8項目、
「参考記事一覧」を除く)のみ。「参考記事一覧」はAIに生成させず、entries
各要素のpost["url"]を本関数側で機械的に列挙して結果dictに追加する
(URLをAIに生成させると実在しないURLを創作するリスクがあるため、決定的に
組み立てる方針)。OpenAI呼び出し回数自体は変わらず1回の実行で+1回。
"""

import json
import re

from openai import OpenAI

from config import OPENAI_API_KEY
from prompts import (
    SYSTEM_PROMPT,
    POST_ANALYSIS_SYSTEM_PROMPT,
    CORE_HARI_IDEA_SYSTEM_PROMPT,
    SUCCESS_FACTOR_SYSTEM_PROMPT,
    PATTERN_LAB_SYSTEM_PROMPT,
    NORTH_STAR_DAILY_SYSTEM_PROMPT,
    CATEGORY_ANALYSIS_TEXT_KEYS,
    CATEGORY_ANALYSIS_LIST_KEYS,
    CATEGORY_ANALYSIS_LIST_COUNT,
    POST_ANALYSIS_TEXT_KEYS,
    CORE_HARI_IDEA_TEXT_KEYS,
    SUCCESS_FACTOR_TEXT_KEYS,
    PATTERN_LAB_TEXT_KEYS,
    NORTH_STAR_DAILY_TEXT_KEYS,
    NORTH_STAR_DAILY_AI_KEYS,
    build_category_analysis_prompt,
    build_post_structure_analysis_prompt,
    build_core_hari_idea_prompt,
    build_success_factor_prompt,
    build_pattern_lab_prompt,
    build_north_star_daily_prompt,
)

MODEL_NAME = "gpt-4o-mini"

_client = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        if not OPENAI_API_KEY:
            raise EnvironmentError("OPENAI_API_KEY が設定されていません。")
        _client = OpenAI(api_key=OPENAI_API_KEY)
    return _client


def _try_parse_json(text: str):
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None


def _try_extract_json_block(text: str):
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def _fallback_from_plain_text(text: str, expected_keys: list) -> dict:
    """
    JSONとして解釈できなかった場合のフォールバック。
    'キー: 値' 形式の行を可能な限り拾い、それでも拾えなければ
    最初のキーに全文を入れて安全に復旧する。
    """
    result = {key: "" for key in expected_keys}

    for key in expected_keys:
        pattern = (
            r'["\']?' + re.escape(key) + r'["\']?\s*[:：]\s*["\']?(.+?)'
            r'(?=(?:["\']?,?\s*["\']?(?:'
            + "|".join(re.escape(k) for k in expected_keys)
            + r')["\']?\s*[:：])|$)'
        )
        match = re.search(pattern, text, re.DOTALL)
        if match:
            value = match.group(1).strip()
            value = value.strip(" \n\t\"',{}")
            result[key] = value

    if not any(result.values()) and expected_keys:
        result[expected_keys[0]] = text.strip()[:500]

    return result


def _parse_response_content(content: str, expected_keys: list) -> dict:
    parsed = _try_parse_json(content)
    if parsed is None:
        parsed = _try_extract_json_block(content)
    if parsed is None or not isinstance(parsed, dict):
        return _fallback_from_plain_text(content, expected_keys)
    return parsed


def _normalize_list_field(value, count: int = CATEGORY_ANALYSIS_LIST_COUNT) -> list:
    """
    タイトル案10個/冒頭フック10個のような配列項目を、
    必ずちょうどcount件の文字列リストに整える。
    """
    if isinstance(value, list):
        items = [str(v).strip() for v in value if str(v).strip()]
    elif isinstance(value, str) and value.strip():
        # 配列で返ってこなかった場合、改行や"、"区切りを試みる
        items = [v.strip(" -・") for v in re.split(r"\n|、", value) if v.strip(" -・")]
    else:
        items = []

    while len(items) < count:
        items.append("")

    return items[:count]


def _call_openai(user_prompt: str, system_prompt: str = SYSTEM_PROMPT, label: str = "OpenAI") -> str:
    print(f"[API START] {label}")
    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.8,
            response_format={"type": "json_object"},
            timeout=60,
        )
        print(f"[API END] {label}")
        return response.choices[0].message.content or ""
    except Exception as e:
        print(f"[API TIMEOUT] {label} skipped: {e}")
        raise


def analyze_category_trend(category_label: str, posts: list) -> dict:
    """
    プール対象のリール群(1カテゴリ分)をまとめて分析する。
    カテゴリごとに1回だけOpenAIを呼び出す(投稿ごとの個別分析は行わない)。

    戻り値: CATEGORY_ANALYSIS_TEXT_KEYS の各キー(文字列)と、
            CATEGORY_ANALYSIS_LIST_KEYS の各キー(10件の文字列リスト)を含む辞書。
    """
    prompt = build_category_analysis_prompt(category_label, posts or [])
    content = _call_openai(prompt, label=f"category trend ({category_label})")

    all_keys = CATEGORY_ANALYSIS_TEXT_KEYS + CATEGORY_ANALYSIS_LIST_KEYS
    parsed = _parse_response_content(content, all_keys)

    result = {}
    for key in CATEGORY_ANALYSIS_TEXT_KEYS:
        result[key] = str(parsed.get(key, "")).strip()
    for key in CATEGORY_ANALYSIS_LIST_KEYS:
        result[key] = _normalize_list_field(parsed.get(key))

    return result


def analyze_post_structure(post: dict) -> dict:
    """
    ②AI分析。Research Candidate Scoreが高い投稿1件について、CORE HARI FACEへの
    変換はまだ行わず、元投稿そのものの「なぜ伸びたか」を構造的に分析する。
    main.py._score_and_analyze_postsが投稿ごとに1回呼び出す
    (1件 = 1回のOpenAI呼び出し)。

    戻り値: POST_ANALYSIS_TEXT_KEYS の各キー(文字列)を含む辞書。
    """
    prompt = build_post_structure_analysis_prompt(post or {})
    content = _call_openai(prompt, system_prompt=POST_ANALYSIS_SYSTEM_PROMPT, label=f"post structure ({post.get('username','')})")

    parsed = _parse_response_content(content, POST_ANALYSIS_TEXT_KEYS)

    result = {}
    for key in POST_ANALYSIS_TEXT_KEYS:
        result[key] = str(parsed.get(key, "")).strip()

    return result


def generate_core_hari_idea(post: dict, analysis: dict) -> dict:
    """
    ③CORE HARI FACE変換 + ④投稿案生成。analyze_post_structure()の結果
    (analysis)を入力として、CORE HARI FACE向けの具体的な投稿案を生成する。
    main.py._score_and_analyze_postsが、②の直後に投稿ごとに1回呼び出す
    (1件 = 1回のOpenAI呼び出し。②と合わせて1投稿あたり計2回)。

    戻り値: CORE_HARI_IDEA_TEXT_KEYS の各キー(文字列)を含む辞書。
    """
    prompt = build_core_hari_idea_prompt(post or {}, analysis or {})
    content = _call_openai(prompt, system_prompt=CORE_HARI_IDEA_SYSTEM_PROMPT, label=f"core hari idea ({post.get('username','')})")

    parsed = _parse_response_content(content, CORE_HARI_IDEA_TEXT_KEYS)

    result = {}
    for key in CORE_HARI_IDEA_TEXT_KEYS:
        result[key] = str(parsed.get(key, "")).strip()

    return result


def analyze_success_factors(post: dict) -> dict:
    """
    成功要因分析(2026-07-01(2回目)追加)。Research Candidate Score(数値配点)
    とは別に、Research Candidate Scoreが高い投稿1件について「なぜ伸びたか・
    冒頭3秒のフック・構成・CTA・心理トリガー・CORE HARI FACEへの応用方法」を
    AIに分析させる。
    analyze_post_structure/generate_core_hari_ideaとは独立した呼び出しであり、
    どちらの結果も入力に使わない(元投稿の情報のみから分析する)。
    main.py._score_and_analyze_postsが投稿ごとに1回呼び出す
    (1件 = 1回のOpenAI呼び出し。②③+④と合わせて1投稿あたり計3回)。

    戻り値: SUCCESS_FACTOR_TEXT_KEYS の各キー(文字列)を含む辞書。
    """
    prompt = build_success_factor_prompt(post or {})
    content = _call_openai(prompt, system_prompt=SUCCESS_FACTOR_SYSTEM_PROMPT, label=f"success factors ({post.get('username','')})")

    parsed = _parse_response_content(content, SUCCESS_FACTOR_TEXT_KEYS)

    result = {}
    for key in SUCCESS_FACTOR_TEXT_KEYS:
        result[key] = str(parsed.get(key, "")).strip()

    return result


def generate_pattern_lab_content(post: dict, success_factors: dict) -> dict:
    """
    SNS Pattern Lab投稿素材生成(2026-07-01(3回目)追加)。analyze_success_factors
    の結果(success_factors)を入力として、匿名ブランド「SNS Pattern Lab」として
    発信できる投稿素材(Instagramカルーセル10枚・リール台本・Threads投稿・
    キャプション、計21項目)を1回のOpenAI呼び出しで生成する。post_analysis/
    core_hari_ideaの結果は入力に使わない(ユーザーが選んだ入力データの方針)。
    main.py._score_and_analyze_postsが、成功要因分析の直後に投稿ごとに1回呼び出す
    (1件 = 1回のOpenAI呼び出し。②③+④/成功要因分析と合わせて1投稿あたり計4回)。

    戻り値: PATTERN_LAB_TEXT_KEYS の各キー(文字列)を含む辞書。
    """
    prompt = build_pattern_lab_prompt(post or {}, success_factors or {})
    content = _call_openai(prompt, system_prompt=PATTERN_LAB_SYSTEM_PROMPT, label=f"pattern lab ({post.get('username','')})")

    parsed = _parse_response_content(content, PATTERN_LAB_TEXT_KEYS)

    result = {}
    for key in PATTERN_LAB_TEXT_KEYS:
        result[key] = str(parsed.get(key, "")).strip()

    return result


def generate_north_star_daily(entries: list, validated_patterns: list = None) -> dict:
    """
    North Star Daily Generator(2026-07-04再設計。旧Creator Intelligence
    Sprint 1 Task Aの9項目を置き換え)。他の分析関数(analyze_post_structure等)
    は投稿1件ごとに呼ばれるが、これは1回の実行(main.py._score_and_analyze_
    posts)でその日のentries全体を入力にして1回だけ呼ばれる(1日1件。投稿件数に
    比例してコストは増えない)。

    入力は新規分析を追加せず、各entryのsuccess_factors/idea["投稿カテゴリ"]を
    そのまま再利用する(ユーザーが選んだ入力データの方針。
    prompts.pyのNORTH_STAR_DAILY_*のdocstring参照)。

    entries: [{"post":..., "analysis":..., "idea":..., "success_factors":...,
               ...}, ...] 形式のリスト(main.py._score_and_analyze_postsが
              その日に分析した投稿の数だけ持つ。Research Candidate Score降順)。空リストの
              場合でもクラッシュせず、全項目が空文字のdictを返す。

    戻り値: NORTH_STAR_DAILY_TEXT_KEYS の各キー(文字列)を含む辞書。うち
            「参考記事一覧」はOpenAIには生成させず、entries各要素の
            post["url"]を改行区切りで列挙したものをこの関数側で組み立てる
            (URLをAIに生成させると実在しないURLを創作するリスクがあるため)。
    """
    entries = entries or []
    if not entries:
        return {key: "" for key in NORTH_STAR_DAILY_TEXT_KEYS}

    prompt = build_north_star_daily_prompt(entries, validated_patterns=validated_patterns or [])
    content = _call_openai(prompt, system_prompt=NORTH_STAR_DAILY_SYSTEM_PROMPT, label="north star daily")

    parsed = _parse_response_content(content, NORTH_STAR_DAILY_AI_KEYS)

    result = {}
    for key in NORTH_STAR_DAILY_AI_KEYS:
        result[key] = str(parsed.get(key, "")).strip()

    reference_urls = [
        (entry or {}).get("post", {}).get("url", "")
        for entry in entries
        if (entry or {}).get("post", {}).get("url")
    ]
    result["参考記事一覧"] = "\n".join(reference_urls) if reference_urls else "(なし)"

    return result


# ── Expert Interview ──────────────────────────────────────────────────────────
# 専門家インタビューエンジン。投稿はテーマからではなく会話から生まれる。
# 2コール/回: ① 質問生成、② Observation/Question/Perspective 抽出

_INTERVIEW_Q_SYSTEM = (
    "あなたはCreator Intelligence PlatformのCreator Conversationパートナーです。\n"
    "目的は「知識の収集」ではなく「専門家の観察・口ぐせ・感覚を引き出すこと」です。\n\n"
    "【禁止】\n"
    "  - 「〜ですか？」形式の確認・知識質問\n"
    "  - 「どう思いますか？」「何が重要ですか？」などの抽象的な問い\n"
    "  - リストアップ・箇条書きを引き出す質問\n\n"
    "【必須】\n"
    "  - 専門家がお客様に話しかけるような、自然な一言\n"
    "  - 現場の瞬間・口癖・感覚を引き出す問い\n"
    "  - 専門家しか言わない言葉・一言が出てくる問い\n\n"
    "回答は必ずJSON形式で。"
)

_INTERVIEW_EXTRACT_SYSTEM = (
    "あなたはCreator Intelligence Platformの思考抽出エンジンです。\n"
    "インタビュー記録から専門家の思考を3種類に分類・抽出します。\n"
    "専門家の言葉をできるだけそのまま残してください。要約・解釈は最小限に。\n"
    "回答は必ずJSON形式で。"
)


def generate_interview_questions(theme: str, vertical_name: str = "専門家") -> list:
    """
    Conversation Interview: 専門家の「会話」を引き出す10問を生成する。

    目的は知識収集ではなく、専門家がお客様に話しかけるような自然な言葉・
    口癖・現場の瞬間を引き出すこと。

    戻り値: 10個の質問文字列のリスト（生成失敗時はデフォルト10問）
    """
    prompt = (
        f"今日のテーマ: 「{theme}」\n"
        f"インタビュー対象: {vertical_name}\n\n"
        "このテーマで、専門家の「会話」を引き出す質問を10個作ってください。\n\n"
        "【禁止パターン】\n"
        "  ✗ 「〜について教えてください」\n"
        "  ✗ 「〜が重要だと思いますか？」\n"
        "  ✗ 「〜の原因は何ですか？」\n"
        "  → 知識・情報を聞く質問は全て禁止\n\n"
        "【良い質問の例】\n"
        "  ○ 朝起きた時どうですか？（と最近よく聞く）\n"
        "  ○ 施術中によく言う言葉は？\n"
        "  ○ 「頑張りすぎですね」みたいな、あなたしか言わない一言は？\n"
        "  ○ その人を見た瞬間、最初にどこを見ますか？\n"
        "  ○ お客様が一番勘違いしていることは？\n"
        "  ○ 最近よく言われることありますか？\n"
        "  ○ うまくいったとき、何が違いましたか？\n\n"
        "質問の条件:\n"
        "  - 短い（20文字以内を目安）\n"
        "  - 専門家が「あ、それ聞く」と思えるもの\n"
        "  - 答えると自然に専門家の口癖・感覚・信念が出てくるもの\n\n"
        'JSON形式で出力: {"questions": ["質問1", ..., "質問10"]}'
    )
    try:
        raw = _call_openai(prompt, system_prompt=_INTERVIEW_Q_SYSTEM,
                           label="expert interview: 質問生成")
        import json as _json
        data = _json.loads(raw)
        qs = data.get("questions", [])
        if isinstance(qs, list) and len(qs) >= 5:
            return qs[:10]
    except Exception as e:
        print(f"  ⚠️ 質問生成に失敗しました（デフォルト10問を使用）: {e}")

    # デフォルト10問（AI生成失敗時のフォールバック — Conversation Interview スタイル）
    return [
        f"「{theme}」で、最近よく言われることは？",
        "施術中によく言う言葉は？",
        "その人を見た瞬間、最初にどこを見ますか？",
        "お客様が一番勘違いしていることは？",
        "うまくいったとき、何が違いましたか？",
        "あなたしか言わない一言があるとしたら？",
        "朝起きた時どうですか？って、最近よく聞きますか？",
        "施術が終わった後、お客様がよく言う言葉は？",
        "これだけはやめてほしい、と思うことは？",
        "今日会ったお客様に、一言だけ伝えるとしたら？",
    ]


def extract_interview_insights(qa_pairs: list) -> dict:
    """
    インタビューQ&Aから Observation/Question/Perspective を抽出する。

    qa_pairs: [{"question": "...", "answer": "..."}, ...]

    戻り値:
        observation  : 専門家が現場で気づいたこと（原文に近い形で）
        question     : 専門家がクライアントに問いかける質問
        perspective  : 専門家独自の考え方・解釈
        speaker_words: 投稿の台本に直接使えるセリフ（専門家の言葉から組み立て）
        raw_qa       : 元のQ&Aリスト（保存用）
    """
    qa_text = "\n\n".join(
        f"Q: {pair['question']}\nA: {pair['answer']}"
        for pair in qa_pairs
        if pair.get("answer", "").strip()
    )

    if not qa_text.strip():
        return {
            "observation": "", "question": "", "perspective": "",
            "speaker_words": "", "raw_qa": qa_pairs,
        }

    prompt = (
        "以下は専門家へのインタビュー記録です。\n\n"
        f"{qa_text}\n\n"
        "この会話から以下を抽出してください。\n\n"
        "【抽出ルール】\n"
        "  - 専門家の実際の言葉をできるだけそのまま使う\n"
        "  - 要約・美化・解釈を加えない\n"
        "  - 空白の場合は空文字にする（作らない）\n\n"
        "Observation（専門家が現場で気づいたこと）:\n"
        "  現場の観察・所見・パターン。「〜することが多い」「〜を見てきた」形式で。\n\n"
        "Question（専門家がクライアントに問いかけること）:\n"
        "  実際に使う質問文。「〜ですか？」形式で。\n\n"
        "Perspective（専門家独自の考え方・解釈）:\n"
        "  他の専門家とは違う独自の視点。「〜だと思っています」「〜から考えています」形式で。\n\n"
        "speaker_words（投稿の台本候補）:\n"
        "  上記3つを組み合わせた「この人が話しかける」セリフ。改行区切りで複数文。\n"
        "  必ず「あなたに話しかける」形式にすること。\n\n"
        "JSON形式で出力:\n"
        '{"observation":"...","question":"...","perspective":"...","speaker_words":"..."}'
    )

    try:
        raw = _call_openai(prompt, system_prompt=_INTERVIEW_EXTRACT_SYSTEM,
                           label="expert interview: 思考抽出")
        import json as _json
        data = _json.loads(raw)
        return {
            "observation":   str(data.get("observation",   "")).strip(),
            "question":      str(data.get("question",      "")).strip(),
            "perspective":   str(data.get("perspective",   "")).strip(),
            "speaker_words": str(data.get("speaker_words", "")).strip(),
            "raw_qa":        qa_pairs,
        }
    except Exception as e:
        print(f"  ⚠️ 思考抽出に失敗しました: {e}")
        return {
            "observation": "", "question": "", "perspective": "",
            "speaker_words": "", "raw_qa": qa_pairs,
        }


# ── World Context Engine ──────────────────────────────────────────────────────
# 社会・生活・心理トレンドを合成する（1コール/日）

_WORLD_CONTEXT_SYSTEM = (
    "あなたはCreator Intelligence PlatformのWorld Context Engineです。\n"
    "SNSトレンドだけでなく、社会・生活・人々の心理を総合的に把握します。\n"
    "専門家が「今このタイミングで何を発信すべきか」の土台を作ります。\n"
    "回答は必ずJSON形式で。"
)


def get_world_context_trends(today: str, season_context: dict) -> dict:
    """
    今日の社会・生活・心理トレンドをAIが合成する（1コール）。

    season_context: world_context.get_season_context() の出力

    戻り値:
        social_trends    : 社会トレンド（ニュース・AI・経済・制度・イベントなど）
        life_trends      : 生活トレンド（消費・検索・SNS・旅行・口コミなど）
        psychology_trends: 心理トレンド（今人々が感じていること）
        hot_tension      : 今この瞬間の最大関心事・緊張感（1文）
        audience_mood    : ターゲット層（30〜40代女性）の今の気分
    """
    season   = season_context.get("season", "")
    month    = season_context.get("month", "")
    month_ctx = season_context.get("month_context", "")
    holiday  = season_context.get("holiday_context", "")
    uv       = season_context.get("uv_level", "")
    pollen   = season_context.get("pollen_level", "")

    prompt = (
        f"今日: {today}（{season}・{month}月）\n"
        f"季節文脈: {month_ctx}\n"
        f"紫外線: {uv} / 花粉: {pollen}\n"
        f"イベント・連休: {holiday}\n\n"
        "この日付・季節を踏まえて、以下を推測・合成してください。\n\n"
        "【social_trends】社会で今起きていること（3〜5点、箇条書き）\n"
        "  ニュース・AI動向・経済・制度変更・スポーツ・映画・ドラマなど\n\n"
        "【life_trends】人々の生活がどう変わっているか（3〜5点、箇条書き）\n"
        "  消費動向・検索トレンド・SNS・旅行・Amazon/楽天・口コミ傾向など\n\n"
        "【psychology_trends】今人々が感じていること（3〜5点、箇条書き）\n"
        "  不安・期待・疲れ・欲求・関心の変化など\n\n"
        "【hot_tension】今この瞬間の最大関心事・緊張感（1文、30文字以内）\n\n"
        "【audience_mood】30〜40代女性の今の気分・心理（1〜2文）\n"
        "  ※美容・健康・セルフケアに関心がある層を想定\n\n"
        'JSON: {"social_trends":"...","life_trends":"...","psychology_trends":"...","hot_tension":"...","audience_mood":"..."}'
    )

    try:
        raw = _call_openai(prompt, system_prompt=_WORLD_CONTEXT_SYSTEM,
                           label="world context: トレンド合成")
        import json as _json
        data = _json.loads(raw)
        return {
            "social_trends":     str(data.get("social_trends",     "")).strip(),
            "life_trends":       str(data.get("life_trends",       "")).strip(),
            "psychology_trends": str(data.get("psychology_trends", "")).strip(),
            "hot_tension":       str(data.get("hot_tension",       "")).strip(),
            "audience_mood":     str(data.get("audience_mood",     "")).strip(),
        }
    except Exception as e:
        print(f"  ⚠️ World Context AI取得失敗: {e}")
        return {
            "social_trends": "", "life_trends": "",
            "psychology_trends": "", "hot_tension": "", "audience_mood": "",
        }


# ── Creator Conversation（旧 Expert Interview）─────────────────────────────
# 専門家との「雑談」からObservation・口ぐせ・思い込みを収集する

_CONVERSATION_Q_SYSTEM = (
    "あなたはCreator Intelligence PlatformのCreator Conversationパートナーです。\n"
    "専門家と「雑談」してください。インタビューではありません。\n\n"
    "目的: Observation（繰り返し気づいていること）を引き出す\n\n"
    "【厳禁】\n"
    "  ✗ 「〜とは何ですか？」「〜について教えてください」（教科書質問）\n"
    "  ✗ 知識・理論を問う質問\n"
    "  ✗ 「はい/いいえ」で答えられる質問\n\n"
    "【良い質問の姿勢】\n"
    "  ○ 専門家がお客様に話しかけるように\n"
    "  ○ 「最近どうですか？」という感覚で\n"
    "  ○ 答えると自然に口ぐせ・感覚・観察が出てくる問い\n\n"
    "回答は必ずJSON形式で。"
)

_CONVERSATION_EXTRACT_SYSTEM = (
    "あなたはCreator Intelligence PlatformのObservation収集エンジンです。\n"
    "会話記録から専門家の「観察・口ぐせ・思い込み・思考」を抽出します。\n\n"
    "収集優先順位:\n"
    "  1位: Observation（繰り返し気づいていること）\n"
    "  2位: 口ぐせ（専門家が自然に使う言葉）\n"
    "  3位: 思い込み（クライアントの誤解・勘違い）\n"
    "  4位: Expert Thinking（専門家がどう考えるか）\n\n"
    "専門家の言葉をできるだけそのまま残す。要約・解釈を加えない。\n"
    "回答は必ずJSON形式で。"
)


def generate_conversation_questions(world_context: dict, vertical_name: str = "専門家") -> list:
    """
    Creator Conversation の質問を生成する（1コール）。

    World Context（季節・社会状況）を踏まえた「今ならではの質問」を生成。
    教科書質問は禁止。専門家がお客様に話しかけるような質問にする。

    戻り値: 10問以内の質問リスト（失敗時はデフォルト10問）
    """
    season    = world_context.get("season", "")
    hot       = world_context.get("hot_tension", "")
    month_ctx = world_context.get("month_context", "")
    psych     = world_context.get("psychology_trends", "")

    prompt = (
        f"今の季節・状況: {season}（{month_ctx}）\n"
        f"社会の関心: {hot}\n"
        f"人々の心理: {psych[:100] if psych else '（情報なし）'}\n"
        f"対象専門家: {vertical_name}\n\n"
        "この専門家と「雑談」するための質問を10問作ってください。\n\n"
        "【禁止】\n"
        "  ✗ 「〜とは何ですか？」「〜について教えてください」\n"
        "  ✗ 知識・理論を問う質問\n"
        "  ✗ はい/いいえで終わる質問\n\n"
        "【良い質問の例】（これをベースに今の季節・社会状況を反映する）\n"
        "  ○ 最近一番多い相談は？\n"
        "  ○ 最近気になっていることは？\n"
        "  ○ 最近驚いたことは？\n"
        "  ○ 施術やレッスンで最初に何を見ますか？\n"
        "  ○ 最近よく言う言葉は？\n"
        "  ○ お客様が一番勘違いしていることは？\n"
        "  ○ 帰る時によく言われる言葉は？\n"
        "  ○ 今年になって増えた悩みは？\n"
        "  ○ 季節で増える相談は？\n"
        "  ○ ニュースを見て最近思ったことは？\n\n"
        "質問は短く（20文字以内）。専門家が「あ、それある」と思えるもの。\n\n"
        'JSON: {"questions": ["質問1", ..., "質問10"]}'
    )

    try:
        raw = _call_openai(prompt, system_prompt=_CONVERSATION_Q_SYSTEM,
                           label="creator conversation: 質問生成")
        import json as _json
        data = _json.loads(raw)
        qs = data.get("questions", [])
        if isinstance(qs, list) and len(qs) >= 5:
            return qs[:10]
    except Exception as e:
        print(f"  ⚠️ 質問生成失敗（デフォルト使用）: {e}")

    # デフォルト10問（ユーザー指定の質問例をそのまま使う）
    return [
        "最近一番多い相談は？",
        "最近気になっていることは？",
        "最近驚いたことは？",
        "施術やレッスンで最初に何を見ますか？",
        "最近よく言う言葉は？",
        "お客様が一番勘違いしていることは？",
        "帰る時によく言われる言葉は？",
        f"今年になって増えた悩みは？",
        "季節で増える相談は？",
        "ニュースを見て最近思ったことは？",
    ]


def extract_conversation_insights(qa_pairs: list) -> dict:
    """
    Creator Conversation の回答からObservation・口ぐせ・思い込みを抽出する（1コール）。

    qa_pairs: [{"question": "...", "answer": "..."}, ...]

    戻り値:
        observations   : Observationリスト（最重要、複数）
        口ぐせ         : 専門家が自然に使う言葉・フレーズ
        思い込み       : クライアントがよく持つ誤解
        expert_thinking: 専門家の思考プロセス・判断軸
        speaker_words  : そのまま投稿の台本になりうるセリフ（改行区切り）
        raw_qa         : 元のQ&A（保存用）
    """
    qa_text = "\n\n".join(
        f"Q: {p['question']}\nA: {p['answer']}"
        for p in qa_pairs
        if p.get("answer", "").strip()
    )

    if not qa_text.strip():
        return {
            "observations": [], "口ぐせ": "", "思い込み": "",
            "expert_thinking": "", "speaker_words": "", "raw_qa": qa_pairs,
        }

    prompt = (
        "以下は専門家との会話記録です。\n\n"
        f"{qa_text}\n\n"
        "この会話から以下を抽出してください。\n\n"
        "【observations】専門家が繰り返し気づいていること（配列、1〜5件）\n"
        "  例: [\"朝起きると顎が疲れている人が多い\", \"頑張り屋さんほど食いしばる\"]\n\n"
        "【口ぐせ】専門家が自然に使う言葉・フレーズ（1〜2文）\n"
        "  例: 「流す前に、緩める」\n\n"
        "【思い込み】クライアントがよく持つ誤解・勘違い（1文）\n"
        "  例: マッサージで流せばむくみが取れると思っている\n\n"
        "【expert_thinking】専門家がどう考えるか・判断するか（1〜2文）\n"
        "  例: 私はまず咬筋を見ます。顔のたるみの多くは咬筋が原因だから。\n\n"
        "【speaker_words】そのまま投稿の台本になりうるセリフ（改行区切り）\n"
        "  ※専門家の言葉をできるだけそのまま使う\n\n"
        '{"observations":["..."],"口ぐせ":"...","思い込み":"...","expert_thinking":"...","speaker_words":"..."}'
    )

    try:
        raw = _call_openai(prompt, system_prompt=_CONVERSATION_EXTRACT_SYSTEM,
                           label="creator conversation: Observation抽出")
        import json as _json
        data = _json.loads(raw)
        obs = data.get("observations", [])
        if isinstance(obs, str):
            obs = [obs] if obs else []
        return {
            "observations":    obs,
            "口ぐせ":          str(data.get("口ぐせ",          "")).strip(),
            "思い込み":        str(data.get("思い込み",        "")).strip(),
            "expert_thinking": str(data.get("expert_thinking", "")).strip(),
            "speaker_words":   str(data.get("speaker_words",   "")).strip(),
            "raw_qa":          qa_pairs,
        }
    except Exception as e:
        print(f"  ⚠️ Observation抽出失敗: {e}")
        return {
            "observations": [], "口ぐせ": "", "思い込み": "",
            "expert_thinking": "", "speaker_words": "", "raw_qa": qa_pairs,
        }
