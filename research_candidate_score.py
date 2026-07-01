"""
research_candidate_score.py
取得・プール済みの投稿1件ごとに「Research Candidate Score」(0〜100点)を計算するモジュール。

【2026-07-05: trend_score.py からのリネーム + AI分析しきい値ゲート復活】
ユーザー要望:「Trend Scoreを廃止してください。代わりにResearch Candidate Scoreを
追加してください。研究対象として価値がある投稿だけをAI分析対象にしてください。」

対応方針(実装前にAskUserQuestionでユーザーに確認済み):
1. 採点項目(7項目・配点)はそのまま変更しない。今回はリネームのみ
   (名前を「Trend Score」→「Research Candidate Score」に変更しただけで、
   計算ロジック・重みは一切変更していない。ユーザー回答:「同じ項目をそのまま
   使う(名前だけ変更)」)。
2. 2026-07-02に廃止した「AI分析実行のスコアしきい値ゲート」を復活させた
   (ユーザー回答:「しきい値ゲートを復活させる」)。select_for_analysisを
   「フィルタなしで常に上位N件」から「ANALYSIS_MIN_SCORE(80点)以上の投稿の
   中から上位top_n件」に戻した。この結果、その日の取得結果が全体的に低スコア
   な場合、AI分析対象が0件になることがある(2026-07-02時点ではこれを問題として
   「常に5件」に変更したが、今回はユーザーが「研究対象として価値がある投稿
   だけをAI分析対象にする」ことを明示的に優先する判断をしたため、0件になる
   ことを許容する設計に戻した)。0件の場合にmain.py側がエラーにならないよう、
   main.py側でも空リストを前提にしたハンドリングを確認すること。

以下の【2026-06-29〜2026-07-02】の履歴は、リネーム前の「Trend Score」という
名称で実装されていた時点の記録であり、当時の意思決定の経緯を正確に残すため
名称を書き換えずに保存している(項目・配点・しきい値の値自体は今回変更して
いないため、内容は引き続き有効)。

【背景・目的(2026-06-29(5回目))】
ユーザー要望:「取得した投稿ごとにTrend Scoreを計算し、スコアが高い投稿だけを
AI分析する」。目的はAI(OpenAI)分析コストを「本当に伸びている投稿」に絞り込み、
かつ投稿単位でCORE HARI FACE向け投稿案への変換しやすさを事前に判定すること。

【2026-06-29(6回目): ヒューリスティック2項目を測定可能な2項目に置き換え】
ユーザーが開発優先順位を変更し、「Trend Scoreエンジン」を以下の要件で
再定義した:「評価項目は最低でも、再生数・フォロワー数に対する再生倍率・
いいね率・コメント率・投稿からの日数・動画時間・投稿頻度」。

これに伴い、5回目で実装した2つのキーワードヒューリスティック項目
(「保存されやすそうな構成」「美容以外でも応用できる型」)はTrend Scoreから
完全に削除した。理由は、これらがキャプションのキーワード・構造を推定するだけの
一次フィルタであり、ユーザーが明示的に列挙した新しい評価項目(動画時間・
投稿頻度)はどちらもBright Dataの実データから直接測定できる値であり、
キーワード推定より信頼できるため。
(「保存されやすいかどうか」「美容以外でも応用できる型かどうか」の判断自体は
無価値になったわけではなく、後段のAI分析(openai_analyzer.analyze_post_structure)
側で「保存したくなる理由」「美容ジャンルに転用できる型」として、より精度の高い
言語モデルによる分析に役割を移した)

【評価項目と配点(合計100点)】
- 再生数                            : 10点 (2026-07-01(2回目)に20点→10点へ変更。下記参照)
- フォロワー数に対する再生倍率       : 30点 (= bright_data_fetcher.view_multiplier。
                                       2026-07-01(2回目)に20点→30点へ変更。下記参照)
- いいね率(いいね数 ÷ 再生数)       : 15点
- コメント率(コメント数 ÷ 再生数)    : 15点
- 投稿からの日数(新しいほど高得点)   : 10点
- 動画時間                          : 10点 (※実測値。下記の重要な注意を参照)
- 投稿頻度                          : 10点 (※実測値。下記の重要な注意を参照)

【重要な注意: 動画時間・投稿頻度の2項目について】
どちらも実際のAPIレスポンスから取得できる実測値であり、キャプションの
キーワード推定ではない。

- 動画時間(_score_duration): bright_data_fetcher._normalize_postのduration_sec
  (Bright Data "length" フィールド)を使う。Instagramリールは15〜60秒程度が
  視聴維持率・完了率の観点で最も伸びやすい帯と一般的に言われているため、
  この帯を満点とし、極端に短い/長い動画は減点する単純な帯評価にしている
  (キャプションの文言は一切見ない)。

- 投稿頻度(_score_post_frequency): post["account_post_count_window"]
  (bright_data_fetcher._attach_account_post_countsが付与する、今回の取得窓
  ―直近RECENT_DAYS日以内・1アカウントあたり最大DEFAULT_RESULTS_PER_ACCOUNT件
  ―の中で、同じsource_accountから実際に取得できた投稿数)を使う。
  「投稿頻度が高いアカウントから、かつ伸びている投稿」は、単発のバズではなく
  再現性のある(コピーする価値が高い)型である可能性が高いという考え方に基づく。
  ※ Bright Dataは1回の取得でアカウントの「投稿頻度」(例: 週何本投稿している
  か)を直接は返さないため、この「取得窓内での観測件数」を投稿頻度の実測代理
  指標として使っている。取得窓(RECENT_DAYS・DEFAULT_RESULTS_PER_ACCOUNT)の
  設定次第で値の意味が変わる点に注意。

いずれも完璧な指標ではないが、キャプションのキーワード推定ヒューリスティック
よりも実データに基づく分、Research Candidate Scoreの一次フィルタとしての
信頼性は高い(投稿の本当の構成評価・「なぜ伸びたか」の言語化は、スコアで
選ばれた投稿に対して後段で実行するAI分析(openai_analyzer.analyze_post_structure)
が行う)。

【スコアによる判定(ユーザー指定の目安)】
- 90点以上 : 必ず分析   (TIER_MUST_ANALYZE)
- 80点以上 : 投稿案候補 (TIER_CANDIDATE)
- それ未満 : 保存のみ   (TIER_SAVE_ONLY。research_candidatesシートへの記録のみで、
                          AI分析は行わずコストを抑える)

※ ユーザー指定の目安には「70点未満:保存のみ」とあり、80点と70点の間
  (70〜79点)の扱いが明示されていない。本実装では「AI分析するのはスコアが
  高い投稿だけ」というユーザーの目的(コスト最小化)を優先し、80点未満は一律で
  「保存のみ」として扱う(=AI分析の実行しきい値ANALYSIS_MIN_SCOREを80点の
  1本に統一する)。70〜79点を別扱いにしたい場合は要望を伝えてください。
  (6回目の要望でもこの閾値構成自体は変更されていないため、5回目の判断を維持する)

【2026-07-01: trend_score_debugシートで配点内訳を確認できるようにした】
実運用で「25件取得したのに80点以上が0件だった」という事象が発生した。
本ファイル自体のスコアリングロジック(_score_*関数群・しきい値)は変更して
いないが、ユーザーが各投稿の生値(再生数・フォロワー数・再生倍率・いいね率・
コメント率・投稿日など)と得点をセットで確認し、配点しきい値を調整するための
sheets_writer.save_research_candidate_score_debug()・research_candidate_score_debug
シートを追加した(詳細はsheets_writer.pyのdocstring参照)。配点を調整する場合は、
本ファイルの_score_views/_score_view_multiplier/_score_like_rate/_score_comment_rate/
_score_recency/_score_duration/_score_post_frequencyの各しきい値を編集する。

【2026-07-02: select_for_analysisのANALYSIS_MIN_SCORE(80点)ゲートを廃止し、
常にTrend Score上位5件をAI分析対象にする(※2026-07-05に下記の通り再度復活させた)】
実運用で「80点以上が0件」となる日が続き、AI分析が一切実行されないという
事態が発生した。ユーザーから明確な方針が示された:「目的は『高品質な投稿を
分析すること』であり、80点以上を集めることではない。Trend Scoreはランキング
用に使う。上位5件は必ずAI分析する。80点以上という条件は廃止する」。

対応として、select_for_analysisを「スコアでフィルタしてから上位N件」から
「フィルタなしで常に上位N件(TOP_N_FOR_ANALYSIS=5)」に変更した。
ANALYSIS_MIN_SCORE/SCORE_THRESHOLD_MUST_ANALYZE/SCORE_THRESHOLD_CANDIDATEと
classify_tierによる「必ず分析/投稿案候補/保存のみ」というラベルは廃止せず
残している(research_candidates/research_candidate_score_debugシート上で投稿の
相対的な質を一目で判断する表示用ラベルとして有用なため)が、AI分析を実行するか
どうかの判定には(2026-07-05に復活させるまでは)使われていなかった。

旧MAX_ANALYZED_POSTS_PER_RUN(80点以上が多数出た場合の安全弁としての上限10件)
は、この変更により構造的に不要になった(常に最大5件しか選ばれない設計になった
ため)。混乱を避けるため削除した。

【2026-07-01(2回目): _score_views/_score_view_multiplierを段階評価に変更
+ 再生倍率の配点を重視】
trend_score_debugシートで実データを確認した結果を踏まえ、ユーザーから
「10万再生未満で0点、再生倍率1倍未満で0点という設計だと、小規模アカウントの
成功事例(再生数は少ないがフォロワー数に対する伸び=再生倍率は高い投稿)が
正当に評価されない。段階評価に変更し、特に再生倍率を重視してほしい」との
要望があった。対応として以下を変更した。

1. _score_views: 10万再生未満を一律0点にしていた閾値を撤廃し、1,000再生
   以上から段階的に加点する設計に変更した(0点になるのは1,000再生未満の
   ごく少数のみ)。
2. _score_view_multiplier: 倍率1.0未満を一律0点にしていた閾値を撤廃し、
   倍率0より大きければ段階的に加点する設計に変更した。
3. 「再生倍率を重視」という要望に対応するため、配点の合計100点は変えずに
   再生数の最大点を20点→10点に下げ、その10点分を再生倍率の最大点20点→30点
   に上乗せした(BREAKDOWN_KEYSの項目構成・他5項目の配点は変更していない)。
   フォロワー規模に対してどれだけ伸びているか(=再生倍率)を、絶対的な
   再生数の多さより重い指標として扱う、という今回の要望を最も直接的に
   反映する変更だと判断したため。
4. 注意: 上記の変更後も、いいね率・コメント率・投稿頻度などが低い投稿は
   80点(ANALYSIS_MIN_SCORE)に届かない場合がある。80点というAI分析実行の
   しきい値自体は今回変更していない。trend_score_debugシートで実データの
   新しい得点を確認し、なお80点に届きにくい場合は、ANALYSIS_MIN_SCORE自体を
   下げるかどうかを別途検討してください(本ファイルの配点ロジックを再度
   触る前に、まずは実データで様子を見ることを推奨)。
"""

