# Evaluation Rubric

- **Status:** Draft
- **Version:** 0.1
- **Date:** 2026-08-03
- **Applies to:** Bootstrap / MVP comparison
- **Primary comparison:** Single-model baseline vs. AI Research Lab OS

## 1. Purpose

本書は、AI研究室OSの出力が単体AIより実際に優れているかを、文章量や印象ではなく、再現可能な基準で比較するための評価規則を定める。

評価対象は「最も賢そうな回答」ではない。以下を同時に満たす回答を高く評価する。

- 事実として正確である
- 根拠を追跡・検証できる
- 強い反証と代替仮説を扱える
- 事実、推論、仮説、不確実性を区別する
- ユーザーの意思決定や次の検証行動に役立つ
- 品質向上に対して費用と処理時間が妥当である

## 2. Evaluation Principle

AI研究室OSは、単体AIより高得点であるだけでは採用しない。

次の条件を満たす必要がある。

1. 品質上の改善が再現される
2. 改善幅が追加コストと遅延に見合う
3. 致命的な事実誤認や架空引用を増やさない
4. 評価者が異なっても極端に結論が変わらない
5. 同じ質問と同じ条件で比較できる

## 3. Compared Systems

最低限、以下の条件を比較する。

### A. Single-model Baseline

1つのモデルに、最終回答の生成を直接依頼する。

### B. Single-model Structured Baseline

1つのモデルに、調査・反証・統合の手順を1つのプロンプト内で実行させる。

### C. AI Research Lab OS

Researcher、Skeptic、Synthesizerを分離し、定義されたプロトコルで処理する。

可能な場合は、各条件で同じモデルを使用し、「モデル差」と「OS構成差」を分離する。

## 4. Evaluation Conditions

比較時は、可能な限り以下を固定する。

- ユーザー質問
- 参照可能な資料
- 検索・ツール利用の可否
- 回答言語
- 最大処理時間
- 最大予算
- 温度などの生成設定
- 出力フォーマット
- 評価時点

モデル名、モデルバージョン、実行日時、プロンプト、ツール、入力資料は必ず保存する。

## 5. Scoring Scale

各品質項目は0〜5点で採点する。

| Score | Definition |
|---:|---|
| 0 | 要件を満たさない、または有害・無関係 |
| 1 | 深刻な欠陥があり、実用に耐えない |
| 2 | 一部有用だが、重要な誤り・欠落がある |
| 3 | 概ね有用だが、明確な改善余地がある |
| 4 | 高品質で、軽微な欠点のみ |
| 5 | 非常に高品質で、検証可能かつ目的に最適化されている |

## 6. Quality Dimensions

### 6.1 Factual Accuracy — Weight 20

評価対象：

- 検証可能な主張が正しいか
- 数値、固有名詞、因果関係を取り違えていないか
- 未確認事項を事実として断定していないか
- 資料間の矛盾を無視していないか

**5点:** 重要な主張が正確で、未確認事項は明示されている。

**0点:** 結論を左右する重大な事実誤認がある。

### 6.2 Evidence Quality and Traceability — Weight 15

評価対象：

- 根拠が主張を実際に支えているか
- 一次情報や適切な資料を優先しているか
- 引用・出典を追跡できるか
- 架空の文献、URL、数値がないか

**5点:** 主要主張と根拠の対応が明確で、第三者が検証できる。

**0点:** 根拠がない、追跡不能、または架空引用がある。

### 6.3 Reasoning Quality — Weight 15

評価対象：

- 結論までの論理が一貫しているか
- 相関と因果を区別しているか
- 前提条件が明示されているか
- 飛躍、循環論法、二重基準がないか

**5点:** 前提・推論・結論の関係が明瞭で、論理的欠陥が見当たらない。

### 6.4 Counterargument and Falsification — Weight 15

評価対象：

- 最も強い反対意見を扱っているか
- 代替仮説を比較しているか
- 自分の結論が誤りとなる条件を示しているか
- 都合の悪い証拠を無視していないか

**5点:** 強い反証を公平に検討し、結論の成立条件と破綻条件を示す。

### 6.5 Uncertainty Calibration — Weight 10

評価対象：

- 事実、推論、仮説、推測を区別しているか
- 確信度が根拠の強さに見合うか
- 不明点や追加調査の必要性を示すか

**5点:** 不確実性が具体的かつ適切に表現され、過剰断定がない。

### 6.6 Coverage and Relevance — Weight 10

評価対象：

- 問いの主要論点を網羅しているか
- 重要度の低い内容で水増ししていないか
- ユーザーの制約と目的に合っているか

**5点:** 重要論点を過不足なく扱い、回答全体が質問に直結している。

### 6.7 Actionability — Weight 10

評価対象：

- 意思決定に使えるか
- 次の行動、検証方法、優先順位が明確か
- 実行条件やリスクが示されているか

**5点:** ユーザーが次に何をすべきか、なぜそうするかが明確である。

### 6.8 Clarity and Information Efficiency — Weight 5

評価対象：

- 構造が理解しやすいか
- 重複や無意味な長文化がないか
- 専門用語が適切に使われているか

**5点:** 必要な情報を最小限の認知負荷で伝える。

