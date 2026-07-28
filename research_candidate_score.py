"""
research_candidate_score.py
取得・プール済みの投稿1件ごとに「Research Candidate Score」(0〜80点)を計算するモジュール。

【2026-07-17: スコアリング大幅改修】
ユーザー要望:「再生数が0または未取得でも投稿日・動画尺・投稿頻度だけで高得点になり
実績を正しく評価できていない」

変更内容(実装前に仕様を書面確認済み):
1. 再生数0または欠損の場合: 再生数_点=0・再生倍率_点=0・tier="評価保留"。
   sort_by_score/select_for_analysisの通常ランキングから除外し、
   split_by_views_availability でEngagement参考候補として別管理する。
2. いいね率・コメント率の分母をviews→followersに変更。
   (フォロワー数0または欠損の場合は0点のまま)
3. 投稿頻度の最大配点: 10点→2点
4. 動画時間の最大配点: 10点→3点
5. 投稿からの日数の最大配点: 10点→5点
6. split_by_views_availability() 追加: (再生数あり, 再生数なし) のタプルを返す
7. sort_no_views_by_engagement() 追加: 再生数なし投稿をエンゲージメント率降順に並べる
8. 異常値チェック(anomalies フィールド)追加:
   - "要データ確認" : いいね率がフォロワー数の100%超
   - "取得エラー"   : 投稿日が未来
   - "再生数未取得" : 再生数0なのにいいね数が存在

【重要: 合計最大点が100→80に変わった】
配点変更後の最大合計 = 再生数(10) + 再生倍率(30) + いいね率(15) + コメント率(15)
                      + 投稿からの日数(5) + 動画時間(3) + 投稿頻度(2) = 80点。
ANALYSIS_MIN_SCORE=80(=SCORE_THRESHOLD_CANDIDATE)は「再生数あり投稿で全項目
ほぼ満点」を意味するため、実運用では閾値の引き下げを検討してください。

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
from collections import deque as _deque

# --- 各配点の最大値（2026-07-22: 正規化スコア導入のため明示） ---
MAX_VIEWS_SCORE        = 10
MAX_VIEW_RATIO_SCORE   = 30
MAX_LIKE_RATE_SCORE    = 15
MAX_COMMENT_RATE_SCORE = 15
MAX_RECENCY_SCORE      = 5
MAX_DURATION_SCORE     = 3
MAX_FREQUENCY_SCORE    = 2
MAX_RAW_SCORE = (
    MAX_VIEWS_SCORE + MAX_VIEW_RATIO_SCORE + MAX_LIKE_RATE_SCORE +
    MAX_COMMENT_RATE_SCORE + MAX_RECENCY_SCORE + MAX_DURATION_SCORE +
    MAX_FREQUENCY_SCORE
)  # = 80

# --- 最低再生数条件（2026-07-22） ---
MIN_VIEWS_ABSOLUTE   = 100_000  # 絶対再生数しきい値
MIN_VIEWS_MULTIPLIER = 1.0      # フォロワー数比しきい値

# --- followers未取得時のフォールバック (2026-07-28: 提案済み・未有効化) ---
# followers=None のままAI分析が完全停止するのを防ぐフォールバック閾値。
# 再生数がこの値以上あれば、フォロワーなし・スコア不足でも分析を許可する案。
# 有効化する場合: select_for_analysis の Gate 3 に以下のバイパス条件を追加する:
#   if score_info.get("normalized_score", 0.0) < ANALYSIS_MIN_SCORE:
#       views = p.get("views", 0) or 0
#       if p.get("followers") is None and views >= NO_FOLLOWERS_MIN_VIEWS:
#           pass  # バイパス: 超バイラル投稿はフォロワーなしでも分析する
#       else:
#           continue
NO_FOLLOWERS_MIN_VIEWS: int = 500_000  # 未有効化

# --- スコアしきい値・判定ラベル（2026-07-22: 正規化スコア100点換算に変更） ---
SCORE_THRESHOLD_MUST_ANALYZE = 80   # 正規化スコア: TIER_MUST_ANALYZE
SCORE_THRESHOLD_CANDIDATE    = 65   # 正規化スコア: TIER_CANDIDATE (AI分析の最低線)

# --- 同一アカウント上限 ---
MAX_POSTS_PER_ACCOUNT = 2         # ①②③ 1アカウントから採用する最大投稿数
MIN_ACCOUNTS_FOR_TREND = 10       # ⑤ Trend Analysis に必要な最低アカウント数
BIAS_THRESHOLD = 0.20             # ⑦ 1アカウント占有率がこの値以上で「偏りあり」

# --- 分析対象期間・目標件数 ---
RESEARCH_WINDOW_DAYS = 10   # 分析対象とする投稿の直近日数(2026-07-18)
MIN_CANDIDATE_POSTS  = 20   # Research Candidateの目標最低件数(2026-07-18)

TIER_MUST_ANALYZE = "必ず分析"
TIER_CANDIDATE = "投稿案候補"
TIER_SAVE_ONLY = "保存のみ"
TIER_PENDING = "評価保留"  # 再生数0または欠損の投稿(通常ランキングから除外)

# AI分析ゲートのしきい値（2026-07-22: 正規化スコア65点以上＝TIER_CANDIDATE以上）。
# 正規化スコア = raw_score / MAX_RAW_SCORE * 100。
# ANALYSIS_MIN_SCORE以上が0件の日はAI分析0件（想定内の挙動）。
ANALYSIS_MIN_SCORE = SCORE_THRESHOLD_CANDIDATE  # = 65 (正規化スコア)

# AI個別分析(openai_analyzer.analyze_post_structure / generate_core_hari_idea等)を
# 実行する最大件数。ANALYSIS_MIN_SCORE以上の投稿の中から上位を選ぶ。
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


def _score_like_rate(likes: int, followers) -> int:
    """
    【2026-07-17】分母をviews→followersに変更。
    いいね率 = いいね数 ÷ フォロワー数。フォロワー数0または欠損の場合は0点。
    しきい値はフォロワー数ベースのInstagram一般的エンゲージメント率に合わせて調整。
    """
    if not followers:
        return 0
    rate = likes / followers
    if rate >= 0.05:   # 5%超: 非常に高エンゲージメント
        return 15
    if rate >= 0.03:   # 3%超: 高エンゲージメント
        return 12
    if rate >= 0.01:   # 1%超: 平均以上
        return 9
    if rate >= 0.005:  # 0.5%超: 平均的
        return 6
    if rate >= 0.001:  # 0.1%超: 低め
        return 3
    return 0


def _score_comment_rate(comments: int, followers) -> int:
    """
    【2026-07-17】分母をviews→followersに変更。
    コメント率 = コメント数 ÷ フォロワー数。フォロワー数0または欠損の場合は0点。
    コメントはいいねより行動コストが高いため、しきい値はいいね率より低く設定。
    """
    if not followers:
        return 0
    rate = comments / followers
    if rate >= 0.005:   # 0.5%超: 非常に高い
        return 15
    if rate >= 0.002:   # 0.2%超: 高い
        return 12
    if rate >= 0.001:   # 0.1%超: 平均以上
        return 9
    if rate >= 0.0005:  # 0.05%超: 平均的
        return 6
    if rate >= 0.0001:  # 0.01%超: 低め
        return 3
    return 0


def _score_recency(posted_at_dt) -> int:
    """
    【2026-07-17】最大配点を10点→5点に変更。
    投稿日が未来の場合は0点(異常値として_check_anomaliesで別途検出)。
    """
    if posted_at_dt is None:
        return 0
    now = dt.datetime.now(dt.timezone.utc)
    days = (now - posted_at_dt).total_seconds() / 86400
    if days < 0:
        return 0  # 未来日付は0点(取得エラー扱い)
    if days <= 2:
        return 5
    if days <= 5:
        return 4
    if days <= 10:
        return 3
    if days <= 15:
        return 2
    if days <= 20:
        return 1
    return 0


def _score_duration(duration_sec) -> int:
    """
    ※実測値(モジュールdocstring参照)。bright_data_fetcherのduration_sec
    (Bright Data "length" フィールド)をそのまま使う。キャプションのキーワード
    推定は行わない。
    【2026-07-17】最大配点を10点→3点に変更。
    """
    if duration_sec is None:
        return 0
    if _DURATION_BEST_RANGE[0] <= duration_sec <= _DURATION_BEST_RANGE[1]:
        return 3
    if _DURATION_OK_RANGE[0] <= duration_sec <= _DURATION_OK_RANGE[1]:
        return 2
    if _DURATION_MARGINAL_RANGE[0] <= duration_sec <= _DURATION_MARGINAL_RANGE[1]:
        return 1
    return 0


def _score_post_frequency(account_post_count_window) -> int:
    """
    ※実測値(モジュールdocstring参照)。bright_data_fetcher._attach_account_
    post_countsが付与するpost["account_post_count_window"](今回の取得窓内で
    同じアカウントから取得できた投稿数)を使う。
    【2026-07-17】最大配点を10点→2点に変更。
    """
    if not account_post_count_window:
        return 0
    if account_post_count_window >= 6:
        return 2
    if account_post_count_window >= 2:
        return 1
    return 0


def normalize_score(raw_score: int) -> float:
    """
    raw_score (0〜MAX_RAW_SCORE) を 0〜100 の正規化スコアに変換する。
    【2026-07-22】配点変更で最大raw_scoreが変わっても判定しきい値を変える必要がなくなる。
    """
    if MAX_RAW_SCORE <= 0:
        return 0.0
    return round(raw_score / MAX_RAW_SCORE * 100, 1)


def classify_tier(total: int, views_available: bool = True) -> str:
    """
    【2026-07-22】正規化スコア(0〜100)を使ってTierを判定する。
    views_available=Falseの場合は TIER_PENDING("評価保留")を返す。
    """
    if not views_available:
        return TIER_PENDING
    normalized = normalize_score(total)
    if normalized >= SCORE_THRESHOLD_MUST_ANALYZE:
        return TIER_MUST_ANALYZE
    if normalized >= SCORE_THRESHOLD_CANDIDATE:
        return TIER_CANDIDATE
    return TIER_SAVE_ONLY


def _check_anomalies(views: int, likes: int, followers, posted_at_dt) -> list:
    """
    【2026-07-17】異常値を検出してラベルのリストを返す(複数同時に発生しうる)。
    - "再生数未取得" : 再生数0なのにいいね数が存在する(再生数の取得漏れを疑う)
    - "要データ確認" : いいね数がフォロワー数を超えている(データ異常を疑う)
    - "取得エラー"   : 投稿日が未来(APIの日付取得エラーを疑う)
    """
    anomalies = []
    if not views and likes:
        anomalies.append("再生数未取得")
    if followers and likes and likes > followers:
        anomalies.append("要データ確認")
    if posted_at_dt is not None:
        now = dt.datetime.now(dt.timezone.utc)
        if posted_at_dt > now:
            anomalies.append("取得エラー")
    return anomalies


def compute_research_candidate_score(post: dict) -> dict:
    """
    投稿1件のResearch Candidate Score(0〜80点)を計算する。

    【2026-07-17】配点の最大合計が100→80に変わった点に注意。
    再生数0/欠損の場合は再生数・再生倍率が強制0点、tierが"評価保留"になる。
    いいね率・コメント率はフォロワー数を分母に使う(viewsは使わない)。

    post: bright_data_fetcher._normalize_post() が返す投稿dict
          (views, likes, comments, followers, view_multiplier, posted_at_dt,
          duration_sec, account_post_count_windowを使う)

    戻り値:
    {
        "total": int,              # 0〜80点(再生数なしは最大40点)
        "breakdown": {             # BREAKDOWN_KEYSの各項目の得点
            "再生数": int, "再生倍率": int, "いいね率": int, "コメント率": int,
            "投稿からの日数": int, "動画時間": int, "投稿頻度": int,
        },
        "tier": "必ず分析" | "投稿案候補" | "保存のみ" | "評価保留",
        "views_available": bool,   # 再生数が取得できているか
        "anomalies": list[str],    # 異常値ラベルのリスト(正常なら空リスト)
    }
    """
    views = post.get("views", 0) or 0
    likes = post.get("likes", 0) or 0
    comments = post.get("comments", 0) or 0
    followers = post.get("followers")
    view_multiplier = post.get("view_multiplier")
    posted_at_dt = post.get("posted_at_dt")
    duration_sec = post.get("duration_sec")
    account_post_count_window = post.get("account_post_count_window")

    views_available = bool(views)
    anomalies = _check_anomalies(views, likes, followers, posted_at_dt)

    breakdown = {
        "再生数": _score_views(views) if views_available else 0,
        "再生倍率": _score_view_multiplier(view_multiplier) if views_available else 0,
        "いいね率": _score_like_rate(likes, followers),
        "コメント率": _score_comment_rate(comments, followers),
        "投稿からの日数": _score_recency(posted_at_dt),
        "動画時間": _score_duration(duration_sec),
        "投稿頻度": _score_post_frequency(account_post_count_window),
    }
    total = sum(breakdown.values())

    return {
        "total": total,
        "normalized_score": normalize_score(total),
        "breakdown": breakdown,
        "tier": classify_tier(total, views_available),
        "views_available": views_available,
        "anomalies": anomalies,
    }


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
    score_posts()済みの投稿リストを並べ替える。

    【2026-07-17】再生数あり投稿(Research Candidate Ranking)を先頭グループに、
    再生数なし投稿(Engagement参考候補)を末尾グループに配置する。
    各グループ内では Research Candidate Score合計降順。
    posts自体をin-placeで並べ替えて返す。
    """
    def _sort_key(p):
        score = (p.get("research_candidate_score") or {})
        views_available = score.get("views_available", True)
        total = score.get("total", 0)
        return (0 if views_available else 1, -total)

    posts.sort(key=_sort_key)
    return posts


