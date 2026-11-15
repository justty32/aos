// The API contract (aos-view API.md + v2 additions B1–B5, 03 §12.3 / §12.8). Written by opus; panels only read these.
// Every string that comes from an agent is already secret-masked by the backend; render it as React text only.

export type Light = "red" | "blue" | "yellow" | "green" | "gray";
export type Epoch = number; // seconds

export interface Cooldown { failures?: number; reason?: string; code?: string; until?: Epoch; state?: string }

export interface Note { at: Epoch | null; status: string; text: string; on: string | null }
export interface Aide { name: string; last_beat: Epoch | null; state: string | null }

export interface Rollup {
  worst: Light; why: string; nodes: number; path: string[];
  counts?: { red: number; yellow: number; blue: number };   // v2: anywhere below, self included
  worst_ids?: string[];                                     // v2: the worst 3 ids below
}

// ok-board board/1 (board-1114/06 §7). Placeholder until U1–U7 are decided; fields are only ever added.
export type BoardMode = "here" | "busy" | "dnd" | "away";
export interface WaitingOn { who: string; what: string; since_at: string; ref?: string; level?: "urgent" | "normal" | "low"; notified_at?: string }
export interface Board1 {
  format?: "board/1"; seq?: number; updated_at: string; by?: "self" | "auto" | "user"; mode: BoardMode;
  text?: string; doing?: string; waiting_on?: WaitingOn[]; back_at?: string; back_text?: string; expires_at?: string;
  accept?: string; deputy?: string;
}

export interface LetterIn {
  dir: "in"; kind: "mail"; letter: string; from: string; to: string; title: string; status: string | null;
  what: string; sent_at: Epoch | null; in_reply_to: string | null;
  priority?: string | null;   // reserved for ok-board's letter classes (03 §12.4)
}

export interface Node {
  id: string; kind: "agent" | "proc" | "external"; state: string | null; phase: string | null;
  busy: string | null; queued: number | null; reason: string | null; cooldown: Cooldown | null;
  light: Light; why: string; parent: string | null; parent_by: string | null; children: string[];
  rollup: Rollup; active_at: Epoch | null; last_answer: string | null; messages: number | null;
  asks: number; reports: LetterIn[]; tags: string[]; team: string | null; note: Note | null; aide: Aide | null;
  passed: number; team_light: { light: Light; why: string } | null;
  ext?: { url: string; listen: string[] | null; ss_at: Epoch | null };
  board?: Board1 | null;
}

export interface Tree {
  format: string; generated_at: Epoch; roots: string[]; llm_workers: number; nodes: Record<string, Node>;
}

export interface Question {
  id: string; question: string; eli5?: string; recommend?: string; why?: string;
  options: { key: string; label: string; consequence?: string }[];
}
export interface Ask {
  letter: string; kind: "decide" | "verify" | "trial" | "chore" | "fyi"; from: string | null; title: string;
  what: string; decide: string | null; questions: Question[]; urgent: boolean; risk: "normal" | "irreversible";
  deadline: string | null; sent_at: Epoch | null; unseen: boolean; same: number; error?: boolean;
}

export type Delivery = "queued" | "read" | "replied" | "unknown";
export interface ThreadItem {
  dir: "in" | "out"; kind: "say" | "mail" | "order"; letter: string | null; from: string; to: string;
  status: string | null; title: string; what: string; sent_at: Epoch | null; in_reply_to: string | null;
  delivery?: Delivery | null; queue_ahead?: number | null; batch?: string | null; correction_of?: string | null;
  priority?: string | null;
}
export interface Turn { queued: number; busy: string | null; active_at: Epoch | null; why?: string }
export interface Thread { name: string; letters: ThreadItem[]; turn: Turn | null; gone?: boolean }

export interface OutItem {
  letter: string; batch: string | null; kind: "say" | "mail" | "order"; to: string; target: string | null;
  title: string; what: string; status: string | null; sent_at: Epoch | null; delivery: Delivery;
  queue_ahead: number | null; checked_at: Epoch | null; turn: Turn | null;
  reply: { letter: string; status: string | null; title: string; at: Epoch | null } | null;
  order: Record<string, string> | null; correction_of: string | null; gone: boolean; followed: boolean;
}

export interface Answered {
  letter: string; at: Epoch; do: "answer" | "reply" | "ok"; title: string | null; from: string | null;
  answers: string[]; out: string | null; corrections: string[];
}

export interface UserBoard { at: string | null; text: string; back: string | null }

export interface AgentCard {
  name: string;
  now: { state: string; phase: string; queued: number | null; busy: string | null; pid: number | null;
         memory_mb: number | null; up_min: number | null; workspace: string | null; last_answer: string | null };
  mailbox: { waiting: number; letters: { status: string; title: string; from: string; sent_at: Epoch | null }[] };
  history: { line: number; role: string; text: string; tools: string[] }[];
}

export interface OrderKind { kind: "expand" | "hire" | "power"; label: string; to: string | null; fields: string[] }

export type RevKey = "tree" | "asks" | "relay" | "outbox" | "board" | "answered" | "ui_state";
export interface Pulse {
  now: Epoch;
  tick: { at: Epoch | null; took_ms: number | null; ok: boolean | null; error: string | null };
  rev: Record<RevKey, string>;
  ext_checked_at: Epoch | null;
  error: string | null;
}

export type UiKey = "seen" | "dismissed" | "seats" | "prefs";
export interface UiState<T = unknown> { key: UiKey; value: T | null; at: Epoch | null; rev: number }

export interface SendResult { ok: boolean; message: string; letter?: string | null }
