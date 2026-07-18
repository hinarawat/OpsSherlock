# 🕵️ OpsSherlock — Multi-Agent DevOps Incident Analysis

**🔗 Live demo:** _add your Streamlit Cloud URL here after deploying_ · **Built with:** LangGraph · LangChain RAG (FAISS + MiniLM) · Tavily · Streamlit · OpenRouter · n8n

> *"When ops go wrong, the game is afoot."* Paste an ops log; a team of AI agents scans it for distinct errors, lets you pick which to investigate, finds the root cause and fix, assesses severity — then, after your review and approval, files a Jira ticket and notifies Slack + email.

**Pipeline:** Scan (list error types) → *you choose one* → Parser → Classifier → RAG (internal runbooks) *or* Tavily web search if nothing matches → Remediation → Checklist → Severity → Summary → **human review & edit** → **you approve** → Jira (direct API) + n8n (Slack + email).

## Quickstart (clone & run — no Docker needed)

```bash
git clone https://github.com/YOUR_USERNAME/OpsSherlock.git
cd OpsSherlock
pip install -r requirements.txt
cp .streamlit/secrets.example.toml .streamlit/secrets.toml
# edit .streamlit/secrets.toml -> add your OPENROUTER_API_KEY (the only required key)
streamlit run app.py
```

Requires Python 3.10+. First run downloads the embedding model (~90MB, one time).
Without the optional keys the app still works — it scans and analyzes logs and shows
reports; Jira/Slack/email/Tavily steps are simply skipped with a clear status message.

## Deploy to Streamlit Community Cloud

