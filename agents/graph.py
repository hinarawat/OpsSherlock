"""LangGraph orchestrator: parser -> classifier -> RAG -> remediation -> checklist -> severity -> summary -> notify."""
from langgraph.graph import StateGraph, START, END

from agents.nodes import (
    IncidentState,
    parser_agent,
    classifier_agent,
    retrieve_node,
    remediation_agent,
    checklist_agent,
    severity_agent,
    summary_agent,
    notify_agent,
)

NODE_LABELS = {
    "parser": "Parser Agent — extracted structured fields",
    "classifier": "Classifier Agent — detected issue type",
    "retrieve": "RAG Retriever — fetched relevant runbooks",
    "remediation": "Remediation Agent — mapped root cause & fix",
    "checklist": "Checklist Agent — built action checklist",
    "severity": "Severity Agent — assessed severity",
    "summary": "Summary Agent — compiled incident report",
    "notify": "Notification — n8n → Slack + Jira",
}


def build_graph(include_notify: bool = True):
    """include_notify=False stops after the summary so a human can review/edit
    the incident before notifications are sent (human-in-the-loop)."""
    g = StateGraph(IncidentState)
    g.add_node("parser", parser_agent)
    g.add_node("classifier", classifier_agent)
    g.add_node("retrieve", retrieve_node)
    g.add_node("remediation", remediation_agent)
    g.add_node("checklist", checklist_agent)
    g.add_node("severity", severity_agent)
    g.add_node("summary", summary_agent)

    g.add_edge(START, "parser")
    g.add_edge("parser", "classifier")
    g.add_edge("classifier", "retrieve")
    g.add_edge("retrieve", "remediation")
    g.add_edge("remediation", "checklist")
    g.add_edge("checklist", "severity")
    g.add_edge("severity", "summary")
    if include_notify:
        g.add_node("notify", notify_agent)
        g.add_edge("summary", "notify")
        g.add_edge("notify", END)
    else:
        g.add_edge("summary", END)
    return g.compile()
