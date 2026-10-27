import pytest
from langchain_core.messages import AIMessage

from agent.models import (
    ModelEntry,
    ModelError,
    Registry,
    chat_model,
    stop_reason,
    system_message,
    text_of,
)
from app.settings import get_settings
from obs.cost import cost_usd, usage_of


def reg():
    return Registry(get_settings().agent_dir / "models.yaml")


def test_registry_has_defaults_with_prices():
    r = reg()
    opus = r.resolve("anthropic:claude-opus-5-5")
    assert opus.id == "claude-opus-5-5" and opus.prices["input"] == 4.0 and opus.price_source
    assert r.resolve("claude-haiku-5-5").prices["output"] == 0.5
    for e in r.entries:
        assert e.price_source and "input" in e.prices


def test_unlisted_provider_model_and_unknown_id():
    assert reg().resolve("openai:some-model").prices == {}
    with pytest.raises(ModelError):
        reg().resolve("nonsense")


def test_no_tool_calling_refused():
    with pytest.raises(ModelError, match="tool calling"):
        chat_model(
            ModelEntry(id="x", model="openai:x", tool_calling=False),
            get_settings(),
            role="analyst",
            max_tokens=10,
        )


def test_anthropic_model_built_without_network():
    m = chat_model(
        reg().resolve("claude-opus-5-5"), get_settings(), role="analyst", max_tokens=1000
    )
    assert m.model == "claude-opus-5-5"
    assert m.output_config == {"effort": "medium"}


def test_cache_breakpoint_only_for_anthropic():
    r = reg()
    sm = system_message("rules", r.resolve("claude-opus-5-5"))
    assert sm.content[0]["cache_control"] == {"type": "ephemeral"}
    assert system_message("rules", r.resolve("gpt-6.1-sol")).content == "rules"


def test_stop_reasons_across_providers():
    assert (
        stop_reason(AIMessage(content="", response_metadata={"stop_reason": "refusal"}))
        == "refusal"
    )
    assert (
        stop_reason(AIMessage(content="", response_metadata={"finish_reason": "content_filter"}))
        == "refusal"
    )
    assert (
        stop_reason(AIMessage(content="", response_metadata={"finish_reason": "SAFETY"}))
        == "refusal"
    )
    assert (
        stop_reason(AIMessage(content="", response_metadata={"finish_reason": "length"}))
        == "length"
    )
    assert (
        stop_reason(AIMessage(content="ok", response_metadata={"stop_reason": "end_turn"})) == "end"
    )


def test_text_of_blocks():
    m = AIMessage(
        content=[
            {"type": "thinking", "thinking": "x"},
            {"type": "text", "text": "a"},
            {"type": "text", "text": "b"},
        ]
    )
    assert text_of(m) == "ab"


def test_cost():
    m = AIMessage(
        content="",
        usage_metadata={
            "input_tokens": 30_000,
            "output_tokens": 2_000,
            "total_tokens": 32_000,
            "input_token_details": {"cache_read": 20_000, "cache_creation": 5_000},
        },
    )
    u = usage_of(m)
    assert u == {"input": 30_000, "output": 2_000, "cache_read": 20_000, "cache_write": 5_000}
    # 5,000 fresh x 4 + 20,000 x 0.2 + 5,000 x 5 + 2,000 x 20, per million
    assert cost_usd(u, reg().resolve("claude-opus-5-5").prices) == pytest.approx(0.089)
    assert cost_usd(u, {}) is None
