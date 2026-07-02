"""
editorial_meeting.py
【2026-07-02: Editorial Meeting MVP — Creator Studio前段の「今日のテーマ会議」】

目的:
  Creator Studio がテーマを自動で決める前に、
  「なぜ今日このテーマを選ぶのか」を説明できる状態を作る。

  世の中の流れ（ニュース・季節・検索トレンド・SNSトレンド）と
  CORE HARIの専門知見を照合し、今日作るべき投稿候補5案を提示する。

OpenAIコスト: 0（ルールベース）
Society Intelligence: 現在はスタブ（月・季節・曜日・イベントのルールで代替）
                     将来は SocietyIntelligence.collect_all() に差し替え可能。
"""

import datetime
from typing import Optional


# ────────────────────────────────────────────────────────────────────────────
# 社会的文脈テーブル（Society Intelligence スタブ）
#
# 将来は creator_intelligence/society/ の各 Provider に差し替える。
# キー: month (1〜12)
# ────────────────────────────────────────────────────────────────────────────

_MONTHLY_SOCIETY = {
    1:  {
        "season":   "新年・冬",
        "topics":   ["新年の体型・顔リセット", "乾燥肌・むくみ対策", "新年の目標設定",
                     "コートとフェイスライン", "年末年始の疲れ顔"],
        "beauty_mood": "リセット・新しい自分",
    },
    2:  {
        "season":   "冬・バレンタイン前",
        "topics":   ["バレンタイン前の美容需要", "乾燥・くすみ対策", "花粉症前のスキンケア",
                     "寒さと顔のむくみ", "マスク生活と顔筋の衰え"],
        "beauty_mood": "好きな人に会う前の美容",
    },
    3:  {
        "season":   "春・花粉・新生活",
        "topics":   ["花粉症と顔のむくみ", "新生活前の印象改善", "春の紫外線対策",
                     "卒業・入学シーズンの写真映え", "年度末疲れと顔のたるみ"],
        "beauty_mood": "新しいスタートへの準備",
    },
    4:  {
        "season":   "春・新生活・GW前",
        "topics":   ["新社会人の第一印象", "GW前の美容準備", "春の代謝アップ",
                     "マスク解禁後の素顔への不安", "写真撮影・集合写真シーズン"],
        "beauty_mood": "素顔への自信",
    },
    5:  {
        "season":   "初夏・GW明け",
        "topics":   ["GW明けの疲れ顔", "紫外線増加と肌ダメージ", "半袖シーズンの首・フェイスライン",
                     "アレルギー・むくみ対策", "母の日ギフト需要"],
        "beauty_mood": "夏に向けた引き締め",
    },
    6:  {
        "season":   "梅雨・初夏",
        "topics":   ["湿気と浮腫み", "梅雨の姿勢悪化と顔への影響", "夏前の小顔需要",
                     "冷房対策と首・肩の凝り", "ノースリーブ・デコルテへの意識"],
        "beauty_mood": "夏前ラストスパート",
    },
    7:  {
        "season":   "夏・海水浴・お盆前",
        "topics":   ["夏の紫外線と顔の老化", "汗・毛穴と肌トラブル", "夏バテと顔のくすみ",
                     "浴衣・夏イベントの美容", "冷房による顔の乾燥"],
        "beauty_mood": "夏の素肌・笑顔への自信",
    },
    8:  {
        "season":   "真夏・お盆",
        "topics":   ["お盆帰省と久しぶりの再会", "夏の疲れと顔の老け感", "日焼け後のケア",
                     "クーラー病と顔のむくみ", "残暑と美容習慣の見直し"],
        "beauty_mood": "夏の疲れを顔に出さない",
    },
    9:  {
        "season":   "初秋・衣替え",
        "topics":   ["衣替えと印象チェンジ", "秋の乾燥と顔の老け込み", "スポーツの秋と顔筋",
                     "残暑ダメージのケア", "秋の新しいチャレンジ"],
        "beauty_mood": "秋にむけてリセット",
    },
    10: {
        "season":   "秋・ハロウィン",
        "topics":   ["ハロウィン・仮装と小顔願望", "秋の乾燥とたるみ", "気温差と顔のむくみ",
                     "食欲の秋と顔への影響", "年末に向けた美容準備"],
        "beauty_mood": "変身願望・なりたい自分",
    },
    11: {
        "season":   "晩秋・年末準備",
        "topics":   ["年末パーティーへの準備", "冷え性と顔のくすみ", "忘年会シーズンの写真映え",
                     "冬の乾燥対策", "来年に向けた美容計画"],
        "beauty_mood": "年末に向けた仕上げ",
    },
    12: {
        "season":   "冬・年末年始",
        "topics":   ["クリスマス・年末の美容仕上げ", "忘年会・新年会の写真映え",
                     "年末疲れと顔のたるみ", "来年の美容目標", "冬の乾燥と顔のコリ"],
        "beauty_mood": "一年の締めくくり・晴れ舞台",
    },
}

