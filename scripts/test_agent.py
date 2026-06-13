"""Smoke-test the cited agent against real data + the configured LLM provider.

Run: uv run python scripts/test_agent.py
"""

import sys

from app.agent import answer


def main() -> None:
    question = sys.argv[1] if len(sys.argv) > 1 else (
        "Which solar parks are under construction? Give one example with its evidence."
    )
    print(f"Q: {question}\n")
    result = answer(question)
    print(f"[provider: {result['provider']}]\n")
    print("ANSWER:\n" + result["answer"])
    print(f"\nSITE IDS referenced: {len(result['site_ids'])}")
    print("SOURCES (citations):")
    for s in result["sources"][:12]:
        print(f"  - {s['type']:9} {s['label']}")


if __name__ == "__main__":
    main()
