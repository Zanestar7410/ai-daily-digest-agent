from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from ai_news_digest.research_mode import run_research_mode
from ai_news_digest.storage import DigestStorage


def _single(values: dict[str, list[str]], key: str) -> str | None:
    items = values.get(key)
    if not items:
        return None
    return items[0]


def _limit(values: dict[str, list[str]], default: int = 20) -> int:
    raw = _single(values, "limit")
    if raw is None:
        return default
    return int(raw)


def render_dashboard_html() -> str:
    return """\
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AI Event Explorer</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f3f0e8;
      --panel: #fffdf8;
      --line: #d5cec2;
      --text: #1f1d1a;
      --muted: #6b655d;
      --accent: #114d4d;
    }
    body { margin: 0; font-family: Georgia, "Times New Roman", serif; background: linear-gradient(180deg, #f8f3e8, #ebe3d3); color: var(--text); }
    main { max-width: 1200px; margin: 0 auto; padding: 32px 20px 60px; }
    h1, h2 { margin: 0 0 12px; }
    .grid { display: grid; grid-template-columns: 2fr 1fr; gap: 20px; }
    .panel { background: var(--panel); border: 1px solid var(--line); border-radius: 18px; padding: 18px; box-shadow: 0 14px 40px rgba(17, 77, 77, 0.08); }
    .stack { display: grid; gap: 16px; }
    label { display: block; font-size: 13px; color: var(--muted); margin-bottom: 6px; }
    input, select, button { width: 100%; padding: 10px 12px; border-radius: 12px; border: 1px solid var(--line); font: inherit; box-sizing: border-box; }
    button { background: var(--accent); color: white; cursor: pointer; }
    ul { list-style: none; padding: 0; margin: 0; display: grid; gap: 10px; }
    li { padding: 12px; border: 1px solid var(--line); border-radius: 12px; background: white; }
    .muted { color: var(--muted); font-size: 14px; }
    @media (max-width: 900px) { .grid { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <main>
    <div class="stack">
      <section class="panel">
        <h1>AI Event Explorer</h1>
        <p class="muted">Browse persisted event records, inspect entity and topic aggregates, and open event details without leaving the local workspace.</p>
      </section>
      <div class="grid">
        <section class="panel">
          <h2>Event Search</h2>
          <div class="stack">
            <div>
              <label for="query">Query</label>
              <input id="query" value="agent">
            </div>
            <div>
              <label for="entity">Entity</label>
              <input id="entity" value="OpenAI">
            </div>
            <div>
              <label for="sort">Sort</label>
              <select id="sort">
                <option value="published_at">Published At</option>
                <option value="confidence">Confidence</option>
              </select>
            </div>
            <button id="search">Search Events</button>
            <ul id="results"></ul>
          </div>
        </section>
        <section class="stack">
          <section class="panel">
            <h2>Run Research</h2>
            <div class="stack">
              <div>
                <label for="research-query">Research Query</label>
                <input id="research-query" value="最近两周 OpenAI agent 相关变化">
              </div>
              <button id="run-research">Run Research</button>
            </div>
          </section>
          <section class="panel">
            <h2>Entity Timeline</h2>
            <ul id="entities"></ul>
          </section>
          <section class="panel">
            <h2>Topics</h2>
            <ul id="topics"></ul>
          </section>
          <section class="panel">
            <h2>Research Reports</h2>
            <ul id="research-reports"></ul>
          </section>
          <section class="panel">
            <h2>Event Detail</h2>
            <div id="detail" class="muted">Select an event from search results to inspect its structured detail.</div>
          </section>
        </section>
      </div>
    </div>
  </main>
  <script>
    async function loadList(path, targetId, formatter) {
      const response = await fetch(path);
      const payload = await response.json();
      const target = document.getElementById(targetId);
      target.innerHTML = "";
      for (const item of payload.items) {
        const node = document.createElement("li");
        node.innerHTML = formatter(item);
        target.appendChild(node);
      }
    }

    async function loadEvents() {
      const query = encodeURIComponent(document.getElementById("query").value);
      const entity = encodeURIComponent(document.getElementById("entity").value);
      const sort = encodeURIComponent(document.getElementById("sort").value);
      const response = await fetch(`/events?query=${query}&entity=${entity}&sort_by=${sort}&limit=10`);
      const payload = await response.json();
      const target = document.getElementById("results");
      target.innerHTML = "";
      for (const item of payload.items) {
        const node = document.createElement("li");
        node.innerHTML = `<strong>${item.title}</strong><div class="muted">${item.source_name} · ${item.published_at}</div>`;
        node.addEventListener("click", () => loadEventDetail(item.event_id));
        target.appendChild(node);
      }
    }

    async function loadEventDetail(eventId) {
      const response = await fetch(`/events/detail?event_id=${encodeURIComponent(eventId)}`);
      const payload = await response.json();
      const item = payload.item;
      document.getElementById("detail").innerHTML = `
        <strong>${item.title}</strong>
        <div class="muted">${item.source_name} · ${item.published_at}</div>
        <p>${item.summary}</p>
        <p><strong>Why It Matters:</strong> ${item.why_it_matters || "n/a"}</p>
        <p><strong>Confidence:</strong> ${item.confidence}</p>
      `;
    }

    async function runResearch() {
      const query = encodeURIComponent(document.getElementById("research-query").value);
      const response = await fetch(`/research/run?query=${query}&limit=8`);
      const payload = await response.json();
      const item = payload.item;
      document.getElementById("detail").innerHTML = `
        <strong>${item.query}</strong>
        <div class="muted">${item.generated_at}</div>
        <p>${item.executive_summary}</p>
        <p><strong>Key Findings:</strong> ${(item.key_findings || []).join(" | ")}</p>
        <p><strong>Evidence:</strong> ${(item.evidence_highlights || []).join(" | ")}</p>
        <p><strong>Verification:</strong> ${(item.verification_notes || []).join(" | ")}</p>
      `;
      await loadResearchReports();
    }

    async function loadResearchReports() {
      const response = await fetch("/research/reports?limit=8");
      const payload = await response.json();
      const target = document.getElementById("research-reports");
      target.innerHTML = "";
      for (const report of payload.items) {
        const node = document.createElement("li");
        node.innerHTML = `<strong>${report.query}</strong><div class="muted">${report.generated_at}</div>`;
        node.addEventListener("click", () => loadResearchReport(report.id));
        target.appendChild(node);
      }
    }

    async function loadResearchReport(reportId) {
      const response = await fetch(`/research/report?report_id=${reportId}`);
      const payload = await response.json();
      const item = payload.item;
      document.getElementById("detail").innerHTML = `
        <strong>${item.query}</strong>
        <div class="muted">${item.generated_at}</div>
        <p>${item.executive_summary}</p>
        <p><strong>Key Findings:</strong> ${(item.key_findings || []).join(" | ")}</p>
        <p><strong>Evidence:</strong> ${(item.evidence_highlights || []).join(" | ")}</p>
        <p><strong>Verification:</strong> ${(item.verification_notes || []).join(" | ")}</p>
      `;
    }

    document.getElementById("search").addEventListener("click", loadEvents);
    document.getElementById("run-research").addEventListener("click", runResearch);
    loadList("/entities?limit=8", "entities", (item) => `<strong>${item.name}</strong><div class="muted">${item.count} mentions</div>`);
    loadList("/topics?limit=8", "topics", (item) => `<strong>${item.name}</strong><div class="muted">${item.count} mentions</div>`);
    loadResearchReports();
    loadEvents();
  </script>
</body>
</html>
"""


