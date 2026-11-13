# 02 fable 規劃（原樣保留）：repo 的 wf/ 走入 aos 的目標形狀、去向表、三軸、always-on、搬遷十段、十題待裁、十六條 aos 問題

← [回入口](../wf-into-aos-plan.md)｜上一份：[01-原話與備料](01-原話與備料.md)｜下一份：[03-opus細化](03-opus細化.md)

> 隊長註：下面是 fable（只讀 01 一份）的交稿，一字未改。它標「待驗」的，以及它讀到的備料舊句（「SESSION-LOG 超過 `index_check` 的 4096 規則」——隊長在 fable 開工後才查到那是模板 repo 沒帶進來的規則、已更正 01），在 [03](03-opus細化.md) 逐條驗掉或改掉。

---

# 02 fable 規劃：repo 的 `wf/` 走入 aos

說明：我只讀了 `01-原話與備料.md` 一份。`CLAUDE.md` 要求的 `AGENTS.md` 我照隊長「只讀這一份」沒去讀，所以凡是牽涉 AGENTS.md 實際字句的地方都標了「待驗」。沒寫檔、沒跑指令。

## 0. 一句話結論

- **目標形狀**：repo 的 `wf/` 改用通用版定的工作區形狀（`wf/_index.json`＋`wf/workflows/*.json`＋`wf/knowledge/*.json`）。只放「這個 repo 跟通用版不一樣的地方」，其餘引用知識庫的通用節點，不抄。
- **歷史紀錄**（佔 77%）原地凍結，不轉 json、不搬。
- **活狀態**繼續是 git 裡的檔，因為要跨兩台機器，aos 的 goal／todo／mailbox 都只在單機。
- **always-on** 只走 `AGENTS.md` 一條路，不動 `system.txt`、不加每輪注入的 hook。
- **換法**：下次用到哪個工作流，就先換那個再用。不排時程、不整批。

## 1. 目標形狀

### 1.1 搬完後 `wf/` 長這樣

```
wf/
  _index.json            路由：每個工作流一筆，指向本地節點或直接指向通用節點
  workflows/<名>.json    只有「本 repo 有差異」或「通用版沒有」的工作流才有檔
  workflows/<名>/archive|reports/   舊紀錄，原地凍結（md）
  knowledge/*.json       本 repo 的知識：user、conventions、gotchas、dev-env、team-model、data-files、claims
  knowledge/code-map/    codemap_gen 生成物（最後一段才搬，或不搬）
  SESSION-LOG.md  HANDOFF.md  WAIT_USER.md+wait-user/   活狀態（見第 3 節）
  inbox/                 只剩「樹外／跨機器」用
  session_logs/          照舊
  tools/                 只剩還有人叫的（見第 2 節）
```

理由：通用版開宗明義就是這個形狀，aos 自己不照做等於通用版沒人試過。使用者說「json 比 markdown 好」（D1）。

### 1.2 三層怎麼分

| 層 | 放什麼 | 判準 |
|---|---|---|
| 知識庫 `proto8/knowledge/wf/`（通用版） | 任何工作區都適用的工作流與骨架 | 換一個 repo 還成立 |
| 知識庫 `proto8/knowledge/aos/` | 怎麼用 aos 本身 | 樹裡任何 agent 都用得到、跟哪個 repo 無關 |
| repo 的 `wf/` | 只有在這個 repo 做事才需要的 | 提到 proto8 路徑、兩台機器、使用者對本專案的偏好 |

### 1.3 跟通用版的關係：引用＋只寫差異

- **沒差異**的工作流：`wf/workflows/` 裡不放檔，`_index.json` 那一筆直接指通用節點。
- **有差異**的（例如 decisions 的落點改到 `proto8/thinking`、CONCEPTS、NORMS）：本地節點只有兩塊，「base：通用哪個節點」＋「local：這裡不一樣的幾條」。
- **通用版沒有**的（team-model、aos-teams、digest…）：本地節點寫全文。
- 用的時候發現某條 local 其實到處適用，就搬進通用版、本地刪掉。這就是「邊用邊併」。
- 理由：抄進來改會變兩份，違反「規矩只有一份、放它所屬的那一層」。整份覆蓋則讀的人不知道差在哪。