import datetime as dt

# --- スコアしきい値・判定ラベル ---
SCORE_THRESHOLD_MUST_ANALYZE = 90
SCORE_THRESHOLD_CANDIDATE = 80

TIER_MUST_ANALYZE = "必ず分析"
TIER_CANDIDATE = "投稿案候補"
TIER_SAVE_ONLY = "保存のみ"

# 表示用ラベル(classify_tier)のしきい値。2026-07-05: AI分析を実行するかどうかの
# 判定にも再びこの値を使う(select_for_analysis参照。2026-07-02〜2026-07-05の間は
# 表示用ラベルのみで使われていた)。
ANALYSIS_MIN_SCORE = SCORE_THRESHOLD_CANDIDATE

# AI個別分析(openai_analyzer.analyze_post_structure / generate_core_hari_idea等)を
# 実行する最大件数。2026-07-05: ANALYSIS_MIN_SCORE以上の投稿の中から、この件数を
# 上限に上位を選ぶ(select_for_analysis参照。ANALYSIS_MIN_SCORE以上が0件の日は
# AI分析対象も0件になる)。
TOP_N_FOR_ANALYSIS = 5

# 視聴維持・完了率の観点で最も伸びやすいとされる動画尺の範囲(秒)。
# 帯の外側は段階的に減点する(モジュールdocstring参照)。
_DURATION_BEST_RANGE = (15, 60)
_DURATION_OK_RANGE = (8, 90)
_DURATION_MARGINAL_RANGE = (3, 120)

