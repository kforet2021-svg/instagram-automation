"""
north_star_index.py
Creator Intelligence Sprint 1(Task C)— North Star Indexの土台。

【2026-07-05: Trend Score → Research Candidate Scoreへのリネームに追従】
ユーザー要望「Trend Scoreを廃止してResearch Candidate Scoreを追加してほしい」に
対応し、trend_score.pyがresearch_candidate_score.pyへリネームされたことに伴い、
本ファイルのMomentum項目が読む入力キーを post["trend_score"] から
post["research_candidate_score"] に更新した(_score_momentum参照)。採点ロジック・
配点(WEIGHTS)自体は変更していない。以下の【2026-07-03】〜【2026-07-04】の履歴は
リネーム前の「Trend Score」という名称だった時点の記録であり、当時の意思決定の
経緯を正確に残すため名称を書き換えずに保存している。

【2026-07-03新設】
ユーザー要望「Trend Scoreとは別に、North Star Indexの土台を追加してほしい。
最初は仮配点でよいので、後から調整しやすい設計にしてください」に対応する。

Trend Score(trend_score.py。再生数・再生倍率など実測可能な数値のみで構成される
0〜100点の指標)とは完全に別の指標として、「この投稿のパターンがCreator
Intelligenceとしてどれだけ価値があるか」を0〜100点で表す試験的なスコア。

設計方針:
- 新規のOpenAI呼び出しは追加しない(コスト増ゼロ)。すでに計算済みの
  trend_score.compute_trend_scoreの内訳(post["trend_score"]["breakdown"])と、
  すでに生成済みのsuccess_factors(openai_analyzer.analyze_success_factorsの
  出力、prompts.SUCCESS_FACTOR_TEXT_KEYS13項目)のテキストだけを入力に、
  ヒューリスティックに6項目を採点する。
- 6項目・配点(WEIGHTS)は仮の値であり、ユーザーが運用しながら調整することを
  前提にしている。各項目の採点ロジックを独立した_score_*関数に分離してあるため、
  「配点(WEIGHTS)だけを変える」か「採点ロジック自体を変える」かを別々に選べる。
- 2026-07-03時点ではどのシートにも保存していない(土台のみ)。main.pyの実行
  ログに要約を出力するだけ。ユーザーの指示「動作確認後に、creator_intelligence
  構成に整理します」に従い、シート化・精緻化は次のスプリント以降に判断する。

評価項目(ユーザー指定の6項目):
- Discovery(発見性)    : 視聴者にとって「これは知らなかった」と思わせる新規性。
- Psychology(心理設計)  : 心理トリガーが具体的・複数使われているか。
- Trust(信頼性)        : 顔出し・共感ストーリーなど、信頼を生む要素があるか。
- Education(教育性)    : 新しい知識・気づきを与えているか。
- Reproducibility(再現性): CORE HARI FACEなど他業種が型として再現しやすいか。
- Momentum(勢い)       : Trend Score側の再生倍率・直近性が高いか(ここだけは
                          Trend Scoreの既存の得点を再利用する実測値ベースの項目。
                          Trend Score合計そのものには影響しない、完全に別の
                          指標として扱う)。

【2026-07-04(2回目): Creator Intelligence Sprint 2(Task5)— COMPONENTS設定化】
ユーザー要望「現在の6項目(Discovery/Psychology/Trust/Education/Reproducibility/
Momentum)を、新しい項目を追加しやすいよう設定管理(config)にしてほしい」に対応する。

従来は「WEIGHTS辞書(配点) + 個別の_score_*関数(post or success_factorsのどちらか
片方だけを受け取り、配点を内部で乗算済みの点数を返す)」という、項目ごとに引数も
戻り値の意味もバラバラな実装だった。これでは新しい項目を1つ追加するたびに
WEIGHTSへのキー追加・専用関数の追加・compute_north_star_index内のbreakdown組み立て
コードの3箇所を手で揃える必要があり、「設定を変えるだけ」では済まなかった。

今回、以下のように統一した:
1. 各_score_*関数のシグネチャを (post, success_factors) -> float (0.0〜1.0の比率)
   に統一した(配点の乗算はしない。Momentumのようにpostしか使わない項目も
   success_factorsを受け取るだけで無視してよい)。
2. COMPONENTS(リスト)に {"key": ..., "weight": ..., "scorer": ...} を1項目1エントリで
   定義した。新しい評価軸を増やす場合、COMPONENTSにエントリを1つ追加し、対応する
   0.0〜1.0の比率を返す関数を書くだけでよい(WEIGHTS/INDEX_KEYSは下のとおり
   COMPONENTSから自動的に導出されるため、手で揃える箇所が1箇所に減った)。
3. WEIGHTS・INDEX_KEYSは後方互換のため引き続き公開するが、COMPONENTSから
   導出した読み取り専用の値になった(他モジュールがWEIGHTS/INDEX_KEYSを
   import している場合に備えた互換性維持。2026-07-04時点ではnorth_star_index.py
   の外部からの参照は無いが、念のため残す)。

配点(各項目の重み)自体はユーザー指定の仮配点(Discovery15/Psychology20/Trust15/
Education15/Reproducibility20/Momentum15、合計100)を変更していない。
"""

# success_factorsのテキスト項目が「判断不可/不明/なし」系の空振り回答だった場合、
# シグナルなし(0点側)とみなすためのマーカー。
_UNKNOWN_MARKERS = ("判断不可", "不明", "使用なし", "なし")


def _has_signal(text: str) -> bool:
    """success_factorsのテキスト項目が空振り(判断不可/不明/なし系)でないか判定する。"""
    if not text:
        return False
    stripped = str(text).strip()
    if not stripped:
        return False
    return not any(marker in stripped for marker in _UNKNOWN_MARKERS)


