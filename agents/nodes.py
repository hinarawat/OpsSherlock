"""LangGraph agent nodes: parser, classifier, RAG retrieve, remediation, checklist, severity, summary, notify."""
import json
import os
import re
from typing import TypedDict

import requests
from langchain_openai import ChatOpenAI


# ---------- LLM (OpenRouter, OpenAI-compatible) ----------
def get_llm(temperature: float = 0):
    return ChatOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ.get("OPENROUTER_API_KEY", ""),
        model=os.environ.get("MODEL", "anthropic/claude-haiku-4.5"),
        temperature=temperature,
    )


def _extract_json(text: str) -> dict:
    """Pull the first JSON object out of an LLM response."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return {}


def _ask(system: str, user: str) -> str:
    resp = get_llm().invoke([("system", system), ("user", user)])
    return resp.content


# ---------- Log scanner (pre-pipeline) ----------
def scan_log(raw_log: str) -> list:
    """Scan a log file and list the distinct error types found."""
    out = _ask(
        "You are a log scanner. Identify the DISTINCT error/issue types in this log "
        "(collapse repeats of the same root error into one entry). Respond with ONLY a "
        'JSON object: {"errors": [{"error_type": str (short human-readable name), '
        '"description": str (one sentence), "evidence": str (one representative log line)}]}. '
        "Max 10 entries.",
        raw_log[:8000],
    )
    data = _extract_json(out)
    return data.get("errors", [])


# ---------- Shared state ----------
class IncidentState(TypedDict, total=False):
    raw_log: str
    focus_error: str       # the error type the user chose to solve
    slack_webhook: str     # optional user-provided Slack incoming webhook (hidden BYO feature)
    jira: dict             # optional user-provided {base_url, email, api_token, project_key} (hidden BYO)
    requester_email: str   # judge/user email -> Jira watcher + n8n emails them the ticket
    jira_ticket: dict      # {key, url, title, severity} fetched back after creation (UI card)
    parsed: dict           # service, error_type, error_message, timestamp
    issue_type: str
    category: str
    context: str           # retrieved runbook chunks OR web search results
    sources: list
    context_source: str    # "knowledge_base" | "web_search" | "none"
    remediation: str
    checklist: str
    severity: str
    severity_rationale: str
    report: str            # final markdown report
    payload: dict          # JSON sent to n8n
    n8n_status: str


# ---------- Agents ----------
def parser_agent(state: IncidentState) -> IncidentState:
    focus = state.get("focus_error", "")
    focus_note = f" Focus ONLY on this error type: '{focus}'. Ignore unrelated errors." if focus else ""
    out = _ask(
        "You are a log parser. Extract structured fields from the raw log."
        + focus_note +
        ' Respond with ONLY a JSON object: {"service": str, "error_type": str, '
        '"error_message": str, "timestamp": str}. Use "unknown" if a field is missing.',
        state["raw_log"][:6000],
    )
    return {"parsed": _extract_json(out)}


def classifier_agent(state: IncidentState) -> IncidentState:
    out = _ask(
        "You are an incident classifier. Given parsed log fields, detect the issue. "
        'Respond with ONLY JSON: {"issue_type": str (short snake_case id, e.g. "k8s_oom_killed"), '
        '"category": str (one of: infrastructure, application, database, network, security, capacity)}.',
        json.dumps(state.get("parsed", {})),
    )
    data = _extract_json(out)
    return {
        "issue_type": data.get("issue_type", "unknown"),
        "category": data.get("category", "unknown"),
    }


def _tavily_search(query: str, max_results: int = 4) -> list:
    """Web search fallback via Tavily. Returns [{title, url, content}]."""
    key = os.environ.get("TAVILY_API_KEY", "").strip()
    if not key:
        return []
    r = requests.post("https://api.tavily.com/search",
                      json={"api_key": key, "query": query, "max_results": max_results,
                            "search_depth": "basic"},
                      timeout=20)
    r.raise_for_status()
    return r.json().get("results", [])


def retrieve_node(state: IncidentState) -> IncidentState:
    from agents.rag import search

    parsed = state.get("parsed", {})
    query = f"{parsed.get('service', '')} {state.get('issue_type', '')} {parsed.get('error_message', '')}"

    # 1) Internal knowledge base (RAG) first
    docs = search(query, k=3, min_score=0.3)
    if docs:
        context = "\n\n---\n\n".join(d.page_content for d in docs)
        sources = [d.metadata.get("source", "runbook") for d in docs]
        return {"context": context, "sources": sources, "context_source": "knowledge_base"}

    # 2) Unknown topic -> Tavily web search fallback
    try:
        results = _tavily_search(f"{query} root cause fix site:stackoverflow.com OR site:github.com OR devops")
        if not results:  # retry without site hints
            results = _tavily_search(f"{query} root cause fix")
    except Exception:
        results = []
    if results:
        context = "\n\n---\n\n".join(
            f"[Web: {r.get('title', '')}]({r.get('url', '')})\n{r.get('content', '')}" for r in results)
        sources = [r.get("url", "web") for r in results]
        return {"context": context, "sources": sources, "context_source": "web_search"}

    return {"context": "No matching internal runbook found, and web search unavailable. "
                       "Answer from general expertise and say so explicitly.",
            "sources": [], "context_source": "none"}


def remediation_agent(state: IncidentState) -> IncidentState:
    src = state.get("context_source", "knowledge_base")
    src_note = {
        "knowledge_base": "The context below comes from our INTERNAL RUNBOOKS. Cite which runbook you used.",
        "web_search": "No internal runbook matched, so the context below comes from WEB SEARCH results. "
                      "Cite the source URLs you used and note this came from the web.",
        "none": "No internal runbook or web results were found. Answer from general expertise and say so.",
    }.get(src, "")
    out = _ask(
        "You are an SRE remediation expert. Using ONLY the context provided, give the "
        "root cause and a recommended fix with rationale. " + src_note +
        " If context is not relevant, say so and give your best general fix. "
        "Be concise (under 200 words). Markdown.",
        f"ISSUE: {json.dumps(state.get('parsed', {}))}\n"
        f"TYPE: {state.get('issue_type')}\n\nCONTEXT:\n{state.get('context', '')}",
    )
    return {"remediation": out}


def checklist_agent(state: IncidentState) -> IncidentState:
    out = _ask(
        "Turn this remediation into a short numbered action checklist (max 6 steps), "
        "each step one line, with a verification step at the end. Markdown numbered list only.",
        state.get("remediation", ""),
    )
    return {"checklist": out}


def severity_agent(state: IncidentState) -> IncidentState:
    out = _ask(
        "You are a severity assessor. Rate this incident. "
        'Respond with ONLY JSON: {"severity": "critical"|"high"|"medium"|"low", '
        '"rationale": str (one sentence: user impact + blast radius)}.',
        f"ISSUE: {json.dumps(state.get('parsed', {}))}\nTYPE: {state.get('issue_type')}",
    )
    data = _extract_json(out)
    return {
        "severity": data.get("severity", "medium"),
        "severity_rationale": data.get("rationale", ""),
    }


def summary_agent(state: IncidentState) -> IncidentState:
    parsed = state.get("parsed", {})
    sev = state.get("severity", "medium")
    icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(sev, "⚪")
    report = (
        f"## {icon} Incident Report — `{state.get('issue_type', 'unknown')}`\n\n"
        f"| | |\n|---|---|\n"
        f"| **Service** | {parsed.get('service', 'unknown')} |\n"
        f"| **Category** | {state.get('category', 'unknown')} |\n"
        f"| **Severity** | {sev.upper()} — {state.get('severity_rationale', '')} |\n"
        f"| **Error** | `{parsed.get('error_message', 'unknown')[:120]}` |\n\n"
        f"### Root Cause & Fix\n{state.get('remediation', '')}\n\n"
        f"### Action Checklist\n{state.get('checklist', '')}\n\n"
        f"*Sources: {', '.join(set(state.get('sources', []))) or 'none'}*"
    )
    payload = {
        "title": f"[{sev.upper()}] {state.get('issue_type')} on {parsed.get('service', 'unknown')}",
        "service": parsed.get("service"),
        "category": state.get("category"),
        "severity": sev,
        "severity_rationale": state.get("severity_rationale"),
        "error_message": parsed.get("error_message"),
        "remediation": state.get("remediation"),
        "checklist": state.get("checklist"),
        "sources": list(set(state.get("sources", []))),
    }
    return {"report": report, "payload": payload}


def _slack_direct(webhook: str, p: dict) -> str:
    icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(p.get("severity", ""), "⚪")
    text = (f"{icon} *{p.get('title')}*\n"
            f"*Severity:* {str(p.get('severity', '')).upper()} — {p.get('severity_rationale', '')}\n"
            f"*Error:* `{str(p.get('error_message', ''))[:150]}`\n\n"
            f"*Fix:*\n{str(p.get('remediation', ''))[:1500]}\n\n"
            f"*Checklist:*\n{str(p.get('checklist', ''))[:1000]}")
    r = requests.post(webhook, json={"text": text}, timeout=15)
    r.raise_for_status()
    return "💬 Slack message sent (direct webhook)."


def _jira_fetch(cfg: dict, key: str, fallback_title: str = "", fallback_severity: str = "") -> dict:
    """READ-ONLY: fetch an already-created ticket back from Jira to render the UI card.
    This never creates or modifies anything in Jira — creation happens in n8n's Jira node."""
    base = cfg["base_url"].rstrip("/")
    auth = (cfg["email"], cfg["api_token"])
    url = f"{base}/browse/{key}"
    ticket = {"key": key, "url": url, "title": fallback_title, "severity": fallback_severity, "status": "?"}
    g = requests.get(f"{base}/rest/api/3/issue/{key}",
                     params={"fields": "status,summary,created"}, auth=auth, timeout=15)
    if g.status_code >= 400:
        raise RuntimeError(f"Jira {g.status_code}: {g.text[:300]}")
    f = g.json().get("fields", {})
    ticket["status"] = f.get("status", {}).get("name", "?")
    ticket["title"] = f.get("summary", ticket["title"])
    ticket["created"] = f.get("created", "")
    return ticket


