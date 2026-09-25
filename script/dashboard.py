"""Observability dashboard cho Day 10 Data Pipeline.

Chay: streamlit run script/dashboard.py
"""
from __future__ import annotations

from contextlib import redirect_stdout
from datetime import datetime
import io
from pathlib import Path
from typing import Any, Callable

import altair as alt
import pandas as pd
import streamlit as st

from core.config import load_settings
from core.utils import read_json

st.set_page_config(page_title="DoMixi · Data Observability", page_icon="🛡️", layout="wide")

SETTINGS = load_settings()
PATHS = SETTINGS.paths
STATES = ["Baseline", "Corrupted", "Repaired"]
STATE_ICONS = {"Baseline": "🧪", "Corrupted": "💉", "Repaired": "🩹"}
# Categorical slots 1-3 cua bang mau tham chieu (validated all-pairs, light & dark).
PALETTE = {
    "light": {"Baseline": "#2a78d6", "Corrupted": "#eb6834", "Repaired": "#1baf7a"},
    "dark": {"Baseline": "#3987e5", "Corrupted": "#d95926", "Repaired": "#199e70"},
}
CRITICAL = {"light": "#e34948", "dark": "#e66767"}
METRIC_LABELS = {
    "retrieval_hit_rate": "Retrieval Hit Rate",
    "mean_token_f1": "Token F1",
    "judge_accuracy": "LLM Judge Accuracy",
    "mean_judge_score": "Judge Score (/5)",
}
ARTIFACTS = {
    "Baseline": {
        "metrics": PATHS.baseline_metrics,
        "answers": PATHS.baseline_answers,
        "quality": PATHS.baseline_quality_report,
        "freshness": PATHS.freshness_report,
        "data": PATHS.clean_json,
        "embeddings": PATHS.embeddings_json,
    },
    "Corrupted": {
        "metrics": PATHS.corrupted_metrics,
        "answers": PATHS.corrupted_answers,
        "quality": PATHS.corrupted_quality_report,
        "freshness": PATHS.quality_dir / "corrupted_freshness_report.json",
        "data": PATHS.corrupted_clean_json,
        "embeddings": PATHS.corrupted_embeddings_json,
    },
    "Repaired": {
        "metrics": PATHS.repaired_metrics,
        "answers": PATHS.repaired_answers,
        "quality": PATHS.quality_dir / "repaired_quality_report.json",
        "freshness": PATHS.quality_dir / "repaired_freshness_report.json",
        "data": PATHS.repaired_clean_json,
        "embeddings": PATHS.repaired_embeddings_json,
    },
}


# ---------------------------------------------------------------- helpers
def theme_mode() -> str:
    try:
        return "dark" if st.context.theme.type == "dark" else "light"
    except Exception:
        return "light"


def colors() -> dict[str, str]:
    return PALETTE[theme_mode()]


def load(path: Path) -> Any:
    try:
        return read_json(path) if path.exists() else None
    except Exception:
        return None


def artifact(state: str, kind: str) -> Any:
    return load(ARTIFACTS[state][kind])


def state_ready(state: str) -> bool:
    return ARTIFACTS[state]["metrics"].exists()


