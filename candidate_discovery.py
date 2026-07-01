"""
candidate_discovery.py
Bright Dataで取得済みの投稿(キャプション・ハッシュタグ)から、
accounts.py にまだ登録されていない「新しいアンテナアカウント候補」を
自動で抽出・分類するモジュール。

【2026-06-29: 人による採用/除外判断を廃止し、完全自動化】
以前は候補をcandidate_accountsシートに出力し、ユーザーが「採用」「除外」を
手入力していたが、目的は「Instagram全体で伸びている投稿を毎日分析すること」
であり、日々の人の判断作業はできる限り無くしたい。そのため、以下の自動採用
ルールに置き換えた。

【自動採用ルール】
ある候補アカウントが、複数の異なるアンテナアカウントの投稿で言及されている
場合(accounts.AUTO_PROMOTE_MIN_SOURCE_ACCOUNTS件以上)、人の承認なしに
自動的にANTENNA_ACCOUNTSへ追加する(accounts_writer.add_accounts)。

1回の実行(1日分の投稿)だけでは言及元アカウントが少なすぎる場合があるため、
しきい値未満の候補は account_mention_tracker シートに「これまでに言及して
きたアカウントの集合」として記録し、複数回の実行をまたいで累積カウントする。
累積でしきい値に達した時点で自動追加される(classify_candidates関数)。

【処理の流れ】
1. main.py が取得した投稿(build_post_poolで絞る前の全件)を渡す
2. build_candidates() が各投稿のキャプションから@メンションを抽出し、
   今回の実行で見つかった言及元アカウントの集合をまとめる
3. classify_candidates() が、過去の累積データ(account_mention_trackerシート
   から読み込んだ previous_sources)と今回の言及元アカウントを合算し、
   しきい値以上なら「自動追加」、未満なら「トラッカーに記録」に振り分ける
4. main.py が accounts_writer.add_accounts() で実際にaccounts.pyへ追記し、
   sheets_writer.save_auto_added_accounts() でログを残す
5. しきい値未満の候補は sheets_writer.upsert_mention_tracker() で
   account_mention_trackerシートに保存し、次回以降に持ち越す

【現時点のスコープ(意図的な制限)】
- 追加コストを抑えるため、プロフィール文(bio)は取得しない。
  キャプション本文の@メンションのみを手がかりにする
  (プロフィール文からの抽出が必要になった場合は、Bright Dataの
  Profiles - Collect by URLを別途呼び出す処理を追加すること。
  本モジュールはそのための拡張ポイントとして
  extract_mentions()を独立した関数にしている)。
- キャプション中の「info@example.com」のようなメールアドレスを
  誤って候補に含めないよう、よくあるメールドメインはEMAIL_DOMAIN_DENYLISTで
  除外している。
"""

import re

MAX_CANDIDATES_PER_RUN = 30
MIN_USERNAME_LENGTH = 2

# 複数の異なるアンテナアカウントから言及されたら自動追加する、というルールの
# しきい値の既定値。呼び出し側がaccounts.AUTO_PROMOTE_MIN_SOURCE_ACCOUNTSを
# 明示的に渡さなかった場合のフォールバック。
DEFAULT_AUTO_PROMOTE_MIN_SOURCE_ACCOUNTS = 2

# キャプション中のメールアドレス(例: info@example.com)を@メンションと
# 誤認しないよう、よくあるメールドメインを除外する。
EMAIL_DOMAIN_DENYLIST = {
    "gmail.com",
    "yahoo.co.jp",
    "yahoo.com",
    "icloud.com",
    "outlook.com",
    "outlook.jp",
    "hotmail.com",
    "hotmail.co.jp",
    "docomo.ne.jp",
    "ezweb.ne.jp",
    "softbank.ne.jp",
    "ymobile.ne.jp",
    "au.com",
    "me.com",
    "live.jp",
}

# Instagramのユーザー名規則(英数字・"_"・"."、最大30文字)に概ね沿った
# @メンションの抽出パターン。
_MENTION_PATTERN = re.compile(r"@([A-Za-z0-9_.]{1,30})")


def _normalize_username(raw: str) -> str:
    username = (raw or "").strip()
    if username.startswith("@"):
        username = username[1:]
    # 文末の句読点・ピリオドがメンションに紛れ込むことがあるため取り除く
    username = username.strip(".")
    return username.lower()


def normalize_known_usernames(accounts: list) -> set:
    """accounts.py のANTENNA_ACCOUNTSなど、既知アカウントのリストを
    比較しやすい小文字集合に変換する。"""
    return {_normalize_username(a) for a in (accounts or []) if a and a.strip()}


