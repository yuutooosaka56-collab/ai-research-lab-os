"""Deterministic provider used for tests and local smoke runs."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Mapping

from .base import AgentName


class MockProvider:
    """Return valid, deterministic envelopes without calling an external API."""

    def __init__(self) -> None:
        self.calls: list[AgentName] = []

    @property
    def provider_name(self) -> str:
        return "mock"

    def run_agent(
        self,
        agent: AgentName,
        request: Mapping[str, Any],
        *,
        run_id: str,
    ) -> Mapping[str, Any]:
        self.calls.append(agent)
        if agent == "researcher":
            output = self._researcher_output(request)
        elif agent == "skeptic":
            output = self._skeptic_output(request)
        elif agent == "synthesizer":
            output = self._synthesizer_output(request)
        else:  # pragma: no cover - protected by AgentName typing
            raise ValueError(f"Unsupported agent: {agent}")
        return self._envelope(agent, request, run_id, output)

    def _envelope(
        self,
        agent: AgentName,
        request: Mapping[str, Any],
        run_id: str,
        output: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        started = datetime.now(timezone.utc)
        completed = datetime.now(timezone.utc)
        digest_source = json.dumps(
            request,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        ).encode("utf-8")
        return {
            "protocol_version": "0.1",
            "run_id": run_id,
            "agent": agent,
            "status": "completed",
            "started_at": started.isoformat(),
            "completed_at": completed.isoformat(),
            "model": {
                "provider": "mock",
                "name": "deterministic-mock",
                "version": "0.1",
            },
            "input_digest": "sha256:"
            + hashlib.sha256(digest_source).hexdigest(),
            "warnings": [],
            "errors": [],
            "output": dict(output),
        }

    @staticmethod
    def _researcher_output(
        request: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        question = str(request.get("question", "")).strip()
        return {
            "question_restated": question,
            "scope": {
                "included": ["MVPの処理フローと検証可能性"],
                "excluded": ["実APIの性能評価と本番運用"],
            },
            "subquestions": [
                {
                    "id": "Q-001",
                    "question": "3段階の処理が検証可能な形で完了するか",
                    "importance": "high",
                    "reason": "最小OSとして成立するための中核条件だから",
                }
            ],
            "assumptions": [
                {
                    "id": "A-001",
                    "text": "Mock出力は外部世界の真実を証明しない",
                    "risk_if_false": "模擬実行を実証結果と誤認する",
                }
            ],
            "claims": [
                {
                    "claim_id": "C-001",
                    "text": "評価対象の質問はユーザー入力として提供された",
                    "type": "fact",
                    "confidence": 1.0,
                    "evidence_ids": ["E-001"],
                    "assumptions": [],
                    "limitations": ["入力内容の真偽自体は検証していない"],
                    "verification_status": "supported",
                },
                {
                    "claim_id": "C-002",
                    "text": "3役を順次実行する構成はMVPの初期検証に適する",
                    "type": "proposal",
                    "confidence": 0.6,
                    "evidence_ids": [],
                    "assumptions": ["最初は単純性を優先する"],
                    "limitations": ["品質向上は実験で未確認"],
                    "verification_status": "not_applicable",
                },
            ],
            "evidence": [
                {
                    "evidence_id": "E-001",
                    "title": "User-supplied question",
                    "source_type": "user_supplied",
                    "locator": "input://question",
                    "published_at": None,
                    "retrieved_at": datetime.now(timezone.utc).isoformat(),
                    "supports_claim_ids": ["C-001"],
                    "reliability": 1.0,
                    "notes": "The orchestrator passed the question directly.",
                }
            ],
            "conflicts": [],
            "unknowns": [
                {
                    "question": "実モデルでも同じ構造を安定して返せるか",
                    "importance": "high",
                    "how_to_resolve": "実Providerを接続して反復試験する",
                }
            ],
            "research_summary": (
                "入力質問を受領し、MVPの構造検証に必要な論点を整理した。"
            ),
        }

    @staticmethod
    def _skeptic_output(
        request: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        return {
            "overall_assessment": (
                "構造確認には使えるが、Mock成功だけでは品質向上を証明できない。"
            ),
            "issues": [
                {
                    "issue_id": "I-001",
                    "severity": "moderate",
                    "category": "missing_empirical_evidence",
                    "target_claim_ids": ["C-002"],
                    "description": "提案の有効性を示す比較実験がまだない",
                    "why_it_matters": "構成の複雑化が品質改善に見合うか不明だから",
                    "recommended_correction": (
                        "単体AIと構造化単体AIを含む比較試験を行う"
                    ),
                }
            ],
            "counterarguments": [
                {
                    "id": "CA-001",
                    "argument": (
                        "単一モデルへの構造化プロンプトでも同等品質になり得る"
                    ),
                    "strength": "moderate",
                    "supporting_evidence_ids": [],
                }
            ],
            "alternative_hypotheses": [
                {
                    "id": "H-001",
                    "hypothesis": "改善がある場合も役割分離ではなく総トークン量が原因",
                    "what_would_support_it": (
                        "同一トークン量の単体AIが同等以上の成績を示す"
                    ),
                    "what_would_falsify_it": (
                        "同一予算条件でOSが継続的に高得点を示す"
                    ),
                }
            ],
            "confidence_adjustments": [
                {
                    "claim_id": "C-002",
                    "original": 0.6,
                    "recommended": 0.4,
                    "reason": "比較試験が未実施だから",
                }
            ],
            "additional_research_required": True,
            "priority_followups": ["評価用質問セットで比較実験を行う"],
            "surviving_strengths": ["処理段階と責務が明示されている"],
        }

    @staticmethod
    def _synthesizer_output(
        request: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        return {
            "direct_answer": "Mock Providerによる3段階処理は完了した。",
            "conclusion": {
                "text": (
                    "Orchestratorの構造は一周動作したが、実AIでの品質優位は未検証である。"
                ),
                "confidence": 0.58,
                "confidence_label": "medium",
                "conditions": ["Mock出力のみを対象とした構造試験である"],
            },
            "supported_findings": [
                {
                    "claim_id": "C-001",
                    "text": "ユーザー入力が研究処理へ渡された",
                    "evidence_ids": ["E-001"],
                    "confidence": 1.0,
                }
            ],
            "important_counterpoints": [
                {
                    "issue_id": "I-001",
                    "text": "品質向上を示す比較実験はまだない",
                    "impact_on_conclusion": (
                        "現時点では構造動作のみを確認済みとする"
                    ),
                }
            ],
            "unresolved_uncertainties": [
                "実モデルでのJSON安定性",
                "単体AIに対する品質と費用の改善幅",
            ],
            "assumptions": ["Mock Providerは外部APIを呼び出さない"],
            "recommended_actions": [
                {
                    "priority": 1,
                    "action": "実Provider Adapterを1種類追加する",
                    "purpose": "実モデル出力を同じ検証経路へ通す",
                    "success_signal": "3役の出力が全て検証を通過する",
                },
                {
                    "priority": 2,
                    "action": "比較用の固定質問セットを作る",
                    "purpose": "単体AIとの差を再現可能に測る",
                    "success_signal": "3条件を同一ルーブリックで採点できる",
                },
            ],
            "citations": [
                {
                    "evidence_id": "E-001",
                    "locator": "input://question",
                }
            ],
            "plain_language_answer": (
                "AI研究室OSの最小ルートはMock環境で最後まで動作しました。"
                "ただし、実際に単体AIより優れているかは次の比較実験で確認します。"
            ),
        }
