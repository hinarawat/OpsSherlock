"""OpsSherlock — Multi-Agent DevOps Incident Analysis (Streamlit chat UI).

Flow: pick log -> full-screen preview -> Scan -> inspect each error type -> solve -> n8n.
"""
import os
import re
from pathlib import Path

import streamlit as st

# Streamlit Cloud secrets -> env, so agents/ stays framework-free
try:
    for k, v in st.secrets.items():
        if isinstance(v, str):
            os.environ.setdefault(k, v)
except Exception:
    pass

from agents.graph import build_graph, NODE_LABELS
from agents.nodes import get_llm, scan_log, notify_agent

st.set_page_config(page_title="OpsSherlock", page_icon="🕵️", layout="wide")

SAMPLE_DIR = Path(__file__).parent / "sample_logs"


@st.cache_resource(show_spinner=False)
def graph():
    # notify is NOT in the graph — it runs only after human approval (review step)
    return build_graph(include_notify=False)


# ---------- Session state ----------
ss = st.session_state
ss.setdefault("messages", [{
    "role": "assistant",
    "content": "Hi, I'm **OpsSherlock** — your incident detective. Pick a sample log on the "
               "left, hit **Preview** to read it full-screen, then **Scan**. I'll list the "
               "error types inside — open each one to see the exact log lines — and you "
               "choose which to solve. After a report, ask me follow-ups.",
}])
ss.setdefault("incident", None)
ss.setdefault("pending", None)
ss.setdefault("awaiting", None)   # completed analysis waiting for human approval
ss.setdefault("dark", False)


# ---------- Theme toggle + layout CSS ----------
def inject_css():
    sidebar_css = """
    section[data-testid="stSidebar"] { width: 340px !important; min-width: 340px !important; }
    """
    dark_css = """
    .stApp, div[data-testid="stAppViewContainer"], div[data-testid="stMain"] {
        background-color: #0e1117 !important; }
    header[data-testid="stHeader"], div[data-testid="stBottom"],
    div[data-testid="stBottomBlockContainer"] { background-color: #0e1117 !important; }
    .stApp p, .stApp li, .stApp span, .stApp label, .stApp h1, .stApp h2, .stApp h3,
    .stApp h4, .stApp td, .stApp th, .stApp code, .stApp div[data-testid="stMarkdownContainer"] {
        color: #e8e8e8 !important; }
    section[data-testid="stSidebar"], section[data-testid="stSidebar"] > div {
        background-color: #161a23 !important; }
    div[data-testid="stChatMessage"] { background-color: #1b2130 !important; border-radius: 10px; }
    .stApp pre, .stApp code { background-color: #12161f !important; }
    div[data-testid="stExpander"], div[data-testid="stExpander"] details {
        background-color: #161a23 !important; border-radius: 8px; }
    div[data-testid="stChatInput"], div[data-testid="stChatInput"] > div,
    div[data-testid="stChatInput"] div[data-baseweb="textarea"],
    div[data-testid="stChatInput"] div[data-baseweb="base-input"],
    div[data-testid="stChatInput"] textarea {
        background-color: #1b2130 !important; color: #e8e8e8 !important;
        border-color: #3a4356 !important; }
    div[data-testid="stChatInput"] textarea::placeholder { color: #9aa4b2 !important; }
    section[data-testid="stChatInputContainer"], div[data-testid="stBottom"] > div {
        background-color: #0e1117 !important; }
    .stApp input, .stApp textarea, div[data-baseweb="input"] > div {
        background-color: #1b2130 !important; color: #e8e8e8 !important; }
    div[data-baseweb="select"] > div { background-color: #1b2130 !important; color: #e8e8e8 !important; }
    .stApp button[kind="secondary"], section[data-testid="stSidebar"] button[kind="secondary"],
    div[data-testid="stDownloadButton"] button {
        background-color: #1b2130 !important; color: #e8e8e8 !important;
        border: 1px solid #3a4356 !important; }
    div[role="dialog"], div[role="dialog"] > div { background-color: #161a23 !important; }
    div[role="dialog"] svg, div[data-testid="stDialog"] svg,
    button[title="Close"] svg, button[aria-label="Close"] svg {
        fill: #e8e8e8 !important; stroke: #e8e8e8 !important; color: #e8e8e8 !important; }
    div[role="dialog"] button, div[data-testid="stDialog"] button {
        background-color: transparent !important; }
    """
    light_css = """
    .stApp, div[data-testid="stAppViewContainer"], div[data-testid="stMain"] {
        background-color: #ffffff !important; }
    header[data-testid="stHeader"], div[data-testid="stBottom"],
    div[data-testid="stBottomBlockContainer"] { background-color: #ffffff !important; }
    .stApp p, .stApp li, .stApp span, .stApp label, .stApp h1, .stApp h2, .stApp h3,
    .stApp h4, .stApp td, .stApp th, .stApp div[data-testid="stMarkdownContainer"] {
        color: #1a1a1a !important; }
    section[data-testid="stSidebar"], section[data-testid="stSidebar"] > div {
        background-color: #f4f6f9 !important; }
    div[data-testid="stChatMessage"] { background-color: #f4f6f9 !important; border-radius: 10px; }
    div[data-testid="stChatInput"], div[data-testid="stChatInput"] textarea {
        background-color: #f4f6f9 !important; color: #1a1a1a !important; }
    div[data-baseweb="select"] > div { background-color: #ffffff !important; color: #1a1a1a !important; }
    """
    theme_css = dark_css if ss.dark else light_css
    st.markdown(f"<style>{sidebar_css}{theme_css}</style>", unsafe_allow_html=True)


