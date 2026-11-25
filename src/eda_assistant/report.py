"""Automatic PDF test report: overview, statistics, acceptance checks, figures."""

from __future__ import annotations

import io
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from . import plots
from .data import TestDataset, channel_statistics, overview, spectrum_peaks, threshold_check

NAVY = colors.HexColor("#1f3a5f")


def _figure_image(fig, width_cm: float = 17):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150)
    plots.plt.close(fig)
    buf.seek(0)
    w, h = fig.get_size_inches()
    return Image(buf, width=width_cm * cm, height=width_cm * cm * h / w)


def _table(rows: list[list], header: bool = True) -> Table:
    table = Table(rows, hAlign="LEFT")
    style = [
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white)]
    table.setStyle(TableStyle(style))
    return table


def build_report(
    ds: TestDataset,
    output: str | Path,
    limits: dict | None = None,
    spectrum_channels: list[str] | None = None,
    title: str | None = None,
    author: str = "",
) -> Path:
    """Write a PDF report and return its path.

    limits: {"channel": {"lower": float | None, "upper": float | None, "metric": "value" | "rms"}}
    """
    limits = limits or {}
    output = Path(output)
    styles = getSampleStyleSheet()
    styles["Title"].textColor = NAVY
    styles["Heading2"].textColor = NAVY
    info = overview(ds)

    story = [
        Paragraph(title or f"Test report – {ds.name}", styles["Title"]),
        Paragraph(f"Generated on {date.today().isoformat()}" + (f" by {author}" if author else ""), styles["Normal"]),
        Spacer(1, 0.4 * cm),
        Paragraph("1. Test overview", styles["Heading2"]),
        _table(
            [
                ["Samples", info["samples"]],
                ["Duration (s)", info["duration_s"]],
                ["Sample rate (Hz)", info["sample_rate_hz"]],
                ["Channels", ", ".join(info["channels"])],
                ["Missing values", ", ".join(f"{k}: {v}" for k, v in info["missing_values"].items()) or "none"],
            ],
            header=False,
        ),
        Paragraph("2. Channel statistics", styles["Heading2"]),
    ]

    rows = [["Channel", "Mean", "Std", "Min", "Max", "RMS"]]
    for name in ds.channels:
        s = channel_statistics(ds, name)
        rows.append([name] + [f"{s[k]:.4g}" for k in ("mean", "std", "min", "max", "rms")])
    story.append(_table(rows))

    if limits:
        story.append(Paragraph("3. Acceptance checks", styles["Heading2"]))
        rows = [["Channel", "Metric", "Lower", "Upper", "Result", "Details"]]
        for name, lim in limits.items():
            r = threshold_check(ds, name, lim.get("lower"), lim.get("upper"), lim.get("metric", "value"))
            details = f"RMS = {r['value']:.4g}" if r["metric"] == "rms" else f"{r['samples_out_of_limits']} samples out"
            if r.get("first_violation_s") is not None:
                details += f" (first at t = {r['first_violation_s']:.2f} s)"
            rows.append([name, r["metric"], r["lower"], r["upper"], "PASS" if r["passed"] else "FAIL", details])
        table = _table(rows)
        for i, row in enumerate(rows[1:], start=1):
            color = colors.HexColor("#1e8449") if row[4] == "PASS" else colors.HexColor("#c0392b")
            table.setStyle(TableStyle([("TEXTCOLOR", (4, i), (4, i), color)]))
        story.append(table)

    story.append(KeepTogether([Paragraph("4. Time series", styles["Heading2"]), _figure_image(plots.time_series(ds, limits=limits))]))

    for name in spectrum_channels or []:
        peaks = spectrum_peaks(ds, name)
        listed = ", ".join(f"{p['frequency_hz']} Hz" for p in peaks["peaks"]) or "none"
        story.append(KeepTogether([
            Paragraph(f"5. Frequency analysis – {name}", styles["Heading2"]),
            Paragraph(f"Dominant frequencies: {listed}", styles["Normal"]),
            _figure_image(plots.psd(ds, name)),
        ]))

    SimpleDocTemplate(str(output), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm).build(story)
    return output