## 7. Weighted Quality Score

品質スコアは100点満点で算出する。

```text
Quality Score = Σ((dimension score / 5) × dimension weight)
```

重みの合計は100とする。

| Dimension | Weight |
|---|---:|
| Factual Accuracy | 20 |
| Evidence Quality and Traceability | 15 |
| Reasoning Quality | 15 |
| Counterargument and Falsification | 15 |
| Uncertainty Calibration | 10 |
| Coverage and Relevance | 10 |
| Actionability | 10 |
| Clarity and Information Efficiency | 5 |
| **Total** | **100** |

## 8. Hard-fail Conditions

以下のいずれかが発生した回答は、総合点にかかわらず失格または要再評価とする。

- 結論を左右する重大な事実誤認
- 架空の出典・引用・データ
- 入力資料と明確に矛盾する断定
- 医療、法律、金融、安全などで重大な危険を増やす助言
- 個人情報、APIキー、秘密情報の漏えい
- 評価条件または予算上限の無視
- 処理回数上限を超える自律反復
- 比較条件の不一致により公平な評価ができない

## 9. Operational Metrics

品質とは別に、各実行で以下を記録する。

| Metric | Definition |
|---|---|
| Input tokens | 全モデルへの入力トークン合計 |
| Output tokens | 全モデルからの出力トークン合計 |
| Estimated cost | 実行時点の料金表による概算費用 |
| Wall-clock time | 受付から最終回答までの実時間 |
| Model calls | モデル呼び出し総数 |
| Tool calls | 検索、コード実行、DB参照などの総数 |
| Iterations | 再批判・再統合の回数 |
| Human interventions | 人間による修正・再指示の回数 |
| Failure count | API失敗、形式違反、タイムアウト等の件数 |

## 10. Efficiency Metrics

### 10.1 Quality Gain

```text
Quality Gain = OS Quality Score - Baseline Quality Score
```

### 10.2 Cost Multiplier

```text
Cost Multiplier = OS Estimated Cost / Baseline Estimated Cost
```

### 10.3 Time Multiplier

```text
Time Multiplier = OS Wall-clock Time / Baseline Wall-clock Time
```

### 10.4 Quality Gain per Additional Cost

```text
Efficiency = Quality Gain / (OS Cost - Baseline Cost)
```

費用差が0以下の場合は、個別に解釈する。

## 11. Provisional MVP Acceptance Criteria

AI研究室OSを単体AIより有効と暫定判断するには、最低限以下を満たすことを目標とする。

1. 代表的な複雑質問で、平均Quality Scoreがベースラインを5点以上上回る
2. Factual AccuracyまたはEvidence Qualityを悪化させない
3. Hard-fail率がベースライン以下である
4. Counterargument and Falsificationが明確に改善する
5. 追加費用と処理時間が記録され、改善幅とのトレードオフを説明できる
6. 少なくとも3カテゴリ以上、合計10問以上で試験する
7. 1つのモデル・1つの質問だけに依存した結論を出さない

この基準はMVP実験後に見直す。

## 12. Recommended Benchmark Categories

初期ベンチマークは、AI研究室OSの強みが期待される複雑問題を中心とする。

1. **Research synthesis** — 複数資料や対立研究の統合
2. **Strategic decision** — 複数制約下での事業・開発判断
3. **Hypothesis generation** — 未確定領域での検証可能な仮説生成
4. **Risk analysis** — 見落としや反証の発見
5. **Architecture design** — 技術的トレードオフを含む設計判断

単純な事実検索や定型計算は、オーバースペック検出用の対照群として少数含める。

## 13. Evaluation Procedure

1. 評価対象の質問と正解資料・判断基準を先に固定する
2. 各システムへ同じ質問と資料を与える
3. 出力、ログ、トークン、費用、時間を保存する
4. システム名を隠して評価できる場合はブラインド評価する
5. 各評価者が独立して採点する
6. 評価差が2点以上ある項目は理由を記録して再確認する
7. Hard-failを先に判定する
8. 品質スコアと運用指標を別々に報告する
9. 結果、失敗例、改善案を保存する

## 14. Evaluator Rules

- 長い回答を高得点にしない
- AI同士の一致を正しさの証拠にしない
- 有名モデルであることを加点しない
- 文体の好みと内容品質を混同しない
- 結論への賛否ではなく、根拠と推論を採点する
- 評価対象の生成に使ったAIだけで最終採点しない
- 自動評価を使う場合も、人間が代表例と失敗例を確認する

## 15. Result Reporting Template

各試験結果には最低限以下を含める。

```text
Test ID:
Question category:
Question:
Reference materials:
Systems compared:
Models and versions:
Execution date:
Quality scores by dimension:
Hard-fail status:
Input/output tokens:
Estimated cost:
Wall-clock time:
Human interventions:
Evaluator notes:
Winner:
Trade-off conclusion:
Follow-up action:
```

## 16. Review Triggers

以下の場合に本評価基準を改訂する。

- 最初の10問のベンチマーク完了
- 主要モデルまたは料金体系の変更
- 評価者間一致が低い
- 点数が実際の有用性と一致しない
- 新しい重要リスクが発見された
- MVPから公開版へ移行する
