"""Run the complete MVP pipeline without external API credentials."""

from __future__ import annotations

import json

from orchestrator import Orchestrator
from providers import MockProvider


def main() -> None:
    result = Orchestrator(MockProvider()).run(
        "AI研究室OSは何のために存在するべきか。"
    )
    print(result.final_answer)
    print()
    print(
        json.dumps(
            {
                "run_id": result.run_id,
                "stages": [
                    {
                        "agent": stage.agent,
                        "valid": stage.validation.valid,
                        "elapsed_seconds": round(
                            stage.elapsed_seconds,
                            6,
                        ),
                    }
                    for stage in result.stages
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
