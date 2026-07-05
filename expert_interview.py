"""
expert_interview.py — DEPRECATED

「Expert Interview」という概念は廃止しました。
新名称は「Creator Conversation」です。

このファイルは後方互換性のためのシムです。
新しいコードでは creator_conversation.py を使用してください。

【2026-07-03: Creator Conversation に移行。このファイルは互換シム。】
"""

# 後方互換シム: 旧呼び出しを新モジュールに委譲
from creator_conversation import format_observations_for_display as format_interview_for_display  # noqa: F401


def run_expert_interview(theme: str = "", today: str = "", vertical_name: str = "専門家",
                         skip_if_no_tty: bool = True):
    """
    廃止済み。Creator Conversation を使用してください。
    シグネチャ変更（selected_topic必須）のため、ダミーTopicを渡す。
    """
    from creator_conversation import run_creator_conversation
    import world_context as wc
    world_ctx = wc.get_season_context(today or "2026-01-01")
    world_ctx.update({
        "social_trends": "", "life_trends": "",
        "psychology_trends": "", "hot_tension": theme,
        "audience_mood": "", "region": "",
    })
    dummy_topic = {"theme": theme or "（テーマ未設定）", "stars": 3, "reason": ""}
    return run_creator_conversation(
        selected_topic=dummy_topic,
        world_context=world_ctx,
        today=today,
        vertical_name=vertical_name,
        skip_if_no_tty=skip_if_no_tty,
    )
