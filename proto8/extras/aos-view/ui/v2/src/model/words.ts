// The back end's light reasons ("why") are English (program output stays English, conventions); the page shows them
// in plain Chinese (P5, 03 §13 草稿; the 11-14 note "卡片上還是英文"). The English stays as the hover title.
// Unknown sentences pass through unchanged. Pure: node --test checks it.

type Rule = [RegExp, (...m: string[]) => string];
const WAIT_ON: Record<string, string> = { "a CLI turn": "一輪 CLI 跑完", "the brain's reply": "模型回信", something: "某件事" };

const RULES: Rule[] = [
  [/^asleep$/, () => "睡著"],
  [/^long quiet, not dead \(daemon says stuck\)$/, () => "很久沒動靜，不是掛了（daemon 標 stuck）"],
  [/^long quiet, not dead: waiting on (.*?)(?:, quiet for (\d+) min)?(?:, (\d+) queued)?$/,
    (w, m, q) => `很久沒動靜，不是掛了：在等${WAIT_ON[w] ?? w}${m ? `，${m} 分鐘沒動靜` : ""}${q ? `；${q} 封信排著` : ""}`],
  [/^stopped normally$/, () => "正常停了"],
  [/^stopped normally, (\d+) below still running$/, (n) => `正常停了，底下還有 ${n} 個在跑`],
  [/^stopped: a turn ran long and was cut by a timeout, not a crash \((.*)\)(?:, (\d+) below still running)?$/,
    (_r, n) => `一輪跑太久被逾時停掉（不是當掉）${n ? `，底下還有 ${n} 個在跑` : ""}`],
  [/^crashed: (.*?)(?:, (\d+) below still running)?$/, (r, n) => `當掉了：${r}${n ? `（底下還有 ${n} 個在跑）` : ""}`],
  [/^(\d+) letter\(s\) waiting for you$/, (n) => `有 ${n} 封信等你回`],
  [/^brain failed (\d+)x: (.*)$/, (n, r) => `模型連續失敗 ${n} 次：${r}`],
  [/^paused by hand$/, () => "被手動暫停"],
  [/^still in a turn, quiet for (\d+) min \(not crashed\)(?:, (\d+) queued.*)?$/,
    (m, q) => `還在這一輪，${m} 分鐘沒新輸出（沒當掉）${q ? `；${q} 封信排著` : ""}`],
  [/^in a turn, last output (\d+) min ago(?:, (\d+) queued.*)?$/, (m, q) => `正在做，${min(m)}有輸出${q ? `；${q} 封信排著` : ""}`],
  [/^in a turn, last output not recorded(?:, (\d+) queued.*)?$/, (q) => `正在做${q ? `；${q} 封信排著` : ""}`],
  [/^working \((.*?)\), last activity (\d+) min ago(?:, (\d+) queued)?$/, (b, m, q) => `在忙（${b}），${min(m)}有動靜${q ? `；${q} 封信排著` : ""}`],
  [/^working \((.*?)\), last activity not recorded(?:, (\d+) queued)?$/, (b, q) => `在忙（${b}）${q ? `；${q} 封信排著` : ""}`],
  [/^in a long turn, quiet for (\d+) min; (\d+) queued.*$/, (m, q) => `一輪做很久，${m} 分鐘沒動靜；${q} 封信排著（沒當掉）`],
  [/^in a turn; (\d+) queued \(read when the turn ends\), last activity (\d+) min ago$/, (q, m) => `正在做；${q} 封信排著，${min(m)}有動靜`],
  [/^in a turn; (\d+) queued \(read when the turn ends\), last activity not recorded$/, (q) => `正在做；${q} 封信排著`],
  [/^running, nothing queued, last activity (\d+) min ago$/, (m) => `閒著，${min(m)}有動靜`],
  [/^running, nothing queued, last activity not recorded$/, () => "閒著"],
  [/^aide silent \(no beat yet\)$/, () => "隊助理還沒出聲"],
  [/^aide silent (\d+) min$/, (m) => `隊助理 ${m} 分鐘沒出聲`],
  [/^no progress 60 min$/, () => "60 分鐘沒進展"],
];

function min(m: string): string {
  const n = Number(m);
  return n < 1 ? "剛剛" : n < 60 ? `${n} 分鐘前` : n < 1440 ? `${Math.floor(n / 60)} 小時前` : `${Math.floor(n / 1440)} 天前`;
}

/** the page's sentence for a back-end reason; unknown ones stay as they are */
export function whyWord(why: string | null | undefined): string {
  if (!why) return "";
  for (const [re, f] of RULES) {
    const m = re.exec(why);
    if (m) return f(...m.slice(1).map((x) => x ?? ""));
  }
  return why;
}
