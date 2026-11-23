# kits — 派 fsm agent 時用的配給包（system prompt＋工具＋功能＋權限），P0 先做「看」包

← [dispatch](../README.md)｜規劃 [onboard-1114](../../../../proto8/thinking/2026-11/14/onboard-1114.md)（計劃 03 §9～§11）｜維護者 repo-aos｜11-14 使用者「都按照推薦」，開 P0

**結論**：派蒐集員（或審稿員）時不要再抄別線的 system.txt，照 [card.md](card.md) 第 1 步把 `gather/` 蓋到 agent-fsm 範本上就好。

## 分層

| 層 | 檔 | 誰改 | 中立嗎 |
|---|---|---|---|
| 通用層 | [general.A.txt](general.A.txt)（A 級：sol、opus） | 以產品版 [proto8/templates/kits/](../../../../proto8/templates/kits/) 為準，先改產品版再抄回 | 中立；必須和產品版一字不差 |
| 站台層 | [site.txt](site.txt)，加上 gpt 才加的 [site.gpt.txt](site.gpt.txt)，記號的值在 [site.json](site.json) | 頂層 | wf 專用，只留在 wf，不進產品版 |
| 角色層 | [roles/gather.txt](roles/gather.txt)、[roles/review.txt](roles/review.txt) | 以產品版為準，同通用層 | 中立；必須和產品版一字不差 |
| 任務層 | 任務書 | 隊長 | — |
| 隊長流程 | [card.md](card.md) | 頂層 | wf 專用，隊員不讀 |

`gather/system.txt` 是照下面的順序拼好的：版本戳、通用層、空行、站台層、gpt 層、空行、角色層。通用層的第 2 步、`BOARD`、`<OWN_BOARD>` 三行換成 site.json 的值，也就是產品版的預設（跟 proto8/templates/tests/kits/test_kits.py 的 `assemble()` 一樣）：知識庫寫「任務書給的那個知識庫夾」，公告板用 `board_read`／`board_wait`。這樣包裡沒有哪台的家目錄，進 git 之後兩台都對；知識庫路徑由任務書給（[card.md](card.md) 第 3 步）。11-22 重拼後合計 3,180 字元，11-23 改站台層那行後 3,173，11-23 改成兩台通用後 3,266。A 級上限是 3,500 字元：計劃原本訂 3,000，但這份 11-22 重拼前就有 3,093，所以放寬（eca-aos 推薦「上限放寬到 3,500」，使用者 11-22 答：「都先按照推薦」）。產品版 proto8/templates/kits/ 的上限是同一個數字，寫在它的 README 和 tests/kits/test_kits.py 的 `SYSTEM_MAX`。

改了任何一層，就照同樣的順序重拼，第一行的日期也要換。

**通用層和角色層以產品版為準**：general.A.txt、roles/*.txt 和 proto8/templates/kits/ 的同名檔必須一字不差，改完用 `cmp` 對（例：`cmp general.A.txt ../../../../proto8/templates/kits/general.A.txt`，沒輸出＝相同）。站台層（site.txt、site.gpt.txt、site.json）只在 wf。

## 「看」包（gather/）

- **工具**：look、change 只留 write／edit／mkdir、gadgets、todo、mailbox、comm 只留 board_read／board_wait（board_set、board_clear、board_ls 關掉）、goal、json 只留讀的、index、self 只留 self_state，共 26 支，跟產品版（proto8/templates/kits/gather/）的清單相同（11-23 對齊）。board_read、board_wait 要 PATH 上有 aos-comm（公司那台 11-23 有：`proto8/bin/aos-comm`、`proto8/lib/packs/comm.json`）；沒有的話只有這兩支會失敗，其他照常。
- **沒給的**（看包沒有 shell；要 shell 得另外掛 shell 包，掛了才有）：shell、delete、events、subagent、def、jsonx、kernel_gate；self_tools、self_system 這類改自己的工具也關掉了，所以它沒有工具能解除自己的限制；但 write、edit 還在、收絕對路徑，改得到自己 stack 裡的 `tools.json`，只靠規矩擋（跟產品版 README 的 Known limits 同一個說法）。
- **腦**：`llm.json` 是 `{"model": "sol", "reasoning_effort": "high"}`（llm kernel 範本 11-21 起沒有 `sol-high`，改成 `sol` 加 `reasoning_effort`），走的 llm kernel 由 `AOS_LLM_KERNEL` 決定。`gather/.env` 不用抄：`AOS_LLM_KERNEL` 由掛的人那邊（上層 daemon 那一列）傳下來；只有還沒改成 `~/aos-home` 一套的機器才需要（見 [03-換機](../../dev-env/03-換機.md)）。
- **固定成本**（每次問腦都會送，11-14 實測字元數）：

| | 工具說明 | system |
|---|---:|---:|
| agent-fsm 範本原樣 | 90,723（55 支） | 約 2,000（各線抄的那份）＋必讀約 40,000 |
| 看包 | 31,215（24 支） | 3,000，沒有必讀清單 |

看包那列是 11-14 量的 24 支；11-23 加了 board_read、board_wait 成 26 支，沒重量。

**工具說明才是最大的固定成本**，砍工具比砍 system 省得多。

## 已知限制（P0）

- **寫檔範圍只是約定**：write_guard、mail_guard 在 P2 才做。在那之前，「只寫自己的 ws」靠 system 的文字，沒有 hook 擋（計劃 03 §9）。
- **沒掛 brain_notify**：活樹 lib 的複本還沒有它，換樹之後再補進被勾清單 hookeds.json（11-21 起 hooks.json 是宣告、不是清單）。
- **其他包還沒做**：「做」「幫」「帶」在 P3；C、D 級的通用層和實測在 P1，要等 ok-release 讓出模型用量。