def _owner_jira_cfg():
    """Only base_url/email/api_token are required now — the app only ever reads (fetches a
    ticket for display), never creates. project_key is unused here (creation lives in n8n)."""
    cfg = {
        "base_url": os.environ.get("JIRA_BASE_URL", "").strip(),
        "email": os.environ.get("JIRA_EMAIL", "").strip(),
        "api_token": os.environ.get("JIRA_API_TOKEN", "").strip(),
    }
    return cfg if all(cfg.values()) else None


def notify_agent(state: IncidentState) -> IncidentState:
    """Step 1: create Jira ticket via direct API (so we can show a live ticket card).
    Step 2: POST everything (incl. ticket link + requester email) to n8n, which
    fans out to Slack (#sherlock-tickets) and emails the requester the full ticket."""
    p = dict(state.get("payload", {}))
    requester = str(state.get("requester_email", "")).strip()
    p["requester_email"] = requester
    results = []
    ticket = None
    jira_key = None

    # --- Step 1: n8n owns CREATION. Its workflow: Webhook -> Jira (create) -> Slack -> IF -> Gmail
    #     -> Respond to Webhook with {"jira_key": "...", "jira_url": "..."}. The app never calls
    #     Jira's create-issue endpoint — that lives entirely in n8n now, so there's exactly one
    #     place a ticket gets created (no more duplicates from app + n8n both creating). ---
    n8n_url = os.environ.get("N8N_WEBHOOK_URL", "").strip()
    if n8n_url:
        try:
            r = requests.post(n8n_url, json=p, timeout=25)
            r.raise_for_status()
            resp = {}
            try:
                resp = r.json()
            except ValueError:
                pass
            # Accept a few common field-naming conventions from the "Respond to Webhook" node
            jira_key = resp.get("jira_key") or resp.get("ticket_key") or resp.get("key")
            jira_url_hint = resp.get("jira_url") or resp.get("ticket_url")
            note = "📨 n8n → Slack notified"
            if requester:
                note += f" + ticket emailed to {requester}"
            if jira_key:
                note += f" · 🎫 Jira ticket {jira_key} created (via n8n)"
            else:
                note += " · ℹ️ n8n didn't return a Jira key — check its 'Respond to Webhook' node"
            results.append(note + ".")
        except Exception as e:
            results.append(f"⚠️ n8n delivery failed: {e}")
    else:
        # fallback: direct Slack webhook if configured (no n8n at all)
        slack_hook = state.get("slack_webhook") or os.environ.get("SLACK_WEBHOOK_URL", "").strip()
        if slack_hook:
            try:
                results.append(_slack_direct(slack_hook, p))
            except Exception as e:
                results.append(f"⚠️ Slack failed: {e}")

    # --- Step 2: read-only fetch to render the live ticket card (never creates anything) ---
    if jira_key:
        byo_jira = state.get("jira") or {}
        jira_cfg = byo_jira if all(byo_jira.get(k) for k in ("base_url", "email", "api_token")) \
            else _owner_jira_cfg()
        if jira_cfg:
            try:
                ticket = _jira_fetch(jira_cfg, jira_key, p.get("title", ""), p.get("severity", ""))
            except Exception as e:
                results.append(f"⚠️ Couldn't fetch ticket details: {e}")
        # Fall back to a minimal card from n8n's own response if the read failed or no
        # read creds are configured — n8n already told us the key and (usually) the URL.
        if not ticket:
            ticket = {"key": jira_key, "url": jira_url_hint or "#",
                     "title": p.get("title", ""), "severity": p.get("severity", ""), "status": "?"}

    if not results:
        return {"n8n_status": "No integration configured — set N8N_WEBHOOK_URL in secrets."}
    out = {"n8n_status": " · ".join(results)}
    if ticket:
        out["jira_ticket"] = ticket
    return out
