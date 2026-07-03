# PROJECT PRINCIPLES

## Mission

私たちが作るのはInstagram自動投稿ツールではない。

専門家の「思考」をAIが学び、
その専門家らしい発信・提案・教育・コンテンツ作成を支援する
Creator Intelligence Platformを作る。

CORE HARIは最初の実証実験であり、
美容専用システムではない。

将来的には

・税理士
・弁護士
・整体師
・コンサルタント
・営業
・マーケター
・講師

など、
あらゆる専門家へ展開できる設計を目指す。

---

# Architecture: 5-Layer Design

```
Layer 1  Business Strategy    なぜ発信するか（Mission・Target・Transformation）
Layer 2  Account Strategy     何を軸に発信するか（Pillar・Positioning・Voice）
Layer 3  Platform Engine      どのプラットフォームで、どう届けるか
           └ Instagram / Threads / TikTok / YouTube / X
               それぞれ独立したDNAと生成ロジックを持つ
Layer 4  Creator Intelligence 専門家の思考を蓄積する
           └ 口ぐせ / 診断 / 価値観 / 観察 / 思い込み / Question / Observation / Thinking
Layer 5  Content Engine       Layer1〜4を統合し、各プラットフォーム向けに独立生成
```

**Platform流用禁止ルール（絶対）**

- InstagramのコンテンツをThreadsへ流用してはならない
- ThreadsのコンテンツをInstagramへ流用してはならない
- 各プラットフォームはDNAが異なる。同じテーマでも生成ロジックは完全に独立させる

---

# First Principles

AIは文章を覚えない。

AIが学ぶのは専門家の「思考・会話・感覚」である。

**Layer4 — Creator Intelligence（蓄積する思考タイプ）**

Expert Interviewから自然に集まるもの（会話・感覚）:
・口ぐせ     専門家が自然に使う言葉・フレーズ
・診断       専門家がクライアントの状態をどう読むか
・価値観     専門家の核心的な信念・こだわり
・観察       専門家が現場で繰り返し気づくこと
・思い込み   クライアントがよく持つ誤解・勘違い

システマティックな知識（構造化）:
・Question    専門家がクライアントに問いかける質問
・Observation 観察を構造化したもの（再現性ある発見）
・Thinking    専門家の思考プロセス・推論の流れ

投稿は毎回生成する。

資産になるのは
投稿ではなく思考である。

---

# Development Rules

新しい機能を作る前に必ず考える。

この機能は

① CORE HARI専用なのか

② 全業種で利用できる設計なのか

専用機能ではなく、
汎用化できる構造を優先する。

新しいプラットフォーム向けコンテンツを追加するときは:

① そのプラットフォームのDNAを先に定義する（`layer3_platform/`）
② 既存プラットフォームのコンテンツを流用しない
③ PlatformEngineを継承した独立したクラスを作る

---

# Knowledge Rules

Expert Interviewから集まる思考は全てLayer4に保存する。

知識タイプ（口ぐせ/診断/価値観/観察/思い込み/Question/Observation/Thinking）を
必ず明示して保存する。

どのプラットフォームに最も活きる思考かを記録する（platform_fit）。

思考は専門家の言葉に近い形で保存する（要約・解釈を加えすぎない）。

---

# Content Rules

投稿を保存しない。

思考だけ保存する。

各プラットフォームのコンテンツは独立生成する:

- Instagram: 視覚的・保存CTAを軸に
- Threads:   思考の途中・会話を軸に
- TikTok:    エンタメ・驚き・共感を軸に
- YouTube:   深さ・権威・体系を軸に
- X:         断言・逆説・鋭い一言を軸に

「最適化」ではなく「そのプラットフォームで生まれたコンテンツ」を作る。

---

# AI Behavior

AIは答えを教えるAIではない。

Creator Intelligenceは専門家インタビューAIである。

専門家のように

観察し（Observation）

質問し（Question）

考え（Thinking）

提案する（Content）。

Expert Interviewで専門家の「口ぐせ・診断・価値観・観察・思い込み」を引き出す。
テーマから投稿を作ることは禁止。必ず専門家の会話から投稿を生成する。

---

# CEO Rule

設計で迷ったら必ずMissionへ戻る。

Instagramを作っているのではない。

Creator Intelligenceを作っている。

プラットフォームは出力先の一つでしかない。

今後すべての実装は
このファイルを最優先で参照すること。