# --- 各評価軸の採点関数(2026-07-04(2回目): シグネチャを(post, success_factors)に統一し、
#     戻り値は0.0〜1.0の比率にした。配点(重み)の乗算はcompute_north_star_indexが
#     COMPONENTSの定義に従って一括で行う) ---


def _score_discovery(post: dict, success_factors: dict) -> float:
    """「伸びた理由」「冒頭3秒のフック」に具体的な記述があるほど発見性が高いと仮定する。"""
    success_factors = success_factors or {}
    hits = sum(
        _has_signal(success_factors.get(key, ""))
        for key in ("伸びた理由", "冒頭3秒のフック")
    )
    return hits / 2


def _score_psychology(post: dict, success_factors: dict) -> float:
    """
    「心理トリガー」欄の充実度を、テクニック名の区切り記号「・」の個数で近似する
    (SUCCESS_FACTOR_SYSTEM_PROMPTが「・」区切りで複数列挙するよう指示しているため)。
    """
    text = (success_factors or {}).get("心理トリガー", "") or ""
    if not _has_signal(text):
        return 0.0
    technique_count = text.count("・") + 1
    return min(technique_count / 2, 1.0)


def _score_trust(post: dict, success_factors: dict) -> float:
    """「顔出し有無」「共感ストーリー」のうち、信頼を生む方向の記述があるかで近似する。"""
    success_factors = success_factors or {}
    hits = sum(
        _has_signal(success_factors.get(key, ""))
        for key in ("顔出し有無", "共感ストーリー")
    )
    return hits / 2


def _score_education(post: dict, success_factors: dict) -> float:
    """「教育性」欄に具体的な記述があるかで近似する(二値:満点 or 0点)。"""
    return 1.0 if _has_signal((success_factors or {}).get("教育性", "")) else 0.0


def _score_reproducibility(post: dict, success_factors: dict) -> float:
    """「CORE HARI FACEへの応用方法」「構成」に具体的な記述があるほど型として再現しやすいと仮定する。"""
    success_factors = success_factors or {}
    hits = sum(
        _has_signal(success_factors.get(key, ""))
        for key in ("CORE HARI FACEへの応用方法", "構成")
    )
    return hits / 2


def _score_momentum(post: dict, success_factors: dict) -> float:
    """
    Research Candidate Score側で既に計算済みの「再生倍率」(0〜30点)・「投稿からの
    日数」(0〜10点。research_candidate_score.BREAKDOWN_KEYS参照)の得点を0〜1に
    正規化する(2026-07-05: trend_score.pyからのリネームに伴い入力キーを変更。
    以前は post["trend_score"] を読んでいた)。実測値の再利用であり、新たな採点
    ロジックは追加しない(Research Candidate Score合計そのものには影響を与えない、
    完全に別の指標)。success_factorsは使わない(引数の形を他の評価軸と揃える
    ためだけに受け取る)。
    """
    breakdown = ((post or {}).get("research_candidate_score") or {}).get("breakdown") or {}
    multiplier_score = breakdown.get("再生倍率", 0) or 0  # 0〜30点
    recency_score = breakdown.get("投稿からの日数", 0) or 0  # 0〜10点
    normalized = (multiplier_score / 30 + recency_score / 10) / 2
    return min(normalized, 1.0)


# --- COMPONENTS設定(2026-07-04(2回目)新設) ---
#
# 新しい評価軸を増やす場合は、ここに1エントリ追加し、(post, success_factors)->
# 0.0〜1.0の比率を返す関数を1つ書くだけでよい。配点(weight)の合計が100になる
# ことを想定しているが、強制はしていない(運用しながら調整する仮配点のため)。
COMPONENTS = [
    {"key": "Discovery", "weight": 15, "scorer": _score_discovery},
    {"key": "Psychology", "weight": 20, "scorer": _score_psychology},
    {"key": "Trust", "weight": 15, "scorer": _score_trust},
    {"key": "Education", "weight": 15, "scorer": _score_education},
    {"key": "Reproducibility", "weight": 20, "scorer": _score_reproducibility},
    {"key": "Momentum", "weight": 15, "scorer": _score_momentum},
]

# 後方互換用(COMPONENTSから導出。他モジュールが直接importしている場合に備える)。
WEIGHTS = {c["key"]: c["weight"] for c in COMPONENTS}
INDEX_KEYS = [c["key"] for c in COMPONENTS]


def compute_north_star_index(post: dict, success_factors: dict) -> dict:
    """
    投稿1件についてNorth Star Index(0〜100点、仮配点)を計算する。
    新規のOpenAI呼び出しは行わない(既存のResearch Candidate Score内訳と
    success_factorsのテキストのみを入力にしたヒューリスティック)。

    post: research_candidate_score.score_posts()済み(post["research_candidate_score"]
          を持つ)投稿。
    success_factors: openai_analyzer.analyze_success_factorsの戻り値dict。

    戻り値: {"total": float, "breakdown": {"Discovery": ..., "Psychology": ...,
             "Trust": ..., "Education": ..., "Reproducibility": ...,
             "Momentum": ...}} (breakdownのキーはCOMPONENTSの定義順)。
    """
    success_factors = success_factors or {}
    post = post or {}

    breakdown = {}
    for component in COMPONENTS:
        fraction = component["scorer"](post, success_factors)
        breakdown[component["key"]] = round(component["weight"] * fraction, 1)

    total = round(sum(breakdown.values()), 1)
    return {"total": total, "breakdown": breakdown}
