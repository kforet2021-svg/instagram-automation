"""
world_context.py

World Context Engine: 毎日の社会・生活・心理トレンドを収集する。

SNSだけを分析することを禁止する。
社会トレンド × 生活トレンド × 心理トレンドを抽出し、
「専門家が今このタイミングで何を発信すべきか」の土台を作る。

収集観点:
  社会トレンド : ニュース・AI・経済・制度変更・イベント・スポーツ・映画・ドラマ
  生活トレンド : 旅行・消費・Amazon/楽天・検索・口コミ・SNS動向
  心理トレンド : 人々が今何を感じているか、何を不安に思っているか、何を求めているか
  季節文脈    : 季節・気温・湿度・紫外線・花粉・大型連休

出力 (dict):
  season         : 季節（春/梅雨/夏/秋/冬）
  month_context  : 今月の生活文脈
  uv_level       : 紫外線レベル（テキスト）
  pollen_level   : 花粉レベル（テキスト）
  holiday_context: 大型連休・季節イベント
  social_trends  : 社会トレンド（箇条書きテキスト）
  life_trends    : 生活トレンド（箇条書きテキスト）
  psychology_trends: 心理トレンド（今人々が感じていること）
  hot_tension    : 今この瞬間の「最大の関心事・緊張感」
  audience_mood  : ターゲット層の今の気分・心理状態

【2026-07-03(1回目): 新規作成。6ステップ生成フロー — Step1。】
"""

from __future__ import annotations
import datetime
from typing import Optional


# ── 季節・環境情報（AIコストゼロ、日付から計算）───────────────────────────

def get_season_context(today: str) -> dict:
    """
    日付から季節・環境情報を計算する（APIコストゼロ）。

    戻り値: season, month_context, uv_level, pollen_level, holiday_context
    """
    try:
        d = datetime.date.fromisoformat(today)
    except Exception:
        d = datetime.date.today()

    month = d.month
    day   = d.day

    # 季節
    if month in (3, 4):
        season = "春"
    elif month == 5:
        season = "初夏"
    elif month == 6:
        season = "梅雨"
    elif month in (7, 8):
        season = "夏"
    elif month == 9:
        season = "初秋"
    elif month in (10, 11):
        season = "秋"
    elif month == 12:
        season = "初冬"
    else:
        season = "冬"

    # 月別の生活文脈
    month_context_map = {
        1:  "新年・目標設定・乾燥対策・正月疲れ",
        2:  "バレンタイン・寒さピーク・花粉始まり",
        3:  "卒業・異動準備・花粉ピーク・春の変わり目",
        4:  "新生活・入学・花粉・気温差大きい",
        5:  "GW・連休疲れ・紫外線増加・5月病",
        6:  "梅雨・湿気・気だるさ・夏準備",
        7:  "夏本番・紫外線MAX・熱中症・お盆準備",
        8:  "お盆・猛暑・夏疲れ・秋準備",
        9:  "残暑・台風・秋始まり・衣替え",
        10: "秋本番・行楽・乾燥始まり・肌荒れ",
        11: "文化祭・紅葉・年末準備・冷え対策",
        12: "年末・忘年会・乾燥・冷え・大掃除",
    }

    # 紫外線レベル（日本・簡易）
    uv_map = {
        1: "低い", 2: "低い", 3: "やや強い", 4: "強い",
        5: "強い", 6: "非常に強い", 7: "最大級", 8: "最大級",
        9: "強い", 10: "やや強い", 11: "低い", 12: "低い",
    }

    # 花粉レベル（日本・簡易）
    pollen_map = {
        1: "ほぼなし（飛散準備期）", 2: "スギ花粉 始まり",
        3: "スギ花粉 ピーク", 4: "スギ終わり・ヒノキ",
        5: "ヒノキ終盤・ほぼ終了", 6: "ほぼなし",
        7: "ほぼなし", 8: "ほぼなし", 9: "ブタクサ（秋花粉）",
        10: "ブタクサ終わり", 11: "ほぼなし", 12: "ほぼなし",
    }

    # 大型連休・季節イベント
    holiday_map = {
        1:  "正月三が日・成人の日",
        2:  "節分・バレンタイン",
        3:  "卒業式シーズン・春分の日",
        4:  "入学式・新生活スタート・昭和の日",
        5:  "GW（5/3〜6）・母の日",
        6:  "梅雨入り・父の日",
        7:  "海の日・夏休み前半・七夕",
        8:  "お盆（8/13〜15）・夏休み後半",
        9:  "防災の日・シルバーウィーク",
        10: "体育の日・ハロウィン",
        11: "七五三・文化の日・勤労感謝の日",
        12: "クリスマス・年末・大晦日",
    }

    return {
        "season":          season,
        "month":           month,
        "month_context":   month_context_map.get(month, ""),
        "uv_level":        uv_map.get(month, ""),
        "pollen_level":    pollen_map.get(month, ""),
        "holiday_context": holiday_map.get(month, ""),
    }