def build_api_response(
    *,
    storage: DigestStorage,
    method: str,
    raw_path: str,
) -> tuple[int, dict]:
    if method != "GET":
        return 405, {"error": "method_not_allowed"}

    parsed = urlsplit(raw_path)
    params = parse_qs(parsed.query)
    path = parsed.path

    if path == "/health":
        return 200, {"status": "ok"}

    if path == "/events":
        events = storage.search_events(
            query=_single(params, "query") or "",
            topic=_single(params, "topic"),
            source=_single(params, "source"),
            entity=_single(params, "entity"),
            event_type=_single(params, "event_type"),
            date_from=_single(params, "date_from"),
            date_to=_single(params, "date_to"),
            sort_by=_single(params, "sort_by") or "published_at",
            limit=_limit(params),
        )
        return 200, {
            "count": len(events),
            "items": [event.model_dump(mode="json") for event in events],
        }

    if path == "/events/detail":
        event_id = _single(params, "event_id")
        if event_id is None:
            return 400, {"error": "missing_event_id"}
        event = storage.get_event(event_id=event_id)
        if event is None:
            return 404, {"error": "not_found"}
        return 200, {"item": event.model_dump(mode="json")}

    if path == "/research/reports":
        reports = storage.list_research_reports(limit=_limit(params))
        return 200, {
            "count": len(reports),
            "items": reports,
        }

    if path == "/research/report":
        raw_report_id = _single(params, "report_id")
        if raw_report_id is None:
            return 400, {"error": "missing_report_id"}
        report = storage.get_research_report(report_id=int(raw_report_id))
        if report is None:
            return 404, {"error": "not_found"}
        return 200, {"item": report}

    if path == "/research/run":
        query = _single(params, "query")
        if query is None:
            return 400, {"error": "missing_query"}
        events = storage.search_events(
            query=query,
            topic=_single(params, "topic"),
            source=_single(params, "source"),
            entity=_single(params, "entity"),
            event_type=_single(params, "event_type"),
            date_from=_single(params, "date_from"),
            date_to=_single(params, "date_to"),
            sort_by=_single(params, "sort_by") or "published_at",
            limit=_limit(params),
        )
        report, markdown = run_research_mode(query=query, events=events)
        report_id = storage.save_research_report(report=report, markdown=markdown)
        saved = storage.get_research_report(report_id=report_id)
        if saved is None:
            return 500, {"error": "research_save_failed"}
        return 200, {"item": saved}

    if path == "/entities":
        entities = storage.list_entities(limit=_limit(params))
        return 200, {
            "count": len(entities),
            "items": entities,
        }

    if path == "/topics":
        topics = storage.list_topics(limit=_limit(params))
        return 200, {
            "count": len(topics),
            "items": topics,
        }

    return 404, {"error": "not_found"}


def serve_api(*, storage: DigestStorage, host: str = "127.0.0.1", port: int = 8000) -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if urlsplit(self.path).path == "/":
                body = render_dashboard_html().encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            status, payload = build_api_response(
                storage=storage,
                method="GET",
                raw_path=self.path,
            )
            body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args) -> None:  # noqa: A003
            return

    server = ThreadingHTTPServer((host, port), Handler)
    try:
        server.serve_forever()
    finally:
        server.server_close()
