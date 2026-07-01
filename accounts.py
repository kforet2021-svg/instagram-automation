"""
accounts.py
Instagram全体トレンドを観測するための「アンテナアカウント」リスト。

【2026-06-29 設計変更(2回目): 候補アカウントの人による採用判断を廃止】
以前は、取得した投稿のキャプションから抽出した新規アカウント候補を
candidate_accountsシートに出力し、ユーザーが「採用/除外」を手入力する
半自動フローだった。しかし目的は「Instagram全体で伸びている投稿を毎日
分析し、CORE HARI FACEの投稿案を自動生成すること」であり、日々の人の
判断作業はできる限り無くしたい。そのため、以下のように完全自動化した。

【運用フロー(完全自動)】
1. ANTENNA_ACCOUNTS(起点アカウント)からBright Dataで投稿を取得する。
2. 取得した投稿のキャプションから@メンションを抽出する(candidate_discovery.py)。
3. ある候補アカウントが、複数の異なるアンテナアカウントから言及されている場合
   (AUTO_PROMOTE_MIN_SOURCE_ACCOUNTS件以上。1回の実行内だけでなく、
   account_mention_trackerシートで複数回の実行をまたいで累積カウントする)、
   人の承認なしに自動的にこのファイルのANTENNA_ACCOUNTSへ追記される
   (accounts_writer.add_accounts、main.pyから毎回呼ばれる)。
   追加されたアカウントはauto_added_accountsシートに記録される(ログ目的、
   ユーザーの操作は不要)。
4. しきい値未満の候補はaccount_mention_trackerシートに記録され、次回以降の
   実行で言及元アカウントが積み上がればしきい値到達時に自動追加される。

【BLOCKED_ACCOUNTS(まれな手動メンテナンス用)】
自動追加されたアカウントが明らかに無関係だった場合のみ、ユーザーが
BLOCKED_ACCOUNTSにユーザー名を追加し、ANTENNA_ACCOUNTSから該当行を削除する
(この操作は日次ではなく、気づいたときに行う程度の低頻度メンテナンスを想定)。
BLOCKED_ACCOUNTSに入れておくと、今後同じアカウントが候補に挙がっても
自動追加されなくなる。

【運用方法】
- ユーザー名は "@" を付けても付けなくても動く("@username" でも "username" でも可)。
- ANTENNA_ACCOUNTS はジャンルを問わない(美容・エンタメ・お笑い・ライフスタイル・
  グルメ・バズ系など)。ジャンルを横断して観測すること自体が目的のため、
  美容ジャンルだけに絞らないこと。
- 末尾の "自動追加された候補アカウント" セクションは accounts_writer.add_accounts
  (main.pyの実行中に呼ばれる)が書き込む。手動で編集してもよいが、コメント行
  (# ---で始まる行)は追記位置を判定するために使われているため、削除しないこと。

【なぜ起点アカウントが依然として必要なのか】
Bright Data(およびApify含む他社サービス)には、ハッシュタグやキーワードを
起点に「未知の投稿」をInstagram全体から無条件に発見する機能は存在しない
(Instagram自体が公開の全体トレンドAPIを提供していないため)。詳細はREADME.md
「Bright Dataだけで『Instagram全体のトレンド取得』は可能か」を参照。

【2026-07-02: ANTENNA_ACCOUNTS_BEAUTYを追加(①全体トレンド+②美容ジャンル
トレンドの統合対応)】
ユーザー要望:「Instagram全体トレンドだけでなく、美容ジャンルトレンドも
取得し、両者を統合して分析してほしい」。

ANTENNA_ACCOUNTS自体は変更しない(ジャンル不問のまま、Bright Dataへの取得は
今までと同じ1回・同じアカウント数で行う=取得コストは増やさない)。
ANTENNA_ACCOUNTS_BEAUTYは、ANTENNA_ACCOUNTS内の「美容ジャンル」アカウント
(下記リスト先頭の20件、コメント上は同じ集合)だけを指す名前付きの参照用
サブセットであり、bright_data_fetcher.apply_beauty_category()がこのリストを
使って、取得済みの投稿のうちこのアカウント由来のものだけを事後的に
category="美容ジャンルトレンド"に再分類する(Bright Dataへの2回目の取得は
発生しない)。ANTENNA_ACCOUNTSへの自動追加(account_mention_tracker経由)で
増えたアカウントはANTENNA_ACCOUNTS_BEAUTYには含まれない(美容ジャンルかどうか
を自動判定する仕組みは無いため。必要であれば手動でこのリストに追記する)。
"""

