以選項 A（範本改成 AOS_HOME 寫法、自帶 .env、copy-out 整支拿掉、文件教 cp -r）為主線：刪掉 copy-out 之前要先解決的每一項，各附解法、級別、工量。

← [入口](README.md)｜上一份 [03 .env](03-env.md)

# 刪 copy-out 前要解決的（使用者 11-10：「copy-out能刪就刪」）

**一句話**：9 項，沒有一項會擋住，lv1、lv2 都不用碰。lv4 只改 kernel 範本的 JSON 資料，不改程式；lv3 只有 agents new 一處，可以先不改。

## 擋路清單

| # | 擋什麼 | 解法 | 級別 | 工量 |
|---|---|---|---|---|
| 1 | 範本 JSON 裡指進 repo 的相對字串、`AOS_CD`＋`..`（[01](01-現況盤點.md) 的表） | 照 copy-out env 的輸出直接改範本：agent-fsm 和 eca-claude 的 `tools.json` 各 3 條，reviewer 的 `fsm.json` 4 條加 `tools.json` 9 條 | lv5 | 小：純 JSON，可以拿 copy-out 產出來對照 |
| 2 | 同上，kernel 範本 | llm-kernel 的 `kernel.json` `exec` 1 條、`endpoints` 4 條、demo 劇本參數 4 條、`endpoints/litellm/_entry` 1 條；llm-team 1 條；daemon-judge 1 條；procs-kernel 1 條 | **lv4 的定義資料**（只改 JSON；aos-llm-kernel 本來就收，不改程式） | 小 |
| 3 | **symlink 10 條**（agent-fsm、eca-claude 的 `tools/memory*/`） | 推薦：拿掉 `tools/` 夾，`tools.json` 的 memory 改成 `{"path": {"$env":"AOS_HOME","$path":"/lib/agent/memory"}, "env": {"AOS_MEMORY": {"$env":"AOS_HOME","$path":"/knowledge/aos"}}}`，`interfaces.json` 的 `memory` key 拿掉（沒找到讀它的程式）。README 改寫成「要可寫的庫：`env` 的 `AOS_MEMORY` 指你自己的庫；要寫入就照同樣寫法登記 `lib/agent/memory_write`」。其他做法見 README 第 1 題 | lv5 | 小到中：兩份範本、兩份 README、templates/docs/01 和 02 的 memory 段 |
| 4 | 沒設 `AOS_HOME` 時，錯誤藏在 stderr.txt | daemon-root、llm-kernel 的 `.env` 加 `AOS_HOME=${AOS_HOME}` 必填檢查（r8）；daemon-root `.env` 加 `AOS_LLM_KERNEL` 預設（[03](03-env.md)） | lv5、lv4 資料 | 小 |
| 5 | **測試**在原地或 `copytree` 用範本，而且大多先把 `AOS_*` 全清掉 | 這些測試的環境補 `AOS_HOME=<這份 proto8>`。已知的有：templates 的 test_daily、test_paths_move；agent-fsm 的 test_selfheal、test_cooldown（另有 test_integration、test_cells 等要看）；reviewer 的 test_reviewer；`lib/aos/review_round/tests/test_round.py`、`lib/aos/measure/tests/test_fake_agent.py`、`lib/agent/agents/tests/test_copy_repo.py`；`extras/gitignore-check`、`extras/image-move-check`。`test_copy_out.py` 整支刪掉；test_daily、test_paths_move 的 `build()` 改成 `cp -r`＋env。paths_move 的 absolute／relative 兩輪，改成「`.env` 寫絕對」「`.env` 寫 `${AOS_WS}/…`」 | 各級的測試檔（只改測試，不改程式） | 中：約 12 支，大多只是在 clean_env 加一行 |
| 6 | `lib/agent/agents`（工具 `agents` 的 `new`）共用 `copy_def.py` | **短期不用動**：對改好的範本 `Rewriter` 改寫 0 處（實測），`new` 照舊。要刪 `copy_def.py` 時：`build_def` 拿掉 repo 範本那個分支，只留 `copytree`；`proto8_mode` 和那行提醒一起拿掉；同時刪 `lib/agent/tests/test_copy_def.py`、改 `agents/tests/test_copy_repo.py`（README 第 3 題） | **lv3**（選做） | 小：約 20 行加 2 支測試 |
| 7 | `install.sh` 會把 `templates/copy-out` 連進 `~/.local/bin` | 拿掉那一行和兩處註解。已經裝過的機器會留一條斷掉的 `~/.local/bin/copy-out`：`install.sh --uninstall` 會清掉指進 repo 的斷連結，但重跑 install 不會清；文件寫一句「刪掉 `~/.local/bin/copy-out`」就好 | lv6 | 小 |
| 8 | **文件**：提到 copy-out 的 md 約 12 份（templates 的 README 和各範本 README、templates/docs/02、daemon-root README、lib/agent/agents README、cmd/aos-agent/docs/04-搬家 的 02～04、NORMS 07-hub 那份「AOS_ 變數的四種性質」、wf 的 dev-env、code map 兩冊、HANDOFF／SESSION-LOG），加上**知識庫 `knowledge/aos/cli/tools.md`**（agent 讀得到）。two-machines 11 和 15 的照抄步驟 | 改成 `cp -r $AOS_HOME/templates/名 目的地`；code map 重新生成 | 文件 | 中 |
| 9 | 「絕對、相對寫法」的需求（使用者 11-10 午：「要用相對位置、絕對位置、環境變數指定都可」） | 不靠 copy-out 也能做到：`.env` 寫 `AOS_HOME=/絕對路徑`＝absolute；寫 `AOS_HOME=${AOS_WS}/../aos/proto8`（相對專案）＝relative；當然也能自己把檔裡的指示詞改成字串。目前只有 test_paths_move 和文件在用這兩種模式，沒有使用者資料依賴它們（proto8 不寫遷移）。已經用 copy-out 抄出去的副本是 `AOS_PROTO8／AOS_HOME` 寫法，不受影響（改名那隊另外處理） | — | 只要改文件 |