# 曜日別の視聴者心理（何曜日に何を求めているか）
_DOW_MINDSET = {
    0: ("月", "週の始まり・新しいスタート気分 / 「今週から変えたい」という意欲が高い"),
    1: ("火", "仕事リズムに戻った / 実用的・知識系コンテンツに反応しやすい"),
    2: ("水", "週の折り返し / 「自分のために時間を使いたい」気持ちが出る"),
    3: ("木", "週末が見えてきた / 「週末の予定に向けて準備したい」モードが始まる"),
    4: ("金", "週末前 / 「自分へのご褒美・お出かけ・人に会う」への意識が高い"),
    5: ("土", "週末・休日 / ゆっくり見るコンテンツ・保存して後で実践 が合う"),
    6: ("日", "週末最終日 / 「来週から頑張ろう」「今日1日を有意義に」モード"),
}

# CORE HARI のテーマ候補（社会トピック → CORE HARI視点への変換マップ）
_CORE_HARI_ANGLES = [
    {
        "trigger_keywords": ["むくみ", "顔のむくみ", "浮腫み", "乾燥", "冷え"],
        "theme": "顔のむくみはリンパではなく咬筋の緊張から来る",
        "core_hari_perspective": "咬筋が緊張していると、顔全体の血行・リンパが滞る。マッサージより先に筋肉のクセを直す。",
        "hook_seed": "「顔がむくんでる」と思ったとき、多くの人が間違えていること",
        "cta_type": "保存",
    },
    {
        "trigger_keywords": ["老け", "たるみ", "疲れ顔", "老化", "くすみ", "老け込み"],
        "theme": "老け見えの正体は骨格ではなく表情グセの積み重ね",
        "core_hari_perspective": "表情グセが毎日少しずつ顔の形を変える。骨格矯正では変わらない、表情筋を変えることで変わる。",
        "hook_seed": "「骨格だから仕方ない」と思っていませんか？　正直に言います",
        "cta_type": "フォロー",
    },
    {
        "trigger_keywords": ["フェイスライン", "小顔", "二重顎", "首", "デコルテ"],
        "theme": "フェイスラインは姿勢と舌の位置で決まる",
        "core_hari_perspective": "舌が下がっていると、顔全体が重力に負ける。姿勢・舌の位置・咬筋のセットで変わる。",
        "hook_seed": "「小顔になりたい」と思っている人が知らないこと",
        "cta_type": "保存",
    },
    {
        "trigger_keywords": ["左右差", "歪み", "非対称", "癖", "グセ"],
        "theme": "顔の左右差はクセから来る — 咬筋の左右差という視点",
        "core_hari_perspective": "左右どちらかで噛む癖が咬筋の左右差を作り、顔の非対称につながる。",
        "hook_seed": "「顔が左右非対称」と悩んでいる方へ、正直に言います",
        "cta_type": "フォロー",
    },
    {
        "trigger_keywords": ["写真", "映え", "撮影", "集合写真", "印象", "再会"],
        "theme": "写真で老けて見える原因は「表情筋のコリ」にある",
        "core_hari_perspective": "表情筋がコリ固まると、笑顔が引きつる。意識した笑顔より、普段の表情グセを直す方が効果的。",
        "hook_seed": "「写真の自分が嫌い」と感じる方へ",
        "cta_type": "問い合わせ",
    },
    {
        "trigger_keywords": ["自信", "印象", "第一印象", "素顔", "マスク解禁", "新生活"],
        "theme": "顔への自信は骨格ではなく「表情筋の使い方」で変わる",
        "core_hari_perspective": "「素顔に自信がない」のは骨格の問題ではなく、表情筋の使い方のクセが原因のことが多い。",
        "hook_seed": "「素顔に自信がない」という方へ、伝えたいことがあります",
        "cta_type": "フォロー",
    },
    {
        "trigger_keywords": ["施術", "エステ", "コスト", "何回", "続ける", "効果", "タイムライン"],
        "theme": "小顔矯正の正直なタイムライン — 何回で何が変わるか",
        "core_hari_perspective": "1回目は感覚変化。3回目で印象変化。6回以上で定着。正直に伝えることが信頼につながる。",
        "hook_seed": "「何回で変わりますか？」に正直に答えます",
        "cta_type": "問い合わせ",
    },
    {
        "trigger_keywords": ["コリ", "肩こり", "頭痛", "姿勢", "スマホ", "デスクワーク"],
        "theme": "スマホ・デスクワークが顔を老けさせる理由",
        "core_hari_perspective": "前傾姿勢が続くと咬筋と首の筋肉が連動して緊張し、フェイスラインがたるむ。",
        "hook_seed": "「最近顔が重い」と感じたら、姿勢を見てください",
        "cta_type": "保存",
    },
    {
        "trigger_keywords": ["表情", "笑顔", "感情表現", "表情豊か"],
        "theme": "「表情が乏しい」と言われる原因は表情筋のコリにある",
        "core_hari_perspective": "表情筋は約60種類。使わない筋肉がコリ固まると、感情は動いているのに表情が出にくくなる。",
        "hook_seed": "「表情が硬い」と言われたことがある方へ",
        "cta_type": "フォロー",
    },
    {
        "trigger_keywords": ["ダイエット", "痩せ", "体型", "リセット", "新年", "目標"],
        "theme": "顔痩せはカロリー制限では変わらない理由",
        "core_hari_perspective": "顔の大きさは骨格×脂肪ではなく、筋肉のコリ・むくみ・姿勢の組み合わせで決まる。",
        "hook_seed": "「痩せたのに顔だけ変わらない」という方へ",
        "cta_type": "保存",
    },
]