BREAKDOWN_KEYS = [
    "再生数",
    "再生倍率",
    "いいね率",
    "コメント率",
    "投稿からの日数",
    "動画時間",
    "投稿頻度",
]


def _score_views(views: int) -> int:
    """
    2026-07-01(2回目): 旧版は10万再生未満を一律0点にしていたが、小規模
    アカウントの成功事例(絶対的な再生数は少ない)も正当に評価できるよう、
    1,000再生以上から段階的に加点する設計に変更した(満点は20点→10点に
    減らし、減らした10点は_score_view_multiplierに上乗せした。モジュール
    docstring参照)。
    """
    if views >= 10_000_000:
        return 10
    if views >= 5_000_000:
        return 9
    if views >= 1_000_000:
        return 8
    if views >= 500_000:
        return 7
    if views >= 200_000:
        return 6
    if views >= 100_000:
        return 5
    if views >= 50_000:
        return 4
    if views >= 20_000:
        return 3
    if views >= 5_000:
        return 2
    if views >= 1_000:
        return 1
    return 0


def _score_view_multiplier(view_multiplier) -> int:
    """
    2026-07-01(2回目): 旧版は倍率1.0未満を一律0点にしていたが、「再生倍率を
    重視してほしい」という要望に対応し、(a)倍率0より大きければ段階的に
    加点する設計に変更し、(b)満点を20点→30点に上げた(_score_viewsから
    移した10点分。モジュールdocstring参照)。フォロワー数に対する伸びを
    Research Candidate Score全体の中で最も重い指標として扱う。
    """
    if not view_multiplier or view_multiplier <= 0:
        return 0
    if view_multiplier >= 20:
        return 30
    if view_multiplier >= 10:
        return 26
    if view_multiplier >= 5:
        return 22
    if view_multiplier >= 3:
        return 18
    if view_multiplier >= 2:
        return 14
    if view_multiplier >= 1:
        return 10
    if view_multiplier >= 0.7:
        return 7
    if view_multiplier >= 0.4:
        return 4
    if view_multiplier >= 0.2:
        return 2
    return 1


