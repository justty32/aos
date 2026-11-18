這份大概講 aos agent 出錯時怎麼手動查：先看哪裡、常見原因、怎麼救（試驗 18，11-18 在公司 WSL 用 haiku 故意弄壞幾次對過）。
← [目錄](README.md)

使用者原話：「Hmmmm。還有，當aos agent出錯的時候，如何手動除錯。這個大概講一下就好」

## 結論

先 `aos-agent ctl ls -l` 看表和冷卻，再看那隻 stack 裡的 `stderr.txt` 結尾。表上那句原因常常只是「起不來」，**真正的原因幾乎都在 `stderr.txt` 最後幾行**。下面的指令都站在樹根 `~/aos-home` 打（`-d .stack` 可省，見 [02](02-預設stack與站在agent夾裡.md)）。各檔怎麼判讀見 [17](17-手動看agent狀態.md)。

## 照這個順序查

1. **找得到 daemon 嗎**：`aos-daemon-ctl ls`。報錯就是指錯地方，看下表第 3 列。
2. **表上那列**：`aos-agent ctl ls -l`。`stopped` 加原因＝倒了；`COOLDOWN` 有值＝腦出錯在冷卻。
3. **stderr 結尾**：`tail -5 .stack/procs/ann/stderr.txt`。找 `error:` 那行，第一個字是誰出錯，接著是代號。
4. **信到哪了**：`ls .stack/procs/ann/queue/new` 看還沒被拿的；`cat .stack/procs/ann/letters.json` 看被丟掉的（`dropped`）。
5. **冷卻**：`cat .stack/procs/ann/cooldown.json`（`code`、`reason`；成功一次就刪掉）。
6. **還看不懂**：看視窗 A 的 log（每次 `running`／`done`／`stopped` 一行），或 `aos-agent -t ann open` 進畫面看 claude 本人說什麼。

`stop_cause.json` 只記被 daemon 停的原因（`sleep`、`remove`、`shutdown`、`stuck`），出錯倒掉時沒有它，不用找。

## 症狀表

| 症狀 | 先看哪裡 | 實際看到的 | 怎麼救 |
|---|---|---|---|
| say 之後一直沒回 | `ctl ls`、`queue/new` | `AnswerMissing waited 5 s; 0000…3.… is not answered yet (the letter is in queue/new/)`；等的時候先有一行 warning `nothing is running ann now; it is stopped on the daemon table` | `aos-agent ctl start -t ann`，會說 `1 queued letter(s) will be answered next`，信不會掉，再 `listen --letter 名字` |
| 起來就倒、連倒三次停住 | `ctl ls` 的原因 → `stderr.txt` | 表上：`failed to start: … aos-loop: error: RunFailed run 1: loop.json#/exec failed with exit code 1; restarted 3 times in a row, each exited within 3s; not restarting again`。`stderr.txt`：`aos-eca-turn: error: CfgBad …/cli.json: screen_close_after_s must be a non-negative integer` | 改好定義，`aos-agent ctl start bad`（掛的當下不檢查 `cli.json`，見 [03](03-自訂定義掛上去.md#故意弄壞)） |
| 指錯地方 | 錯誤那行 | 夾不在：`DaemonMissing daemon folder not found: ../nope`；夾在但不是 daemon 的 stack（例如指到 `.stack/procs/ann`）：`StateMissing …/procs_state.json not found (daemon not started yet, or procs_state is off)`；名字打錯：`InstanceMissing annn is not on the daemon table …` | `-d` 指 daemon 的 stack（樹根的 `.stack`），`-t` 用 `ctl ls` 上的名字 |
| 信被丟 | `letters.json` | `LetterDropped … will not be answered: ann dropped it (bad: it was not a valid message)`（往 queue 丟 `{"hello":1}`） | 內容要是 `{"role":"user","content":"…"}`，或直接用 `say`，見 [04](04-aos-post丟信.md) |
| 腦出錯、進冷卻 | `ctl ls -l`、`cooldown.json`、`stderr.txt` 結尾 | `llm.json` 填不存在的模型：第一封 `LetterDropped … (failed: the agent failed after it was handed over)`；`cooldown.json` 的 `reason` 是 `claude exited 1: There's an issue with the selected model (claude-no-such-model). …`；`ctl ls -l` 有 `until 16:46 (1)` | 改好之後等冷卻到（30 秒、1 分、2 分…加倍），冷卻中寄的信會接著答；被丟的那封要重寄 |
| eca 的 claude 自己出錯（用不認得的旗標模擬） | `stderr.txt` 結尾 | `cooldown.json` 只寫 `claude exited 1 with no result in its output:`，`stderr.txt` 才有 `error: unknown option '--no-such-flag'`；`open` 畫面則是 `cli_session: error: CliFailed claude exited right after starting (wrong session id?)` | 改 `cli.json`；沒登入、額度用完也是走這條（`CliFailed`），**沒實測** |
| 畫面開著時卡在權限提問 | `aos-agent -t ann open` 進去看 | **沒實測**。照 [eca-claude 範本說明](../../../../templates/eca-claude/README.md)：範本是 `dontAsk`，不跳框；只有自己加了回 `ask` 的 hook、畫面又開著，才會跳框等人按，看起來像卡住 | 進畫面按掉，`Ctrl+\` 離開 |

`claude` 不在 PATH 時代號是 `CliMissing … is not on PATH`（讀程式得知，**沒實測**；aos 叫的命令寫死是 `claude`，`cli.json` 不能換）。

## 還是查不出來時，收集這幾個

```sh
cd ~/aos-home && S=.stack/procs/ann && aos-agent ctl ls -l > /tmp/dbg.txt; tail -50 $S/stderr.txt >> /tmp/dbg.txt; cat $S/letters.json $S/cooldown.json >> /tmp/dbg.txt; tail -5 $S/history.jsonl >> /tmp/dbg.txt
```

再加上視窗 A 最後幾十行、用的定義夾（`cli.json`、`llm.json`）。**不要貼** `claude/env.json`、`~/.claude.json`、`~/.claude/` 裡的東西，也不要貼任何金鑰；`history.jsonl` 有對話內容，貼之前自己看一眼。

## 發現的問題

1. **`cooldown.json` 的原因有時是空的**：旗標錯時 `reason` 只寫到 `with no result in its output:` 就沒了，真正的 `unknown option` 只在 `stderr.txt`。
2. **listen 會誤報**：冷卻剛到、agent 正要重試那一刻，`listen` 報 `AnswerMissing … bad stopped on an error before answering: …(failure 2 in a row; cooldown until 16:47:34)`，引的是舊的錯；5 秒後同一封 `listen --letter` 就拿到 `OK`。
3. **畫面那條的提示會誤導**：旗標錯時 `open` 說 `wrong session id?`，其實跟對話編號無關。
4. 第一封碰上錯的信直接被丟（`failed`），不會留著等冷卻後重試，要自己重寄。`stderr.txt` 最後一行常是 `RunFailed` 或 `brain_notify: warning`，真的錯在前一兩行。