# ---------- Full-screen preview modal (close with the X) ----------
@st.dialog("📄 Log preview", width="large")
def preview_dialog(name: str, text: str):
    st.markdown(f"**{name}** · {len(text.splitlines())} lines")
    st.download_button("⬇️ Download this log", text, file_name=name)
    st.code(text, language="log")


# ---------- Sidebar ----------
with st.sidebar:
    st.title("🕵️ OpsSherlock")
    st.caption("Multi-agent log analysis · LangGraph + RAG + n8n")
    st.toggle("☀️ Switch to light theme" if ss.dark else "🌙 Switch to dark theme", key="dark")
    st.divider()
    st.subheader("📂 Choose a log to investigate")
    samples = {p.stem.replace("_", " ").title(): p for p in sorted(SAMPLE_DIR.glob("*.log"))}
    choice = st.selectbox("Sample log", list(samples), label_visibility="collapsed")
    log_text = samples[choice].read_text()
    c1, c2 = st.columns(2)
    with c1:
        if st.button("👀 Preview", use_container_width=True):
            preview_dialog(samples[choice].name, log_text)
    with c2:
        do_scan = st.button("🔎 Scan log", type="primary", use_container_width=True)
    st.download_button("⬇️ Download", log_text, file_name=samples[choice].name,
                       use_container_width=True)
    st.divider()
    st.markdown(
        "**Pipeline:** Scan → *you pick an error* → Parser → Classifier → RAG → "
        "Remediation → Checklist → Severity → Summary → n8n (Slack + Jira)"
    )
    slack_ok = bool(os.environ.get("SLACK_WEBHOOK_URL", "").strip() or os.environ.get("N8N_WEBHOOK_URL", "").strip())
    jira_ok = bool(os.environ.get("JIRA_BASE_URL", "").strip() or os.environ.get("N8N_WEBHOOK_URL", "").strip())
    st.markdown(f"**Slack:** {'🟢' if slack_ok else '🔴'} · **Jira:** {'🟢' if jira_ok else '🔴'}")
    invite = os.environ.get("SLACK_INVITE_URL", "").strip()
    if invite:
        st.divider()
        st.markdown(f"[💬 Join **#sherlock-tickets**]({invite}) to watch incident alerts arrive live.")
    if not os.environ.get("OPENROUTER_API_KEY"):
        st.error("Set OPENROUTER_API_KEY in secrets.")

inject_css()

# ---------- Chat history ----------
def ticket_card(t: dict):
    icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(t.get("severity", ""), "⚪")
    with st.container(border=True):
        c1, c2 = st.columns([4, 1])
        with c1:
            st.markdown(f"##### 🎫 {t.get('key')} — {t.get('title')}")
            st.markdown(f"{icon} **{str(t.get('severity', '')).upper()}** · Status: `{t.get('status')}` "
                        f"· *fetched live from Jira*")
        with c2:
            st.link_button("Open in Jira ↗", t.get("url", "#"), use_container_width=True)


for m in ss.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
        if m.get("ticket"):
            ticket_card(m["ticket"])
        if m.get("trail"):
            with st.expander("🕵️ Agent trail — how I solved it", expanded=False):
                st.markdown(m["trail"])


def looks_like_log(text: str) -> bool:
    return len(text) > 80 and bool(
        re.search(r"(ERROR|FATAL|WARN|CRIT|Exception|failed|Failed|\d{4}[-/]\d{2}[-/]\d{2})", text)
        or "\n" in text.strip()
    )


def matching_lines(raw_log: str, evidence: str, error_type: str, limit: int = 5) -> list:
    """Find log lines related to a detected error (by evidence tokens)."""
    tokens = [t for t in re.findall(r"[A-Za-z_\-]{4,}", f"{evidence} {error_type}")
              if t.lower() not in {"error", "with", "from", "that", "this", "type"}][:6]
    hits = []
    for line in raw_log.splitlines():
        if any(t in line for t in tokens):
            hits.append(line)
        if len(hits) >= limit:
            break
    return hits or ([evidence] if evidence else [])