def split_by_views_availability(posts: list) -> tuple:
    """
    【2026-07-17】score_posts()済みの投稿リストを再生数あり/なしに分割する。

    戻り値: (posts_with_views, posts_without_views)
    - posts_with_views   : Research Candidate Ranking対象(通常ランキング)
    - posts_without_views: Engagement参考候補(いいね率・コメント率で並べ直す)
    """
    with_views = [
        p for p in (posts or [])
        if (p.get("research_candidate_score") or {}).get("views_available", True)
    ]
    without_views = [
        p for p in (posts or [])
        if not (p.get("research_candidate_score") or {}).get("views_available", True)
    ]
    return with_views, without_views


def sort_no_views_by_engagement(posts: list) -> list:
    """
    【2026-07-17】再生数なし投稿をエンゲージメント率(いいね+コメント)÷フォロワー降順に並べる。
    Engagement参考候補の表示順に使う。
    """
    def _engagement_key(p):
        likes = p.get("likes", 0) or 0
        comments = p.get("comments", 0) or 0
        followers = p.get("followers") or 0
        if not followers:
            return 0.0
        return (likes + comments) / followers

    posts.sort(key=_engagement_key, reverse=True)
    return posts


# Trend Analysis で優先するキーワード（施術・セルフケア・顔の変化・表情筋・姿勢・美容知識）
_TREND_PREFERRED_KEYWORDS = (
    "施術", "セルフケア", "顔の変化", "表情筋", "顔筋", "姿勢", "美容知識",
    "小顔", "たるみ", "むくみ", "リフトアップ", "フェイスライン", "骨格",
    "顔矯正", "顔トレ", "ビフォーアフター", "before after",
)

