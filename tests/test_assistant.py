"""Tests of the agent loop with a scripted fake client (no API key, no network)."""

import json
from types import SimpleNamespace as NS

from eda_assistant.assistant import TOOLS, EngineeringAssistant


class FakeClient:
    """Replays scripted responses and records every request."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []
        self.beta = NS(messages=NS(create=self._create))

    def _create(self, **kwargs):
        # Snapshot the message list: the assistant keeps appending to it after the call.
        self.requests.append({**kwargs, "messages": list(kwargs["messages"])})
        return self.responses.pop(0)


def tool_use(id_, name, input_):
    return NS(type="tool_use", id=id_, name=name, input=input_)


def text(t):
    return NS(type="text", text=t)


def test_tool_loop_runs_local_tools_and_returns_answer(dataset, docs):
    client = FakeClient(
        [
            NS(stop_reason="tool_use", content=[
                tool_use("t1", "search_documentation", {"query": "acceptance criteria"}),
                tool_use("t2", "threshold_check", {"channel": "outlet_temp_C", "lower": None, "upper": 85, "metric": "value"}),
            ]),
            NS(stop_reason="end_turn", content=[text("The run fails: outlet temperature exceeds 85 °C [TP-HL-001, Acceptance criteria].")]),
        ]
    )
    answer = EngineeringAssistant(dataset, docs, client=client).ask("Does the run pass?")

    assert answer.stop_reason == "end_turn"
    assert "fails" in answer.text
    assert [c.name for c in answer.tool_calls] == ["search_documentation", "threshold_check"]
    assert json.loads(answer.tool_calls[1].output)["passed"] is False

    # Both tool results go back in a single user message, matched by id.
    second = client.requests[1]["messages"]
    results = second[-1]["content"]
    assert [r["tool_use_id"] for r in results] == ["t1", "t2"]
    assert client.requests[0]["model"] == "claude-opus-5-5"


def test_tool_errors_are_reported_not_raised(dataset):
    client = FakeClient(
        [
            NS(stop_reason="tool_use", content=[tool_use("t1", "channel_statistics", {"channel": "bad", "start_s": None, "end_s": None})]),
            NS(stop_reason="end_turn", content=[text("That channel does not exist.")]),
        ]
    )
    answer = EngineeringAssistant(dataset, client=client).ask("Stats of bad?")
    assert answer.tool_calls[0].is_error
    assert client.requests[1]["messages"][-1]["content"][0]["is_error"] is True


def test_refusal_is_handled(dataset):
    client = FakeClient([NS(stop_reason="refusal", content=[])])
    answer = EngineeringAssistant(dataset, client=client).ask("...")
    assert answer.stop_reason == "refusal"


def test_tool_schemas_are_strict():
    for tool in TOOLS:
        schema = tool["input_schema"]
        assert tool["strict"] is True
        assert schema["additionalProperties"] is False
        assert set(schema["required"]) == set(schema["properties"])
