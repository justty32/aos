← [入口](../2026-10-22-ideas.md)｜涵蓋：1. Python 版 aos-inst 刪掉、寬鬆度與錯誤代號照 C++ 版（10-22）、2. 對 fable 的 aos-exec × s6／runit 報告的回應（10-22）｜下一份 [02-3-env-基礎子集與---dotenv-ove](02-3-env-基礎子集與---dotenv-ove.md)

## 1. Python 版 aos-inst 刪掉、寬鬆度與錯誤代號照 C++ 版（10-22）

背景：impls（C++）與 bin（Python）「刻意沒對齊」的五處與兩條寬鬆度差別（[session log 10-21](../../../wf/session_logs/2026-10/2026-10-21.md)）。

使用者原話：

> 對於python版，aos-inst指令可以刪掉了，跟C++版一樣做成lib就好。C++版比較寬鬆這塊，希望python也遵循，錯誤訊息多代號也遵循。子行程直接呼叫我覺得OK。

第 4 點（子行程直接呼叫）頂層問過之後，使用者補：

> Python 版照舊去 PATH 找 aos-exec 就好，只是 C++ 版這樣做我接受

> 因為以後可能會變成一個aos指令，後面接子指令。比如aos exec, aos loop這樣

決定：

1. bin 版刪掉 `aos-inst` 命令列；inst 只剩 Python 庫 `aos_inst.py`，單子一律經 aos-exec 在行程內跑（同 C++ 版 inst 是 C lib）。
2. Python 照 C++ 的寬鬆：設定檔（loop／daemon／fsm）第一行 `#!` 跳過、不再報錯；`.env` 去前導空白只認 ASCII 空白。
3. 錯誤一行照 C++ 多一個代號：`程式名: 代號 原因`（例 `aos-exec: EntryMissing 原因`、`aos-loop: Usage usage: …`）。
4. C++ 版 loop／fsm／daemon 在子行程裡直接呼叫 `run_cli`、不叫 PATH 上的 aos-exec：使用者接受這個差異（以後可能收成一支 `aos` 加子命令）；**Python 版不改**，照舊叫 PATH 上的 aos-exec。

結論：

- 沒有 aos-inst 命令列，只有它才跑得動的兩種寫法也不成立——+x 的 `_exec` 第一行寫 `#!/usr/bin/env aos-inst`（CONVENTION P-28 的 (A)），和小殼 `exec aos-inst _exec.json`（(1) 寫成 `exec aos-exec _exec.json`）；同一個檔拿掉 `+x` 就是兩版都認的 JSON 入口（(B)）。
- bin 的 aos-exec、aos-loop、aos-daemon、aos-fsm 自己的錯都是 `程式名: 代號 原因`，代號照 impls 原始碼（對照在 [bin/README](../../bin/README.md)）；aos-tick 不在 impls，沒加。
- 10-23 使用者看過回報：「都按照建議做。」——inst 單子錯誤訊息兩版字面不同的兩處（原因開頭、`OpenFailed` 帶不帶檔名）照現狀不改。代號的名字照 [命名統合](../2026-10-23-naming.md)（它翻案了這裡「既有 impls 代號沿用、不改名」「aos-tick 不加代號」兩條）。

## 2. 對 fable 的 aos-exec × s6／runit 報告的回應（10-22）

報告：[proto8/notes/aos-exec-s6-runit.md](../../notes/aos-exec-s6-runit.md)；方向題原文在 [04-不適合-衝突-方向題-套件](../../notes/aos-exec-s6-runit/04-不適合-衝突-方向題-套件.md)。

使用者原話：

> 這份報告很有價值，這會減少我們以後的工作量，等於說我們想要的很多功能都有現成輪子，不必重新造。然後方向題這塊，a.我覺得OK，aos-exec先維持只用標準庫。b.看看工作量、看看大家都是怎麼做的。cde.都先不要討論agent

決定：

- (a) aos-exec 先維持只用標準庫、不叫外部程式。
- (b) `.env` 要不要補 unset／多行／引號：先調查工作量與各家做法；調查在 [notes/dotenv-格式比較](../../notes/dotenv-格式比較.md)，使用者看過再記決定。
- (c)(d)(e)（一個 agent 一個 Linux 使用者、入口用 execline 寫、單子長 limits／lock key）先不討論。
