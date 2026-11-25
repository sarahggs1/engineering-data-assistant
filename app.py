"""Streamlit interface of the Engineering Data Assistant.

    streamlit run app.py
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from eda_assistant import plots
from eda_assistant.data import channel_statistics, from_frame, load_csv, lowpass, overview, spectrum_peaks, threshold_check
from eda_assistant.docs import DocumentIndex
from eda_assistant.report import build_report

EXAMPLES = Path(__file__).parent / "examples"

st.set_page_config(page_title="Engineering Data Assistant", layout="wide")
st.title("Engineering Data Assistant")
st.caption("Analyze test data, check acceptance criteria, generate reports, and ask questions in plain language.")

# ---------------------------------------------------------------- data source
with st.sidebar:
    st.header("1. Test data")
    uploaded = st.file_uploader("CSV file (time column + channels)", type="csv")
    if uploaded is not None:
        ds = from_frame(pd.read_csv(uploaded), name=Path(uploaded.name).stem)
    else:
        ds = load_csv(EXAMPLES / "data" / "heated_loop_run_042.csv")
        st.info("Using the example run `heated_loop_run_042` (synthetic data).")

    st.header("2. Documentation")
    doc_files = st.file_uploader("Procedures, specs, guides (.md / .txt)", type=["md", "txt"], accept_multiple_files=True)
    if doc_files:
        docs = DocumentIndex.from_texts({f.name: f.getvalue().decode("utf-8") for f in doc_files})
    else:
        docs = DocumentIndex.from_folder(EXAMPLES / "docs")
        st.info("Using the example documentation (fictitious test procedure and guides).")

info = overview(ds)
c1, c2, c3, c4 = st.columns(4)
c1.metric("Samples", f"{info['samples']:,}")
c2.metric("Duration", f"{info['duration_s']} s")
c3.metric("Sample rate", f"{info['sample_rate_hz']:g} Hz")
c4.metric("Channels", len(info["channels"]))

tab_data, tab_freq, tab_check, tab_ask = st.tabs(["Time series", "Frequency analysis", "Acceptance & report", "Ask the assistant"])

# ---------------------------------------------------------------- time series
with tab_data:
    selected = st.multiselect("Channels", ds.channels, default=ds.channels)
    cutoff = st.number_input("Optional low-pass filter cutoff (Hz, 0 = off)", min_value=0.0, value=0.0, step=1.0)
    if selected:
        view = ds
        if cutoff > 0:
            frame = ds.frame.copy()
            for name in selected:
                frame[name] = lowpass(ds, name, cutoff)
            view = from_frame(frame, name=ds.name, time_column=ds.time_column)
        st.pyplot(plots.time_series(view, selected))
    st.dataframe(pd.DataFrame([channel_statistics(ds, c) for c in ds.channels]).drop(columns="window_s"), hide_index=True)

# ---------------------------------------------------------------- frequency
with tab_freq:
    channel = st.selectbox("Channel", ds.channels, index=len(ds.channels) - 1)
    st.pyplot(plots.psd(ds, channel))
    peaks = spectrum_peaks(ds, channel, n_peaks=5)["peaks"]
    st.write("Dominant frequencies:", ", ".join(f"**{p['frequency_hz']} Hz**" for p in peaks) or "none")

# ---------------------------------------------------------------- acceptance + report
with tab_check:
    st.write("Acceptance limits (edit the table, leave a cell empty for no limit).")
    default_limits = json.loads((EXAMPLES / "limits.json").read_text()) if uploaded is None else {}
    rows = [
        {"channel": c, "lower": default_limits.get(c, {}).get("lower"), "upper": default_limits.get(c, {}).get("upper"),
         "metric": default_limits.get(c, {}).get("metric", "value")}
        for c in ds.channels
    ]
    edited = st.data_editor(
        pd.DataFrame(rows),
        column_config={"metric": st.column_config.SelectboxColumn(options=["value", "rms"])},
        disabled=["channel"],
        hide_index=True,
    )
    limits = {}
    for r in edited.to_dict("records"):
        lower = None if pd.isna(r["lower"]) else float(r["lower"])
        upper = None if pd.isna(r["upper"]) else float(r["upper"])
        if lower is not None or upper is not None:
            limits[r["channel"]] = {"lower": lower, "upper": upper, "metric": r["metric"]}

    if limits:
        results = [threshold_check(ds, c, l["lower"], l["upper"], l["metric"]) for c, l in limits.items()]
        table = pd.DataFrame(results)
        table["passed"] = table["passed"].map({True: "PASS", False: "FAIL"})
        st.dataframe(table, hide_index=True)

    spectrum_channels = st.multiselect("Include a frequency analysis for", ds.channels)
    if st.button("Generate PDF report", type="primary"):
        with tempfile.TemporaryDirectory() as tmp:
            path = build_report(ds, Path(tmp) / f"{ds.name}_report.pdf", limits=limits, spectrum_channels=spectrum_channels)
            st.download_button("Download the report", path.read_bytes(), file_name=path.name, mime="application/pdf")

# ---------------------------------------------------------------- assistant
with tab_ask:
    has_key = bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))
    if not has_key:
        st.warning("Set ANTHROPIC_API_KEY (or log in with `ant auth login`) to use the assistant. The other tabs work offline.")
    question = st.text_input(
        "Question",
        value="Does this run meet the acceptance criteria of the test procedure? If not, what does the troubleshooting guide suggest?",
    )
    if st.button("Ask", type="primary"):
        from eda_assistant.assistant import EngineeringAssistant

        with st.spinner("Analyzing..."):
            try:
                answer = EngineeringAssistant(ds, docs).ask(question)
            except Exception as exc:  # show API or credential problems in the UI
                st.error(f"The assistant could not run: {exc}")
            else:
                st.markdown(answer.text)
                with st.expander(f"How this answer was built ({len(answer.tool_calls)} tool calls)"):
                    for call in answer.tool_calls:
                        st.markdown(f"**{call.name}** `{json.dumps(call.input)}`")
                        st.code(call.output[:2000], language="json")
