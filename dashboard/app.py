"""Dashboard 6 panel đọc từ data/logs.jsonl, theo contract config/dashboard.yaml.

Chạy: streamlit run dashboard/app.py
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "config" / "dashboard.yaml"
LOG_PATH = REPO_ROOT / os.getenv("LOG_PATH", "data/logs.jsonl")
LOCAL_TZ = "Asia/Ho_Chi_Minh"

# Categorical slots 1-4 (validated reference palette); threshold line is neutral ink.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
THRESHOLD_COLOR = "#52514e"
OPERATORS = {"lte": ("≤", lambda v, t: v <= t), "gte": ("≥", lambda v, t: v >= t)}

st.set_page_config(page_title="Day 13 Monitoring", layout="wide")


@st.cache_data
def load_config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))["dashboard"]


def load_logs() -> pd.DataFrame:
    if not LOG_PATH.exists():
        return pd.DataFrame()
    rows = []
    for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    df = pd.DataFrame(rows)
    if df.empty or "ts" not in df:
        return pd.DataFrame()
    df["ts"] = pd.to_datetime(df["ts"], utc=True, format="ISO8601").dt.tz_convert(LOCAL_TZ)
    df["minute"] = df["ts"].dt.floor("min")
    return df


def threshold_text(panel: dict) -> str:
    th = panel["threshold"]
    symbol, _ = OPERATORS[th["operator"]]
    return f"{th['aggregation']} {symbol} {th['value']:g} {panel['unit']}"


def status_badge(value: float, panel: dict) -> str:
    th = panel["threshold"]
    _, ok = OPERATORS[th["operator"]]
    return "✅ Đạt" if ok(value, th["value"]) else "⚠️ Không đạt"


def rule(value: float) -> alt.Chart:
    return (
        alt.Chart(pd.DataFrame({"y": [value]}))
        .mark_rule(color=THRESHOLD_COLOR, strokeDash=[6, 4], strokeWidth=1.5)
        .encode(y="y:Q")
    )


def line_chart(df: pd.DataFrame, y_title: str, threshold: float | None, domain: list[str],
               y_domain: list[float] | None = None) -> alt.Chart:
    hover = alt.selection_point(fields=["minute"], nearest=True, on="pointerover", empty=False)
    base = alt.Chart(df).encode(
        x=alt.X("hoursminutes(minute):O", title="Thời gian (GMT+7)", axis=alt.Axis(labelAngle=0)),
        y=alt.Y("value:Q", title=y_title, scale=alt.Scale(domain=y_domain) if y_domain else alt.Undefined),
        color=alt.Color(
            "series:N", scale=alt.Scale(domain=domain, range=SERIES[: len(domain)]),
            legend=alt.Legend(orient="top", title=None),
        ),
    )
    lines = base.mark_line(strokeWidth=2)
    points = base.mark_point(size=64, filled=True).encode(
        opacity=alt.condition(hover, alt.value(1), alt.value(0)),
        tooltip=[
            alt.Tooltip("hoursminutes(minute):O", title="Phút"),
            alt.Tooltip("series:N", title="Series"),
            alt.Tooltip("value:Q", title=y_title, format=",.4~f"),
        ],
    ).add_params(hover)
    layers = [lines, points]
    if threshold is not None:
        layers.append(rule(threshold))
    return alt.layer(*layers).properties(height=260)


def bar_chart(df: pd.DataFrame, x: str, y_title: str, threshold: float | None, x_title: str,
              temporal: bool = True) -> alt.Chart:
    x_enc = (
        alt.X(f"hoursminutes({x}):O", title=x_title, axis=alt.Axis(labelAngle=0))
        if temporal else alt.X(f"{x}:N", title=x_title, axis=alt.Axis(labelAngle=0))
    )
    bars = alt.Chart(df).mark_bar(color=SERIES[0], cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
        x=x_enc,
        y=alt.Y("value:Q", title=y_title),
        tooltip=[alt.Tooltip(f"hoursminutes({x}):O" if temporal else f"{x}:N", title=x_title),
                 alt.Tooltip("value:Q", title=y_title, format=",.4~f")],
    )
    layers = [bars]
    if threshold is not None:
        layers.append(rule(threshold))
    return alt.layer(*layers).properties(height=260)


def panel_header(panel: dict) -> None:
    st.subheader(panel["title"])
    st.caption(f"Đơn vị: **{panel['unit']}** · Threshold: `{threshold_text(panel)}` · Nguồn: `{panel['source']}`")


def empty(msg: str = "Chưa có dữ liệu trong khoảng thời gian này.") -> None:
    st.info(msg)


def render_latency(panel: dict, resp: pd.DataFrame) -> None:
    panel_header(panel)
    if resp.empty:
        return empty()
    q = lambda s, p: float(s.quantile(p / 100, interpolation="higher"))  # noqa: E731
    lat, ttft = resp["latency_ms"].astype(float), resp["ttft_ms"].astype(float)
    p95 = q(lat, 95)
    top, bottom = st.columns(2), st.columns(2)
    top[0].metric("P50", f"{q(lat, 50):,.0f} ms")
    top[1].metric("P95", f"{p95:,.0f} ms")
    bottom[0].metric("P99", f"{q(lat, 99):,.0f} ms")
    bottom[1].metric("TTFT P95", f"{q(ttft, 95):,.0f} ms")
    st.markdown(f"P95 so với threshold: **{status_badge(p95, panel)}**")
    per_min = resp.groupby("minute").agg(
        p50=("latency_ms", lambda s: q(s.astype(float), 50)),
        p95=("latency_ms", lambda s: q(s.astype(float), 95)),
        p99=("latency_ms", lambda s: q(s.astype(float), 99)),
        ttft_p95=("ttft_ms", lambda s: q(s.astype(float), 95)),
    ).reset_index()
    long = per_min.melt("minute", var_name="series", value_name="value")
    domain = ["p50", "p95", "p99", "ttft_p95"]
    st.altair_chart(line_chart(long, "ms", panel["threshold"]["value"], domain), width="stretch")


def render_traffic(panel: dict, req: pd.DataFrame, minutes: int) -> None:
    panel_header(panel)
    if req.empty:
        return empty()
    rate = len(req) / minutes
    cols = st.columns(2)
    cols[0].metric("Tổng request", f"{len(req):,}")
    cols[1].metric("Trung bình / phút", f"{rate:.2f}")
    st.markdown(f"rate_per_minute so với threshold: **{status_badge(rate, panel)}**")
    per_min = req.groupby("minute").size().rename("value").reset_index()
    st.altair_chart(bar_chart(per_min, "minute", "requests / phút", panel["threshold"]["value"],
                              "Thời gian (GMT+7)"), width="stretch")


def render_errors(panel: dict, req: pd.DataFrame, failed: pd.DataFrame, tool: pd.DataFrame) -> None:
    panel_header(panel)
    if req.empty:
        return empty()
    error_rate = len(failed) / len(req) * 100
    success = tool["tool_success"].astype(bool)
    retrieval_rate = success.mean() * 100 if len(success) else float("nan")
    cols = st.columns(3)
    cols[0].metric("Error rate", f"{error_rate:.2f} %")
    cols[1].metric("Retrieval success", "—" if pd.isna(retrieval_rate) else f"{retrieval_rate:.1f} %")
    cols[2].metric("Request lỗi", f"{len(failed):,}")
    st.markdown(f"error_rate_pct so với threshold: **{status_badge(error_rate, panel)}**")
    req_min = req.groupby("minute").size()
    fail_min = failed.groupby("minute").size() if not failed.empty else pd.Series(dtype=float)
    tool_min = tool.groupby("minute")["tool_success"].apply(lambda s: s.astype(bool).mean() * 100)
    per_min = pd.DataFrame({
        "error_rate_pct": (fail_min.reindex(req_min.index, fill_value=0) / req_min * 100),
        "tool_success_rate_pct": tool_min.reindex(req_min.index),
    }).reset_index().melt("minute", var_name="series", value_name="value").dropna()
    st.altair_chart(line_chart(per_min, "%", panel["threshold"]["value"],
                               ["error_rate_pct", "tool_success_rate_pct"]), width="stretch")
    if not failed.empty:
        st.markdown("**Breakdown theo `error_type`**")
        st.dataframe(failed["error_type"].value_counts().rename_axis("error_type").reset_index(name="count"),
                     hide_index=True, width="stretch")


def render_cost(panel: dict, resp: pd.DataFrame) -> None:
    panel_header(panel)
    if resp.empty:
        return empty()
    total = float(resp["cost_usd"].sum())
    cols = st.columns(2)
    cols[0].metric("Tổng chi phí", f"${total:.4f}")
    cols[1].metric("Trung bình / request", f"${total / len(resp):.6f}")
    st.markdown(f"total so với threshold: **{status_badge(total, panel)}**")
    per_min = resp.groupby("minute")["cost_usd"].sum().rename("value").reset_index()
    # Threshold applies to the window total, so it is shown on the tile rather than per-minute bars.
    st.altair_chart(bar_chart(per_min, "minute", "USD / phút", None, "Thời gian (GMT+7)"),
                    width="stretch")


def render_tokens(panel: dict, resp: pd.DataFrame) -> None:
    panel_header(panel)
    if resp.empty:
        return empty()
    sums = pd.DataFrame({
        "field": ["tokens_in", "tokens_out"],
        "value": [int(resp["tokens_in"].sum()), int(resp["tokens_out"].sum())],
    })
    cols = st.columns(2)
    cols[0].metric("tokens_in", f"{sums.value[0]:,}")
    cols[1].metric("tokens_out", f"{sums.value[1]:,}")
    worst = int(sums.value.max())
    st.markdown(f"sum_by_field so với threshold: **{status_badge(worst, panel)}**")
    st.altair_chart(bar_chart(sums, "field", "tokens", panel["threshold"]["value"], "Field", temporal=False),
                    width="stretch")


def render_quality(panel: dict, resp: pd.DataFrame) -> None:
    panel_header(panel)
    if resp.empty:
        return empty()
    mean = float(resp["quality_score"].mean())
    st.metric("Mean quality_score", f"{mean:.3f}")
    st.markdown(f"mean so với threshold: **{status_badge(mean, panel)}**")
    per_min = resp.groupby("minute")["quality_score"].mean().rename("value").reset_index()
    per_min["series"] = "mean"
    st.altair_chart(line_chart(per_min, "score (0–1)", panel["threshold"]["value"], ["mean"], y_domain=[0, 1]),
                    width="stretch")


config = load_config()
panels = {p["id"]: p for p in config["panels"]}

st.title(config["title"])
with st.sidebar:
    st.header("Bộ lọc")
    minutes = st.selectbox("Time range", [15, 30, 60, 180, 1440], index=2,
                           format_func=lambda m: f"{m} phút" if m < 60 else f"{m // 60} giờ")
    anchor_latest = st.toggle("Kết thúc tại log mới nhất", value=False,
                              help="Bật khi xem lại log cũ; tắt để xem cửa sổ tính đến hiện tại.")
    st.caption(f"Nguồn: `{LOG_PATH.relative_to(REPO_ROOT)}` · Tự refresh {config['refresh_seconds']}s")


@st.fragment(run_every=f"{config['refresh_seconds']}s")
def render_dashboard() -> None:
    df = load_logs()
    if df.empty:
        st.warning(f"Không đọc được log tại `{LOG_PATH}`. Hãy chạy API và `scripts/load_test.py`.")
        return
    end = df["ts"].max() if anchor_latest else pd.Timestamp(datetime.now(timezone.utc)).tz_convert(LOCAL_TZ)
    start = end - timedelta(minutes=minutes)
    window = df[(df["ts"] > start) & (df["ts"] <= end)]
    st.caption(
        f"**Time range:** {start:%Y-%m-%d %H:%M} → {end:%H:%M} (GMT+7, {minutes} phút) · "
        f"Cập nhật lúc {datetime.now().astimezone():%H:%M:%S} · {len(window):,} log records"
    )

    event = window.get("event", pd.Series(dtype=str))
    resp = window[event == "response_sent"]
    req = window[event == "request_received"]
    failed = window[event == "request_failed"]
    tool = window[window["tool_success"].notna()] if "tool_success" in window else window.iloc[0:0]

    row1 = st.columns(2)
    with row1[0], st.container(border=True):
        render_latency(panels["latency"], resp)
    with row1[1], st.container(border=True):
        render_traffic(panels["traffic"], req, minutes)
    row2 = st.columns(2)
    with row2[0], st.container(border=True):
        render_errors(panels["errors"], req, failed, tool)
    with row2[1], st.container(border=True):
        render_cost(panels["cost"], resp)
    row3 = st.columns(2)
    with row3[0], st.container(border=True):
        render_tokens(panels["tokens"], resp)
    with row3[1], st.container(border=True):
        render_quality(panels["quality"], resp)


render_dashboard()
