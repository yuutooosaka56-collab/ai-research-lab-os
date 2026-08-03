# AI Research Lab OS

> 複雑な問いに対して、複数のAIが調査・反証・統合を行い、単体AIより高品質で検証可能な回答を生成できるかを研究・実装するプロジェクト。

## Status

**Bootstrap / Pre-MVP**

本リポジトリは、AI研究室OSの最小実験版を設計する初期段階です。正式なMission・Vision・AI憲法は、MVP完成後にAI研究室OS自身を用いて再検討します。

## Initial Scope

最初のMVPでは、以下の3役のみを実装候補とします。

1. **Researcher** — 問いの分解、論点・情報・根拠候補の収集
2. **Skeptic** — 反証、根拠不足、論理的欠陥、代替仮説の検出
3. **Synthesizer** — 結論、不確実性、次の検証行動への統合

```text
User Question
    ↓
Researcher
    ↓
Skeptic
    ↓
Synthesizer
    ↓
Evidence-aware Answer
```

## Documents

- [Bootstrap Charter](docs/00_Project/BootstrapCharter.md)
- [Risks and Constraints](docs/00_Project/RisksAndConstraints.md)
- [ADR-0001: Development Model](docs/01_ADR/ADR-0001-Development-Model.md)
- [ADR Template](docs/01_ADR/ADR-Template.md)
- [MVP Architecture](docs/02_Architecture/MVPArchitecture.md)
- [Agent Protocol](docs/03_Protocols/AgentProtocol.md)
- [Evaluation Rubric](docs/04_Evaluation/EvaluationRubric.md)

## Machine-readable Schemas

- [Common Types](src/schemas/common.schema.json)
- [Researcher Output](src/schemas/researcher.schema.json)
- [Skeptic Output](src/schemas/skeptic.schema.json)
- [Synthesizer Output](src/schemas/synthesizer.schema.json)

The schemas use JSON Schema Draft 2020-12 and are intended for Orchestrator-side validation before outputs are accepted or passed to the next agent.

## Validation Engine

`src/validation` provides two validation layers.

1. **Schema validation** — JSON parsing, required fields, types, formats, allowed values, confidence ranges
2. **Semantic validation** — Claim/Evidence reference integrity, cross-agent references, confidence labels, execution timing, duplicate IDs, potential secret detection

Schema validation is always executed first. Semantic validation runs only when the payload is structurally safe to inspect.

```python
from validation import validate_agent_output

report = validate_agent_output(
    synthesizer_payload,
    researcher_payload=researcher_payload,
    skeptic_payload=skeptic_payload,
)

if not report.valid:
    print(report.schema.issues)
    print(report.semantic.issues if report.semantic else [])
```

### Development setup

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest
```

## Repository Structure

```text
ai-research-lab-os/
├── README.md
├── CHANGELOG.md
├── pyproject.toml
├── .gitignore
├── docs/
│   ├── 00_Project/
│   ├── 01_ADR/
│   ├── 02_Architecture/
│   ├── 03_Protocols/
│   └── 04_Evaluation/
├── src/
│   ├── schemas/
│   └── validation/
├── tests/
└── examples/
```

## Non-goals at Bootstrap Stage

現段階では、以下を実装しません。

- 多数の専門エージェント
- ベクトルデータベース
- 長期記憶
- 自律的な無制限反復
- LangGraphやMCPの先行導入
- 本番運用・課金・一般公開サービス

## Governance

- 人間が最終的な採否を決定します。
- 重要な設計判断はADRに記録します。
- AIを追加する場合は、その必要性を実験で示します。
- 出力量ではなく、正確性・検証可能性・費用対効果で評価します。

## License

未決定です。外部公開・共同開発を本格化する前にライセンスを選定します。
