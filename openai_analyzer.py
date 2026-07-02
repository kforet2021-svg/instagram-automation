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
