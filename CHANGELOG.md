# Changelog

このプロジェクトの重要な変更を記録します。

形式は [Keep a Changelog](https://keepachangelog.com/) を参考にし、正式リリース開始後はセマンティックバージョニングを採用する予定です。

## [Unreleased]

### Added

- 初期リポジトリ構造
- Bootstrap Charter
- Risks and Constraints
- ADR-0001: Development Model
- ADR Template
- Evaluation Rubric
- MVP Architecture
- Agent Protocol
- Common JSON Schema definitions
- Researcher output schema
- Skeptic output schema
- Synthesizer output schema
- Draft 2020-12 schema validation engine
- Claim/Evidence and cross-agent semantic validation
- Confidence-label, timing, duplicate-ID, and secret detection checks
- Python project configuration and validation tests
- GitHub Actions CI workflow for Python 3.11 and 3.14
- CI badge and local test instructions in README
- Provider abstraction for model-independent agent execution
- Deterministic Mock Provider for credential-free runs
- Bounded sequential Orchestrator for Researcher, Skeptic, and Synthesizer
- Fail-closed validation between every agent stage
- Run ID, provider call limit, and lightweight audit event tracking
- Orchestrator tests for completion, invalid output, call limits, and empty input
- Runnable Mock MVP example
- Packaged JSON Schema resources for non-editable installations
