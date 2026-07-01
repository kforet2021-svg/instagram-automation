"""
accounts_writer.py
accounts.py の ANTENNA_ACCOUNTS に新しいアカウントを自動追記するための
ファイル書き込みユーティリティ。

【2026-06-29】候補アカウントの採用/除外を人が毎日判断する運用をやめ、
複数のアンテナアカウントから言及された候補は人の承認なしに自動的に
ANTENNA_ACCOUNTSへ追加する設計に変更した。このモジュールはその
「ファイルへの実際の追記」部分だけを担う(どの候補を追加すべきかという
判定ロジックはcandidate_discovery.pyのclassify_candidates()が行う)。

main.pyが日次実行のたびにadd_accounts()を呼ぶ。何度呼んでも、既に
ANTENNA_ACCOUNTSに存在するユーザー名は重複追加しない(冪等)。
"""

from pathlib import Path

from accounts import ANTENNA_ACCOUNTS
from candidate_discovery import normalize_known_usernames

ACCOUNTS_FILE = Path(__file__).resolve().parent / "accounts.py"

# accounts.py内の、自動追加の差し込み位置を示すマーカーコメントの一部。
# accounts.py側のこのコメント文を削除すると本モジュールは動かなくなるため、
# accounts.py側にも削除しない旨を明記している。
INSERT_MARKER = "自動追加されたアカウント ---"


def add_accounts(usernames: list) -> list:
    """
    まだANTENNA_ACCOUNTSに無いユーザー名だけを、accounts.py のマーカー位置に
    追記する。

    戻り値: 実際に新規追加したユーザー名のリスト(小文字・@無し)。
    """
    if not usernames:
        return []

    known = normalize_known_usernames(ANTENNA_ACCOUNTS)
    text = ACCOUNTS_FILE.read_text(encoding="utf-8")

    to_add = []
    for raw_username in usernames:
        username = (raw_username or "").strip().lower()
        if username.startswith("@"):
            username = username[1:]
        if not username or username in known:
            continue
        if username in to_add:
            continue
        # ファイル内に既にクオート付きで存在する場合も二重追加しない(念のため)
        if f'"{username}"' in text:
            continue
        to_add.append(username)

    if not to_add:
        return []

    marker_index = text.find(INSERT_MARKER)
    if marker_index == -1:
        raise RuntimeError(
            "accounts.py内に自動追加用のマーカーコメントが見つかりませんでした。"
            "accounts.pyの構造が変更された可能性があります。"
            "手動でANTENNA_ACCOUNTSに追記してください: " + ", ".join(to_add)
        )

    line_end = text.find("\n", marker_index)
    if line_end == -1:
        raise RuntimeError("accounts.pyのマーカーコメント行の形式が想定外でした(改行が見つかりません)。")

    insertion = "".join(f'    "{u}",\n' for u in to_add)
    new_text = text[: line_end + 1] + insertion + text[line_end + 1 :]
    ACCOUNTS_FILE.write_text(new_text, encoding="utf-8")

    return to_add