1. Push this repo to GitHub (keep `.streamlit/secrets.toml` out of it — it's already git-ignored).
2. Go to https://share.streamlit.io → **New app** → pick the repo, branch `main`, file `app.py`.
3. In **Advanced settings → Secrets**, paste the contents of your local `secrets.toml` (see below for the full list of keys).
4. Deploy. First boot takes a few minutes (installs deps + embedding model).

## How it works

1. **Scan** — pick a sample log or paste your own. The scanner agent lists the distinct error types found (deduped, with the exact log lines for each) so you can choose which one to investigate.
2. **Analyze** — a chain of specialist agents (parser, classifier, retriever, remediation, checklist, severity, summary) runs on just that error. If an internal runbook matches, it's used and cited; if not, the agent falls back to a live **Tavily** web search and cites those sources instead.
3. **Review & approve** — nothing is sent anywhere yet. You see the full report and an editable card (title, severity, fix, checklist, notification email) and can change anything before deciding.
4. **Send** — on approval, the app creates a **Jira** ticket directly via the Jira API (then fetches it back and shows a live ticket card with a link), and POSTs the incident to an **n8n** webhook which posts to Slack and emails whoever you specified.

### Secrets — create your own `secrets.toml`, don't reuse anyone else's

The repo never includes a real `secrets.toml` (it's git-ignored on purpose — see `.gitignore`). Every person running this app creates their **own** copy with their **own** keys:

```bash
cp .streamlit/secrets.example.toml .streamlit/secrets.toml
```

Then fill in `.streamlit/secrets.toml`:

```toml
OPENROUTER_API_KEY = "sk-or-..."        # required
MODEL = "anthropic/claude-haiku-4.5"    # optional, any OpenRouter model

TAVILY_API_KEY = ""                     # optional — web search fallback (app.tavily.com)

JIRA_BASE_URL = ""                      # optional — https://yoursite.atlassian.net
JIRA_EMAIL = ""
JIRA_API_TOKEN = ""                     # id.atlassian.com -> Security -> API tokens
JIRA_PROJECT_KEY = ""                   # e.g. OPS (check your project's ticket prefix)

N8N_WEBHOOK_URL = ""                    # optional — Slack + email fan-out
SLACK_INVITE_URL = ""                   # optional — shown in the sidebar
```

Only `OPENROUTER_API_KEY` is required to run log analysis end-to-end. Everything below it is optional and only enables its own piece of the notification chain — the app works fine with any of them left blank; it just skips that step with a clear status message.

**Important — the notification keys are not shareable.** `N8N_WEBHOOK_URL`, `JIRA_*`, and Slack all point at one specific person's accounts:

- `N8N_WEBHOOK_URL` only works if there's an **active n8n workflow behind it**, and that workflow holds its own Slack and Gmail *credentials* (OAuth connections made inside n8n, not in this repo). Reusing someone else's webhook URL — even if you had it — would just post to *their* Slack channel and send from *their* Gmail, not yours.
- `JIRA_*` uses one person's Atlassian account and API token — tickets always land in *that* person's Jira project.

So: if you only want to analyze logs, set `OPENROUTER_API_KEY` and stop there. If you want the full Jira/Slack/email chain, you need to set up your **own** n8n workflow (see below), your own Jira project + API token, and your own Slack channel — then put those in your own `secrets.toml`.

### n8n workflow (Slack + email fan-out)

n8n only handles Slack and email — Jira ticket creation happens directly from the app (so the live ticket card can render without depending on n8n).

1. **Webhook node** — POST. Payload includes `title`, `severity`, `severity_rationale`, `error_message`, `remediation`, `checklist`, `jira_key`, `jira_url`, `requester_email`.
2. **Slack node** — post to your incident channel using `{{ $json.body.title }}`, `{{ $json.body.severity }}`, `{{ $json.body.jira_url }}`, etc.
3. **IF node** — condition: `{{ $json.body.requester_email }}` is not empty.
4. **Gmail node** (true branch) — To: `{{ $json.body.requester_email }}`, subject `{{ $json.body.title }}`, body with remediation + checklist + Jira link.
5. **Activate** the workflow and use the `/webhook/` (production) URL, not `/webhook-test/`.

### What a reviewer actually gets (no false promises)

- **Slack:** join the invite link in the sidebar → see incident alerts arrive live in the channel. Fully self-serve.
- **Email:** enter an email in the review step before approving → n8n emails the full report + ticket link. Fully automatic, if the n8n Gmail node is wired.
- **Jira dashboard access:** *not* self-serve — Jira has no public "view by email" mechanism. The app will add the email as a ticket **watcher** only if that email already belongs to a member of the Jira site; otherwise it's silently skipped (no invite is sent automatically). The **live ticket card in the app** is how anyone sees proof the ticket was created, without needing Jira access at all.

## Data sources

See [`DATA_SOURCES.md`](./DATA_SOURCES.md) for exactly where every sample log and knowledge-base runbook came from (mix of real datasets — Loghub, Scoutflo SRE Playbooks — and authored content).

## Project structure

```
app.py                     # Streamlit chat UI (scan -> pick error -> review -> approve)
agents/graph.py            # LangGraph orchestrator (stops before notify for human review)
agents/nodes.py            # scanner + 7 pipeline agents + Jira/Slack notify logic
agents/rag.py              # LangChain FAISS retriever over runbooks (relevance-thresholded)
knowledge_base/*.md        # runbooks (RAG corpus) — real SRE playbooks + authored
sample_logs/*.log          # demo logs across 7 topics — some real, some crafted
.streamlit/secrets.example.toml   # copy to secrets.toml and fill in
DATA_SOURCES.md            # provenance table for every log & runbook
```

## Demo script (3 min)

1. Pick a sample log (e.g. **K8s Oom Killed**) → **Scan** → see the distinct errors found with their exact log lines → pick one → watch the agents run live in the trail.
2. Review the generated report, edit something in the review card, **Approve & send** → watch the Jira ticket card appear and the Slack message land.
3. Paste an error type not in the knowledge base (e.g. an obscure Elasticsearch or Kafka error) → scan → solve → the agent trail shows it fell back to **Tavily web search** instead of the internal runbooks.
4. Ask a follow-up question after any report — the agent answers using that incident's context.