# Trend Analysis から除外する商品販売主体キーワード
_TREND_EXCLUDE_KEYWORDS = (
    "通販", "販売中", "お買い物", "ec限定", "楽天", "amazon", "アマゾン",
    "購入はこちら", "ショッピング", "商品紹介", "商品レビュー", "お試しセット",
    "ポイント還元", "割引", "セール", "クーポン", "キャンペーン価格",
)


def _is_product_sales_post(post: dict) -> bool:
    """商品販売中心のリールかどうかを判定する。"""
    text = ((post.get("caption") or "") + " " + " ".join(post.get("hashtags") or [])).lower()
    return any(kw in text for kw in _TREND_EXCLUDE_KEYWORDS)


def _has_preferred_content(post: dict) -> bool:
    """施術・セルフケア系コンテンツが含まれているか判定する。"""
    text = ((post.get("caption") or "") + " " + " ".join(post.get("hashtags") or [])).lower()
    return any(kw in text for kw in _TREND_PREFERRED_KEYWORDS)


def select_for_analysis(posts: list, top_n: int = TOP_N_FOR_ANALYSIS) -> list:
    """
    score_posts()済みの投稿リストから、AI個別分析の対象を選ぶ。

    【2026-07-22】3つのゲートで絞り込む（正規化スコア65点以上が最低線）:
      Gate 1: views_available=True 必須（再生数なし投稿は対象外）
      Gate 2: 最低再生数条件 views >= MIN_VIEWS_ABSOLUTE OR
              view_multiplier >= MIN_VIEWS_MULTIPLIER（どちらか一方を満たせばOK）
      Gate 3: 正規化スコア >= ANALYSIS_MIN_SCORE (= 65)
    Gate 2 を失敗した投稿には pool_exclusion_reason を付与する（副作用）。

    【2026-07-20】商品販売主体のリールを除外。施術・セルフケア系を優先選出。
    """
    scored = []
    for p in (posts or []):
        score_info = p.get("research_candidate_score")
        if not score_info:
            continue
        # Gate 1: 再生数取得必須
        if not score_info.get("views_available", True):
            continue
        # Gate 2: 最低再生数条件（いずれか一方を満たせばOK）
        views          = p.get("views", 0) or 0
        view_multiplier = p.get("view_multiplier") or 0.0
        meets_abs  = views >= MIN_VIEWS_ABSOLUTE
        meets_mult = view_multiplier >= MIN_VIEWS_MULTIPLIER
        if not meets_abs and not meets_mult:
            if not p.get("pool_exclusion_reason"):
                if views < MIN_VIEWS_ABSOLUTE:
                    p["pool_exclusion_reason"] = "再生数10万未満"
                else:
                    p["pool_exclusion_reason"] = "フォロワー数未満の再生"
            continue
        # Gate 3: 正規化スコアしきい値
        if score_info.get("normalized_score", 0.0) < ANALYSIS_MIN_SCORE:
            continue
        # Gate 4: 商品販売主体を除外
        if _is_product_sales_post(p):
            continue
        scored.append(p)

    scored.sort(
        key=lambda p: p["research_candidate_score"].get("normalized_score", 0.0),
        reverse=True,
    )
    # 施術・セルフケア系を優先: preferred を先頭に、残りを後ろに
    preferred = [p for p in scored if _has_preferred_content(p)]
    others    = [p for p in scored if not _has_preferred_content(p)]
    return (preferred + others)[:top_n]


