"""
creator_intelligence.knowledge.base

【2026-07-04(6回目)新設】
KnowledgeStoreの抽象インターフェース。knowledge_registry.pyはこのインターフェース
だけに依存し、保存先がGoogle SheetsかDBかは意識しない(Sprint2設計レビュー②)。

各メソッドが返す/受け取る「values」は、常に
{"成功パターン": str, "心理トリガー": str, "CTAパターン": str, "フック": str,
 "再利用可能な構成": str, "参考記事": str, "参考URL": str, "信頼度": str,
 "初回発見日": str, "最後に確認した日": str, "使用回数": int, "実績": str}
という列名キーのdict(sheets_writer.KNOWLEDGE_LIBRARY_HEADERSと同じ列構成)を想定する。
列構成自体を変える場合はsheets_writer.KNOWLEDGE_LIBRARY_HEADERSとこのdocstringの
両方を合わせて更新すること。
"""

from abc import ABC, abstractmethod


class KnowledgeStore(ABC):
    """知識ストア(knowledge_library)の読み書きインターフェース。"""

    @abstractmethod
    def all(self) -> list:
        """
        既存の全レコードを返す。
        戻り値: [{"id": 実装依存の識別子(updateにそのまま渡す), "values": dict}, ...]
        """
        raise NotImplementedError

    @abstractmethod
    def append(self, values: dict) -> None:
        """新しいレコードを1件追加する(初めて見るパターンの場合)。"""
        raise NotImplementedError

    @abstractmethod
    def update(self, record_id, values: dict) -> None:
        """既存レコードを更新する(record_idはall()が返した"id"をそのまま渡す)。"""
        raise NotImplementedError