待驗：
- 通用版 `nodes.json` 的節點格式有沒有「引用別的節點」的欄位；沒有的話要加一個（例如 `base`）。
- `_index.json` 能不能指向 `wf/` 夾外的知識庫節點，以及用什麼寫法才能兩台機器、活樹與 repo 都解得開。

## 2. 去向表

| 東西 | 去向 | 備註 |
|---|---|---|
| decisions、planning、feature-dev、investigation、testing、refactor、tidy（規矩） | 轉成 json 薄節點留 `wf/`，引用通用版 | 通用版已有。testing 的 local 只有一條「本專案只要 build 得過」 |
| `refactor/reports`、`tidy/reports`、各 `archive/` | 凍結不動 | 新紀錄照舊寫 md 進同一個夾。紀錄是給人讀的散文，不轉 json |
| `common/user.md`＋`user/01～03` | 常駐的十來條進 AGENTS.md；細節轉 `wf/knowledge/user.json` | 見第 4 節。01 的 push 授權、02 的日誌寫法、03 的 thinking 寫法按需讀 |
| `common/conventions`、`gotchas` | 轉 `wf/knowledge/conventions.json`、`gotchas.json` | 通用版有骨架，照骨架填 |
| `common/code-map`（256K，生成的） | 原地不動，最後一段再決定搬不搬 | 搬就要改 `codemap_gen.py` 與鐵律 3 的字句。待驗：通用版 `code-map-rules.json` 期待的位置 |
| `common/data-files` | 轉 `wf/knowledge/data-files.json` | 通用版沒有。先留本地，用過覺得通用再併 |
| dev-env | 轉 `wf/knowledge/dev-env.json` | 專屬度很高，全留 repo |
| dispatch README、lessons、driving-cli-agents | 通用的部分併進通用版 `knowledge/dev-dispatch.json`，剩下的做本地薄節點 | 邊用邊併，下次派工時做 |
| dispatch/aos-teams 01～07 | 候選進知識庫 `aos/` | 它講的是怎麼用 aos 的隊伍，不是這個 repo 的事。待驗內容；要使用者裁（題 9） |
| team-model | 轉 `wf/knowledge/team-model.json`，留 repo | 是使用者對模型的偏好，要跟著 git 跨兩台機器 |
| CLAIMS | 先原樣留著，dispatch 換的那次再定 | 待驗：一個月內改過幾次、現役列是不是空的。沒人用就進丟棄候選 |
| inbox 規矩（PROTOCOL、ROSTER、wake-policy、TEMPLATE） | 縮成一個節點 `wf/workflows/inbox.json`，只講「樹外／跨機器走這裡，樹內走 aos 信箱」 | 六個 STATUS 與欄位的定義引用 aos 信箱的說明，不再自己寫一份。wake-policy 由 `mail_notify` 取代 |
| `wf/inbox/done/` 78 封 | 凍結不動 | |
| decide-page.md、`wf/tools/decide_page`、`progress_board`、`forum_*`、`progress_*` | 凍結：可以繼續用，不加功能、不轉形態 | 去留等 user-zone-plan |
| digest、experiments、hackathon、workshop、ideas、spec | 規矩先不動；下次真的要用才轉。archive 凍結 | 一直沒人用的進丟棄候選 |
| resources.md | 丟棄候選 | WORKFLOWS 沒列 |
| TEMPLATE.workflow | 丟 | 通用版 `workflow-template.json` 已有 |
| TEMPLATE.handoff | HANDOFF 瘦身那段一起看，多半併進 HANDOFF 檔頭三行說明 | |
| `session_logs/` | 照舊（md、進 git） | 寫法從 `user/02` 改成引用通用版 `layers.json#/logs` |
| `salvage/` | 丟棄候選 | 10-13 已封存，git 裡找得回 |
| INDEX.md＋INDEX/、WORKFLOWS.md＋parts、STRUCTURE.md | 最後一段由 `_index.json` 取代後刪 | 過渡期見第 7 節 |
| `codemap_gen.py` | 留 | 鐵律 3 在叫 |
| `index_gen.py`、`index_check.py`、`check_anchors.py` | 留 | `proto8/thinking` 每次 commit 都在用。跟「檢查工具不留」的兩種讀法有關（題 2） |
| `index_gen_desc.json`（168K） | 跟 index_gen 一起留 | 待驗：它是什麼、md 變少後會不會跟著縮 |
| `fix_moved_links*`、`metainfo_migrate`、`find_big_lists` | 丟棄候選 | 一次性的搬遷工具 |
| `tabledb*` | 鐵律 6 改指 aos 的 json 工具之後丟 | 待驗：還有沒有檔靠 tabledb 格式 |
| `json_text*` | 待驗它做什麼 | 如果是「json 印成人看的文字」，它就是第 8 節要的最小輔助 |
| `inbox_*.sh`、`notify_watch.sh`、`test_inbox.sh`、`hook-settings-snippet.json` | 丟棄候選 | 一個月 0 改動；`new/ teams/ mail/ orders` 沒有實例。樹外來信用 `ls wf/inbox/*.md` 就夠 |
| `compact_reload.sh` | 留、改小 | 見第 3、4 節 |
| SESSION-LOG、HANDOFF、WAIT_USER | 見第 3 節 | |

