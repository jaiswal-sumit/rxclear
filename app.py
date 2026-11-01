"""Streamlit demo UI for the medication safety agent.

Run: .venv/bin/streamlit run app.py
"""

import streamlit as st

from src.agents import generate_report

st.set_page_config(page_title="RxClear — Medication Safety", page_icon="💊", layout="wide")

st.title("RxClear")
st.caption(
    "Understand your medications in plain language. Powered by AI agents, "
    "NIH RxNav, and openFDA data."
)

with st.sidebar:
    st.header("Your medications")
    meds_text = st.text_area(
        "One per line — spell them the way they appear on your bottles",
        value="lisinopril\nmetformin\nibuprofen",
        height=150,
    )
    language = st.selectbox(
        "Preferred language",
        ["English", "Spanish", "Hindi", "Vietnamese", "Tagalog", "Chinese"],
    )
    run = st.button("Check my medications", type="primary", use_container_width=True)
    st.caption(
        "Not medical advice. Always confirm with your pharmacist or doctor."
    )

if run:
    meds = [m.strip() for m in meds_text.splitlines() if m.strip()]
    if not meds:
        st.warning("Add at least one medication.")
        st.stop()

    with st.spinner("Agents are checking FDA labels and interactions…"):
        report = generate_report(meds, language=language)

    if report.urgent_flags:
        for flag in report.urgent_flags:
            st.error(f"🚨 {flag}")

    if report.interaction_warnings:
        st.subheader("Interaction warnings")
        for w in report.interaction_warnings:
            box = st.error if w.severity.lower() == "high" else st.warning
            box(f"**{' + '.join(w.drugs)}** — {w.plain_language_explanation}\n\n**What to do:** {w.action}")

    st.subheader("Your medications, in plain language")
    for drug in report.drugs:
        with st.expander(f"💊 {drug.name}"):
            st.markdown(f"**What it does:** {drug.what_it_does}")
            st.markdown(f"**How to take it:** {drug.how_to_take}")
            if drug.warnings:
                st.markdown("**Warnings:**")
                for warn in drug.warnings:
                    st.markdown(f"- {warn}")
            if drug.other_names:
                st.markdown(f"**Also sold as:** {', '.join(drug.other_names)}")

    if report.questions_for_pharmacist:
        st.subheader("Ask your pharmacist")
        for q in report.questions_for_pharmacist:
            st.markdown(f"- {q}")

    st.caption(report.disclaimer)