# 新しい候補アカウントを自動追加する条件: 累積で何件の異なるアンテナアカウントから
# 言及されたら自動追加するか(candidate_discovery.pyが参照する)。
AUTO_PROMOTE_MIN_SOURCE_ACCOUNTS = 2

# --- Instagram全体トレンド観測用アンテナアカウント(ジャンル不問) ---
ANTENNA_ACCOUNTS = [
    # 美容ジャンル(顔トレ・小顔・表情筋・たるみ改善などCORE HARI FACEに近い領域)
    "hanafusahifuka",
    "kii_t.t",
    "ikemenseizoki",
    "cs60_iroha",
    "biyou.tomoko",
    "kooooomi64",
    "korugi_akt",
    "takataka.0105",
    "torikospaa",
    "beauty_honest_review",
    "marika_bodycare_salon3526",
    "chisato.ns",
    "harusame_chu",
    "yakekuso_dayo",
    "seitai.binotuikyuu",
    "akemisan0622",
    "wakana__kaneko",
    "yuko__babyskincare",
    "hiromiin_beauty_life",
    "k_beautyon_hakata",
    # ジャンル不問・バズ系/トレンド観測用
    "japanbuzznews",
    "ami.yamanaka",
    "diesel_bros_asuka",
    "marcpanther",
    "geinou.hikaritokage",
    "blackchocolate4232",
    "dailyfashion_news_jp",
    "mmiyuyu",
    "enno_syouji",
    "168ch_1",
    "rakko__photo",
    "chamitabi",
    "geinoubanashi",
    "noritabi2021",
    "_73__________",
    "jun_pen.chibi",
    "sorano_kurage_",
    "showfight921",
    "sportsknockouttv",
    "kazu178.co.jp",
    "pyomo_kojiro_ryoma",
    "masayo_mima",
    "mamedango1",

    # --- ここから下: 複数のアンテナアカウントから言及されたため、
    #     accounts_writer.add_accounts によって自動追加されたアカウント ---
]

# --- 美容ジャンルトレンド観測用サブセット(2026-07-02追加) ---
# ANTENNA_ACCOUNTS先頭20件と同じ集合(モジュールdocstring参照)。
# Bright Dataへの取得は増やさず、取得済み投稿の事後的なカテゴリ再分類にのみ使う。
ANTENNA_ACCOUNTS_BEAUTY = [
    "hanafusahifuka",
    "kii_t.t",
    "ikemenseizoki",
    "cs60_iroha",
    "biyou.tomoko",
    "kooooomi64",
    "korugi_akt",
    "takataka.0105",
    "torikospaa",
    "beauty_honest_review",
    "marika_bodycare_salon3526",
    "chisato.ns",
    "harusame_chu",
    "yakekuso_dayo",
    "seitai.binotuikyuu",
    "akemisan0622",
    "wakana__kaneko",
    "yuko__babyskincare",
    "hiromiin_beauty_life",
    "k_beautyon_hakata",
]

# 自動追加された後に「明らかに無関係だった」と判断したアカウントを入れておくと、
# 今後同じアカウントが候補に挙がっても自動追加されなくなる(候補抽出自体は
# 続けるが、しきい値を満たしても追加をスキップする)。
# まれな手動メンテナンス用のリストであり、日次で確認する必要はない。
BLOCKED_ACCOUNTS = [
]