# ────────────────────────────────────────────────────────────────────────────
# メイン関数
# ────────────────────────────────────────────────────────────────────────────

def run_editorial_meeting(today: str, past_themes: Optional[list] = None) -> dict:
    """
    Editorial Meeting を実行し、結果 dict を返す。

    Args:
        today:       "YYYY-MM-DD"
        past_themes: 過去7日のテーマリスト（重複回避に使う）

    Returns:
        {
          "date":                今日の日付,
          "society_signals":     TOP5社会トレンド,
          "core_hari_connections": CORE HARIとの接点,
          "follower_wants":      フォロワーが今知りたいこと,
          "candidates":          5案 [{ theme, hook_seed, reason, cta_type }, ...],
          "selected":            採用案,
          "selection_reason":    採用理由,
          "similarity_warning":  昨日との類似警告(あれば),
        }
    """
    past_themes = past_themes or []

    dt  = datetime.date.fromisoformat(today)
    dow = dt.weekday()
    month = dt.month

    society_ctx  = _MONTHLY_SOCIETY.get(month, _MONTHLY_SOCIETY[7])
    dow_name, dow_mindset = _DOW_MINDSET[dow]

    # ── 1. 今日、世の中で話題になっていること TOP5 ─────────────────────
    season_topics = society_ctx["topics"][:5]
    society_signals = [
        {"rank": i+1, "topic": t, "source": "季節・SNSトレンド（推定）"}
        for i, t in enumerate(season_topics)
    ]

    # ── 2. CORE HARIと接点があるテーマ ────────────────────────────────
    connections = []
    for topic_dict in society_signals:
        topic_text = topic_dict["topic"]
        for angle in _CORE_HARI_ANGLES:
            if any(kw in topic_text for kw in angle["trigger_keywords"]):
                connections.append({
                    "society_topic": topic_text,
                    "core_hari_theme": angle["theme"],
                    "perspective": angle["core_hari_perspective"],
                })
                break

    # ── 3. フォロワーが今知りたいこと ─────────────────────────────────
    beauty_mood = society_ctx["beauty_mood"]
    follower_wants = [
        f"{season_topics[0]}について CORE HARI ならではの視点",
        f"{dow_mindset.split('/')[0].strip()} の気分に合った美容情報",
        f"{beauty_mood} を叶えるための専門家の正直な答え",
        "他のサロンが言わない、顔の仕組みの話",
        "「続きも見たい」と思えるシリーズ化できる知識",
    ]

    # ── 4. 今日作るべき投稿候補を5案 ────────────────────────────────
    candidates = _build_candidates(
        society_signals, dow, month, beauty_mood, past_themes
    )

    # ── 5. 採用理由付きで1案を選択 ──────────────────────────────────
    selected, reason, warning = _select_candidate(candidates, past_themes, dow, beauty_mood)

    return {
        "date":                   today,
        "dow":                    dow_name,
        "season":                 society_ctx["season"],
        "beauty_mood":            beauty_mood,
        "dow_mindset":            dow_mindset,
        "society_signals":        society_signals,
        "core_hari_connections":  connections,
        "follower_wants":         follower_wants,
        "candidates":             candidates,
        "selected":               selected,
        "selection_reason":       reason,
        "similarity_warning":     warning,
    }