沒有任何 repo 的東西要搬去 `~/aos-home/ws/public`、`ws/tools`、`ws/temp`。那三處是單機、不進 git，repo 的規矩與工具要跟著 git 走。它們只收執行期的暫存檔與多隻 agent 共用的程式。

## 3. 三軸活狀態

| 現在 | 變成 | 理由 |
|---|---|---|
| SESSION-LOG.md（20K） | 仍是 `wf/SESSION-LOG.md`，瘦到 4096 bytes 以內 | 已定「跨 session 的事不是 todo、要進 git」；goal 不給 eca |
| WAIT_USER.md＋wait-user/ | 照 user-zone-plan；接上前原樣不動 | D4 |
| `wf/inbox` | 樹內走 aos 信箱（已是現況）；`wf/inbox` 只留樹外與跨機器 | aos 信箱不跨機器 |
| HANDOFF.md（28K） | 仍是 `wf/HANDOFF.md`，改成只留最新一條 | aos 沒有 compact 事件，只能靠 CLI 的 hook |

### SESSION-LOG
- 每條一行：`- [工作流] 一句狀態 → 下一步（連結）`，照通用版 `live-lists.json` 的格式。長的來龍去脈搬到對應的 thinking 檔。
- 格式先不換 json（題 3）。通用版的 `session_start` 是用 grep 數 md 條目，使用者 W11 也裁過活清單「現在不改」。要換就跟通用版一起換。

### WAIT_USER
- 接上前：`WAIT_USER.md` 是唯一的一份，照舊手寫。不做雙寫。
- 接上的方式：新的等使用者事項改成寄信。aos 的 `letter.json` 已有 `decide`、`what`、`not_done` 欄位，四類對得上：
  - 01 要你裁的 → `decide`
  - 02 真機驗證、04 雜事 → `what`／`not_done`
  - 03 試驗場 → 看 user-zone-plan 收不收
- 舊的 38 條不搬（使用者偏好「不做舊版遷移」），留在檔裡，裁一條劃一條，空了就刪檔。
- **要 user-zone-plan 那條線回答的一題**：`~/.aos/user/` 是單機的，WAIT_USER 現在靠 git 兩台機器都看得到。公司機寄的信，使用者在家看不看得到？這題沒答案之前 wf 這邊不切。

