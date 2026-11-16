// The two stores of the page: data (what the backend said) and ui (where the user is, what is open).
import type { Answered, Ask, LetterIn, OrderKind, OutItem, Pulse, SlashCmd, Tree, UserBoard } from "../api/types.ts";
import { createStore } from "./store.ts";
import { parseHash, type Route, type Tab, type View } from "./route.ts";

/** kept in the backend's ui-state drawer (this machine only): the page opens the way it was left (q6b a, 02f §4) */
export interface Prefs {
  view?: View;
  left_open?: boolean; right_open?: boolean;   // only the user opens / closes the sides (q6b a); missing = open
  tree_open?: string[];                        // departments open in the left tree; missing = the default (02f §2.2)
}

export interface DataState {
  tree: Tree | null; treeError: string | null;
  asks: Ask[]; relay: LetterIn[]; outbox: OutItem[]; outboxChecked: number | null;
  board: UserBoard | null; answered: Answered[]; orders: OrderKind[]; slash: SlashCmd[];
  seen: Record<string, number>; dismissed: Record<string, number>; prefs: Prefs;
  pulse: Pulse | null;
  pulseOkAt: number | null;      // client time (s) of the last pulse that answered
  pulseError: string | null;
  skew: number;                  // server now - client now (s)
  clock: number;                 // client now (s), moved by the 10 s local tick (12.8 #7)
  errors: Record<string, string>;
  loaded: boolean;
}

export const data = createStore<DataState>({
  tree: null, treeError: null, asks: [], relay: [], outbox: [], outboxChecked: null, board: null, answered: [],
  orders: [], slash: [], seen: {}, dismissed: {}, prefs: {}, pulse: null, pulseOkAt: null, pulseError: null, skew: 0,
  clock: Date.now() / 1000, errors: {}, loaded: false,
});

export type InboxTab = "todo" | "track" | "done";
export type Filter = null | "ask" | "red" | "yellow" | "reply";

export interface UiState {
  route: Route;
  inboxTab: InboxTab;
  filter: Filter;
  searchOpen: boolean;
  searchText: string;
  flashTarget: string | null;
  helpOpen: boolean;
  panelOpen: boolean;
  fill: { text: string; n: number } | null;
  flashGo: Tab | null;
  slashAt: number;
  historyJump: number;
  cmdRev: number;
  sendRequest: number;
  boardOpen: boolean;
  draftsOpen: boolean;
  multi: string[];               // selected agents; two or more form a multi-selection
  anchor: string | null;         // the last clicked agent for Shift ranges
  flash: string | null;          // one line at the bottom of the composer ("已送出…")
  focusComposer: number;         // bump to move the caret into the composer
  prefill: Prefill | null;       // the composer takes it once (更正, reply to a letter)
}

export interface Prefill { target: string; mode: "say" | "mail" | "order"; orderKind?: string; mailTitle?: string; mailStatus?: string; correctionOf?: string; n: number }

export const ui = createStore<UiState>({
  route: parseHash(typeof location === "undefined" ? "" : location.hash),
  inboxTab: "todo", filter: null, searchOpen: false, searchText: "", flashTarget: null, helpOpen: false, panelOpen: false, fill: null, flashGo: null, slashAt: 0, historyJump: 0, cmdRev: 0, sendRequest: 0, boardOpen: false, draftsOpen: false, multi: [], anchor: null,
  flash: null, focusComposer: 0, prefill: null,
});

/** server "now" as seen from the client clock (for "N min ago"). */
export function serverNow(d: DataState): number {
  return d.clock + d.skew;
}
