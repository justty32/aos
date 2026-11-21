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

`gather/system.txt` 是照下面的順序手工拼好的：版本戳、通用層、站台層、gpt 層、角色層。`<KNOWLEDGE>`、`<BOARD>` 換成 site.json 的值，`<OWN_BOARD>` 留空。合計 3,000 字元，是計劃訂的 A 級上限。

改了任何一層，就照同樣的順序重拼，第一行的日期也要換。

**通用層和角色層以產品版為準**：general.A.txt、roles/*.txt 和 proto8/templates/kits/ 的同名檔必須一字不差，改完用 `cmp` 對（例：`cmp general.A.txt ../../../../proto8/templates/kits/general.A.txt`，沒輸出＝相同）。站台層（site.txt、site.gpt.txt、site.json）只在 wf。

**今晚換樹之後**：comm 包（board_read、board_wait）可用，site.json 的 BOARD 值可以改成 `board_read {"who":"user"}`，不再讀檔或跑 aos-frontend。

## 「看」包（gather/）

- **工具**：look、change 只留 write／edit／mkdir、gadgets、todo、mailbox、goal、json 只留讀的、index、self 只留 self_state，共 24 支。這是 wf 這份的數目。產品版（proto8/templates/kits/gather/）多了 comm 包的 board_read、board_wait 兩支（其他三支關掉），共 26 支；那兩支要 PATH 上有 aos-comm，活樹換樹之後才有，所以 wf 這份換樹前不加。
- **沒給的**（看包沒有 shell；要 shell 得另外掛 shell 包，掛了才有）：shell、delete、events、subagent、def、jsonx、kernel_gate；self_tools、self_system 這類改自己的工具也關掉了，所以它沒辦法自己解除限制。
- **腦**：sol-high，走 llm-gpt。
- **固定成本**（每次問腦都會送，11-14 實測字元數）：

| | 工具說明 | system |
|---|---:|---:|
| agent-fsm 範本原樣 | 90,723（55 支） | 約 2,000（各線抄的那份）＋必讀約 40,000 |
| 看包 | 31,215（24 支） | 3,000，沒有必讀清單 |

**工具說明才是最大的固定成本**，砍工具比砍 system 省得多。

## 已知限制（P0）

- **寫檔範圍只是約定**：write_guard、mail_guard 在 P2 才做。在那之前，「只寫自己的 ws」靠 system 的文字，沒有 hook 擋（計劃 03 §9）。
- **沒掛 brain_notify**：活樹 lib 的複本還沒有它，換樹之後再補進被勾清單 hookeds.json（11-21 起 hooks.json 是宣告、不是清單）。
- **其他包還沒做**：「做」「幫」「帶」在 P3；C、D 級的通用層和實測在 P1，要等 ok-release 讓出模型用量。
