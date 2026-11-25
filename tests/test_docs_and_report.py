import json
from pathlib import Path

from eda_assistant.report import build_report

LIMITS = json.loads((Path(__file__).resolve().parents[1] / "examples" / "limits.json").read_text())


def test_search_finds_acceptance_criteria(docs):
    hits = docs.search("acceptance criteria outlet temperature limit")
    assert hits[0]["source"].startswith("TP-HL-001")
    assert hits[0]["section"] == "Acceptance criteria"


def test_search_finds_troubleshooting(docs):
    hits = docs.search("why does the outlet temperature overshoot")
    assert any(h["source"].startswith("TG-HL-003") for h in hits)


def test_report_is_written(dataset, tmp_path):
    path = build_report(dataset, tmp_path / "report.pdf", limits=LIMITS, spectrum_channels=["accel_pump_g"])
    data = path.read_bytes()
    assert data.startswith(b"%PDF")
    assert len(data) > 20_000