def extract_mentions(text: str) -> list:
    """
    キャプション本文から@メンションのユーザー名を抽出する。
    メールアドレスのドメイン部分(例: gmail.com)が紛れ込んだ場合は
    EMAIL_DOMAIN_DENYLISTで除外する。
    """
    if not text:
        return []

    raw_matches = _MENTION_PATTERN.findall(text)
    mentions = []
    seen = set()
    for raw in raw_matches:
        username = _normalize_username(raw)
        if not username or len(username) < MIN_USERNAME_LENGTH:
            continue
        if username in EMAIL_DOMAIN_DENYLIST:
            continue
        if username in seen:
            continue
        seen.add(username)
        mentions.append(username)
    return mentions


def build_candidates(
    posts: list, known_accounts: list, max_candidates: int = MAX_CANDIDATES_PER_RUN
) -> list:
    """
    取得済みの投稿群(1回の実行分)から、未知のアカウント候補を抽出する。

    posts: bright_data_fetcher._normalize_post() が返す投稿dictのリスト
           (build_post_poolで絞る前の全取得投稿を渡すこと。フィルタ後だと
           手がかりが減ってしまうため)
    known_accounts: accounts.py の ANTENNA_ACCOUNTS

    戻り値: メンション回数が多い順に並んだ候補リスト。各要素は
    {
        "username": str,
        "mention_count": int,
        "source_accounts": list[str],  # 今回の実行でその候補に言及していた投稿者
        "sample_caption": str,         # 参考用キャプション(最初の1件、抜粋)
        "sample_hashtags": list[str],  # 参考用ハッシュタグ(最初の1件分)
    }
    """
    known = normalize_known_usernames(known_accounts)
    candidates = {}

    for post in posts or []:
        if post.get("fetch_error"):
            continue

        caption = post.get("caption") or ""
        source_account = _normalize_username(post.get("source_account") or post.get("username") or "")

        for username in extract_mentions(caption):
            if username in known:
                continue
            if source_account and username == source_account:
                # 自分自身のキャプション内自己メンション(リポスト元クレジット等)は除外
                continue

            entry = candidates.get(username)
            if entry is None:
                entry = {
                    "username": username,
                    "mention_count": 0,
                    "source_accounts": [],
                    "sample_caption": caption.replace("\n", " ")[:120],
                    "sample_hashtags": list(post.get("hashtags") or [])[:5],
                }
                candidates[username] = entry

            entry["mention_count"] += 1
            if source_account and source_account not in entry["source_accounts"]:
                entry["source_accounts"].append(source_account)

    ranked = sorted(
        candidates.values(),
        key=lambda c: (c["mention_count"], c["username"]),
        reverse=True,
    )
    return ranked[:max_candidates]


def classify_candidates(
    candidates: list,
    previous_sources: dict,
    blocked_accounts: list,
    min_source_accounts: int = DEFAULT_AUTO_PROMOTE_MIN_SOURCE_ACCOUNTS,
) -> dict:
    """
    build_candidates() の結果(今回の実行分)と、これまでの累積言及元アカウント
    (previous_sources)を合算し、自動追加するか・トラッカーに記録するかを判定する。
    人の判断は一切介在しない(BLOCKED_ACCOUNTSは事前にユーザーが設定済みの
    まれなメンテナンスリストであり、毎日の判断作業ではない)。

    candidates: build_candidates() の戻り値
    previous_sources: {username: set(これまでに言及していたアカウントの集合)}
                       (sheets_writer.get_mention_tracker() の戻り値を整形したもの)
    blocked_accounts: accounts.py の BLOCKED_ACCOUNTS
    min_source_accounts: 自動追加のしきい値(通常は accounts.AUTO_PROMOTE_MIN_SOURCE_ACCOUNTS を渡す)

    戻り値:
    {
        "to_promote": [候補dict(source_accountsは累積後のソート済みリスト), ...],
        "to_track": [候補dict(同上。まだしきい値未満), ...],
        "blocked": [候補dict, ...],  # ブロックリストに該当し、判定自体を見送ったもの
    }
    """
    blocked = normalize_known_usernames(blocked_accounts)
    to_promote, to_track, blocked_list = [], [], []

    for candidate in candidates or []:
        username = candidate["username"]

        if username in blocked:
            blocked_list.append(candidate)
            continue

        merged_sources = set(previous_sources.get(username, set())) | set(
            candidate.get("source_accounts") or []
        )
        merged_entry = dict(candidate)
        merged_entry["source_accounts"] = sorted(merged_sources)

        if len(merged_sources) >= min_source_accounts:
            to_promote.append(merged_entry)
        else:
            to_track.append(merged_entry)

    return {"to_promote": to_promote, "to_track": to_track, "blocked": blocked_list}