def modified(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%H:%M:%S %d/%m") if path.exists() else "—"


def run_step(label: str, fn: Callable[[], Any]) -> None:
    buffer = io.StringIO()
    with st.status(label, expanded=True) as status:
        st.write("Đang chạy… (embedding + LLM judge có thể mất 20–60 giây)")
        try:
            with redirect_stdout(buffer):
                fn()
            status.update(label=f"✅ {label} — xong", state="complete", expanded=False)
            st.session_state["last_log"] = buffer.getvalue()
            st.session_state["flash"] = ("success", f"{label}: hoàn tất")
        except Exception as exc:  # hien loi ro rang cho nguoi demo
            status.update(label=f"❌ {label} — lỗi", state="error")
            st.session_state["last_log"] = buffer.getvalue() + f"\nERROR: {exc}"
            st.session_state["flash"] = ("error", f"{label} lỗi: {exc}")
    st.rerun()


def step_phase1() -> None:
    from pipelines.phase1 import main

    main()


def step_corrupt() -> None:
    from pipelines.corruption_flow import run_corruption_stage

    run_corruption_stage(SETTINGS)


def step_repair() -> None:
    from pipelines.corruption_flow import run_repair_stage

    run_repair_stage(SETTINGS)


def step_all() -> None:
    step_phase1()
    step_corrupt()
    step_repair()


# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.markdown("## 🎛️ Điều khiển Pipeline")
    st.caption("Bấm lần lượt ① → ② → ③ để demo Silent Failure và Self-healing.")
    if st.button("① Chạy Baseline (Phase 1)", width="stretch", type="primary"):
        run_step("Phase 1 — Baseline", step_phase1)
    if st.button("② Tiêm 6 lỗi dữ liệu", width="stretch", disabled=not state_ready("Baseline")):
        run_step("Corruption — tiêm lỗi", step_corrupt)
    if st.button("③ Repair từ Raw snapshot", width="stretch", disabled=not state_ready("Corrupted")):
        run_step("Repair — phục hồi", step_repair)
    st.divider()
    if st.button("▶ Chạy toàn bộ ①②③", width="stretch"):
        run_step("Full demo", step_all)

    st.divider()
    st.markdown("**Cấu hình**")
    st.caption(
        f"LLM: `{SETTINGS.llm_provider}` · `{SETTINGS.model_name}`  \n"
        f"Embedding: `{SETTINGS.embedding_model.split('/')[-1]}`  \n"
        f"Freshness SLA: `age_days > {SETTINGS.freshness_threshold_days}` ≤ 25%"
    )
    if st.session_state.get("last_log"):
        with st.expander("📜 Log lần chạy gần nhất"):
            st.code(st.session_state["last_log"], language="text")

flash = st.session_state.pop("flash", None)
if flash:
    (st.success if flash[0] == "success" else st.error)(flash[1])

# ---------------------------------------------------------------- header
st.title("🛡️ Data Observability Dashboard")
st.caption(
    "Crossref → Clean → **GX 1.x Quality Gate** → ChromaDB → RAG Eval → 💉 Corruption → 🩹 Idempotent Repair"
)

cols = st.columns(3)
for col, state in zip(cols, STATES):
    metrics = artifact(state, "metrics")
    quality = artifact(state, "quality") if metrics else None
    freshness = artifact(state, "freshness") if metrics else None
    with col.container(border=True):
        st.markdown(f"#### {STATE_ICONS[state]} {state}")
        if not metrics:
            st.caption("Chưa chạy")
            continue
        gate_ok = bool(quality and quality.get("success"))
        fresh_ok = bool(freshness and freshness.get("is_fresh"))
        st.markdown(
            f"{'✅' if gate_ok else '🚨'} Quality gate: **{'PASS' if gate_ok else 'FAIL'}**"
            f" &nbsp;·&nbsp; {'✅' if fresh_ok else '🚨'} Freshness: **{'FRESH' if fresh_ok else 'STALE'}**"
        )
        base = artifact("Baseline", "metrics") if state != "Baseline" else None
        m1, m2 = st.columns(2)
        for target, key in ((m1, "retrieval_hit_rate"), (m2, "mean_token_f1")):
            delta = None
            if base:
                delta = f"{metrics[key] - base[key]:+.2f}"
            target.metric(METRIC_LABELS[key], f"{metrics[key]:.2f}", delta=delta)
        st.caption(f"Cập nhật: {modified(ARTIFACTS[state]['metrics'])} · {quality.get('row_count') if quality else '—'} rows")

tabs = st.tabs(["📊 So sánh 3 trạng thái", "🛡️ Quality & Freshness", "💉 Corruption log", "🔍 Từng câu hỏi", "💬 Hỏi thử RAG", "📄 Reports"])

# ---------------------------------------------------------------- tab 1: comparison
with tabs[0]:
    rows = []
    for state in STATES:
        metrics = artifact(state, "metrics")
        if not metrics:
            continue
        for key, label in METRIC_LABELS.items():
            value = float(metrics.get(key, 0))
            rows.append(
                {
                    "state": state,
                    "metric": label,
                    "value": value / 5 if key == "mean_judge_score" else value,
                    "display": f"{value:.1f}/5" if key == "mean_judge_score" else f"{value:.2f}",
                }
            )
    if not rows:
        st.info("Chưa có kết quả. Bấm **① Chạy Baseline** ở thanh bên trái.")
    else:
        df = pd.DataFrame(rows)
        present = [s for s in STATES if s in set(df["state"])]
        palette = colors()
        color = alt.Color(
            "state:N",
            scale=alt.Scale(domain=present, range=[palette[s] for s in present]),
            legend=alt.Legend(title=None, orient="top"),
        )
        base_chart = alt.Chart(df).encode(
            x=alt.X("metric:N", title=None, sort=list(METRIC_LABELS.values()), axis=alt.Axis(labelAngle=0)),
            xOffset=alt.XOffset("state:N", sort=present),
        )
        bars = base_chart.mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, stroke=None).encode(
            y=alt.Y("value:Q", title="Điểm (chuẩn hoá 0–1)", scale=alt.Scale(domain=[0, 1.1]), axis=alt.Axis(grid=True, tickCount=5)),
            color=color,
            tooltip=[alt.Tooltip("state:N", title="Trạng thái"), alt.Tooltip("metric:N", title="Chỉ số"), alt.Tooltip("display:N", title="Giá trị")],
        )
        labels = base_chart.mark_text(dy=-8, fontSize=11).encode(
            y="value:Q", text="display:N", detail="state:N"
        )
        st.altair_chart((bars + labels).properties(height=360), width="stretch")

        table = df.pivot(index="metric", columns="state", values="display").reindex(list(METRIC_LABELS.values()))
        st.dataframe(table[present], width="stretch")

        if state_ready("Corrupted"):
            base = artifact("Baseline", "metrics")
            corrupted = artifact("Corrupted", "metrics")
            drop = base["retrieval_hit_rate"] - corrupted["retrieval_hit_rate"]
            st.warning(
                f"**Silent failure:** trên dữ liệu lỗi, RAG vẫn trả lời trơn tru, không báo lỗi — nhưng Hit Rate giảm "
                f"**{drop:.0%}**, Token F1 giảm **{base['mean_token_f1'] - corrupted['mean_token_f1']:.0%}**.",
                icon="⚠️",
            )
        summary = load(PATHS.quality_dir / "repair_summary.json")
        if state_ready("Repaired") and summary:
            st.success(
                f"**Self-healing:** repair tự kích hoạt vì *{summary['trigger']}* · idempotent (chạy 2 lần giống hệt): "
                f"**{summary['idempotent_two_runs_identical']}** · khớp nội dung baseline: **{summary['repaired_matches_baseline_content']}**",
                icon="🩹",
            )