# ── World Context（AIが社会・生活・心理トレンドを合成）─────────────────────

def get_world_context(today: str, region: str = "") -> dict:
    """
    World Context を取得する。

    Step1: 季節文脈をAIコストゼロで計算
    Step2: OpenAI で社会・生活・心理トレンドを合成（1回）

    region: 地域名（省略時は config.REGION を使用）。全国より地域情報を優先。

    戻り値: 季節情報 + social_trends + life_trends + psychology_trends + hot_tension + audience_mood
    """
    if not region:
        try:
            from config import REGION
            region = REGION
        except Exception:
            region = ""

    season_ctx = get_season_context(today)

    # AIによるトレンド合成（地域優先）
    ai_trends = _fetch_ai_trends(today, season_ctx, region=region)

    return {**season_ctx, **ai_trends, "region": region}


def _fetch_ai_trends(today: str, season_ctx: dict, region: str = "") -> dict:
    """OpenAI でソーシャル・生活・心理トレンドを合成する（1回）。"""
    try:
        from openai_analyzer import get_world_context_trends
        return get_world_context_trends(today, season_ctx, region=region)
    except Exception as e:
        print(f"  ⚠️ World Context AI取得失敗（フォールバック使用）: {e}")
        return _fallback_trends(season_ctx)


def _fallback_trends(season_ctx: dict) -> dict:
    """AI失敗時のフォールバック（季節文脈から簡易推定）。"""
    season = season_ctx.get("season", "")
    month_ctx = season_ctx.get("month_context", "")

    return {
        "social_trends":    f"（取得失敗）{season}の時期のニュース・トレンドを参照してください",
        "life_trends":      f"生活文脈: {month_ctx}",
        "psychology_trends": f"{season}の疲れ・変化への適応・{month_ctx}",
        "hot_tension":      f"{season}ならではの体の変化・悩み",
        "audience_mood":    f"{season}を意識した生活改善への関心",
    }


# ── 表示 ─────────────────────────────────────────────────────────────────────

def print_world_context(ctx: dict) -> None:
    """World Context をターミナルに表示する。"""
    W = 60
    THICK = "=" * W
    THIN  = "-" * W

    print()
    print(THICK)
    print("  ① WORLD CONTEXT")
    print(THICK)

    print(f"\n  【季節・環境】")
    print(f"    季節      : {ctx.get('season', '')}  （{ctx.get('month_context', '')}）")
    print(f"    紫外線    : {ctx.get('uv_level', '')}")
    print(f"    花粉      : {ctx.get('pollen_level', '')}")
    if ctx.get("holiday_context"):
        print(f"    イベント  : {ctx.get('holiday_context', '')}")

    if ctx.get("social_trends"):
        print(f"\n  【社会トレンド】")
        for line in ctx["social_trends"].splitlines():
            if line.strip():
                print(f"    {line.strip()}")

    if ctx.get("life_trends"):
        print(f"\n  【生活トレンド】")
        for line in ctx["life_trends"].splitlines():
            if line.strip():
                print(f"    {line.strip()}")

    if ctx.get("psychology_trends"):
        print(f"\n  【心理トレンド — 今人々が感じていること】")
        for line in ctx["psychology_trends"].splitlines():
            if line.strip():
                print(f"    {line.strip()}")

    if ctx.get("hot_tension"):
        print(f"\n  【今の最大関心事】")
        print(f"    {ctx['hot_tension']}")

    print()


def derive_audience_psychology(world_context: dict, vertical_name: str = "専門家") -> dict:
    """
    World Context から Audience Psychology を導出する（AIコストゼロ）。

    Layer 2 で定義するほど重くせず、World Context の心理トレンドを
    「今日の読者心理」に変換する。

    戻り値:
      reader_mindset   : 今日の読者の心理状態
      reader_anxiety   : 今の読者が感じている不安・悩み
      reader_desire    : 今の読者が本当に求めているもの
      content_direction: この心理に応える投稿の方向性
    """
    psychology = world_context.get("psychology_trends", "")
    mood       = world_context.get("audience_mood", "")
    tension    = world_context.get("hot_tension", "")
    season     = world_context.get("season", "")
    month_ctx  = world_context.get("month_context", "")

    reader_anxiety   = tension if tension else f"{season}による体の変化・疲れ"
    reader_desire    = f"{season}を気持ちよく過ごしたい・{month_ctx}に適応したい"
    reader_mindset   = mood if mood else psychology[:80] if psychology else f"{season}の生活を整えたい"

    content_direction = (
        f"「{season}ならではの体の変化」を入口にする。\n"
        f"「今この時期に知っておきたい」タイミング感を持たせる。\n"
        f"「自分で試せる」具体的なアクションで締める。"
    )

    return {
        "reader_mindset":    reader_mindset,
        "reader_anxiety":    reader_anxiety,
        "reader_desire":     reader_desire,
        "content_direction": content_direction,
    }
