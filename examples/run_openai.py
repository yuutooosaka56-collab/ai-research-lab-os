"""Run the three-agent pipeline with the OpenAI Responses API.

This example performs three API calls and may incur usage charges.
Set OPENAI_API_KEY and OPENAI_MODEL before running it.
"""

from __future__ import annotations

import argparse
import json

from orchestrator import Orchestrator
from providers import OpenAIProvider


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run AI Research Lab OS with OpenAI."
    )
    parser.add_argument("question", help="Research question to process")
    args = parser.parse_args()

    provider = OpenAIProvider.from_env()
    result = Orchestrator(provider).run(args.question)
    print(
        json.dumps(
            {
                "run_id": result.run_id,
                "final_answer": result.final_answer,
                "stages": [stage.agent for stage in result.stages],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