# ---------------------------------------------------------------- tab 2: quality & freshness
with tabs[1]:
    available = [s for s in STATES if artifact(s, "quality")]
    if not available:
        st.info("Chưa có báo cáo chất lượng.")
    else:
        chosen = st.segmented_control(
            "Trạng thái dữ liệu", available, default=available[-1], key="quality_state"
        ) or available[-1]
        quality = artifact(chosen, "quality")
        freshness = artifact(chosen, "freshness") or {}
        q1, q2, q3, q4 = st.columns(4)
        q1.metric("GX Quality Gate", "PASS ✅" if quality["success"] else "FAIL 🚨", border=True)
        q2.metric("Expectations đạt", f"{quality['successful_expectations']}/{quality['evaluated_expectations']}", border=True)
        q3.metric("Freshness SLA", "FRESH ✅" if freshness.get("is_fresh") else "STALE 🚨", border=True)
        q4.metric(
            "Tỷ lệ bài quá hạn",
            f"{freshness.get('stale_ratio', 0):.0%}",
            help=f"Ngưỡng cảnh báo: > 25% bài có age_days > {SETTINGS.freshness_threshold_days}",
            border=True,
        )

        checks = pd.DataFrame(quality["checks"])
        checks["Kết quả"] = checks["success"].map({True: "✅ Pass", False: "🚨 Fail"})
        checks["Chi tiết"] = checks.apply(
            lambda r: f"observed = {r['observed_value']}"
            if "observed_value" in r and pd.notna(r.get("observed_value"))
            else f"{int(r.get('unexpected_count', 0) or 0)} dòng vi phạm ({(r.get('unexpected_percent') or 0):.1f}%)",
            axis=1,
        )
        st.markdown(f"**Great Expectations {quality.get('gx_version', '')} — {quality['row_count']} dòng**")
        st.dataframe(
            checks[["Kết quả", "expectation", "column", "Chi tiết"]].rename(columns={"expectation": "Expectation", "column": "Cột"}),
            width="stretch",
            hide_index=True,
        )

        data = artifact(chosen, "data")
        if data:
            ages = pd.DataFrame(data)[["paper_id", "title", "published", "age_days"]]
            ages["age_days"] = pd.to_numeric(ages["age_days"], errors="coerce")
            threshold = SETTINGS.freshness_threshold_days
            st.markdown(f"**Phân bố độ tuổi bài báo (`age_days`) — đường đỏ là SLA {threshold} ngày**")
            hist = (
                alt.Chart(ages)
                .mark_bar(color=colors()[chosen], cornerRadiusTopLeft=4, cornerRadiusTopRight=4, stroke=None)
                .encode(
                    x=alt.X("age_days:Q", bin=alt.Bin(step=30), title="age_days (ngày)"),
                    y=alt.Y("count():Q", title="Số bài báo"),
                    tooltip=[alt.Tooltip("count():Q", title="Số bài"), alt.Tooltip("age_days:Q", bin=alt.Bin(step=30), title="age_days")],
                )
            )
            rule = alt.Chart(pd.DataFrame({"x": [threshold]})).mark_rule(
                color=CRITICAL[theme_mode()], strokeDash=[6, 4], strokeWidth=2
            ).encode(x="x:Q")
            rule_label = alt.Chart(pd.DataFrame({"x": [threshold], "t": [f"SLA {threshold} ngày"]})).mark_text(
                align="left", dx=6, dy=-120, color=CRITICAL[theme_mode()], fontWeight="bold"
            ).encode(x="x:Q", text="t:N")
            st.altair_chart((hist + rule + rule_label).properties(height=280), width="stretch")
            stale = ages[ages["age_days"] > threshold].sort_values("age_days", ascending=False)
            with st.expander(f"🚨 {len(stale)} bài quá hạn (age_days > {threshold})"):
                st.dataframe(stale, width="stretch", hide_index=True)