def _score_like_rate(likes: int, views: int) -> int:
    if not views:
        return 0
    rate = likes / views
    if rate >= 0.10:
        return 15
    if rate >= 0.07:
        return 12
    if rate >= 0.05:
        return 9
    if rate >= 0.03:
        return 6
    if rate >= 0.01:
        return 3
    return 0


def _score_comment_rate(comments: int, views: int) -> int:
    if not views:
        return 0
    rate = comments / views
    if rate >= 0.01:
        return 15
    if rate >= 0.005:
        return 12
    if rate >= 0.002:
        return 9
    if rate >= 0.001:
        return 6
    if rate >= 0.0003:
        return 3
    return 0


def _score_recency(posted_at_dt) -> int:
    if posted_at_dt is None:
        return 0
    now = dt.datetime.now(dt.timezone.utc)
    days = (now - posted_at_dt).total_seconds() / 86400
    if days <= 2:
        return 10
    if days <= 5:
        return 8
    if days <= 10:
        return 6
    if days <= 15:
        return 4
    if days <= 20:
        return 2
    return 0


def _score_duration(duration_sec) -> int:
    """
    ※実測値(モジュールdocstring参照)。bright_data_fetcherのduration_sec
    (Bright Data "length" フィールド)をそのまま使う。キャプションのキーワード
    推定は行わない。
    """
    if duration_sec is None:
        return 0
    if _DURATION_BEST_RANGE[0] <= duration_sec <= _DURATION_BEST_RANGE[1]:
        return 10
    if _DURATION_OK_RANGE[0] <= duration_sec <= _DURATION_OK_RANGE[1]:
        return 7
    if _DURATION_MARGINAL_RANGE[0] <= duration_sec <= _DURATION_MARGINAL_RANGE[1]:
        return 4
    return 0


def _score_post_frequency(account_post_count_window) -> int:
    """
    ※実測値(モジュールdocstring参照)。bright_data_fetcher._attach_account_
    post_countsが付与するpost["account_post_count_window"](今回の取得窓内で
    同じアカウントから取得できた投稿数)を使う。
    """
    if not account_post_count_window:
        return 0
    if account_post_count_window >= 8:
        return 10
    if account_post_count_window >= 6:
        return 8
    if account_post_count_window >= 4:
        return 6
    if account_post_count_window >= 2:
        return 3
    return 0