# ─────────────────────────────────────────────────────────────────────────────
# 同一アカウント上限・統計・インターリーブ (2026-07-18追加)
# ─────────────────────────────────────────────────────────────────────────────

def _account_key(post: dict) -> str:
    """投稿の所有アカウントを一意に識別するキー。"""
    return (
        (post.get("source_account") or "").strip().lower()
        or (post.get("username") or "").strip().lower()
        or "_unknown_"
    )


def limit_per_account(
    posts: list,
    max_per_account: int = MAX_POSTS_PER_ACCOUNT,
) -> tuple:
    """
    【2026-07-18: ①②③】同一アカウントから採用する投稿をmax_per_account件に制限する。

    score_posts() + sort_by_score()済みリストを想定(スコア降順が前提)。
    アカウント内では先頭max_per_account件を残し、3件目以降は除外する。

    除外された投稿には post["pool_exclusion_reason"] = "同一アカウント上限" を付与する。

    Returns:
        (accepted: list, excluded: list)
    """
    counts: dict = {}
    accepted: list = []
    excluded: list = []
    for post in posts or []:
        key = _account_key(post)
        cnt = counts.get(key, 0) + 1
        counts[key] = cnt
        if cnt <= max_per_account:
            accepted.append(post)
        else:
            post["pool_exclusion_reason"] = "同一アカウント上限"
            excluded.append(post)
    return accepted, excluded


