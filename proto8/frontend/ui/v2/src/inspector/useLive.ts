// A panel's own data (thread, bot card): fetched when opened, again every 15 s while the tab is visible,
// and at once when one of the given kinds changed in a pulse (02c §4.5).
import { useCallback, useEffect, useRef, useState } from "react";
import { getJson } from "../api/client.ts";
import { onChange } from "../api/poll.ts";
import type { RevKey } from "../api/types.ts";

export interface Live<T> { data: T | null; error: string | null; at: number | null; loading: boolean; reload: () => void }

export function useLive<T>(path: string | null, kinds: RevKey[], everyMs = 15000): Live<T> {
  const [state, setState] = useState<{ data: T | null; error: string | null; at: number | null; loading: boolean }>(
    { data: null, error: null, at: null, loading: false });
  const cur = useRef(path);
  cur.current = path;
  const load = useCallback(async () => {
    if (!path) return;
    setState((s) => ({ ...s, loading: true }));
    try {
      const { body } = await getJson<T>(path);
      if (cur.current === path) setState({ data: body, error: null, at: Date.now() / 1000, loading: false });
    } catch (e) {
      if (cur.current === path) setState((s) => ({ ...s, error: e instanceof Error ? e.message : String(e), loading: false }));
    }
  }, [path]);
  useEffect(() => {
    setState({ data: null, error: null, at: null, loading: false });
    if (!path) return;
    load();
    const t = setInterval(() => { if (document.visibilityState === "visible") load(); }, everyMs);
    const off = onChange((ch) => { if (ch.some((k) => kinds.includes(k))) load(); });
    return () => { clearInterval(t); off(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, load, everyMs, kinds.join(",")]);
  return { ...state, reload: load };
}
