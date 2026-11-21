# aos-frontend API (phase 0 + phase 1)

Backend: `aos-frontend serve` (Python stdlib, 127.0.0.1:8767). It serves the static frontend from `ui/v1/` (全景 v1 清單版, frozen 11-14; `--ui DIR` serves another; the old `web/` is kept but not served) at `/`, `/app.js`, `/style.css`, and JSON under `/api/`. Every JSON reply has `Content-Type: application/json; charset=utf-8` and `Cache-Control: no-store`. All strings that come from agents are already secret-masked by the backend; the frontend must still insert them with `textContent` (never `innerHTML` with data).

Errors: HTTP 4xx/5xx with `{"ok": false, "error": "Code", "message": "human text (zh-Hant)"}`.

## Session / CSRF

- `GET /api/session` → `{"token": "<hex>", "version": "view-api/0"}` and sets cookie `aosview=<token>; HttpOnly; SameSite=Strict`.
- Every POST must send header `X-View-Token: <token>` and `Content-Type: application/json`; the cookie must match too. Missing/wrong → 403 `{"error":"TokenBad"}` (frontend: fetch a new session, retry once).
- `Origin` check: a POST whose `Origin` header is present and is not `http://127.0.0.1:<port>` or `http://localhost:<port>` → 403 `OriginBad` (this includes the literal `null`). A POST with no `Origin` header is let through to the token + cookie check; the `Host` header must still be 127.0.0.1/localhost. Pages are served with `Referrer-Policy: same-origin` (was `no-referrer`, which can make a browser send `Origin: null`).

## Read