def compute_account_stats(posts: list) -> dict:
    """
    【2026-07-18: ④⑤⑥⑦】投稿リストのアカウント別集計情報を返す。

    Returns dict:
        total_posts       : int   — 投稿総数
        account_count     : int   — ユニークアカウント数
        max_account       : str   — 最多投稿アカウント名
        max_count         : int   — そのアカウントの投稿数
        max_ratio         : float — 占有率 (0.0〜1.0)
        has_bias          : bool  — max_ratio >= BIAS_THRESHOLD
        has_min_accounts  : bool  — account_count >= MIN_ACCOUNTS_FOR_TREND
        details           : dict  — {account: count, ...}
    """
    details: dict = {}
    for p in posts or []:
        k = _account_key(p)
        details[k] = details.get(k, 0) + 1

    total = len(posts or [])
    if not details or total == 0:
        return {
            "total_posts": 0, "account_count": 0, "max_account": "",
            "max_count": 0, "max_ratio": 0.0,
            "has_bias": False, "has_min_accounts": False, "details": {},
        }

    max_acc = max(details, key=details.get)
    max_cnt = details[max_acc]
    max_ratio = max_cnt / total

    return {
        "total_posts": total,
        "account_count": len(details),
        "max_account": max_acc,
        "max_count": max_cnt,
        "max_ratio": max_ratio,
        "has_bias": max_ratio >= BIAS_THRESHOLD,
        "has_min_accounts": len(details) >= MIN_ACCOUNTS_FOR_TREND,
        "details": details,
    }