def format_scan_result(label: str, raw_log: str, errors: list) -> str:
    """Bake the full scan result (descriptions + evidence lines) into permanent chat text,
    so it stays visible in history even after the interactive picker below is gone."""
    parts = [f"I found **{len(errors)} error type(s)** in `{label}`:\n"]
    for i, e in enumerate(errors, 1):
        etype = e.get("error_type", f"Error {i}")
        lines = matching_lines(raw_log, e.get("evidence", ""), etype, limit=4)
        parts.append(f"**{i}. {etype}** — {e.get('description', '')}\n```\n" + "\n".join(lines) + "\n```")
    parts.append("👇 Pick one below to solve it.")
    return "\n\n".join(parts)


def do_scan_log(raw_log: str, label: str):
    ss.messages.append({"role": "user", "content": f"Scan **{label}** for errors."})
    with st.chat_message("user"):
        st.markdown(f"Scan **{label}** for errors.")
    with st.chat_message("assistant"):
        with st.spinner("🔎 Scanning log for error types…"):
            try:
                errors = scan_log(raw_log)
            except Exception as e:
                st.error(f"Scan failed: {e}")
                return
        if not errors:
            msg = "I couldn't find distinct error types in this log. Try another file."
            st.markdown(msg)
            ss.messages.append({"role": "assistant", "content": msg})
            return
        body = format_scan_result(label, raw_log, errors)
        st.markdown(body)
        ss.messages.append({"role": "assistant", "content": body})
    ss.pending = {"raw_log": raw_log, "label": label, "errors": errors}
    st.rerun()


def node_detail(node: str, out: dict) -> str:
    """One-line summary of what each agent actually produced."""
    try:
        if node == "parser":
            p = out.get("parsed", {})
            return f"service: `{p.get('service')}` · error: `{str(p.get('error_message'))[:70]}`"
        if node == "classifier":
            return f"issue: `{out.get('issue_type')}` · category: `{out.get('category')}`"
        if node == "retrieve":
            src = out.get("context_source", "")
            if src == "web_search":
                return "🌐 no internal runbook matched — used Tavily web search: " + \
                       ", ".join(f"`{s[:60]}`" for s in out.get("sources", [])[:3])
            if src == "none":
                return "no internal runbook or web results — answering from general expertise"
            return "📚 runbooks used: " + ", ".join(f"`{s}`" for s in set(out.get("sources", [])))
        if node == "remediation":
            return str(out.get("remediation", ""))[:90].replace("\n", " ") + "…"
        if node == "checklist":
            steps = len(re.findall(r"^\s*\d+\.", out.get("checklist", ""), re.M))
            return f"{steps} action steps prepared"
        if node == "severity":
            return f"**{out.get('severity', '?').upper()}** — {out.get('severity_rationale', '')}"
        if node == "summary":
            return "incident report compiled"
        if node == "notify":
            return out.get("n8n_status", "")
    except Exception:
        pass
    return ""


def run_pipeline(raw_log: str, focus_error: str):
    ss.pending = None
    ss.messages.append({"role": "user", "content": f"Solve: **{focus_error}**"})
    with st.chat_message("user"):
        st.markdown(f"Solve: **{focus_error}**")

    trail = []
    with st.chat_message("assistant"):
        state = {"raw_log": raw_log, "focus_error": focus_error,
                 "requester_email": ss.get("requester_email", "").strip()}
        with st.status("🤖 Agents are working…", expanded=True) as status:
            try:
                for i, update in enumerate(graph().stream(state, stream_mode="updates"), 1):
                    for node, out in update.items():
                        label = NODE_LABELS.get(node, node)
                        detail = node_detail(node, out or {})
                        st.markdown(f"**Agent {i} — {label}**")
                        if detail:
                            st.caption(detail)
                        trail.append(f"**Agent {i} — {label}**" + (f"  \n  ↳ {detail}" if detail else ""))
                        if out:
                            state.update(out)
                # collapse the working log once done — details live in the Agent trail expander
                status.update(label=f"✅ Analysis complete — {len(trail)} agents ran",
                              state="complete", expanded=False)
            except Exception as e:
                status.update(label="❌ Pipeline failed", state="error")
                st.error(f"Error: {e}")
                return
        report = state.get("report", "No report generated.")
        st.markdown(report)
        with st.expander("🕵️ Agent trail — how I solved it", expanded=False):
            st.markdown("\n\n".join(trail))
        st.info("✋ Nothing sent yet — review & approve below to create the Jira ticket "
                "and notify Slack/email.")

    ss.incident = state
    ss.awaiting = state
    ss.messages.append({"role": "assistant", "content": report,
                        "trail": "\n\n".join(trail)})


