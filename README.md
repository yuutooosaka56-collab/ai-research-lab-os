# AI Research Lab OS

[![CI](https://github.com/yuutooosaka56-collab/ai-research-lab-os/actions/workflows/ci.yml/badge.svg)](https://github.com/yuutooosaka56-collab/ai-research-lab-os/actions/workflows/ci.yml)

> 複雑な問いに対して、複数のAIが調査・反証・統合を行い、単体AIより高品質で検証可能な回答を生成できるかを研究・実装するプロジェクト。

## Status

**Bootstrap / Mock MVP**

Researcher、Skeptic、Synthesizerを順次実行し、各出力を構造・意味の両面で検証する最小ルートが、Mock Provider環境で動作する段階です。外部AI APIはまだ接続していません。

正式なMission・Vision・AI憲法は、実モデルを使ったMVP評価後にAI研究室OS自身を用いて再検討します。

## Initial Scope

最初のMVPでは、以下の3役のみを扱います。

1. **Researcher** — 問いの分解、論点・情報・根拠候補の収集
2. **Skeptic** — 反証、根拠不足、論理的欠陥、代替仮説の検出
3. **Synthesizer** — 結論、不確実性、次の検証行動への統合

```text
User Question
    ↓
Orchestrator
    ↓
Researcher → validation
    ↓
Skeptic → validation
    ↓
Synthesizer → validation
    ↓
Evidence-aware Answer
```

不正な出力は次のエージェントへ渡さず、その時点で処理を停止します。

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

## Mock MVP Run

`MockProvider`は外部APIやAPIキーを使用せず、3役の有効な模擬出力を返します。これは処理構造と検証経路の試験用であり、AI研究品質の実証ではありません。

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -e ".[dev]"
python examples/run_mock.py
```

Pythonから直接実行する場合：

```python
from orchestrator import Orchestrator
from providers import MockProvider

result = Orchestrator(MockProvider()).run(
    "AI研究室OSは何のために存在するべきか。"
)

print(result.run_id)
print(result.final_answer)
```

## Tests

```bash
python -m pytest
```

テストは、正常完走、各段階の検証、不正出力の遮断、呼び出し上限、秘密情報検出、Claim/Evidence参照整合性などを対象とします。

## Continuous Integration

GitHub Actions runs the test suite on pushes and pull requests targeting `main`. The workflow checks Python 3.11 and 3.14, compiles the source tree, and runs `pytest`.

Workflow: [`.github/workflows/ci.yml`](.github/workflows/ci.yml)

## Repository Structure

```text
ai-research-lab-os/
├── .github/
│   └── workflows/
│       └── ci.yml
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
│   ├── orchestrator/
│   ├── providers/
│   ├── schemas/
│   └── validation/
├── tests/
│   ├── test_orchestrator.py
│   └── test_validation.py
└── examples/
    └── run_mock.py
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
