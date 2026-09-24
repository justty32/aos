← [本提案](README.md)

# 主方案：claude／codex 當一種 cpu（池）

## 1. 一句話：不用寫新的 cpu，開一個池、寫一張單子就行

cpu 規範已經拍板兩件事（[cpu §9](../../spec/cpu/README.md)）：**工作單的 method 只有 `aos-exec` 一種**、**cpu 的環境就是工作的環境**——
「llm cpu」也不是另一種 cpu，只是環境裡找得到 `aos-llm` 的普通 exec cpu。照同一個道理：

- **claude-cpu＝池名叫 `claude` 的普通 exec cpu**，它的環境（PATH、HOME、登入）裡找得到 `claude`；codex 同理。
- **一張單子＝一份 inst**，argv 就是 `claude -p …` 或 `codex exec …`，stdin 接任務書、stdout 接結果檔。
- kernel 派單、daemon 拉起與重拉、aos-exec 跑與逾時砍、回音與 ack——**全部照現有的走，一行不改**。

另寫一支 `aos-claude-cpu` 主人程式（新 method、自己管 session）也做得到，但它違反上面兩條拍板，而且要重做 daemon 握手、停機階梯、開機對帳，**不建議**。
「零程式」只涵蓋**人手動放單**；要安全取消、控制額度、可靠地接著聊，都要階 1 以後的程式（審查必修 1～4、9）。

## 2. 池怎麼開

proto5（現在）：kernel.json 多一顆，`aos-kernel halt` → 改 info → `boot`（新 cpu 的家會自動補）：

```json
{"cpus": {"k": {"pool": "kernel"}, "0": {}, "llm": {"pool": "llm", "envs": {"AOS_LLM_CONFIG": "/abs/llm.json"}},
          "cc": {"pool": "claude"}, "cx0": {"pool": "codex"}, "cx1": {"pool": "codex"}}}
```

