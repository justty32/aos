eca-aos-kb 的工作筆記：使用者交代的知識庫（proto8/knowledge/）寫法規矩，與做過之後學到、下次照做的步驟；接手的人照這份做。

← [我的地盤](README.md)｜[地盤規矩](../../README.md)

# 使用者交代的規矩（逐字原話）

1. **不寫日期註記，量測數字預設刪**（2026-11-22）：「知識庫那邊，這種"日期註記"要刪掉，量測數字，除非很常用很重要的也都刪掉。」
   - 日期註記＝講「什麼時候改的、以前是怎樣」的句子或子句：`Measured 2026-…`、`On 2026-… X was cut`、`since 2026-…`、`before this was fixed`、`in this batch`、docs 裡的「11-21 起」「（11-21）」「原本……也換成 md 了」、`the user chose on 11-19`。
   - 刪法：句子改成只講現況；整句只在講歷史就整句拿掉。拿掉註記後若句子跟現況對不上（例：docs/01 的樹狀圖靠「11-21 起是 md」補說明），順手改成現在的樣子。
   - 不算註記、不動：範例值裡的日期（`"2026-11-13 09:00"`、ls 範例輸出的時間戳）、格式說明、記版本的機制說明、「not yet」「for now」這種講現在還沒有的功能。
   - 量測數字＝某次量到多少（幾支約幾字、幾 token）。只留 agent 做決定時常用又重要的，留下的不帶日期、而且要重量確定現在還對；量不了就刪。上限、門檻、預設值（3,000 字、35%、max_subagents 4）不是量測數字，不動。
2. **原話是例外**（2026-11-22）：「原話和原話的日期可以留。」
   - 「使用者 11-13「……」」這種引了原話的出處，連日期一起留著（docs/ 約 17 處、knowledge/wf/ 約 16 處都是這種）。
   - 沒有原話、只有「使用者某日決定」的，算日期註記，照第 1 條拿掉。
3. **改的句子不標記；拿不準的補上**（2026-11-22）：「改的句子不用標那個，這種東西都刪掉。拿不準的都補上。」
   - 改過的句子不加「since 2026-11-22」「no longer」「used to」這類話，只寫現況。
   - 回報時列成「拿不準」的缺漏，下一次就補上，不要一直留著。
4. **中文映照版不碰**（2026-11-22）：「kb-zn不用管」——`proto8/knowledge-zh-md/` 不讀、不改、不跟著同步。

# 下次照做

## 範本改了，知識庫跟上

1. `git show --stat <commit>`，再看 `templates/eca-claude`、`templates/eca-pi` 的 `tools.json`、`cli.json` diff；包的內容看 `proto8/py/packs/<包>.json`。
2. grep `proto8/knowledge/`（aos/、wf/、docs/、根目錄的頁）找受影響的工具名、包名、支數；也要搜「eca has」「stock template」「stock agent-fsm」這類講「誰有這支工具」的句子。
3. 每個「X 有某工具」的句子都對照範本的 `tools.json` 確認。eca-claude 和 eca-pi 的 `tools.json` 用 `diff` 比，不要照 README 的說法。
4. 不在範本裡的工具，寫法統一：「no stock template has X (agent-fsm or eca): add it first with `self_tools` `{"op": "add", "path_json": {"$env": "AOS_HOME", "$path": "/lib/tools/agent/X"}}`」。路徑先在 `proto8/lib/` 確認存在：self_hook、clock_register、agent_def、tools_def 在 `/lib/tools/agent/`，jsonx_* 在 `/lib/tools/aos/`。
5. 寫到 eca 的 skills、外掛、settings 來源的地方（aos/body.md 的 CLI 工具清單、aos/cli/eca.md 的 settings 段、aos/definition.md 的 cli.json 欄位），範本那邊還在改的話，先只回報位置，等它交件。

## packs.md 的每包字數表

- 整個知識庫只留這一份量測數字：agent 靠它判斷「加這包划不划算」。kits.md 不另外寫數字，指向 `aos/packs.md#/Tool packs`。
- 不寫量測日期，也不寫某個範本的總字數。
- 工具說明有改動就重量：`python3 -I wf/ws/eca-aos/eca-aos-kb/measure_packs.py /home/lorkhan/repo/aos/proto8`，印出「包 TAB 支數 TAB 字數」，照著換表上的數字。
- 量之前先確認 `py/` 和 `lib/` 的 `_tooldef.json`、`packs/*.json` 一樣（`cmp`），不一樣就是還沒跑 install.py，回報，不要自己跑。

## 交件

- `wf/tools/commit-request claim --line <線名> 檔…`，然後 `submit --line <線名> --files 檔… --msg-file 訊息檔`。commit 訊息第二段附使用者原話，訊息檔放 `~/.aos/scratch/<線名>/`（repo 外）。
- 中文檔名：不要直接拿 `git diff --name-only` 的輸出，git 會把中文檔名轉成 `"\346…"` 這種跳脫字串，claim 會拿到錯的路徑、submit 也會失敗（`does not exist`）。改用 `git -c core.quotePath=false diff --name-only`，或手寫路徑。拿錯的 claim 用 `commit-request release --line <線名> <同樣那串路徑>` 放掉（`release --all` 在這裡被權限擋了）。
- 交之前 `git diff -- 檔` 確認只有自己的字；不 push，不刪檔。

## 範圍與回報

- 只改 `proto8/knowledge/`。發現範本、程式、`wf/` 寫錯（例：py/packs/README.md 寫錯 eca-pi 掛哪幾包）就回報 eca-aos，不自己改。
- 不在活 daemon 上下指令；aos 工具只用自己的 self_*。
- 回報寫繁體中文，先寫結論：commit 雜湊、改了哪頁哪句、拿不準沒改的、替使用者做的選擇（逐條列）。
- 知識庫存檔就生效：一頁一次寫完整，寫英文、短句、一句一件事，只寫核對過的事。