### inbox
- 待驗：寄件者「arcagi」（49 封）、「aos」（24 封）是誰，是樹外的另一個專案，還是另一台機器上的自己。
- 如果以後都進了同一棵樹，`wf/inbox` 整個進丟棄候選。

### HANDOFF
- 改成覆寫式，檔裡只有最新一條，舊的靠 git 找。
- `compact_reload.sh` 只印它。

## 4. always-on 規矩怎麼進每一輪

### 結論：只走 AGENTS.md

- **AGENTS.md**：CLI 每個 session 自己載入、進 git、兩台同步，codex 也認。它就是 repo 這一層的常駐入口。
- **不用 `system.txt`**：它在 `~/aos-home/agents/repo-aos/`，單機、不進 git。「repo 的規矩不抄進 system.txt」是現行結論，這份規劃不改它。
- **不加每輪注入**（UserPromptSubmit 或改 `cli_hook.py`）：每輪多花 token，只有 claude 身有，現在也沒有它要解的具體痛點（D3：「玩了自然會想到」）。
- **`aos/rules.json`** 照舊由 system.txt 那句指路，AGENTS.md 不重複。

### `user.md` 只在 compact 後才灌回，是問題

- 一個新開的 session（不是 compact）完全看不到「回覆繁中、只有 main、先結論大白話、調度者不親做」這些，除非它自己去讀。
- 反過來，compact 後一次灌 19.5K（`user.md` 5.9K＋分檔 13.6K），大半是當下用不到的細節。
- 而且 compact 後這個 hook 在 eca 身裡有沒有真的跑，還沒驗過。

### 做法

1. 把 `user.md` 裡每輪都要守的那十來條一行規矩（估 1K 以內）直接寫進 AGENTS.md 的「使用者偏好」小節。
2. 其餘（01 push 授權與出門代決、02 換手與日誌、03 thinking 寫法）進 `wf/knowledge/user.json`，按需讀。AGENTS.md 只列「什麼時候該去讀哪一塊」。
3. 兩邊不重複：進了 AGENTS.md 的那幾條，`user.json` 不再寫。
4. `compact_reload.sh` 改成只印 HANDOFF 那一條＋一句提醒。使用者偏好已經在 AGENTS.md，不用再灌。

待驗：
- AGENTS.md 現在是不是已經有其中幾條（有的話只補缺的）。
- CLI 在 compact 後會不會重新帶入 AGENTS.md。我的認知是會，請隊長實測一次。

## 5. AGENTS.md／CLAUDE.md 最後的輪廓

`CLAUDE.md` 不變，一句「去讀 AGENTS.md」。

`AGENTS.md` 目標 6K 以內：

1. **這是什麼**（兩行）：aos 專案；你多半是樹裡的 `repo-aos`。
2. **開場看三樣**：`wf/SESSION-LOG.md`；等使用者的（接上前是 `WAIT_USER.md`，接上後是 user-zone）；信（aos 信箱會自己通知，樹外的看 `wf/inbox/*.md`）。
3. **鐵律**：2 授權、3 新檔第一行＋commit 前 `codemap_gen --apply`、4、5 大方向是使用者的、6 長條列走 json。不寫自動記憶。
4. **使用者偏好**（十來行，從 `user.md` 搬來）。
5. **路由**（三行）：工作流查 `wf/_index.json`；本 repo 的知識在 `wf/knowledge/`；通用版在知識庫 `wf/`。
6. **什麼時候讀什麼**（一張小表）：要 push → `user.json` 的授權；要 compact → HANDOFF；要派工 → team-model；換機器 → dev-env。

拿掉的：INDEX、WORKFLOWS、STRUCTURE 的指路，`inbox_read.sh`，tabledb 的字眼。