- `GET /api/tree` → `{"tree": TREE|null, "error": str|null}`
  - `TREE = {"format": "view-tree/0", "generated_at": epoch_s, "roots": [id...], "llm_workers": int, "nodes": {id: NODE}}`
  - `NODE = {"id", "kind": "agent"|"proc", "state", "phase", "busy": null|"think"|"act"|"wait"|..., "queued": int|null, "reason", "cooldown": null|{failures, reason, code, until, state}, "light": "red"|"blue"|"yellow"|"green"|"gray", "why": str, "why_full": str, "parent": id|null, "parent_by": "config"|"subagent"|"prefix"|"rule"|null, "children": [id...], "rollup": {"worst": light, "why": str, "nodes": int (self included), "path": [id...]}, "active_at": epoch_s|null, "last_answer": str|null, "messages": int|null, "asks": int, "reports": [LETTER_IN up to 3], "tags": [str], "team": str|null, "note": NOTE|null, "aide": AIDE|null, "passed": int, "team_light": {"light": "red"|"yellow", "why": str}|null}`
  - Phase 1 fields (only on a team's leader node, i.e. the node named by `leader` in `~/.aos/view/teams/<team>/aide.json`, or the team folder's name; other nodes: `team`/`note`/`aide`/`team_light` null, `passed` 0):
    - `NOTE = {"at": epoch_s|null, "status": "start"|"progress"|"done"|"blocked"|"decision"|"handoff"|"ask", "text": str (masked), "on": str|null}` = the captain's latest `aos-frontend note` ("隊長留話"; show verbatim, it is not a model's words).
    - `AIDE = {"name": str, "last_beat": epoch_s|null, "state": str|null}` = the team's aide. The aide node itself stays in `nodes` (with `parent` = the leader, `parent_by: "aide"`) but is **not** in any `children` list and not in `roots`, so it takes no seat and does not count in rollup (§10).
    - `passed` = how many of the team's decision files reached the user zone (receipts in `state/passed/<team>/`).
    - `team_light` = the phase-1 light of the team, counted into `rollup.worst`/`rollup.why` only (the node's own `light` is unchanged): red `aide silent N min` (aide.json exists and no beat for 35 min; `aide silent (no beat yet)` once aide.json is 35 min old with no beat, before that it is warming up and gives no light); yellow `no progress 60 min` (latest note older than 60 min and not `done`; paused while a zone letter from that team waits). None when the leader and all its children are stopped.
  - `why_full` 與 `why` 同一句，但錯誤／冷卻原因不截成 80 字；全文先遮罩，最多 2000 字，超過截尾加 `…`。`why` 保留原本短版，舊頁面不變。
  - Running lights: busy → green `working (X), last activity N min ago`; letters queued and not busy → green `in a turn; N queued (read when the turn ends)`, yellow only after 60 min with no activity (never red); else green `running, nothing queued, ...` (an eca body reports no busy, so this may still be a long turn). Red is only for a stopped node with a `reason` or brain failures (fixtures).
  - `rollup.why` = the `why` of the node that gave `rollup.worst` (or the team light).
  - Relay letters whose body has `zone: "view/1"` (the aides' report/beat/pass/post) are ingested by the backend, never listed in `reports`, `/api/relay` or `/api/thread`.
  - Nesting is unlimited: render recursively from `roots` through `children`. Roots with `kind == "agent"` are departments; roots with `kind == "proc"` go to a "機房" section.
- `GET /api/asks` → `{"asks": [ASK...]}` (user-zone letters waiting for the user, urgent first)
  - `ASK = {"letter", "kind": "decide"|"verify"|"trial"|"chore"|"fyi", "from", "title", "what", "decide": str|null, "questions": [{"id","question","eli5","options":[{"key","label","consequence"?}],"recommend","why"?}], "urgent": bool, "risk": "normal"|"irreversible", "deadline": str|null, "sent_at": epoch_s|null, "unseen": bool, "same": int}`
- `GET /api/thread?name=ID` → `{"name", "letters": [ITEM...]}` newest first, max 50: what the user sent to this agent (say and mail) and what came back to the relay mailbox from it.
  - `ITEM = {"dir": "out"|"in", "kind": "say"|"mail", "letter", "from", "to", "status": str|null, "title", "what", "sent_at": epoch_s, "in_reply_to": str|null}`
  - Out items of the last 7 days to an agent also carry `delivery`: `queued` (a mail still in its mailbox / a say not yet in its history), `read` (the mail left its mailbox / the say is in its history), `replied` (a relay letter has `in_reply_to` = this letter; for a say: the agent wrote to the relay after it), `unknown` (`ctl state` / `history ls` could not be read). Only official commands are used (Q7 a), cached 15 s per agent (cleared when the user sends to it). A `queued` item also has `queue_ahead`: for a mail its place in the mailbox, for a say `queued - (my later says still queued) - 1` (the queue is FIFO; approximate).
  - The reply also has `turn`: null, or `{queued, busy, active_at, why}` when the agent is running with letters queued (or busy) = it is inside a turn and reads them when the turn ends.
- `GET /api/relay` → `{"letters": [ITEM...]}` newest first, max 100, all `dir: "in"` (every reply in the relay mailbox).
- `GET /api/agent?name=ID` (agents only) → `{"name", "now": {"state","phase","queued","busy","pid","memory_mb","up_min","workspace","last_answer","last_answer_full","last_answer_cut"}, "mailbox": {"waiting": int, "letters": [{"status","title","from","sent_at"}]}, "history": [{"line": int, "role", "text", "tools": [str]}]}` (history newest first, max 30, ordinary text cut at 600 chars). Assistant content starting with `[aos] slash: /` also has `slash: "/command"`; its masked text preserves newlines up to 4000 characters (trailing `…` when cut). `now.last_answer_full` is the last assistant's masked text, preserving newlines up to 4000 characters, or null if absent; `now.last_answer_cut` says whether that text was cut. Slow (CLI calls, ~0.3 s): fetch only when the user opens that agent.

## Write (POST, JSON body)

- `POST /api/answer`
  - decide: `{"letter", "do": "answer", "answers": {"q1": "a", ...}, "note": str}` (every question needed; backend adds the `*` for non-recommended keys)
  - other kinds: `{"letter", "do": "reply", "text": str}`; fyi: `{"letter", "do": "ok"}`
  - → `{"ok": true, "message": "已送出：…"}`
- `POST /api/say` `{"name", "text"}` → `{"ok", "message"}`. Agents only. Backend prefixes `[使用者經全景頁]` and appends how to reply.
- `POST /api/mail` `{"name", "status": "REQUEST"|"DONE"|"BLOCKED"|"NEEDS-USER"|"FAILED"|"PROGRESS", "title", "what"}` → `{"ok", "message", "letter"}`. Sent as from `user` with `reply_to` = the relay mailbox, so replies show up in `/api/thread`. An agent that never got a letter has no `<stack>/mailbox/` yet: the backend makes it first (`aos-post init`, as `aos-mailbox send --to` does).

No stop / rm / push / start endpoints exist, by design. Later phases add endpoints under `/api/` (departments `tags`, zoom map, HR `hire` requests, power `budget`); the frontend should keep one module per panel so new panels plug in.

## Chairman's orders (phase 0.5: interface only)

The page never changes the tree itself. An order is one REQUEST letter to whoever takes that kind of order; the receiver does the work through its own rules (hiring an agent goes through the kernel gate) and replies to the relay mailbox.

- `GET /api/orders` → `{"kinds": [{"kind": "expand"|"hire"|"power", "label", "to": receiver|null, "fields": [extra field names]}]}`. `to: null` = the target department itself. Receivers come from config `orders.<kind>.to` (default: expand → the target itself, hire and power → `repo-aos` until an HR / power department exists).
- `POST /api/order` `{"kind", "target": node id, "what": str, ...extra fields}` → `{"ok", "message", "letter"}`. Extra fields: expand `budget`; hire `role`, `model`, `count`; power `priority`, `quota`. The letter body carries `order: {kind, target, ...}`; it shows in `/api/thread` of the receiver as `kind: "order"`.

## Phase 1: relay mailbox and the aide (no model)

Files (view home, default `~/.aos/view`):

- `teams/<team>/aide.json` `{team, parent, leader, aide, tags}` (written by the captain), `notes.jsonl` (`aos-frontend note`), `outbox/<id>.json` + `outbox/sent/` + `sent.jsonl` `{id, at, sha256, kind, title}` (`aos-frontend decide`), `seq` (flock counter), `aide_state.json`, `send_failed`.
- `state/teams/<team>.json` `{team, aide, parent, last_beat, last_seq, report: {at, seq, status, title, what, summary_by, snapshot_sha256, facts}, post: {at, seq, title, what}}`; `state/passed/<team>/<id>.json` receipt `{payload_id, sha256, zone_letter, kind, title, reply_to, aide, relay_letter, sent_at}`.
- `done/<YYYY-MM>/<letter>/` processed view/1 letters; `rejected/<letter>/` + `reason.txt` (`CODE reason`: KindBad TeamBad StatusBad SenderBad PayloadBad PayloadHashBad PayloadIdBad PayloadIdReused SecretInPayload SchemaBad ReplyToBad). Plain replies stay in `mailbox/new|cur/`.

Relay letter body (`aos-post send --reply-to <view mailbox> <view mailbox>`, sender = the aide's stack): `zone: "view/1"`, `kind` report|beat|pass|post, `team`, `parent`, `seq`, `from` (aide), `to: "view"`, `status` (report PROGRESS/BLOCKED/DONE, beat PROGRESS, pass NEEDS-USER, post DONE), `title`, `what`.

- report: `said {now,next,blocked}` (empty in phase 1), `summary_by: "none"`, `snapshot_sha256` (over `facts`), `facts {leader {name,state,busy,queued}, members [{name,state,busy,queued}], note, pending_pass}`.
- pass: `payload_id "<team>/<id>"`, `payload_text` (the captain's file verbatim), `payload_sha256`, `written_by`, `reply_to_team` (leader stack + `/mailbox`).
- Hash = sha256 of `json.dumps({k: letter[k] for k in (kind title what questions done_when risk urgent deadline default_if_silent dedupe_key) if k in letter}, sort_keys=True, separators=(",",":"), ensure_ascii=False)`, taken after `zone.build_letter` fills its defaults (so a decide letter without `what` hashes like the zone's copy).

Ingestion (every poll, and `aos-frontend ingest`): recompute the hash (mismatch = rejected), dedupe by payload_id + hash, at most 8 passes per hour in total (10 when the deadline is < 30 min away), urgent first then nearest deadline; `aos-user send --kind <kind> --reply-to <reply_to_team>` with `AOS_STACK=<view home>`, body = payload + `from: <team>` + `origin: "<team>/<id> sha256:<hex> via <aide>"`.

Captain CLI: `aos-frontend note [--team T] [--on NAME] STATUS TEXT`, `aos-frontend decide [--team T] FILE` (prints the id; `SecretInPayload` / `SchemaBad` refuse), `aos-frontend match REPLY_FOLDER` (`aos-user verify`, then the zone's `done/*/<in_reply_to>/letter.json` hash vs `sent.jsonl`: `ok: match <team>/<id> sha256:<hex>` exit 0, or `aos-frontend: error: PayloadMismatch ...` exit 1). Aide: `aos-frontend aide-tick [--team T]` (template `aide-def/`).

## Phase 2: externals (machine room)

Nodes with `kind: "external"` are things outside the daemon table, from config `externals` (default `[{"id": "LiteLLM", "url": "http://127.0.0.1:4000/health/liveliness", "port": 4000}]`). They are roots, shown in 機房. Extra field `ext: {url, listen: [addresses], ss_at}`. Light: red = health check failed; yellow = healthy but listening on all interfaces (`ss` checked once a day); green = healthy; gray = no health URL. Only local health URLs are fetched.

## The user's board (布告欄)

One line the user leaves before going away (sleep, out), so an agent that waits long for an answer can look first.

- `GET /api/board` → `{"user": null | {"at": iso, "text": str (masked), "back": str|null}}`
- `POST /api/board` `{"text": str (<= 1000; "" = clear), "back": str (<= 100, optional)}` → `{"ok", "message", "user"}`. Logged in `state/sent.jsonl` as `kind: "board"`.
- Files: `board/user.json` (latest), `board/user.jsonl` (every change).
- Agents read it with one command, no model: `aos-frontend board` after `source $AOS_HOME/env.sh`, or `$AOS_HOME/frontend/bin/aos-frontend board` (plain text), `--json`, `--all` (adds every team's latest `aos-frontend note`: a team's board is its captain's note). Every say and mail from the page now ends with this hint (it names the running file's absolute path).

## Answered asks

- After a successful `POST /api/answer` the letter is dropped from the cached tree at once, so the next `/api/asks` does not bring the card back (the page also never redraws a letter it answered).
- `GET /api/answered` → `{"answered": [{"letter", "at": epoch_s, "do": "answer"|"reply"|"ok", "title", "from", "answers": [str], "out"}]}` = what the user answered on this page in the last 24 h, newest first (from `state/sent.jsonl`; records before 11-14 11:05 have no `title`/`from`). The page lists them under "📤 已送出的回答"; a correction is a plain `POST /api/mail` (REQUEST, title `更正：<title>`) to `from` (a zone letter cannot be answered twice).

## Version

- `GET /api/version` → `{"api": "view-api/0", "ui": "<the served UI's VERSION line>", "ui_dir": "v1"}`. v1 (`ui/v1/`) is frozen: bug fixes only; new APIs may be added for the new UI, but fields and behavior v1 uses do not change.

## v2 additions (全景 v2.0, 11-14; 03 §12.3 B1–B6, §12.8)

Nothing v1 uses changed; every item below is new.

- **B1 second port.** config `ui_ports` (default `[{"port": 8768, "dir": "ui/v2/dist"}]`, dir relative to the frontend folder, the one above `bin/`) = extra listeners in the same process: one collector, one token, one cookie. A dir without `index.html` is not served (the port stays closed; `serve` prints one `aos-frontend: warning: port N not opened: DIR has no index.html ...` line on stderr). `/` → `index.html` (no-store, sets the cookie); `/assets/<name>` with `^[A-Za-z0-9._-]+$` and `.js .css .svg .woff2 .png .map` only, immutable. Same CSP; Origin is checked per port. Every `/api/*` answers on both ports.
- **B2 `GET /api/pulse`** → `{now, tick: {at, took_ms, ok, error}, rev: {tree, asks, relay, outbox, board, answered, ui_state}, ext_checked_at, error}`. The page polls only this (5 s; 30 s when hidden) and fetches a kind when its `rev` changed. `/api/tree|asks|relay|board|answered|outbox` send `ETag` and answer `304` to `If-None-Match`, with `X-Last-Tick`. The tree rev leaves out fields that move every round (`why`, `generated_at`, `llm_workers`, `rollup.why`, `_*`, `team_light.why`, an external's `active_at` and `ext.ss_at`).
- **B3 `GET /api/outbox`** → `{items: [{letter, batch, kind say|mail|order, to, target, title, what, status, sent_at, delivery queued|read|replied|unknown, queue_ahead, checked_at, turn, reply: {letter,status,title,at}|null, order, correction_of, gone, followed}], checked_at}`: what the page sent in 7 days. Replies are matched on every read; delivery (`aos-agent ctl state`) is checked in a background thread, at most 6 agents a round, the ones just written to first; under 24 h every round, 1–7 days every 6th, older `followed: false`. `read` is inferred (left the mailbox or entered the history).
- **B4 `GET /api/ui-state?key=seen|dismissed|seats|prefs`** → `{key, value, at, rev}`; **`PUT /api/ui-state`** `{key, value}` (token + cookie + Origin as POST; ≤ 256 KB). `seen` / `dismissed` take a diff `{id: epoch | null}`: merged keeping the newer time, `null` deletes, entries over 14 days dropped. `seats`, `prefs` = last write wins. Files: `state/ui/<key>.json`.
- **B5** `POST /api/say|mail|order` take optional `batch`, `correction_of` (`^[A-Za-z0-9._:-]{1,120}$`), kept in `state/sent.jsonl`; `/api/say` now returns `letter`. `/api/answered` items gain `corrections: [letter]`. `/api/thread?name=` for a name no longer on the tree: `{…, gone: true, turn: null}` when there is any history, else 404.
- **Agent boards (ok-board board/1, read only).** Each agent node gains `board`: the stack's `board.json` when its `format` is `board/1` (known keys only, strings masked), else `null`. The page reads it in ok-board's four steps (not posted / clock fix / expiry 24 h → grey / a sleeping or stopped proc = away).
- **Rollup** gains `counts {red, yellow, blue}` (self and everything below) and `worst_ids` (the worst 3 below).
- **UI** `ui/v2/dist` (built from `ui/v2/` in the dev copy: React 19, Tailwind 4, Vite 8; `VERSION`). Only the build is installed, no `node_modules`. `dist/` is not in git (11-17): build it first on a machine with node, following `ui/v2/README.md`.

### B6 畫面指令

- `GET /api/slash` → `{"commands": [{"name":"compact","args":"optional","confirm":false,"how":"turn","cli":["claude","codex"]}, ...]}`。`name` 不帶 `/`，`args` 為 `none|optional|required`，`how` 為 `turn|screen`。預設六個指令：compact、status、usage、goal、clear、exit；compact／goal 可帶參數，其他不能，clear／exit 要前端確認。只有設定 `VIEW_SLASH_FIXTURE=FILE` 才從 JSON 陣列讀名單，每次 GET／POST 都重讀，供 demo 驗證尚未掛接的指令。
- `POST /api/slash` `{"name":"agent-id","text":"/compact keep the plan"}` → `{"ok","message","letter"}`。沿用 Host、Origin、token＋cookie、大小與 JSON／字串檢查；只收表上的 agent，去頭尾空白後須 `/` 開頭、單行、最多 1000 字，指令與參數符合名單，agent 正在 running、CLI 種類支援、queued 為 0。失敗 HTTP 400；成功 stdin 原樣送給 `aos-agent say -t NAME --from user-via-page -`，不加開頭或尾巴，逾時 20 秒。
- 送出後清 delivery cache，`log_sent` 記 `kind:"slash"`、to、text、ok、letter／error；只稽核留底，不進 outbox／thread。成功訊息「已把 /compact 送進 board 的畫面」；在一輪裡會提示「這一輪結束才會做，這段時間別再對它說話」。
- `/api/compact` 為相容保留，共用檢查與送出函式，但紀錄的 `kind` 仍是 `compact`，訊息仍用「這一輪結束才會壓」。