**真的擋住、短期刪不掉的：沒有。** 最接近的是 #3，不先處理 symlink，「教 `cp -r`」就是錯的教法（r3）。不想改範本結構的話，繞法是文件改教 `cp -rL`（r1 實測通），但打錯成 `cp -r` 就會壞。

## 指令長相

**A（主線，從零到問一題）**：

```sh
export AOS_HOME=~/repo/aos-tools/proto8          # 或寫進下面兩份 .env，就 0 個 export
mkdir -p something/stacks llms/stacks
cp -r $AOS_HOME/kernel/llm-kernel llms/def
cp -r $AOS_HOME/templates/daemon-root something/defs
cp -r $AOS_HOME/templates/agent-fsm something/defs/ann
(cd llms && aos-exec --stack stacks/llm def &)          # 另一個殼也行
cd something && aos-exec --stack stacks/root defs &      # 根的 .env 給好 AOS_LLM_KERNEL 預設
aos-agent -d stacks/root ctl add --auto-restart -w . defs/ann
aos-agent -d stacks/root -t ann say "hello"
aos-agent -d stacks/root -t ann listen
```

**B**：同 A；想把檔裡的 AOS_HOME 改成絕對或相對路徑，再跑 `copy-out --template … --proto8 absolute|relative 目的地`。

**C（現況）**：

```sh
export AOS_HOME=~/repo/aos-tools/proto8 AOS_LLM_KERNEL=$PWD/llms/stacks/llm
copy-out --template kernel/llm-kernel llms/def
copy-out --template daemon-root something/defs
copy-out --template agent-fsm something/defs/ann
# 之後同 A 的起、掛、問
```

| | 要改的檔與級別 | 工量 | 風險 |
|---|---|---|---|
| A | 上表 #1～#9（lv5、lv4 資料、測試、文件、lv6；lv3 選做） | 約半天：範本加測試約 2 小時，文件約 2 小時 | 漏改的測試會因為 `AOS_HOME is not set` 而紅，這種錯一看就懂；漏改的文件教錯指令；第 1 題選 (c) 的話，`cp -r` 打錯就壞 |
| B | 同 A，但不刪 copy-out，也不刪 test_copy_out | 比 A 少一點 | copy-out 對新範本的 env 模式改寫 0 處，留下來只剩 absolute／relative 兩種模式還有用 |
| C | 不用改 | 0 | 使用者原本的疑問（為什麼不能直接 cp）沒有解決 |

## 代定的細節

- 指示詞一律寫 `{"$env": "AOS_HOME", "$path": "/<proto8 底下>"}`，`$path` 開頭帶 `/`，跟 copy-out 的 env 輸出一字不差。
- kernel demo 劇本裡的 `{"$env":"AOS_CD","$path":"../../templates/agent-fsm"}` 也改成 AOS_HOME 寫法：抄出去以後才不會指錯，kernel/docs/01 那句「只在直接跑 repo 裡這份定義時對」跟著刪。
- llm-team 的 `endpoints.*.kernel`（相對 `AOS_STACK`）不動，它指的不是 repo。
- agent 範本不帶 `.env`，只有會被 `aos-exec` 直接起的根範本（daemon-root、kernel/llm-kernel，以及 llm-team、daemon-judge、procs-kernel 這三份 kernel）才帶必填檢查。
- 範本 `.env` 不放 `AOS_HOME` 的實際值，只放一行註解，示範 `${HOME}/repo/aos-tools/proto8` 的寫法。
- `.py` 的 import 不動：抄出去以後靠 `install.sh` 的 `aos-proto8.pth`，跟現在一樣；沒跑 install.sh 的人照舊會看到 `ModuleMissing`。
- 範本的 `README.md` 和 `tests/` 照樣會被 `cp -r` 帶走（copy-out 也會帶 README、會帶 tests）。文件寫一句「`tests/` 可以刪」就好，不另外做排除。
- 這份報告用的變數名照使用者 11-10「AOS_PROTO8改成AOS_HOME」，跟改名那隊的工作樹一致。
