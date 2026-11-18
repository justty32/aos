set-def 走 kernel 排隊、外部 MCP 沒驗的三項：家機乾淨 clone＋暫存樹＋真 claude haiku 實跑的紀錄（線 verify-night-1118，只驗不改程式）。

← [11-18](README.md)｜被驗的：[set-def 新做法](../14/misc-1114.md#1-fx-1set-def-改成停拔同一個-stack-掛回)、[下午改動獨立驗證](下午改動-獨立驗證.md)、[外部 MCP 接真 server](../13/external-mcp-real-server.md)「沒驗」那句｜驗的版本 HEAD `2f1a150c7`

線 `verify-night-1118`（opus）在家機（Manjaro）做。暫存在 `~/.aos/scratch/verify-night-1118/`（沒刪）：`repo/`（本機 HEAD 的 clone、自己跑過 `install.py`，退 0、29 支指令）、`tree/`（從 `templates/start-eca` 抄的樹）、`mcp/`（假 MCP server 與它的 log）。所有 aos 指令經 `t.sh`（bash、清掉全部 `AOS_*`、只設 `AOS_HOME`＝暫存 clone 的 proto8、`source` 樹的 `env.sh`）跑；`~/aos-home` 與活的 daemon 沒碰。真腦用 `claude` 2.1.327、`haiku`，一共問了 6 句（ann 2 句、cat 4 句，每句都只是短答）。

## 先講結論

| 項目 | 過不過 | 一句話 |
|---|---|---|
| set-def 走 kernel、有空格（跑著／停著／睡著） | ✅ 過 | 照說明走，跟直連一樣；表、狀態欄、畫面、到期單都對 |
| 兩個已知顯示小毛病（工作區欄變 `-`、到期單殘留） | ✅ 沒出現 | `2b4320644`（cooldown-1118 件 B）已修，這條路徑也好了；那筆當時沒在真 eca 上跑，這次補到 |
| set-def 走 kernel、**格滿要排隊** | ❌ 不過（新發現） | 掛回那封信被排進隊、set-def 逾時報錯、agent 不在表上；信之後才被套上，會把人照提示手動掛回的那隻**停掉** |
| set-def 走 kernel、名字不在 `allowed` | ⚠️ 照說明，但先拔了才被拒 | 拔掉之後才被拒，agent 留在表外；錯誤行教的手動掛回指令照抄還是走同一個 kernel、還是被拒 |
| claude 的 `except`→`--disallowedTools` | ✅ 過 | 被排掉的那支整支不在 claude 的工具清單裡；拿掉 `except` 就出現（對照組） |
| CLI 自接的 server 一起來就退 | ✅ 過（aos 看得到） | stack 的 `stderr.txt` 多一行 warning；回合照走，腦也知道那台沒連上 |
| CLI 自接的 server 中途死 | ✅ 回合不壞；aos 看不到 | claude 自己把那次叫當錯誤、下一次叫自己重起 server；aos 這邊沒有任何一行 |
| 經 aos 的 server 卡住不回 | ✅ 過 | 60 秒後收掉整個行程群、回錯誤給腦，腦接著做下一步 |

要你裁的只有排隊那題（見文末）。

## 件 1：set-def 走 kernel 排隊

### 場子

- 樹：`cp -r $AOS_HOME/templates/start-eca tree`；`agents/ann`、`agents/bob` 是 eca-claude（`llm.json` 改成 `haiku`），`agents/ann-v2`、`ann-v3` 是 ann 的逐字抄本（給 set-def 換用）。
- kernel：`cp -r templates/kernel/procs-kernel tree/kern`，`aos-daemon-ctl -d .stack add $PWD/kern` 掛到根上（表上一列 `kern running`）。`kern/kernel.json` 各情境改寫（站每輪重讀）。
- 走 kernel＝`AOS_KERNEL=tree/.stack/procs/kern/requests`、`AOS_DAEMON=tree/.stack`，指令不帶 `-d`（帶 `-d` 就不走 kernel）。下面寫 `K aos-agent …` 就是這樣跑；`-d .stack` 的是直連、拿來看表。
- 先確認走 kernel 讀表通：`K aos-agent ctl ls` 列出五列，`kern/requests/reply/` 有回信（站把 `procs_state_path` 那封轉給 daemon、daemon 答了）。

### 1a 有空格（`{"max_running": 20, "queue": true}`）

| 情境 | 指令 | 實際 | 預期 | 結果 |
|---|---|---|---|---|
| 跑著、開著畫面 | 先 `aos-agent -d .stack --target ann open --detach`，再 `K aos-agent ctl set-def ann agents/ann-v2` | 1.8 秒；印 `closed`、`definition of ann is now …/ann-v2; it runs it now (stack … kept)`，退 0。表上 `running`、pid 換新、`def` 是 `../agents/ann-v2`、`ws` 在；畫面的 socket 當場不見；history 行數不變。再問「上一句回了哪個字」→ `apple`（對話接得上） | 照 `--help` | ✅ |
| 停著、stop 留了到期單 | 開畫面 → `K aos-agent ctl stop ann`（`claude/screen_close.json` 出現）→ `K aos-agent ctl set-def ann agents/ann-v3` | 1.2 秒；`… it stays stopped; ctl start runs it`。`ctl ls` 那列工作區欄**有值**（不是 `-`）；`aos-daemon-ctl ls` 的 ws 欄也有；`screen_close.json` **已清掉**；畫面關了 | 照說明；兩個小毛病要看有沒有 | ✅（兩個都沒出現） |
| 睡著 | `K … ctl start ann`、`K … ctl sleep ann`、`K … ctl set-def ann agents/ann-v2`，再 `K … ctl wake ann` | `no screen (already closed)`、`… it stays asleep; ctl wake (or a daemon restart) runs it`；表上 `sleeping`、`def` 換了、`ws` 在；wake 後 `running`、用 v2 | 照說明 | ✅ |

兩個小毛病沒出現的原因：`2b4320644`（cooldown-1118 件 B 的 (2)(3)）已經改了 daemon 的 `reconcile.cpp`（add＋stop／sleep 同一封信的列也寫 ws）與 `aos-eca-screen close`（關畫面順手清到期單）。那筆的訊息寫「eca 真身都沒跑」，這次在真 eca＋走 kernel 上看到兩個都好了。

小地方（不擋事）：走 kernel 時一次 set-def 印三行 `aos-agent: warning: routing via AOS_KERNEL=…`（停、拔、掛回各寄一封信，各印一次）。

### 1b 格滿、開著排隊（`{"max_running": 4, "queue": true}`）

站數「在跑的」是數根那張表上 `running`／`stuck` 的列，`_clock`、`_sweeper`、`kern` 自己就佔三格。站判 `procs_added` 一律當「要一格」（`py/tools/aos/kernel/procs_rules.py` 的 `verdict`），不管同一封信裡有沒有帶 `procs_stopped`／`procs_slept`。set-def 掛回那封信就是 `procs_added`（加上停著的帶 `procs_stopped`、睡著的帶 `procs_slept`），所以：

| 情境 | 指令 | 實際 |
|---|---|---|
| 停著的 ann、格滿（`kern`＋兩個系統＋bob＝4） | `K aos-agent ctl set-def --timeout-s 8 ann agents/ann-v3` | 先拔掉了；掛回那封信**進了隊**（`kern` 的 `queue.json` 有一列 `names: ["ann"]`）。8 秒後兩行錯：`aos-post: error: RegretFailed letter not in new/ (already taken, or never there): …`，接著 `aos-agent: error: DaemonFailed no reply to the set-def letter … within 8 s; could not withdraw it; it may still be applied; inspect adjacent …/kern/queue.json; ann was detached and is not on the table now; attach it again by hand: aos-agent ctl add -n ann -s … -w … …/agents/ann-v2`。表上沒有 ann |
| 接著騰出一格 | `K aos-agent ctl stop bob` | 排著的那封出隊、套上：ann 回到表上、`stopped`、`def` 是 v3（set-def 要的）。回信 `{"applied": true}` 落在 `kern/requests/reply/`，沒人收 |
| 同上，但中間照錯誤行的提示直接掛回 | 再做一次（換 v2、`--timeout-s 5`，同樣進隊）→ 照提示 `aos-agent -d .stack ctl add -n ann -s … -w … agents/ann-v3`（直連，掛上、`running`）→ `K aos-agent ctl stop bob` 騰格 | 排著的那封這時才套上：**手動掛回、正在跑的 ann 被停掉**（`ann stopped`，root log 13:06:17 running → 13:06:20 stopped）；`def` 留在手動掛的 v3，set-def 要的 v2 沒換上；回信照樣 `{"applied": true}` |
| 跑著的 ann、隊裡已經有人在等 | ann 跑著、格滿；`K aos-agent ctl start --on-queued ok bob`（`queued bob at position 1`）→ `K aos-agent ctl set-def --timeout-s 8 ann agents/ann-v3` | set-def 停 ann 騰出的那一格被排在前面的 bob 拿走；ann 的掛回信排在後面，同一種 `DaemonFailed`、ann 不在表上。再 stop bob，ann 才用 v3 回來、`running` |

預期：說明寫「停著的換完還是停著」「中間有一小段不在表上」，沒寫會排隊；照理停著／睡著的掛回不需要一格。**不過**：格滿時 set-def 會失敗，而且失敗後 agent 不在表上、要等到有格才自己回來；錯誤行叫人「手動掛回」，照做的話，之後那封遲到的信會把手動掛回的那隻停掉。錯誤行本身有寫 `it may still be applied` 與 `queue.json` 的位置，但提示的指令沒提醒先等或先處理排著的那封。

另外：`aos-post: error: RegretFailed …` 那行是內部收回信件失敗的原話，直接漏到使用者眼前，在 `aos-agent` 自己那行之前；看的人會以為是兩件事。

### 1c 名字不在白名單（`{"allowed": ["bob"], "max_running": 20, "queue": true}`）

- `K aos-agent ctl set-def --timeout-s 8 ann agents/ann-v2`（ann 跑著）：先停、先拔，掛回才被站拒：`aos-agent: error: AddRejected the set-def letter was refused: NameUnknown ann not in allowed; ann was detached and is not on the table now; attach it again by hand: aos-agent ctl add -n ann -s … -w … …/agents/ann-v3`。提示裡的舊定義是對的。
- 照錯誤行原樣打（環境裡還有 `AOS_KERNEL`）：一樣走 kernel、一樣 `AddRejected … NameUnknown ann not in allowed`。要加 `-d .stack` 直連才掛得回去（或改站的設定；我是把 `allowed` 拿掉再打同一行，掛回、`running`）。
- 預期：說明寫「掛回失敗＝錯誤行教你怎麼手動接回」，這點照說明。不完美的地方：`set-def` 不先問站准不准就拔（kernel 沒有「先問」的介面，這是設計上的限制，不是 bug）；提示的指令沒帶 `-d`，在同一個殼照抄會再被同一站擋。

## 件 2：外部 MCP 沒驗的三項

### 場子

- 假 server：`mcp/fake_mcp.py`（自己寫的 stdio MCP，一行一則 JSON-RPC；工具 `echo`、`secret`、`boom`＝收到就 `os._exit(9)`、`hang`＝永遠不回；帶 `--exit-at-start` 一起來就印一行 stderr、退 3；每個動作記進 `FAKE_MCP_LOG`）。不連網、不裝東西。
- agent `cat`：`agents/ann` 的抄本（eca-claude、haiku、每句上限 0.5 美金），`cli.json` 加 `"mcp_servers": ["mcp/fk.json", "mcp/fkc.json"]`；`fk`＝正常、`"except": ["secret"]`，`fkc`＝`--exit-at-start`。經 aos 那台另一份 `mcp/fa.json`（名字 `fa`，同一支 server），`aos-mcp-import --only echo,hang mcp/fa.json`（`imported 2 of 4 tools`），再把 `mcp/fa.json` 加進 `cat/tools.json` 的 `$override`。
- 一句一問：`aos-agent -d .stack --target cat say "…"`、`listen --timeout-s 180～300`；看 `stack/claude/live.jsonl` 的 init 事件與 tool_result、stack 的 `stderr.txt`、server 的 log。

### 2a claude 的 `except`→`--disallowedTools`

- 第 1 句：「列出名字以 mcp__fk 開頭的工具；叫 mcp__fk__echo；試著叫 mcp__fk__secret」。
- 實際：init 事件的 `tools` 裡 fk 只有 `mcp__fk__boom`、`mcp__fk__echo`、`mcp__fk__hang`，**沒有 `secret`**；腦答 `mcp__fk__secret is not in my tool list`；echo 回 `Echo: hi`。server log 只有一次 `call echo`。
- 對照：把 `fk.json` 的 `except` 拿掉，下一句的 init 事件出現 `mcp__fk__secret`，腦也答「yes」。
- 預期：被排掉的那支 claude 看不到、叫不到。✅ 過（claude 2.1.327 的做法是整支從清單拿掉，不是叫了才拒）。

### 2b CLI 自己接的 server 一起來就退

- 同一句裡（`fkc` 一起來就退）：init 事件 `{"name": "fkc", "status": "failed"}`；stack `stderr.txt` 多一行 `cli_session: warning: external MCP server fkc was not connected when claude started (status failed)`；回合照走、回信照到；腦自己也說 `the fkc server failed to connect (CONNECTION_CLOSED)`。claude 一次開場會試起兩次 fkc（log 兩行 start）。
- 預期（11-13 修過的 P3 (a)）：aos 印一行 warning、不擋回合。✅ 過。
- 坑：這行只在 stack 的 `stderr.txt`；`listen` 收到的回答裡沒有，`ctl ls` 也看不出。不去看那個檔就不會知道。server 自己印的 `fake_mcp: crashing at start on purpose` 哪裡都沒留。

### 2c CLI 自己接的 server 中途死

- 第 2 句：「叫 mcp__fk__boom；再叫 mcp__fk__echo」。
- 實際：boom 那次 tool_result 是 `Connection closed`（`is_error: true`）；下一次叫 echo，claude 自己重起一台 server（log 換了 pid 538144 → 538383），回 `Echo: after`。回合照走、3.5 秒；stack `stderr.txt` 沒有任何新行（只有 fkc 那行舊的又印一次）；`ctl ls` 照舊 `running`。事後沒有殘留的 server 行程。
- 預期：中途死只有 CLI 自己知道，aos 補不到（11-13 判斷）。✅ 照預期：腦拿得到錯誤、回合不壞；aos 這邊看不到，server 自己的 stderr（`dying mid-call`）也沒留。
- 沒驗：畫面那條（互動模式）的一起來就退與中途死；那條沒有 init 事件可讀。

### 2d 經 aos 的 server 卡住不回

- 直接叫（不經腦）：`aos-tools --file agents/cat/tools.json call fa_hang '{"text":"x"}'`（`AOS_WS`、`AOS_STACK` 指暫存夾）→ 62 秒後退 1，stderr **兩行一樣的** `mcp_tool: error: CommandFailed MCP server request timed out`；server 行程有收掉。`fa_echo` 照回 `Echo: direct`。匯入時凍結的 `_metainfo.timeout_ms` 是 60000。
- 經真 claude（第 3 句）：「叫 mcp__aos__fa_hang；再叫 mcp__aos__fa_echo」。實際 65 秒做完：hang 那次腦拿到 `aos-mcp: error: CommandFailed fa_hang timed out (60 s); its process group was killed`，接著 echo 回 `Echo: after`；server log 一起來就收到 `call hang`、62 秒後下一台才起來答 echo；事後沒有殘留的 server 行程；`ctl ls` 照舊 `running`。
- 預期：60 秒後收掉、腦拿得到錯誤、照走下一步。✅ 過。
- 坑：(1) 這 60 秒腦整個卡住（這一輪別的事都不能做），要短就手改那支的 `timeout_ms`（sync 會保留手改的值）；`timeout_ms` 改成 0（不限）那種沒試。(2) 直接叫時同一行錯印兩次（`mcp_tool` 與外層各印一次），經腦那條看到的是 aos-mcp 換過的字（`fa_hang timed out (60 s)`），兩條字不一樣，查 log 時要知道。(3) 錯誤代號是 `CommandFailed`；11-13 的紀錄寫 `ServerFailed MCP server request timed out`，現在換了。

## 收尾

- 根 `aos-daemon-ctl -d ~/.aos/scratch/verify-night-1118/tree/.stack shutdown`＝`5 procs asleep`；記下的根行程（pid 472428 起的 `aos-exec root`、daemon 472447）都不在了；`pgrep -af verify-night-1118` 沒有東西；假 server 沒有殘留；aos 畫面的 tmux 都由 aos 自己開（帶它自己的 `-f …/claude/tmux.conf`，不讀 `~/.tmux.conf`），set-def／shutdown 後 socket 都不在。我沒有自己開 tmux。
- 殘留：`~/.claude/projects/` 多了這棵樹工作區那份 transcript（真腦那幾句）。

## 要你裁的

**格滿時 set-def 走 kernel 會排隊、失敗後 agent 不在表上**（1b）。可以怎麼處理（我沒動）：

- 甲：不改程式，只在 set-def 的 `--help`、知識庫寫明「走 kernel 而且站有 `max_running`＋`queue` 時，格滿會失敗；失敗後先看站的 `queue.json`，排著就等它套上，不要手動掛回」。
- 乙：站（`procs_rules.py`）對「`procs_added` 同一封又帶同名 `procs_stopped`／`procs_slept`」不算一格（加了也不會跑）。停著、睡著的 set-def 就不會排隊；跑著的照樣可能排在別人後面。
- 丙：set-def 走 kernel 時，掛回那封信帶 `queue_wait_ms`（例如跟 `--timeout-s` 一樣），逾時由站拒掉、不會晚到；錯誤行的手動掛回提示再加 `-d <daemon>`（走 kernel 照抄會再被同一站擋，1c 也是）。

推薦乙＋丙的後半（提示加 `-d`）：乙讓「停著的換完還是停著」名副其實，丙的後半是錯誤行照抄就能用。