def classify_tier(total: int) -> str:
    if total >= SCORE_THRESHOLD_MUST_ANALYZE:
        return TIER_MUST_ANALYZE
    if total >= SCORE_THRESHOLD_CANDIDATE:
        return TIER_CANDIDATE
    return TIER_SAVE_ONLY


def compute_research_candidate_score(post: dict) -> dict:
    """
    投稿1件のResearch Candidate Score(0〜100点)を計算する。

    post: bright_data_fetcher._normalize_post() が返す投稿dict
          (views, likes, comments, view_multiplier, posted_at_dt, duration_sec,
          account_post_count_windowを使う)

    戻り値:
    {
        "total": int,                 # 0〜100点
        "breakdown": {                # BREAKDOWN_KEYSの各項目の得点
            "再生数": int, "再生倍率": int, "いいね率": int, "コメント率": int,
            "投稿からの日数": int, "動画時間": int, "投稿頻度": int,
        },
        "tier": "必ず分析" | "投稿案候補" | "保存のみ",
    }
    """
    views = post.get("views", 0) or 0
    likes = post.get("likes", 0) or 0
    comments = post.get("comments", 0) or 0
    view_multiplier = post.get("view_multiplier")
    posted_at_dt = post.get("posted_at_dt")
    duration_sec = post.get("duration_sec")
    account_post_count_window = post.get("account_post_count_window")

    breakdown = {
        "再生数": _score_views(views),
        "再生倍率": _score_view_multiplier(view_multiplier),
        "いいね率": _score_like_rate(likes, views),
        "コメント率": _score_comment_rate(comments, views),
        "投稿からの日数": _score_recency(posted_at_dt),
        "動画時間": _score_duration(duration_sec),
        "投稿頻度": _score_post_frequency(account_post_count_window),
    }
    total = sum(breakdown.values())

    return {"total": total, "breakdown": breakdown, "tier": classify_tier(total)}


def score_posts(posts: list) -> list:
    """
    投稿リストの各要素に "research_candidate_score" キー
    (compute_research_candidate_scoreの戻り値)を付与する。post自体を変更し、
    同じリストを返す(main.pyから扱いやすくするため)。
    """
    for post in posts or []:
        post["research_candidate_score"] = compute_research_candidate_score(post)
    return posts


def sort_by_score(posts: list) -> list:
    """
    score_posts()済みの投稿リストを、Research Candidate Score合計が高い順に
    並べ替える。posts自体をin-placeで並べ替えて返す
    (main.pyがresearch_candidatesシート保存前に呼ぶ)。
    """
    posts.sort(key=lambda p: (p.get("research_candidate_score") or {}).get("total", 0), reverse=True)
    return posts


def select_for_analysis(posts: list, top_n: int = TOP_N_FOR_ANALYSIS) -> list:
    """
    score_posts()済みの投稿リストから、AI個別分析の対象を選ぶ。

    【2026-07-05】ユーザー要望「研究対象として価値がある投稿だけをAI分析対象に
    してください」に対応し、2026-07-02に廃止していたスコアしきい値ゲートを
    復活させた。ANALYSIS_MIN_SCORE(80点)以上の投稿だけに絞り込み、その中から
    Research Candidate Score上位top_n件(既定5件)を選ぶ。ANALYSIS_MIN_SCORE
    以上の投稿が1件もない日は、戻り値が空リストになる(=AI分析が実行されない
    日がある、という2026-07-02以前の挙動に戻った。これは「常に何かを分析する」
    より「研究対象として価値がある投稿だけを分析する」をユーザーが優先した
    結果であり、想定どおりの挙動)。呼び出し側(main.py)は空リストを前提に
    ハンドリングすること。
    """
    scored = [
        p for p in (posts or [])
        if p.get("research_candidate_score")
        and p["research_candidate_score"]["total"] >= ANALYSIS_MIN_SCORE
    ]
    scored.sort(key=lambda p: p["research_candidate_score"]["total"], reverse=True)
    return scored[:top_n]