## 6. 可以直接丟的

### 判準（符合任一條就列候選）
- 一個月內沒 commit，而且 AGENTS.md、路由、工具都沒引用。
- 已經有 aos 機制在用、兩邊做同一件事。
- 一次性的搬遷工具。
- 設計了但一個實例都沒有。

### 候選

| 候選 | 符合哪條 |
|---|---|
| `wf/salvage/` | 已封存 |
| inbox 腳本整組、`hook-settings-snippet.json` | 0 改動；`new/teams/mail/orders` 無實例 |
| inbox 的 ROSTER、wake-policy | `mail_notify` 取代 |
| `fix_moved_links*`、`metainfo_migrate`、`find_big_lists` | 一次性 |
| `tabledb*` | aos json 工具涵蓋（鐵律 6 要先改） |
| `resources.md`、`TEMPLATE.workflow` | 沒列入路由；通用版已有 |
| INDEX/、WORKFLOWS-parts/、STRUCTURE.md | 最後一段被 `_index.json` 取代 |
| CLAIMS | 待驗有沒有人在用 |
| digest、experiments、hackathon、workshop、ideas、spec 的規矩檔 | 待驗各自最後一次用是什麼時候。超過一個月沒用的問使用者 |

- 歷史紀錄（archive、reports、session_logs、`inbox/done`）預設凍結，不列入丟棄。要丟請使用者明說。
- 每次刪檔都另起一個 commit，並先給使用者看清單、點頭才刪。

## 7. 搬遷順序

**總規則**
- 每段一個或幾個 commit，直接進 `main`，退回就是 `git revert`。
- 段 3 以後不排時程，觸發條件是「下次要用到這個工作流」，先換再用。
- 轉一個節點時，舊 md 在同一個 commit 刪掉，不留兩份。

| 段 | 做什麼 | 驗收（看得到的） |
|---|---|---|
| 0 驗事實（不改檔） | 把本文所有「待驗」查掉。實測 compact 後 `compact_reload.sh` 在 `repo-aos` 身裡有沒有跑、AGENTS.md 有沒有被重新帶入 | 一張待驗結果表。有哪條推翻了本規劃就回頭改 |
| 1 always-on 補洞 | 常駐偏好進 AGENTS.md，`compact_reload.sh` 改小。`user.md` 暫時只刪掉重複的那幾條，還不轉 json | 開一個全新 session，什麼檔都不讓它讀，問「用什麼語言回、能不能開分支、要不要先問」，答得對。AGENTS.md 在 8K 以內 |
| 2 活狀態瘦身 | SESSION-LOG 瘦到 4096 以內。HANDOFF 改成只留最新一條 | `index_check` 對 SESSION-LOG 不再報超限。手動 compact 一次，印出來的只有一條 HANDOFF |
| 3 第一個工作流：decisions | 建 `wf/_index.json`（只有一筆）、`wf/workflows/decisions.json`（base＋local 落點）。`WORKFLOWS.md` 那一列改指 json。刪 `decisions.md` | 派一隻全新 subagent「幫我記一個決定」，它從 AGENTS → 路由 → 本地節點 → 通用節點走得通，落點說對。`index_check`、`check_anchors` 過。使用者自己看一次這個 json，回報好不好讀（第 8 節的觸發點） |
| 4 其餘通用版已有的 | planning → investigation → feature-dev → testing → tidy → refactor，用到才換 | 每個同段 3。refactor 放最後，因為 `wf/tools` 引用它 33 處，換之前先 grep 工具裡寫死的路徑 |
| 5 知識類 | conventions、gotchas、dev-env、data-files、user 細節、team-model 轉成 `wf/knowledge/*.json` | AGENTS.md 的「什麼時候讀什麼」表每一列都指得到檔。`common/` 被工具引用 19 處，先查 |
| 6 dispatch／aos-teams／CLAIMS | 通用的併進通用版，aos-teams 依題 9 的裁定處理 | 下次派隊時照新節點走完一輪，把撞到的問題記下來 |
| 7 信 | inbox 規矩縮成一個節點，腳本刪（要先點頭） | 樹內寄一封、樹外放一封，兩邊都被看到 |
| 8 WAIT_USER | 等 user-zone-plan 落地才做：新事項寄信，舊檔自然排空 | 依 user-zone-plan 的驗收 |
| 9 收尾 | 沒用到的工作流問去留。`_index.json` 補齊後刪 INDEX、WORKFLOWS、STRUCTURE。清 `wf/tools`。AGENTS.md 改成第 5 節的輪廓。code-map 搬或不搬 | `wf/` 裡除了凍結的歷史與活狀態檔，沒有規矩類的 md。全新 session 只靠 AGENTS.md 找得到任何一個工作流 |

