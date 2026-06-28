# Web Product Plan — Next.js + Tailwind + FastAPI

Turns the existing CLI system into a web product, **without touching the engine**.
The CLI (`run.py`) stays — it still satisfies the brief's "single documented
command" requirement. The web layer is built *on top* and directly earns the brief's
bonus items (replay viewer, config live-preview).

## Guiding principle

The engine in `src/` is already a clean library. FastAPI just **calls into it** and
returns JSON. Next.js renders that JSON. No engine logic moves into the web layer —
that keeps constraints 1–5 intact and the web layer thin.

## Folder layout (monorepo)

```
interopera-takehome/
  src/                 # EXISTING engine — unchanged, reused as a library
  run.py               # EXISTING CLI — kept (core submission)
  api/                 # NEW — FastAPI backend
    main.py            # app + CORS + router include
    deps.py            # shared: load engine, graph client, audit
    services.py        # thin wrappers calling src/ (run pipeline, get figures, trace)
    routes/
      reports.py       # /run, /figures, /figures/{id}
      reconcile.py     # /reconciliation
      audit.py         # /audit
      config.py        # /config (+ live preview)
  web/                 # NEW — Next.js (App Router) + Tailwind
    app/
      page.tsx               # dashboard (firm selector + figures table)
      figures/[id]/page.tsx  # figure detail (trace / replay viewer)
      audit/page.tsx         # audit log timeline
      config/page.tsx        # config editor + live preview
    components/
      FiguresTable.tsx StatusBadge.tsx TracePanel.tsx FirmSwitch.tsx
    lib/api.ts               # typed fetch helpers
  docker-compose.yml   # neo4j + api + web (extend existing)
```

## FastAPI endpoints

| Method | Path | Returns | Notes |
|---|---|---|---|
| POST | `/api/run?firm=A` | run summary (counts, all_passed, firewall) | runs the full pipeline |
| GET | `/api/figures?firm=A` | list of figures (table rows) | value, status, limit, utilization |
| GET | `/api/figures/{id}?firm=A` | one figure + **graph_path + citation + reconciliation delta + producing rule** | powers the replay viewer (bonus) |
| GET | `/api/reconciliation?firm=A` | per-figure pass/fail + delta | Phase 5 |
| GET | `/api/audit` | append-only event list + `chain_intact` flag | the logbook |
| GET | `/api/config/{firm}` | the firm's YAML method config | for the editor |
| POST | `/api/config/preview` | figures recomputed under posted method knobs **without saving** | config live-preview (bonus) |
| GET | `/api/multihop-demo` | the multi-hop graph query result | Phase 2 showcase |

All endpoints are read-mostly and call existing `src/` functions. `/run` and the
engine stay deterministic; the API adds no math.

## Next.js screens

1. **Dashboard** (`/`) — firm dropdown (A/B), "Run" button, figures table with
   colored status badges (Tailwind). Flip firm → 3 numbers change. This *is* the
   assignment, visualized.
2. **Figure detail** (`/figures/[id]`) — the replay viewer: value vs answer key
   (delta), the Cypher graph path, the source citation (doc/page/passage), and which
   config rule produced it. **= bonus +2–4.**
3. **Audit log** (`/audit`) — timeline of events with a "chain intact ✓" badge;
   show that UPDATE/DELETE are forbidden.
4. **Config editor** (`/config`) — Firm A vs Firm B method knobs side by side; edit a
   knob → live preview of the recomputed figures via `/api/config/preview`.
   **= bonus +2–3.**

## How they connect

- **Dev:** `web/next.config.js` rewrites `/api/:path*` → `http://localhost:8000/api/:path*`.
  Run `uvicorn api.main:app --reload` and `npm run dev` side by side.
- **Prod:** docker-compose adds two services:
  - `api`  — builds the Python image, depends_on neo4j healthy, runs uvicorn.
  - `web`  — builds the Next image, talks to `api` over the compose network.

## Build order (each step independently runnable)

1. **FastAPI skeleton + `/api/figures` + `/api/run`** → hit it in the browser /
   `curl`. Quick win, proves it's alive. *(start here)*
2. `/api/figures/{id}` with trace + delta + producing rule (replay data).
3. Next.js dashboard + figures table + firm switch (talks to step 1).
4. Figure detail page (replay viewer) — bonus.
5. Audit page + config editor with live preview — bonus.
6. docker-compose: add `api` + `web`; update README with the web start command.

## Effort estimate

Steps 1–3 (a working clickable dashboard): a few hours. Steps 4–6 (bonus polish +
containerization): another half day. The engine work — the hard 70% — is already done.
