// Time words (pure). The page counts "N min ago" itself from epoch fields, on the 10 s local tick (12.8 #7).

export function ago(t: number | null | undefined, now: number): string {
  if (!t) return "沒有紀錄";
  const s = Math.max(0, now - t);
  if (s < 45) return "剛剛";
  if (s < 3600) return `${Math.round(s / 60)} 分前`;
  if (s < 86400) return `${Math.floor(s / 3600)} 小時前`;
  return `${Math.floor(s / 86400)} 天前`;
}

export function hhmm(t: number | null | undefined): string {
  if (!t) return "--:--";
  const d = new Date(t * 1000);
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

export function dayTime(t: number | null | undefined, now: number): string {
  if (!t) return "--";
  const d = new Date(t * 1000), n = new Date(now * 1000);
  const same = d.toDateString() === n.toDateString();
  return same ? hhmm(t) : `${d.getMonth() + 1}/${d.getDate()} ${hhmm(t)}`;
}

export function parseIso(s: string | null | undefined): number | null {
  if (!s) return null;
  const t = Date.parse(s);
  return Number.isFinite(t) ? t / 1000 : null;
}