- 段 1、2 跟 json 無關，是最小、最不會壞、馬上有用的，所以排最前。
- 過渡期的路由：`WORKFLOWS.md` 仍是全表；換過的那幾列指向 json，`_index.json` 只有換過的。每個工作流任何時候只有一份規矩。

## 8. 人怎麼讀 json（D1）

- **現在不做新工具。** 節點小，欄位是整句的白話，直接看或叫 agent 念都行。
- 先查 `wf/tools/json_text*.py` 是不是已經做這件事（待驗）。是的話它就是最小輔助，留下來。
- **什麼時候做**：段 3 讓使用者親自看第一個 json 節點。他說「不好讀」那一次才做。
- **做的話最小是**：一支把一個節點印成 markdown 到螢幕的小程式，不產生檔，避免又多一份。因為別的 agent 也抱怨過同類問題，放 `~/aos-home/ws/tools` 共用。
- 網頁、編輯器都不做。等 user-zone 那條線的「agent 搭配網頁」出來再說。

## 9. 要使用者裁的題，以及跟現行規矩的衝突

| # | 題 | 選項與後果 | 推薦 |
|---|---|---|---|
| 1 | 7M 歷史紀錄 | (a) 原地凍結：零成本，`wf/workflows/` 裡 json 與舊 md 夾並存。(b) 集中搬到一個夾：乾淨，但要修上千條連結。(c) 刪：最乾淨，要查只能翻 git | a |
| 2 | 「檢查工具 wf/ 那邊完全不留」怎麼讀 | (a) 模板那套不帶進 aos，repo 留自己的 `index_gen`／`index_check`／`check_anchors`／`codemap_gen`。(b) `wf/tools` 的檢查工具全拿掉：`proto8/thinking` 每次 commit 的索引重生與檢查就沒了，鐵律 3 也要改 | a。現在每個 commit 都在用 |
| 3 | SESSION-LOG 等活清單的格式 | (a) 先瘦身、維持 md，之後跟通用版一起換。(b) 現在就換 json：合 D1，但通用版的 `session_start` 計數與 W11 的裁定要一起改 | a |
| 4 | WAIT_USER 切換時舊的 38 條 | (a) 不搬、自然排空：有一陣子要看兩個地方。(b) 一次全寄成信：一個地方，但要逐條改寫 | a。最終照 user-zone-plan |
| 5 | 常駐的使用者偏好寫進 AGENTS.md | (a) 寫進去：每個 session 都有，AGENTS.md 多約 1K。(b) 維持只在 compact 後灌回：新 session 會漏 | a |
| 6 | 換的節奏 | (a) 用到才換：慢，但每次都有真實使用當驗收。(b) 排時程一口氣換：快，違反「不整批換」 | a |
| 7 | progress_board、decide_page | (a) 凍結，等 user-zone。(b) 繼續加功能：可能跟 user-zone 的網頁重工。(c) 現在丟：使用者手上少一個看板 | a |
| 8 | 鐵律 6 的 tabledb 改指 aos json 工具 | 改：可丟 `tabledb*`。不改：兩套並存 | 改，段 5 做 |
| 9 | aos-teams 01～07 進知識庫 `aos/` | 進：樹裡每隻 agent 都讀得到，但要改寫成不綁這個 repo。不進：只有在這個 repo 的才看得到 | 進，段 6 做，先驗內容 |
| 10 | 很久沒用的工作流（hackathon、workshop、experiments、digest…） | (a) 不轉，規矩 md 留著等用到。(b) 段 9 時逐個問要不要丟 | a 再 b |