# ---------------------------------------------------------------- tab 3: corruption log
with tabs[2]:
    log = load(PATHS.corruption_log)
    if not log:
        st.info("Chưa tiêm lỗi. Bấm **② Tiêm 6 lỗi dữ liệu**.")
    else:
        st.markdown(
            f"**{log['corruption_types']} kịch bản lỗi** · số dòng {log['rows_before']} → {log['rows_after']} · seed = `{log['seed']}` (tái lập được)"
        )
        icons = {
            "drop_latest_records": "🗑️",
            "blank_summary": "⬜",
            "inject_noise": "🔣",
            "truncate_title": "✂️",
            "stale_date": "🕰️",
            "duplicate_rows": "👯",
        }
        grid = st.columns(3)
        for i, entry in enumerate(log["corruptions"]):
            with grid[i % 3].container(border=True):
                st.markdown(f"#### {icons.get(entry['corruption'], '•')} `{entry['corruption']}`")
                st.caption(entry["description"])
                st.metric("Dòng bị ảnh hưởng", entry["affected_rows"])
                with st.expander("Chi tiết"):
                    detail = {"paper_id": entry["affected_paper_ids"]}
                    if "original_titles" in entry:
                        detail["title gốc"] = entry["original_titles"]
                    if "original_published" in entry:
                        detail["published gốc"] = entry["original_published"]
                    st.dataframe(pd.DataFrame(detail), width="stretch", hide_index=True)

