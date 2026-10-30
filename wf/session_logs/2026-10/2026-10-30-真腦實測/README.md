# 10-30 晚 真腦實測（WAIT_USER 親手試，頂層代跑）

← [session log 10-30](../2026-10-30.md)｜[WAIT_USER](../../../WAIT_USER.md)｜[SESSION-LOG](../../../SESSION-LOG.md)

使用者打遊戲沒空親手試：「你能繼續推進嗎」「litellm 我開了，盡量都用 gpt 的」。由一個 opus agent 在家機 Manjaro 照 [WAIT_USER](../../../WAIT_USER.md) 各條代跑；腦一律 GPT（`chatgpt-gpt-6-sol`，範本原樣跑時是範本寫的 `chatgpt-gpt-6-luna-low`），工作區都在 scratchpad、跑完不進 git。叫 claude 的那層（第 6、8 項）用 `claude -p --model haiku`。impls 是當晚重建的（全套 788／0 fail）。

`R=~/repo/simple_tools/aos/proto8`。換 sol 的做法：把 `demo/agent-nia` 複製一份、`parts.json`／`tools.json` 的 `../../lib` 換成絕對路徑、`endpoint/litellm` 的模型換 sol（parts.json 的 env 蓋過外面的環境變數，只能改檔）。

| # | 項目 | 結果 | 一句話 |
|---|---|---|---|
| 1 | aos-round 帶 agent-nia 接真腦 | 過 | 照 WAIT_USER 原指令一字不差跑通 |
| 2 | queue 與停著等 | 過（指令過時） | WAIT_USER 的 PATH 少 aos-fsm（10-30 晚 agent-nia 改叫 aos-round 後要它）；補上就過 |
| 3 | 掛到 daemon（daemon-3） | 過 | 照原指令 |
| 4 | 信箱模式 daemon（daemon-2） | 過 | 照原指令 |
| 5 | agent-nia 接真腦（10-28 那條） | 指令過時，併進第 1 項 | `new/q1.txt` 是舊協議，PATH 也少 aos-fsm、aos-post |
| 6 | Claude Code 經 aos-mcp 用 ask_round 問 agent-nia | 過 | haiku 叫工具、agent-nia 用 sol 答，agent 不常駐 |
| 7 | say／listen／aos-chat | 過（指令過時） | agent-dan 是舊協議、say 說不到；換 `demo/agent-dan-q` 就過；互動手感留使用者 |
| 8 | aos-eca-hub 與試驗場四隻 | 非互動部分過 | 家機 `~/code/playground` 是 10-29 舊版，在 scratchpad 照 eca § D 重建；`open`／畫面那段留使用者 |
| 9 | 沙箱 root、nvim、cli-tools attach | 沒跑 | 照交代留使用者 |

## 1. aos-round 帶 agent-nia 接真腦

```sh
export PATH=$R/impls/aos-exec/bin:$R/impls/aos-loop/bin:$R/impls/aos-fsm/bin:$R/impls/aos-post/bin:$R/bin:$R/extras/human/bin:$PATH
mkdir -p ws/.stack && cd ws && echo litellm > .stack/endpoint.txt
echo '{"role": "user", "content": "現在幾點？17乘23是多少？"}' | AOS_WS=$PWD aos-parts --file $R/demo/agent-nia/parts.json run queue $R/demo/agent-nia push
aos-exec --ws . $R/demo/agent-nia; echo $?     # 0，約 7 秒
```

trace：idle→think→act→think→act→think(10)→finish→idle(10, next null)，`next` 欄讀得懂；`aos-listen --last 1`＝「現在是 UTC 13:44。17 乘 23 等於 391。」；usage 三行（luna-low）。一格一格叫（`aos-round` 重複 7 次、sol）：state 依序 think、act、think、finish、idle，第 6 次起退 10，答「391」。

## 2. queue 與停著等

原指令 PATH 沒有 `impls/aos-fsm/bin` → `aos-round: CommandMissing aos-fsm 起不來 …`、loop 退 1、`aos-listen` 一直等。補上 aos-fsm、`.stack/endpoint.txt` 寫 litellm 後：答「現在是 UTC 2026 年 10 月 30 日 13:46。」、`--last 5` 一問一答、`queue/` 只剩 `order.json`。

停著等（sol 版 `ROUND_ON_EMPTY=idle`、loop.json 拿掉 max 加 `interval_ms` 300）背景開著：兩句各答；寫 `{"paused": true}` 後 `aos-listen --status` 印 `loop phase paused`、再 say 的信留在 `queue/new`（`new 1`）；放行後答出；寫 stopped 後 loop 退 0。

## 3、4. daemon-3、daemon-2

照 WAIT_USER 原指令。daemon-3：第一次 `ls` 有 tick_loop、tick、tick_max1、tick_exec，`rm tick_max1` 後不見，退 0。daemon-2：回信 `{"applied": true}`，名單 sam、tick、tock；`loops_removed tick` 後剩 sam、tock；stopped 後退 0。

## 5. agent-nia 接真腦（10-28 那條）

原指令跑出 `CommandMissing aos-fsm`、退 1、沒有 `out/`。就算 PATH 補齊，10-30 起輸入是 queue，`new/q1.txt` 不會被看；現行寫法就是第 1 項，所以併進去。

## 6. Claude Code 經 aos-mcp 問 agent-nia

