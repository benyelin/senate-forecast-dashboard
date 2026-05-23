from __future__ import annotations

from pathlib import Path
import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parent
OUTPUTS = ROOT / "outputs"
INPUTS = ROOT / "inputs"

st.set_page_config(page_title="2026 Senate Forecast", page_icon="🗳️", layout="wide")


def read_csv_safe(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def pct(x):
    try:
        return f"{float(x):.1%}"
    except Exception:
        return "—"


def num(x, digits=1):
    try:
        return f"{float(x):.{digits}f}"
    except Exception:
        return "—"


summary = read_csv_safe(OUTPUTS / "forecast_summary.csv")
race_stats = read_csv_safe(OUTPUTS / "race_stats.csv")
seat_dist = read_csv_safe(OUTPUTS / "seat_distribution.csv")
scenarios = read_csv_safe(OUTPUTS / "scenario_summary.csv")
bayes = read_csv_safe(INPUTS / "bayesian_update_generated.csv")
poll_avgs = read_csv_safe(INPUTS / "polling_averages_generated.csv")

st.title("2026 Senate Forecast Dashboard")
st.caption("Polling ingestion → Bayesian update → correlated simulation → scenario diagnostics.")

if summary.empty:
    st.error("No forecast outputs found. Run `python run_full_pipeline.py` first.")
    st.stop()

s = summary.iloc[0]

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Dem Control Odds", pct(s.get("dem_control_probability")))
c2.metric("Expected Dem Seats", num(s.get("expected_dem_seats"), 2))
c3.metric("Median Dem Seats", num(s.get("median_dem_seats"), 0))
c4.metric("Polling Weight", pct(s.get("polling_weight")))
c5.metric("Implied Correlation", pct(s.get("implied_correlation")))

c6, c7, c8, c9 = st.columns(4)
c6.metric("Days Out", num(s.get("days_out"), 0))
c7.metric("Total Error SD", num(s.get("total_error_sd"), 2))
c8.metric("National Error SD", num(s.get("national_error_sd"), 2))
c9.metric("Race Error SD", num(s.get("race_error_sd"), 2))

st.divider()

tab_overview, tab_races, tab_scenarios, tab_polls, tab_method = st.tabs(
    ["Overview", "Race Table", "Scenarios", "Polling & Bayes", "Method"]
)

with tab_overview:
    left, right = st.columns([1.25, 1])

    with left:
        st.subheader("Seat Distribution")
        if seat_dist.empty:
            st.info("No seat distribution file found.")
        else:
            fig = px.bar(
                seat_dist,
                x="dem_seats",
                y="probability",
                labels={"dem_seats": "Democratic Seats", "probability": "Probability"},
                text=seat_dist["probability"].map(lambda v: f"{v:.1%}"),
            )
            fig.update_traces(textposition="outside")
            fig.update_layout(yaxis_tickformat=".0%", showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

    with right:
        st.subheader("Model Settings")
        st.write(f"Control threshold: **{int(s.get('dem_control_threshold', 51))} seats**")
        st.write(f"Baseline Democratic seats: **{int(s.get('dem_baseline_seats', 47))}**")
        st.write(f"National environment margin: **{num(s.get('national_environment_margin'), 2)}**")

        if not race_stats.empty and "tipping_share_of_control_sims" in race_stats.columns:
            tipping = race_stats.sort_values("tipping_share_of_control_sims", ascending=False).head(8)
            show = tipping[["state", "tipping_share_of_control_sims", "simulated_dem_win_prob", "model_margin_dem"]].copy()
            show["tipping_share_of_control_sims"] = show["tipping_share_of_control_sims"].map(lambda v: f"{v:.1%}")
            show["simulated_dem_win_prob"] = show["simulated_dem_win_prob"].map(lambda v: f"{v:.1%}")
            show["model_margin_dem"] = show["model_margin_dem"].map(lambda v: f"{v:.1f}")
            st.subheader("Most Common Tipping Races")
            st.dataframe(show.rename(columns={
                "state": "State",
                "tipping_share_of_control_sims": "Tipping Share",
                "simulated_dem_win_prob": "Dem Win Prob",
                "model_margin_dem": "Model Margin",
            }), use_container_width=True, hide_index=True)

with tab_races:
    st.subheader("Race-Level Forecast")
    if race_stats.empty:
        st.info("No race stats found.")
    else:
        display = race_stats.copy()
        display["Dem Win Prob"] = display["simulated_dem_win_prob"].map(lambda v: f"{v:.1%}")
        display["Pre-Sim Prob"] = display["pre_sim_dem_win_prob"].map(lambda v: f"{v:.1%}")
        display["Model Margin"] = display["model_margin_dem"].map(lambda v: f"{v:.1f}")
        display["Avg Sim Margin"] = display["avg_simulated_margin_dem"].map(lambda v: f"{v:.1f}")
        cols = [
            "state", "race_tier", "dem_candidate", "gop_candidate", "current_holder",
            "Model Margin", "Dem Win Prob", "Avg Sim Margin",
            "elasticity", "dem_win_counts_for_seat_change"
        ]
        st.dataframe(display[cols].rename(columns={
            "state": "State",
            "race_tier": "Tier",
            "dem_candidate": "Dem Candidate",
            "gop_candidate": "GOP Candidate",
            "current_holder": "Current Holder",
            "elasticity": "Elasticity",
            "dem_win_counts_for_seat_change": "Seat Gain If Dem Wins",
        }), use_container_width=True, hide_index=True)

        fig = px.bar(
            race_stats.sort_values("simulated_dem_win_prob"),
            x="simulated_dem_win_prob",
            y="state",
            orientation="h",
            labels={"simulated_dem_win_prob": "Democratic Win Probability", "state": "State"},
        )
        fig.update_layout(xaxis_tickformat=".0%")
        st.plotly_chart(fig, use_container_width=True)

with tab_scenarios:
    st.subheader("National Swing Sensitivity")
    if scenarios.empty:
        st.info("No scenario outputs found. Run `python scenario_runner.py`.")
    else:
        fig = px.line(
            scenarios,
            x="manual_national_swing_dem",
            y="dem_control_probability",
            markers=True,
            labels={
                "manual_national_swing_dem": "National Swing Toward Democrats",
                "dem_control_probability": "Democratic Control Probability",
            },
        )
        fig.update_layout(yaxis_tickformat=".0%")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(scenarios, use_container_width=True, hide_index=True)

with tab_polls:
    st.subheader("Weighted Polling Averages")
    if poll_avgs.empty:
        st.info("No generated polling averages found.")
    else:
        st.dataframe(poll_avgs, use_container_width=True, hide_index=True)

    st.subheader("Bayesian Update Audit")
    if bayes.empty:
        st.info("No Bayesian update file found.")
    else:
        st.dataframe(bayes, use_container_width=True, hide_index=True)

with tab_method:
    st.subheader("Methodology")
    st.markdown("""
    **Pipeline**

    1. Enter/export polls into `inputs/polls_raw.csv`.
    2. `ingest_polls.py` creates weighted polling averages.
    3. `bayesian_update.py` combines fundamentals and polling.
    4. `run_model.py` simulates race margins using shared national and race-specific errors.
    5. `scenario_runner.py` tests national swing sensitivity.
    6. This dashboard reads the output CSVs.

    **Key modeling choices**

    - Outcomes are simulated from margins.
    - Shared national error creates correlated outcomes.
    - Race-specific error captures local uncertainty.
    - Time-to-election calibration controls uncertainty and polling weight.
    - Candidate metadata is separate from numerical assumptions.
    """)

    st.code("""
python run_full_pipeline.py --as-of 2026-05-22 --days-out 165 --sims 50000
streamlit run dashboard_app.py
    """.strip(), language="bash")
