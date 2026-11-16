// Small in-memory LRU stores optionally expire entries after a fixed number of seconds.
export function createMemo<V>(max: number, ttlS?: number) {
  const entries = new Map<string, { value: V; at: number }>();
  return {
    get(key: string, now: number): V | undefined {
      const entry = entries.get(key);
      if (!entry) return undefined;
      if (ttlS !== undefined && now - entry.at >= ttlS) {
        entries.delete(key);
        return undefined;
      }
      entries.delete(key);
      entries.set(key, entry);
      return entry.value;
    },
    set(key: string, value: V, now: number): void {
      entries.delete(key);
      entries.set(key, { value, at: now });
      while (entries.size > Math.max(0, max)) entries.delete(entries.keys().next().value!);
    },
  };
}
