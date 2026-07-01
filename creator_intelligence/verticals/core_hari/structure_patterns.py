"""
creator_intelligence/verticals/core_hari/structure_patterns.py

CORE HARI FACE が使う「構造パターン」定義。

【重要】ここに書くのは「構造・フック型・CTA型・心理トリガー」だけ。
投稿の内容（実際のセリフ・知識・解説文）は一切書かない。
内容は core_hari_kb シートの KBEntry から取得して組み立てる。

これらの構造パターンは Instagram 分析から学んだ「伸びる型」を
CORE HARI 向けに選定したものであり、型そのものは他の Vertical でも再利用できる。
"""

from creator_intelligence.platform.vertical_base import StructurePattern

# 7パターン（月〜日のローテーション）
# required_kb_tags: このパターンを使うために KB に必要なタグ
# proposed_kb_topics: KB 不足時に提案する知識候補のトピック名
CORE_HARI_STRUCTURE_PATTERNS = [

    # ── 月曜 ─────────────────────────────────────────────────────────
    StructurePattern(
        pattern_id="edu_3step",
        hook_type="疑問形（〜って〜ですか？）",
        structure="疑問提示 → 3ステップ解説 → 保存CTA",
        cta_type="保存",
        mission="保存を狙う",
        psychology_trigger="情報ギャップ（答えが気になって最後まで見る）",
        required_kb_tags=["仕組み", "施術"],
        proposed_kb_topics=[
            "小顔矯正の仕組み（何に働きかけるのか）",
            "施術中に起きていること（筋肉・リンパ・骨格それぞれの変化）",
            "施術の痛みの有無と感覚",
        ],
    ),

    # ── 火曜 ─────────────────────────────────────────────────────────
    StructurePattern(
        pattern_id="cause_reveal",
        hook_type="共感フック（〜が気になる方へ）",
        structure="悩み共感 → 原因の正体 → 解決の方向性 → 保存CTA",
        cta_type="保存",
        mission="保存を狙う",
        psychology_trigger="原因帰属（自分の悩みの理由が分かる→保存したくなる）",
        required_kb_tags=["原因", "たるみ", "老け見え"],
        proposed_kb_topics=[
            "たるみ・老け見えの主な原因（顔筋・重力・生活習慣）",
            "顔筋が衰えるとどうなるか（具体的な変化）",
            "CORE HARIがアプローチする仕組み",
        ],
    ),

    # ── 水曜 ─────────────────────────────────────────────────────────
    StructurePattern(
        pattern_id="myth_busting",
        hook_type="否定形フック（〜は本当ですか？）",
        structure="通説への疑問 → 正しい情報 → CORE HARIの立場 → 保存CTA",
        cta_type="保存",
        mission="保存を狙う",
        psychology_trigger="認知的不協和（「知ってると思ってたことが違う」という驚き）",
        required_kb_tags=["誤解", "むくみ", "骨格"],
        proposed_kb_topics=[
            "骨格だから無理、という誤解とその実態",
            "むくみ・リンパと骨格の違い（何が先に変わるか）",
            "CORE HARIが最初にアプローチする部位とその理由",
        ],
    ),

    # ── 木曜 ─────────────────────────────────────────────────────────
    StructurePattern(
        pattern_id="self_check",
        hook_type="行動提案フック（今日から直せる〜）",
        structure="気づき促進 → 3つのNG習慣・グセ → フォローCTA",
        cta_type="フォロー",
        mission="フォローを狙う",
        psychology_trigger="自己関連性（自分のことだと気づく → フォローして続きを見たくなる）",
        required_kb_tags=["生活習慣", "表情グセ", "左右差"],
        proposed_kb_topics=[
            "顔の老け見えを加速する表情グセ（具体例）",
            "噛み癖・寝方・スマホ姿勢が顔に与える影響",
            "顔の左右差の主な原因",
        ],
    ),

    # ── 金曜 ─────────────────────────────────────────────────────────
    StructurePattern(
        pattern_id="before_after_timeline",
        hook_type="正直フック（〜に正直に答えます）",
        structure="よくある疑問 → 1回目・3回目・6回目の変化 → 問い合わせCTA",
        cta_type="問い合わせ",
        mission="問い合わせを狙う",
        psychology_trigger="社会的証明 × 段階的期待（変化の具体的タイムラインで安心感）",
        required_kb_tags=["効果", "変化", "施術回数"],
        proposed_kb_topics=[
            "1回目の施術後に感じる変化（むくみ・軽さ・感覚）",
            "3回目前後で起きる変化（ライン・輪郭）",
            "6回目・継続後に起きる変化（定着・骨格バランス）",
            "個人差について正直に伝えるべきこと",
        ],
    ),

    # ── 土曜 ─────────────────────────────────────────────────────────
    StructurePattern(
        pattern_id="empathy_solution",
        hook_type="共感フック（〜が気になっていませんか？）",
        structure="悩みへの共感 → 原因特定 → 解決の方向性 → 保存CTA",
        cta_type="保存",
        mission="保存を狙う",
        psychology_trigger="共感 × 希望（あきらめなくていいと気づく）",
        required_kb_tags=["左右差", "生活習慣"],
        proposed_kb_topics=[
            "顔の左右差の主な原因（具体的な習慣・グセ）",
            "左右差に対してCORE HARIがどうアプローチするか",
            "セルフケアと施術を組み合わせる理由",
        ],
    ),

    # ── 日曜 ─────────────────────────────────────────────────────────
    StructurePattern(
        pattern_id="first_visit_guide",
        hook_type="安心フック（初めての方へ）",
        structure="不安の解消 → 当日の流れ全公開 → 問い合わせCTA",
        cta_type="問い合わせ",
        mission="問い合わせを狙う",
        psychology_trigger="不確実性の除去（知らないから怖い → 知れば踏み出せる）",
        required_kb_tags=["施術の流れ", "カウンセリング", "ホームケア"],
        proposed_kb_topics=[
            "初回カウンセリングで聞くこと・かかる時間",
            "施術中の流れと所要時間",
            "施術後のホームケア指導の内容",
            "初回に押しつけないと決めていること・理由",
        ],
    ),
]