def filter_by_window(
    posts: list,
    days: int = RESEARCH_WINDOW_DAYS,
) -> tuple:
    """
    【2026-07-18: 項目1】分析対象を直近days日以内の投稿に絞り込む。

    score_posts() の前に適用することを想定。
    期間外の投稿には post["pool_exclusion_reason"] = "期間外" を付与する
    (既に別の除外理由がある場合は上書きしない)。

    Returns: (within: list, excluded: list)
    """
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    within: list = []
    excluded: list = []
    for post in posts or []:
        posted_at = post.get("posted_at_dt")
        if posted_at is not None and posted_at >= cutoff:
            within.append(post)
        else:
            if not post.get("pool_exclusion_reason"):
                post["pool_exclusion_reason"] = "期間外"
            excluded.append(post)
    return within, excluded


def interleave_by_account(posts: list) -> list:
    """
    【2026-07-18: ⑧】同じアカウントが連続しないよう、ラウンドロビン方式で並び替える。
    各アカウント内での順序(Research Candidate Score降順)は維持する。
    """
    groups: dict = {}
    for post in posts or []:
        k = _account_key(post)
        groups.setdefault(k, []).append(post)

    queues = _deque(_deque(g) for g in groups.values())
    result: list = []
    while queues:
        q = queues.popleft()
        result.append(q.popleft())
        if q:
            queues.append(q)
    return result
