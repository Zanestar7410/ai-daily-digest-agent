# Architecture

## Overview

The repository is organized around a two-stage workflow:

1. `Discovery and summarization`
2. `Structured rendering and archival`

The two stages are connected through a structured JSON contract, which keeps the workflow modular and auditable.

## Modes

### Codex automation mode

This is the default day-to-day workflow.

- Codex automation performs web search
- Codex automation selects digest candidates
- Codex automation writes `input/latest_digest.json`
- The local Python project renders the final PDF

### API mode

This is the showcase and portable reproduction workflow.

- The local Python project uses `GPT-5.4` plus the `web_search` tool
- It can be executed with `OPENAI_API_KEY` when an API-backed workflow is required
- It writes the digest JSON to disk
- It renders the final PDF locally

## Main components

### Source policy

`config/search_sources.json`

Defines trusted domains and search hints for:

- official channels
- authoritative institutions
- high-quality media
- high-signal GitHub community posts

### Data contract

`input/latest_digest.json`

The digest JSON is the boundary object between discovery and rendering.

### Rendering pipeline

`src/ai_news_digest/render_pipeline.py`

Handles:

- validation
- persistence
- LaTeX rendering
- PDF compilation

### API workflow

`src/ai_news_digest/api_mode.py`

Handles:

- OpenAI web search collection
- shortlist selection
- Chinese summarization
- digest JSON generation

### Storage

`src/ai_news_digest/storage.py`

Maintains local SQLite state for:

- seen items
- digest runs
- selected digest entries

## Design rationale

- Discovery and rendering are decoupled for auditability and operational flexibility.
- Codex automation mode keeps local daily usage simple.
- API mode keeps the repository portable and self-contained for demonstration.
- PDF output makes the system suitable for recurring reporting, review, and archival workflows.