# ---------------------------------------------------------------- tab 4: per question
with tabs[3]:
    answers = {s: artifact(s, "answers") for s in STATES}
    answers = {s: {a["id"]: a for a in v} for s, v in answers.items() if v}
    if "Baseline" not in answers:
        st.info("Chưa có kết quả đánh giá.")
    else:
        present = [s for s in STATES if s in answers]
        rows = []
        for item_id, base in answers["Baseline"].items():
            row = {"ID": item_id, "Loại": base["question_type"], "Câu hỏi": base["question"]}
            for state in present:
                item = answers[state].get(item_id)
                row[f"F1 · {state}"] = item["token_f1"] if item else None
                row[f"Hit · {state}"] = ("✅" if item["retrieval_hit"] else "❌") if item else "—"
            rows.append(row)
        table = pd.DataFrame(rows)
        st.dataframe(
            table,
            width="stretch",
            hide_index=True,
            column_config={
                f"F1 · {s}": st.column_config.ProgressColumn(f"F1 · {s}", min_value=0.0, max_value=1.0, format="%.2f")
                for s in present
            },
        )

        options = list(answers["Baseline"].keys())
        default_index = 0
        if "Corrupted" in answers:
            worst = min(options, key=lambda i: answers["Corrupted"].get(i, {}).get("token_f1", 1.0))
            default_index = options.index(worst)
        pick = st.selectbox(
            "Xem chi tiết câu hỏi",
            options,
            index=default_index,
            format_func=lambda i: f"{i} · {answers['Baseline'][i]['question'][:90]}",
        )
        st.markdown(f"**Ground truth:** {answers['Baseline'][pick]['ground_truth']}")
        cards = st.columns(len(present))
        for card, state in zip(cards, present):
            item = answers[state].get(pick)
            with card.container(border=True):
                st.markdown(f"**{STATE_ICONS[state]} {state}**")
                if not item:
                    st.caption("—")
                    continue
                verdict = item["judge"]
                st.markdown(
                    f"{'✅' if item['retrieval_hit'] else '❌'} retrieval · F1 **{item['token_f1']:.2f}** · judge **{verdict['score']}/5**"
                )
                st.info(item["answer"] or "(câu trả lời rỗng)")
                st.caption(f"Judge: {verdict['reasoning']}")
                st.caption("Top docs: " + ", ".join(item["retrieved_doc_ids"]))

# ---------------------------------------------------------------- tab 5: playground
with tabs[4]:
    indexed = [s for s in STATES if ARTIFACTS[s]["embeddings"].exists()]
    if not indexed:
        st.info("Chưa có collection nào trong ChromaDB.")
    else:
        test_set = load(PATHS.eval_testset) or []
        samples = ["(tự nhập câu hỏi)"] + [t["question"] for t in test_set]
        sample = st.selectbox("Chọn câu hỏi mẫu từ test set", samples, index=1 if len(samples) > 1 else 0)
        question = st.text_input("Câu hỏi", value="" if sample == samples[0] else sample)
        c1, c2 = st.columns([1, 1])
        chosen_states = c1.multiselect("Collection", indexed, default=indexed)
        use_agent = c2.toggle("Dùng LLM Agent (chậm hơn, cần API key)", value=False)
        if st.button("🔎 Hỏi", type="primary", disabled=not question.strip()):
            from retrieval.index import LocalEmbeddingIndex
            from retrieval.qa import answer_question

            cards = st.columns(max(1, len(chosen_states)))
            for card, state in zip(cards, chosen_states):
                with card.container(border=True):
                    st.markdown(f"**{STATE_ICONS[state]} {state}** · `{load(ARTIFACTS[state]['embeddings'])['collection_name']}`")
                    try:
                        index = LocalEmbeddingIndex.load(SETTINGS, ARTIFACTS[state]["embeddings"])
                        if use_agent:
                            from retrieval.agent import build_agent, run_agent_question

                            with st.spinner("Agent đang suy nghĩ…"):
                                answer = run_agent_question(build_agent(SETTINGS, index), question)
                            st.info(answer)
                        result = answer_question(question, settings=SETTINGS, index=index)
                        if not use_agent:
                            st.info(result.answer or "(câu trả lời rỗng)")
                        st.caption("Tài liệu truy xuất:")
                        for rank, (doc_id, title) in enumerate(zip(result.retrieved_doc_ids, result.retrieved_titles), start=1):
                            st.markdown(f"{rank}. **{title}**  \n`{doc_id}`")
                    except Exception as exc:
                        st.error(f"Lỗi: {exc}")

# ---------------------------------------------------------------- tab 6: reports
with tabs[5]:
    for title, path in (("Phase 1 report", PATHS.baseline_report), ("Corruption report (3 trạng thái)", PATHS.comparison_report)):
        with st.expander(f"📄 {title} — `{path.relative_to(PATHS.project_dir).as_posix()}`", expanded=path == PATHS.comparison_report):
            if path.exists():
                st.markdown(path.read_text(encoding="utf-8"))
            else:
                st.caption("Chưa được sinh.")