沒寫 `envs`＝整包繼承 daemon 開機那一刻的環境。**用哪份登入要明定**：環境裡若剛好有 `ANTHROPIC_API_KEY`／`OPENAI_API_KEY`，它們可能改走 API 計費而不是訂閱（哪個優先**未實測**）；建議在這顆 cpu 的 `envs` 裡明寫要的那幾個、其他 `clear`。
proto5-2（池式）：`aos-kernel cpu add --pool claude --count 1`，下一格生效。**池裡幾顆＝最多同時幾張單子在跑**；它只限「同時幾張」，不限總額度（見 [cost-safety §1](cost-safety.md#1-錢花在哪)）。

## 3. 一張單子怎麼寫

inst 的路徑規則（[inst-posix fields §3.1](../../spec/inst-posix/fields.md)）：**只有 `cwd` 相對 inst 所在的資料夾**；`stdin`／`stdout`／`stderr` 與之後的 `$ref` 都相對**解出來的 `cwd`**（也就是工作區）。
所以任務書與輸出**一律寫絕對路徑**，每張單子一個資料夾，不然會去工作區找 task.md、不同單子互蓋輸出：

```json
{"_metainfo": {"_type": "posix", "_version": 1},
 "argv": ["claude", "-p", "--output-format", "json", "--model", "sonnet",
          "--permission-mode", "acceptEdits", "--permission-prompts", "none", "--safe-mode",
          "--allowedTools", "Bash(make test)", "--disallowedTools", "Bash(git push:*)"],
 "cwd": {"$env": "AOS_WS"},
 "stdin": "/abs/jobs/j1/task.md",
 "stdout": {"$opt": "mkdir", "$val": "/abs/jobs/j1/out/result.json"},
 "stderr": {"$opt": ["append", "mkdir"], "$val": "/abs/jobs/j1/out/err.log"}}
```

```json
{"_metainfo": {"_type": "posix", "_version": 1},
 "argv": ["codex", "exec", "--json", "-m", "gpt-6-astra", "-s", "read-only", "--skip-git-repo-check", "-"],
 "cwd": {"$ref": "/abs/ws.json#/repo"},
 "stdin": "/abs/jobs/j2/task.md",
 "stdout": {"$opt": "mkdir", "$val": "/abs/jobs/j2/out/events.jsonl"},
 "stderr": {"$opt": ["append", "mkdir"], "$val": "/abs/jobs/j2/out/err.log"}}
```

放單：`aos-kernel add /abs/jobs/j1/inst.json --once --pool claude --timeout-ms 1800000 --name j1`（**不給 `--wait-ms`＝放了就走**；`--wait-ms 0` 是「馬上逾時」，不是不等）。
**指示詞的用處**：`cwd` 用 `$env`／`$ref` 指工作區（換工作區只改一處）；模型名用 `$env` 讓不同 cpu 帶不同預設。argv 的元素**不當路徑改寫**，`codex -o FILE` 要寫絕對路徑。
`acceptEdits`＋`--permission-prompts none` 只准改檔；**要跑測試就得在 `--allowedTools` 明列那幾句 Bash**，不然一律被拒。claude 的任務書走 stdin **未實測**；不行就在 argv 最後放「讀 /abs/jobs/j1/task.md 並照做」。

## 4. 回音與結果

once 的回音只有執行狀態（`code`、`kind`、`timed_out`、`stopped`），答案在 stdout 檔——跟現在 aos-llm 一樣。**讀完回音要 `aos-kernel ack`**，不然回音檔一直留在 `K/responses/`。
`code=0` 再讀結果：claude 的 json 有沒有錯誤旗標（欄位名未實測）；codex 照官方文件看 `turn.completed`（成功）或 `turn.failed`，答案在 `item.completed` 的 agent_message，**不能撿最後一行當答案**（事件名是官方契約，本機未實跑）。額度用完、登入過期時退出碼可能是 0，只看退出碼不夠。

## 5. 上下文怎麼延續

cpu 本身不記事：**延續放在一個「cli 家」**，裡面 `session.json` 記最後一次**確認成功**的 session id。
下一張單子多帶：claude `--resume <id> --fork-session`；codex `codex exec fork <id> -`（子命令 help 沒列 `-s`／`-C`，但把它們放在子命令**前面**可以解析，實際有沒有套用待驗，見 [cli-facts](cli-facts.md)）。

**提交規則（審查必修 9）**：`session.json` **不由單子自己寫**。單子只把「這次的 session id＋答案」寫進自己資料夾的結果檔；
**收回音的那一方**（`aos-cli`）看到 kernel 判成功（`code=0`、沒逾時、沒被停、輸出驗得過）才把 session 往前推。
這樣「單子寫完 session 但被逾時砍在退出前」不會發生不一致：kernel 判失敗，session 就不前進。

每次都 fork 的用處：失敗那次的腦內紀錄不會混進下一次。但**fork 不回復已經改掉的檔**；結果不明（`Interrupted`、`stopped`、`Removed`）時 cli 家停在 `busy`、**不自動重送**，等人看過工作區再說。
同一個 cli 家一次只准一張單子在跑（兩張接同一個 session 會分岔），由 `say` 擋；取消還沒確認停下之前也維持 `busy`。

## 6. 使用者怎麼跟它講話

**階 0（不寫程式）**：自己寫 inst＋task.md、`aos-kernel add … --once`、`aos-kernel ls` 看、讀 `out/`、`aos-kernel ack`。能用，手續多，也沒有 session 與額度控制。

**階 1（薄包裝 `aos-cli`，手感照 `aos-agent`）**：

```text
cc-alice/                      一個 cli 家
  info.json   {"_metainfo": {"_type": "cli_agent", "_version": 1}, "cli": "claude", "model": "sonnet",
               "cwd": "../ws", "kernel": "/abs/K2", "pool": "claude", "timeout_ms": 1800000, "flags": [...]}
  session.json  最後一次確認成功的 session id
  turns/0003/   task.md、inst.json、out/（每說一次話一個資料夾，單號持久）
```

| 指令 | 做什麼 |
|---|---|
| `aos-cli init --cli claude｜codex --target 家 [--cwd DIR]` | 生家與預設旗標 |
| `aos-cli say "…" --target 家 [--wait]` | 寫 `turns/N/`、照 info 產 inst（絕對路徑、`--resume`／`fork`）、放單；前一張沒收＝`busy` |
| `aos-cli run TURN_DIR` | **單子的 argv[0]**：跑 claude／codex、解析輸出、寫 `turns/N/out/result.json`（不碰 `session.json`） |
| `aos-cli listen`、`status` | 看回話、看在哪；**順手收回音**：驗結果、推 session、ack |
| `aos-cli cancel`、`continue` | 取消（§7）、解連敗暫停 |

## 7. 長任務、逾時、取消

- **逾時**：單子的 `timeout_ms`（建議 30 分鐘起跳），到了 aos-exec 砍整個 process group（先 TERM、2 秒後 KILL）。它自己 `setsid` 出去的砍不到。
  codex 有一個「共用的背景 server」（頂層 help 的 `--no-daemon`），工作是不是真的在我們砍得到的那組裡**要驗**，不能只看 CLI 被砍了。
- **取消是個洞**：`aos-kernel rm` 對正在跑的 once **當下就回 `Removed`**，但那顆 cpu 上的 claude 照樣跑完、照樣改檔（[kernel §2](../../spec/kernel/syscall.md)）。
  要真的停只能叫 daemon 砍那顆 cpu（proto5 往 daemon 家放 `kill` 單，[daemon methods](../../spec/daemon/methods.md)；proto5-2 `aos-daemon kill --pool claude cc`）。砍掉後 daemon 自己不重拉，**但 kernel 下一格會補 spawn**（`ensure_cpus`）。
  **競態**：查到「單子在 cc 上」到真的砍下去之間，單子可能已經跑完、cc 已經換跑下一張——照 cpu 名砍會誤殺別張。寬限期內跑完的也可能照常成功。
  所以 `aos-cli cancel` 只能是「盡力」：砍之前再確認那顆 cpu 手上還是這張；之後結果一律當「不明」、保持 busy。**長遠要 kernel 提供「按單號砍」**。
- **停機**：`aos-kernel halt` 等正在跑的做完——半小時的單子會讓 halt 報 `Timeout`（預設只等 30 秒），單子照跑。
- **排隊**：一顆 cpu 一次一件，池滿了在 kernel 排隊；排隊時間不算逾時。

## 8. 工具

它們**用自己的工具**（Read／Edit／Bash／網路），不接 aos 的工具檔——這正是用它們的理由。範圍靠三層：
旗標（`--tools`、`--allowedTools`、`--restricted`、codex `-s`）＜ 工作目錄（`cwd`、`--add-dir`）＜ 牢（bwrap，見 [cost-safety](cost-safety.md)）。
想讓它叫 aos 的指令或別的 agent，走 skill 或 MCP，見 [others §4](others.md#4-反過來讓它們用-aos)；注意 `--safe-mode` 會把 skill 與 MCP 一起關掉，所以要分兩種設定：**封閉任務**（safe-mode）與**准用 aos 工具**（不開 safe-mode、`--strict-mcp-config` 只給指定的）。

## 9. 失敗

照 exec 回音分：`timed_out`、`stopped`、`kind=aos`（inst 讀不到或壞掉，那次根本沒跑）、`kind=child` 且 `code≠0`（**找不到 claude 的 127 也在這一類**，[cpu methods](../../spec/cpu/methods.md)）、`code=0` 但輸出說失敗。
aos-cli 寫進 `turns/N/out/` 並在 `status` 印一句白話；**連續三次失敗就不再放新單**（照 aos-agent 的連敗暫停），`aos-cli continue` 解。
注意這只管 aos-cli **自己要放的**；人事先直接用 `aos-kernel add` 塞進 kernel 的單子不會因此停（見 [cost-safety §1](cost-safety.md#1-錢花在哪)）。

## 10. 跟 exec cpu 差在哪

| | 一般 exec cpu 的工作 | claude／codex 的單子 |
|---|---|---|
| 時間 | 毫秒到秒 | 分鐘到半小時 |
| 花費 | 免費（本機） | 吃訂閱額度或 API 錢 |
| 副作用 | inst 寫的那些 | 它自己決定改什麼檔、跑什麼指令 |
| 要什麼 | inst 給的 | 網路、登入檔、HOME |
| 重跑安全嗎 | 看工作 | **不安全**：重做一次、改兩次檔、花兩次錢 |
| 取消 | 很少需要 | 常要，而且現在做不乾淨（§7） |

所以**不要把 claude 單子登記成反覆行程**：反覆行程失敗（含 `Interrupted`）會被排回去再跑。
`--once` 的 `Interrupted` kernel 原樣交回交件者、不重跑（[kernel terms](../../spec/kernel/terms.md)），要不要重送由人決定。