工具小資料夾 `ask_nia/`：`.env` 寫 `ASK_AGENT=<sol 版 agent-nia，endpoint/default 換成 openai>`，`_entry`／`_tooldef.json`／`_metainfo` 捷徑指 `lib/aos/ask_round/`；另一個 agent 資料夾 `aos-tools add` 它；`mcp.json` 指 `extras/ai_tools/bin/aos-mcp --ws <ws> <agent 資料夾>`。

```sh
echo "用 mcp__aos__ask_nia 工具問那隻 agent：『17乘23是多少？順便告訴我現在幾點』…" | \
  env -u CLAUDECODE … claude -p --model haiku --mcp-config mcp.json --strict-mcp-config --allowedTools mcp__aos__ask_nia
```

回：「17 乘 23 是 391。現在是 UTC 時間 2026 年 10 月 30 日 13:48…」；`calls.jsonl` 一行 code 0、7119 ms；被問的工作區在 `<stack>/ask_nia/`，usage 兩行 sol。注意：`--allowedTools` 吃多個值，題目要從 stdin 給，放在後面會被吃掉（`Input must be provided…`）。

## 7. say／listen／aos-chat

`aos-say` → `aos-exec --ws . demo/agent-dan` → 退 0 但信留在 `queue/new`，`aos-listen` 一直等（agent-dan 讀 `new/`、寫 `out/`，human README 有寫「舊協議的範本說不到」）。換 `demo/agent-dan-q`（外面設 `AOS_BRAIN_URL`、`AOS_BRAIN_MODEL=chatgpt-gpt-6-sol`）：答「17 乘 23 是 391。」、`--last 3` 對。`printf '你好，用一句話自我介紹\n/status\n' | aos-chat --trace demo/agent-dan-q`：印 `· idle 7ms · think 2286ms · act 18ms · idle 退 10`、回答、`/status` 一整段，退 0。互動的打字、Ctrl-D 手感沒試。

## 8. aos-eca-hub 與試驗場

家機 `~/code/playground` 是 10-29 的舊試驗場（agent-bob-1 等，沒有 `env.sh`），新四隻只在 WSL。在 scratchpad `pg/` 照 [eca § D](../../../../proto8/thinking/2026-10-30-eca.md#d-第-9-步試驗場怎麼重做codeplayground不進-git) 建：bob-1＝eca-claude 複本（`ECA_ON_EMPTY=stop`、不給 max、`prompt.txt`、cli.json 加 Write＋`acceptEdits`、haiku）；bob-2＝eca-claude 原樣只換 haiku；nia-idle＝第 2 項的 sol 停著等版；dan-pause＝agent-dan-q 複本；hub＝空名單的信箱模式 daemon。**都叫真的 claude -p**（haiku），不是假 CLI。

- bob-1：`aos-exec --ws ws/ws1 bob-1` 10 秒退 0，`result.md`＝「17 乘 23 的答案是 391；今天的心情是平靜又專注…」，`--last 1` 看得到，`transcripts/` 有 symlink。過。
- bob-2 與 nia-idle 用一字不差的同一組指令（背景 aos-exec、say 兩句、paused 後 say、`--status`、放行、stopped）：兩隻都記得「阿土」、paused 時 `new 1`／`phase paused`、放行後答「再見，阿土！」、退 0。`--status` 最後一格 bob-2 是 `turn`、nia-idle 是 `finish`（aos-round 之後不再叫 round）。過。
- 掛 daemon：`aos-eca-hub add --template bob-2 --name bob2 ws/ws2h` 建 `.stack` 捷徑；`ls` 顯示收起了、對話 id；cd 進去 say／listen 經 daemon 答得出；`state` 對；`stop` → `eca_archive/bob2-<UTC>/`（「CLI 的對話 1 份換成了複製」）、工作區 `.stack` 捷徑不見。過。
- dan-pause（真腦 sol）：看 `state.txt` 變 think 就寫 paused，6 秒後 `--status` 印 paused、`cur 1`、最後一格 think；改 `system.txt` 再放行，act、idle(10) 收工。停在格與格之間是對的；但 think 已經拿到回答，改 system.txt 只影響下一次問腦（這題沒叫工具，所以沒看到效果）——要看到「照改過的走」得問一題會叫工具的。
- **沒跑、留使用者**：`open`（第一次的信任提問、畫面、Ctrl-] 跳出）、畫面開著時 say 走 pty、`close`。

## 發現（都沒改程式）

1. **aos-round 找不到 aos-fsm 的訊息會誤導**：印 `No such file or directory: b'/home/lorkhan/bin/aos-fsm'`——那是 PATH 最後一格，不是它真的去找的地方；看起來像路徑寫死。小事，記 SESSION-LOG。
2. **say 給舊協議的 agent 不會報錯**：`aos-say` 後 `aos-exec … demo/agent-dan` 退 0、信原封留在 queue，`aos-listen` 只說「沒有程式在跑」一直等。人會以為 agent 壞了；README 有寫，但跑的當下沒提示。記 SESSION-LOG。
3. WAIT_USER 有三條的指令 10-30 晚就過時了（PATH 少 aos-fsm、`new/q1.txt`、agent-dan）——aos-round 第 4 步換過去時沒回頭改親手試的指令。
4. 不是 aos 的：LiteLLM 的 `chatgpt-*` 會自稱「Codex」（agent-dan-q 自我介紹答「我是 Codex」）；`lib/base/clock` 給 UTC，所以 agent 報的是 UTC 時間。
