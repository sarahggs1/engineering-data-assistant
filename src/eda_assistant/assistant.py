"""Natural-language assistant for test data, built on Claude tool use.

The engineer asks a question ("Does this run meet the acceptance criteria of
the test procedure?"). Claude answers by calling local analysis tools: it
searches the documentation, computes statistics, checks limits, looks at the
spectrum. Raw data stays local; Claude only sees each tool's small JSON result.
Every tool call is recorded so the engineer can audit how the answer was built.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import anthropic

from .data import TestDataset, channel_statistics, overview, spectrum_peaks, threshold_check
from .docs import DocumentIndex

MODEL = "claude-opus-5-5"
MAX_TURNS = 12

SYSTEM_PROMPT = """You are an engineering data assistant for test engineers.
You answer questions about one test dataset and the technical documentation provided with it.

Use the tools to get facts: never invent a value, a limit or a requirement.
When a question involves requirements, procedures or acceptance criteria, search the documentation first,
then apply the limits you found with the analysis tools.
In your answer, cite each documentation passage you relied on as [source, section],
give the numbers you computed with their units, and state clearly what passed, what failed and what could not be checked.
If the documentation does not cover something, say so instead of guessing. Be concise: engineers read this between tests."""


def _schema(properties: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": properties, "required": required, "additionalProperties": False}


NULLABLE_NUMBER = {"type": ["number", "null"]}

TOOLS = [
    {
        "name": "dataset_overview",
        "description": "Describe the loaded test dataset: number of samples, duration, sample rate, channel names and missing values. Call it first if you do not know the channel names.",
        "input_schema": _schema({}, []),
        "strict": True,
    },
    {
        "name": "channel_statistics",
        "description": "Descriptive statistics (mean, std, min, max, RMS, 5th and 95th percentiles) of one channel, optionally restricted to a time window in seconds. Use null for an open window bound.",
        "input_schema": _schema(
            {"channel": {"type": "string"}, "start_s": NULLABLE_NUMBER, "end_s": NULLABLE_NUMBER},
            ["channel", "start_s", "end_s"],
        ),
        "strict": True,
    },
    {
        "name": "threshold_check",
        "description": "Check one channel against acceptance limits. metric 'value' checks every sample and reports violations with their time; metric 'rms' checks the RMS over the whole run. Use null for a missing limit.",
        "input_schema": _schema(
            {
                "channel": {"type": "string"},
                "lower": NULLABLE_NUMBER,
                "upper": NULLABLE_NUMBER,
                "metric": {"type": "string", "enum": ["value", "rms"]},
            },
            ["channel", "lower", "upper", "metric"],
        ),
        "strict": True,
    },
    {
        "name": "spectrum_peaks",
        "description": "Dominant frequencies of a channel from its power spectral density, e.g. to identify the source of a vibration.",
        "input_schema": _schema(
            {"channel": {"type": "string"}, "n_peaks": {"type": "integer"}},
            ["channel", "n_peaks"],
        ),
        "strict": True,
    },
    {
        "name": "search_documentation",
        "description": "Search the technical documentation (test procedures, specifications, instrumentation guides) and return the most relevant passages with their source and section.",
        "input_schema": _schema({"query": {"type": "string"}}, ["query"]),
        "strict": True,
    },
]


@dataclass
class ToolCall:
    name: str
    input: dict
    output: str
    is_error: bool = False


@dataclass
class AssistantAnswer:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: str = ""


class EngineeringAssistant:
    def __init__(self, dataset: TestDataset, docs: DocumentIndex | None = None, client=None, model: str = MODEL):
        self.dataset = dataset
        self.docs = docs
        self.client = client or anthropic.Anthropic()
        self.model = model

    # -- local tools ---------------------------------------------------------
    def run_tool(self, name: str, args: dict) -> str:
        ds = self.dataset
        if name == "dataset_overview":
            result = overview(ds)
        elif name == "channel_statistics":
            result = channel_statistics(ds, args["channel"], args.get("start_s"), args.get("end_s"))
        elif name == "threshold_check":
            result = threshold_check(ds, args["channel"], args.get("lower"), args.get("upper"), args.get("metric", "value"))
        elif name == "spectrum_peaks":
            result = spectrum_peaks(ds, args["channel"], int(args.get("n_peaks") or 3))
        elif name == "search_documentation":
            if self.docs is None:
                return json.dumps({"passages": [], "note": "No documentation was loaded."})
            result = {"passages": self.docs.search(args["query"], top_k=3)}
        else:
            raise ValueError(f"Unknown tool: {name}")
        return json.dumps(result)

    # -- agent loop ----------------------------------------------------------
    def ask(self, question: str) -> AssistantAnswer:
        messages = [{"role": "user", "content": question}]
        calls: list[ToolCall] = []

        for _ in range(MAX_TURNS):
            response = self.client.beta.messages.create(
                model=self.model,
                max_tokens=16000,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages,
                thinking={"type": "adaptive"},
                output_config={"effort": "medium"},
                # On a safety decline, the API retries the same request on a suitable fallback model.
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )

            if response.stop_reason == "refusal":
                return AssistantAnswer("The model declined to answer this request.", calls, "refusal")

            # Keep the full content (including thinking blocks) so the conversation stays valid.
            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "pause_turn":
                continue
            if response.stop_reason != "tool_use":
                text = "\n".join(b.text for b in response.content if b.type == "text").strip()
                if response.stop_reason == "max_tokens":
                    text += "\n\n(Answer truncated: output limit reached.)"
                return AssistantAnswer(text, calls, response.stop_reason)

            results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                try:
                    output, is_error = self.run_tool(block.name, dict(block.input)), False
                except Exception as exc:  # report the error to Claude instead of crashing
                    output, is_error = f"Error: {exc}", True
                calls.append(ToolCall(block.name, dict(block.input), output, is_error))
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": output, "is_error": is_error})
            messages.append({"role": "user", "content": results})

        return AssistantAnswer("Stopped: too many tool calls without a final answer.", calls, "max_turns")