def _build_candidates(
    society_signals: list,
    dow: int,
    month: int,
    beauty_mood: str,
    past_themes: list,
) -> list:
    """
    5案の投稿候補を生成する。
    過去テーマと重複しない + 季節性・曜日性を反映。
    """
    # 季節トレンドに合う角度を優先スコアで並べる
    scored = []
    for angle in _CORE_HARI_ANGLES:
        score = 0
        for sig in society_signals:
            if any(kw in sig["topic"] for kw in angle["trigger_keywords"]):
                score += (6 - sig["rank"])  # 上位ほど高スコア

        # 過去テーマと類似なら減点
        for pt in past_themes:
            if pt and (angle["theme"][:10] in pt or pt[:10] in angle["theme"]):
                score -= 5

        # 曜日補正: 月曜=フォロー系、金=問い合わせ系、週末=保存系
        if dow in (0, 1, 6) and angle["cta_type"] == "フォロー":
            score += 2
        if dow in (4, 5) and angle["cta_type"] in ("問い合わせ", "保存"):
            score += 2

        scored.append((score, angle))

    scored.sort(key=lambda x: x[0], reverse=True)

    candidates = []
    seen_themes = set()
    for score, angle in scored:
        if angle["theme"] in seen_themes:
            continue
        if len(candidates) >= 5:
            break

        # 採用理由を自動生成
        reasons = []
        for sig in society_signals[:3]:
            if any(kw in sig["topic"] for kw in angle["trigger_keywords"]):
                reasons.append(f"「{sig['topic']}」というトレンドと接点がある")
        if angle["cta_type"] == "フォロー" and dow in (0, 1, 6):
            reasons.append("週初め〜週末最終日はフォロー獲得に効果的なタイミング")
        if angle["cta_type"] == "保存" and dow in (5, 6):
            reasons.append("週末は「後で読み返す」保存行動が増える")
        if any(kw in beauty_mood for kw in angle["trigger_keywords"]):
            reasons.append(f"今月の視聴者気分「{beauty_mood}」と一致する")
        if not reasons:
            reasons.append("CORE HARIの専門性を最も活かせるテーマ")

        candidates.append({
            "no":          len(candidates) + 1,
            "theme":       angle["theme"],
            "hook_seed":   angle["hook_seed"],
            "cta_type":    angle["cta_type"],
            "perspective": angle["core_hari_perspective"],
            "reason":      " / ".join(reasons[:2]),
            "score":       score,
        })
        seen_themes.add(angle["theme"])

    # 5案に満たない場合はデフォルト補充
    defaults = [
        {
            "no": len(candidates) + 1,
            "theme": "顔の悩みに向き合うための正直な話",
            "hook_seed": "「変わらないかも」と思っていませんか？",
            "cta_type": "フォロー",
            "perspective": "正直であることがCORE HARIの最大の専門性",
            "reason": "信頼構築として常に有効なテーマ",
            "score": 0,
        },
    ]
    while len(candidates) < 5:
        d = defaults[0].copy()
        d["no"] = len(candidates) + 1
        candidates.append(d)

    return candidates[:5]