GREETING_RE = re.compile(r"^\s*(hi+|hello+|hey+|yo|hola|namaste|good\s*(morning|afternoon|evening))[\s!.,]*$", re.I)


def answer_followup(question: str):
    ss.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    # Instant reply for greetings/small talk — no LLM call needed
    if GREETING_RE.match(question):
        answer = ("Hey! 👋 I'm **OpsSherlock**, your incident detective. Here's how I work: "
                  "pick a sample log from the sidebar (or paste your own log here), hit "
                  "**Scan**, and I'll show you the error types inside. Choose one and my "
                  "agent team will find the root cause, severity, and fix — then notify "
                  "Slack + Jira. You can also just ask me DevOps questions directly!")
        with st.chat_message("assistant"):
            st.markdown(answer)
        ss.messages.append({"role": "assistant", "content": answer})
        return

    incident = ss.incident
    if incident:
        system = (
            "You are OpsSherlock, a DevOps incident assistant. Answer using this incident "
            f"analysis:\n\nREPORT:\n{incident.get('report', '')}\n\n"
            f"RUNBOOK CONTEXT:\n{incident.get('context', '')[:3000]}\n\nBe concise and practical."
        )
    else:
        system = (
            "You are OpsSherlock, a DevOps incident assistant. No log analyzed yet. Answer "
            "general DevOps questions concisely; remind the user to pick a sample log or paste one."
        )
    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            try:
                answer = get_llm(temperature=0.3).invoke([("system", system), ("user", question)]).content
            except Exception as e:
                answer = f"⚠️ I couldn't reach the model: `{e}`. Check the OPENROUTER_API_KEY and MODEL settings."
        st.markdown(answer)
    ss.messages.append({"role": "assistant", "content": answer})


# ---------- Human-in-the-loop: review & approve before anything is sent ----------
if ss.awaiting:
    st.markdown("### ✋ Review before sending — edit anything, then approve")
    p = dict(ss.awaiting.get("payload", {}))
    sev_options = ["critical", "high", "medium", "low"]
    with st.container(border=True):
        p["title"] = st.text_input("Jira ticket title", value=p.get("title", ""))
        p["severity"] = st.selectbox(
            "Severity", sev_options,
            index=sev_options.index(p["severity"]) if p.get("severity") in sev_options else 2)
        p["remediation"] = st.text_area("Root cause & fix", value=p.get("remediation", ""), height=180)
        p["checklist"] = st.text_area("Action checklist", value=p.get("checklist", ""), height=140)
        review_email = st.text_input("📧 Email the ticket to (optional)",
                                     value=ss.get("requester_email", "").strip(),
                                     help="We'll email the full incident report and ticket link "
                                          "to this address once it's created.")
        c1, c2 = st.columns(2)
        approve = c1.button("✅ Approve & send (Jira + Slack + Email)",
                            type="primary", use_container_width=True)
        skip = c2.button("❌ Skip notifications", use_container_width=True)

    if approve:
        state = ss.awaiting
        state["payload"] = p
        state["requester_email"] = review_email.strip()
        with st.spinner("📨 Creating Jira ticket and notifying…"):
            out = notify_agent(state)
        state.update(out)
        ss.incident = state
        ss.awaiting = None
        ss.messages.append({"role": "assistant",
                            "content": f"**Approved & sent.**\n\n> {out.get('n8n_status', '')}",
                            "ticket": out.get("jira_ticket")})
        st.rerun()
    if skip:
        ss.awaiting = None
        ss.messages.append({"role": "assistant",
                            "content": "Okay — notifications skipped. The report stays here in the chat."})
        st.rerun()

# ---------- Pending error choice: details are already in the chat message above; just pick ----------
if ss.pending:
    st.markdown("**Choose which error to solve** (details above 👆):")
    cols = st.columns(min(len(ss.pending["errors"]), 3))
    for i, e in enumerate(ss.pending["errors"]):
        etype = e.get("error_type", f"Error {i+1}")
        with cols[i % len(cols)]:
            if st.button(f"🚀 {etype}", key=f"solve_{i}", type="primary", use_container_width=True):
                run_pipeline(ss.pending["raw_log"], etype)
                st.rerun()

# ---------- Inputs ----------
if do_scan:
    do_scan_log(log_text, choice)

if prompt := st.chat_input("Paste a log to scan, or ask a question…"):
    if looks_like_log(prompt):
        do_scan_log(prompt, "pasted log")
    else:
        answer_followup(prompt)
