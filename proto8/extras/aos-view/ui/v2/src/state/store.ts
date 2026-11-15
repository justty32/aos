// A tiny store on React 19's useSyncExternalStore (03 §12.2: instead of zustand, not on this machine).
import { useSyncExternalStore } from "react";

export interface Store<S> {
  get(): S;
  set(patch: Partial<S> | ((s: S) => Partial<S>)): void;
  subscribe(f: () => void): () => void;
}

export function createStore<S extends object>(init: S): Store<S> {
  let state = init;
  const subs = new Set<() => void>();
  return {
    get: () => state,
    set(patch) {
      const p = typeof patch === "function" ? patch(state) : patch;
      let changed = false;
      for (const k in p) if ((p as S)[k as keyof S] !== state[k as keyof S]) { changed = true; break; }
      if (!changed) return;
      state = { ...state, ...p };
      subs.forEach((f) => f());
    },
    subscribe(f) { subs.add(f); return () => { subs.delete(f); }; },
  };
}

export function useStore<S, T>(store: Store<S>, pick: (s: S) => T): T {
  return useSyncExternalStore(store.subscribe, () => pick(store.get()));
}