def _select_candidate(
    candidates: list,
    past_themes: list,
    dow: int,
    beauty_mood: str,
) -> tuple:
    """
    5案から1案を選び、（選択案, 理由, 類似警告）を返す。

    選択ロジック:
      1. score が最も高い案を選ぶ
      2. 過去テーマと類似している場合は次点を選ぶ
      3. それでも類似なら警告を添えて最高スコア案を採用
    """
    yesterday_theme = past_themes[0] if past_themes else ""

    def _is_similar(theme: str, past: str) -> bool:
        if not past:
            return False
        # 最初の8文字が重なれば類似と判定
        return theme[:8] in past or past[:8] in theme

    selected = None
    warning  = ""

    for cand in sorted(candidates, key=lambda c: c["score"], reverse=True):
        if not _is_similar(cand["theme"], yesterday_theme):
            selected = cand
            break

    if selected is None:
        selected = candidates[0]
        warning = (
            f"昨日のテーマ「{yesterday_theme}」と類似した可能性があります。\n"
            f"全5案が類似している場合は、角度や切り口を変えて再生成を検討してください。"
        )

    reason = (
        f"[採用理由]\n"
        f"・テーマ: {selected['theme']}\n"
        f"・{selected['reason']}\n"
        f"・今日（{['月','火','水','木','金','土','日'][dow]}曜日）の視聴者気分は"
        f"「{beauty_mood}」— このテーマと合致する\n"
        f"・CTA: {selected['cta_type']}型"
    )
    if yesterday_theme:
        reason += f"\n・昨日のテーマ「{yesterday_theme}」と異なるテーマを選択"

    return selected, reason, warning


# ────────────────────────────────────────────────────────────────────────────
# 表示関数
# ────────────────────────────────────────────────────────────────────────────

def print_editorial_meeting(meeting: dict) -> None:
    """Editorial Meeting の結果をターミナルに出力する。"""
    W     = 64
    THICK = "━" * W
    THIN  = "─" * W

    def sec(title: str) -> None:
        print(f"\n  {title}")
        print(f"  {THIN}")

    def body(text: str, indent: int = 4) -> None:
        pad = " " * indent
        for line in (text or "").splitlines():
            print(f"{pad}{line}")

    print(f"\n{THICK}")
    print(f"  📋 Editorial Meeting  [{meeting['date']} ({meeting['dow']}曜日)]")
    print(f"  季節: {meeting['season']}  /  視聴者気分: {meeting['beauty_mood']}")
    print(f"  曜日の特性: {meeting['dow_mindset']}")
    print(THICK)

    # 1. 今日の社会トレンド TOP5
    sec("1. 今日、世の中で話題になっていること TOP5")
    for sig in meeting["society_signals"]:
        print(f"    {sig['rank']}. {sig['topic']}")
        print(f"       → 出典: {sig['source']}")

    # 2. CORE HARIとの接点
    sec("2. CORE HARIと接点があるテーマ")
    conns = meeting["core_hari_connections"]
    if conns:
        for c in conns:
            print(f"    ・社会トレンド 「{c['society_topic']}」")
            print(f"      → CORE HARI視点: {c['core_hari_theme']}")
    else:
        print("    （接点なし — デフォルトテーマで対応）")

    # 3. フォロワーが今知りたいこと
    sec("3. フォロワーが今知りたいこと")
    for i, w in enumerate(meeting["follower_wants"], 1):
        print(f"    {i}. {w}")

    # 4. 投稿候補5案
    sec("4. 今日作るべき投稿候補 5案")
    for cand in meeting["candidates"]:
        selected_mark = "  ★ 採用 " if cand == meeting["selected"] else f"  案{cand['no']}    "
        print(f"\n  {selected_mark} 【{cand['theme']}】")
        print(f"      Hook候補: 「{cand['hook_seed']}」")
        print(f"      CTA型   : {cand['cta_type']}")
        print(f"      選定理由: {cand['reason']}")

    # 5. 採用理由
    sec("5. 採用した理由")
    body(meeting["selection_reason"])

    # 類似警告
    if meeting["similarity_warning"]:
        print(f"\n  ⚠️  類似警告:")
        body(meeting["similarity_warning"])

    print(f"\n{THICK}\n")
