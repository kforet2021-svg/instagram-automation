"""
phase2/model_pricing.py

OpenAIモデル単価設定。1Mトークンあたりのドル単価。
単価不明なモデルはこのファイルに追記する。
単価が未登録の場合は post_generator.py が「推定不可」を表示する。

【2026-07-15(1回目): 新規作成。】
"""

# モデル名 → {"input": ドル/1Mトークン, "output": ドル/1Mトークン}
PRICING: dict[str, dict[str, float]] = {
    "gpt-4o-mini":        {"input": 0.150,  "output": 0.600},
    "gpt-4o-mini-2024-07-18": {"input": 0.150, "output": 0.600},
    "gpt-4o":             {"input": 2.500,  "output": 10.000},
    "gpt-4o-2024-11-20":  {"input": 2.500,  "output": 10.000},
    "gpt-4o-2024-08-06":  {"input": 2.500,  "output": 10.000},
    "gpt-4-turbo":        {"input": 10.000, "output": 30.000},
    "gpt-4":              {"input": 30.000, "output": 60.000},
    "o1-mini":            {"input": 1.100,  "output": 4.400},
    "o1":                 {"input": 15.000, "output": 60.000},
    "o3-mini":            {"input": 1.100,  "output": 4.400},
}

# 為替レート（表示用のみ。実際の請求はUSD）
USD_TO_JPY = 155.0


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> str:
    """
    トークン数から推定費用を文字列で返す。
    単価不明なモデルは「推定不可」を返す。
    """
    p = PRICING.get(model)
    if not p:
        return "推定不可（単価未登録モデル）"
    usd = (input_tokens * p["input"] + output_tokens * p["output"]) / 1_000_000
    jpy = usd * USD_TO_JPY
    return f"${usd:.4f}（約{jpy:.1f}円）"