**跟現行規矩的衝突**

- **SESSION-LOG 現在 20K**，`index_check` 的規則是 4096 以內。這是現況就違規，段 2 修。
- **D1（json）對上 W11（活清單現在不改、照寫 md）**：我選先守 W11，見題 3。
- **D1 對上歷史紀錄與 session_logs 繼續寫 md**：我的讀法是 D1 管規矩與知識，紀錄是散文。讀錯請更正。
- **「規矩只有一份」**：本規劃沒有改它。AGENTS.md 加使用者偏好是搬不是抄。不碰 `system.txt` 與共用知識庫，唯一例外是題 9 的 aos-teams，那是因為它本來就屬於 aos 層。
- **鐵律 3**：code-map 如果搬位置，鐵律字句與 `codemap_gen.py` 要同一個 commit 改。所以放最後，也可以不搬。
- **CLAIMS 規定 AGENTS.md 與 hub 檔只有調度者能寫**：段 1、2、9 都要由主 session 親手做，不能派出去。
- **8 KB**：只是拆檔工作流的推薦值。待驗 repo 的 `index_check.py` 是不是對所有 md 硬擋 8K；是的話跟使用者 14:56 的話不合，要放寬成只在拆檔工作流裡提。
- **main-session-in-aos 的「樹外照舊 `wf/inbox`」**：保留，沒衝突。

## 10. 規劃中撞到的 aos 問題（只記）

1. hook 沒有 compact 事件，HANDOFF 只能靠 CLI 自己的 SessionStart hook。
2. hook 沒有「每輪前注入」事件；畫面 hook 只記帳，不能吐文字給模型。
3. eca 的 `before_tool` 看不到 CLI 自己的 Bash／Write，所以「commit 前跑 `codemap_gen`」沒辦法用 aos 擋。
4. `aos/rules.json` 沒有程式讀進 prompt，全靠 agent 自己去讀。
5. `system.txt` 與 agent 定義是單機、不進 git，兩台機器會各長各的。
6. 信箱不跨機器，跟 `wf/inbox` 也不互通（`MailboxBad`）。
7. 寄信給使用者還沒有（user-zone 規劃中）；`~/.aos/user/` 單機，跨兩台怎麼辦待答。
8. goal／todo 不給 eca，也不進 git，「跨 session 沒做完的事」在 aos 裡沒有對應機制。
9. 沒有領地／租約機制（CLAIMS 無處可去）。
10. `index_view` 只讀不生成，aos 沒有 `index_gen`／`index_check` 的對應，repo 只能留自己的。
11. 信讀後不是刪就是 archive，版控留痕只有 `keep` 追加 JSONL，不像 `wf/inbox/done` 可以翻。
12. 沒有廣播、topic、團隊信箱、進度板。
13. 家機的 `ws/public`、`ws/tools`、`ws/temp` 都還沒建。
14. 通用版 `knowledge/wf` 缺 HANDOFF、CLAIMS、inbox、data-files、team-model 的對應。節點「引用另一個節點、只寫差異」的寫法有沒有，待驗。
15. repo 的 `wf/_index.json` 要指向知識庫節點時，路徑怎麼寫才能在 repo、活樹、兩台機器都解得開，待驗。
16. compact 後 repo 的 `.claude/settings.json` hook 在 eca 身裡是否照跑，沒驗過（`--settings` 合併「照理並存」）。
