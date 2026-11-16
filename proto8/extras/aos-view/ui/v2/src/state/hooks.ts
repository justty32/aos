import { useMemo } from "react";
import { data, ui, serverNow, type DataState, type UiState } from "./app.ts";
import { useStore } from "./store.ts";
import { buildInbox, headCounts, type Todo } from "../model/inbox.ts";

export const useData = <T,>(pick: (s: DataState) => T): T => useStore(data, pick);
export const useUi = <T,>(pick: (s: UiState) => T): T => useStore(ui, pick);
export const useNow = (): number => useStore(data, serverNow);

/** asks answered on this page: hidden at once, before the backend's next tree (v1 0.8 lesson). */
export const answeredHere = new Set<string>();

export function useInbox(): { todo: Todo[]; hidden: Todo[]; counts: ReturnType<typeof headCounts> } {
  const tree = useData((s) => s.tree);
  const asks = useData((s) => s.asks);
  const relay = useData((s) => s.relay);
  const outbox = useData((s) => s.outbox);
  const seen = useData((s) => s.seen);
  const dismissed = useData((s) => s.dismissed);
  const answered = useData((s) => s.answered);
  const now = useNow();
  return useMemo(() => {
    const done = new Set([...answeredHere, ...answered.map((a) => a.letter)]);
    const { todo, hidden } = buildInbox({ tree, asks, relay, outbox, seen, dismissed, answeredHere: done, now });
    return { todo, hidden, counts: headCounts(todo, tree) };
  }, [tree, asks, relay, outbox, seen, dismissed, answered, now]);
}
