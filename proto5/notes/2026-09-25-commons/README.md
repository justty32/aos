← [notes 索引](../README.md)｜規格 [spec/team/commons.md](../../spec/team/commons.md)｜名冊樣板 [examples/commons/](../../examples/commons/README.md)｜調度層 [playbook/](../../playbook/README.md)

# commons 隊報告：跨團隊公共資料夾＋圖書館員（2026-09-25）

**一句話**：一台機器一份公共資料夾，所有團隊的成員都能唯讀查、都能投稿，但只有圖書館員隊寫得進去；圖書館員隊幾乎全是程式，只有「新投稿跟舊條目很像」才叫一次便宜模型判收不收。真跑 2 次都走完「A 隊投 → 圖書館入庫 → B 隊查到並用在自己單子上」（77 秒、91 秒），另做 1 次圖書館員單跳（deepseek 6 秒判對）。真跑抓到一個弱點（「像」只比標題會漏），已改並加回歸測試。
基底：main `6695892`（開工 `3c7da0d`，中途 rebase 一次）。

## 1. 設計摘要

| 項 | 做法 | 在哪 |
|---|---|---|
| 放哪、誰看得到 | 預設在團隊資料夾的**上一層** `commons/`；名冊三層（出廠開 → 團隊層 `commons` → 成員層 `commons`），開了＝唯讀掛 `/work/commons`＋自動裝 `commons_search`、`commons_submit`＋郵差准寄 `contribute` | [commons.md §1](../../spec/team/commons.md#1-放在哪誰看得到名冊三層)、`aos_agent_init.py` |
| 裡面 | `lessons/`（一條一檔）、`teams/`、`workflows/`、`tools/`（一條一資料夾）、`index.json`（機器用、可手改）、`INDEX.md`（人看）、`inbox/`（投稿） | [§2](../../spec/team/commons.md#2-裡面長怎樣) |
| 投稿 | 成員 `commons_submit` → 自己 outbox 一份 `kind: contribute` → **自己隊的郵差**驗欄位、把附件抄進 `commons/inbox/<號>/`、回信「送到了」 | `on_contribute` |
| 審 | **圖書館員隊的郵差**每輪 `desk()`：必填、大小、路徑、符號連結、執行位（只准 `#!` 開頭）、完全重複 → 退；乾淨 → 直接入庫；像 → 寄信叫圖書館員判 | `desk`、`judge_one`、`similar` |
| 判 | 圖書館員（模板 `librarian`，`may: ["commons_write"]`）只有 `commons_verdict` 一支會動東西的工具：`accept`／`reject`＋一句理由；只收被叫去判的（`NotAsked`） | `on_commons_write` |
| 回信 | 投稿隊的郵差每輪看自己送出去的投稿有沒有 `result.json`，有就寄信給投稿者 | `pending_results` |
| 查 | `commons_search`：純程式查 `index.json`（關鍵字＋標籤），`show: id` 印全文；也能 `read /work/commons/…` | 工具 |
| 人 | `aos-team commons ls／show／search／add／rm／reindex／import／desk` | `cmd_commons` |
| 跟 playbook | playbook＝調度層、進 git、給人讀；commons＝aos 團隊層、在機器上、給 agent 查；`aos-team commons import proto5/playbook` 一鍵匯入（重跑安全） | [§7](../../spec/team/commons.md#7-commons-與-playbook同一件事的兩層) |

沿用既有模式：申請走信（新 kind 登記在 `aos_team_requests.KINDS`）、郵差機械檢查、名冊三層開關照 spawn、json 縮排 2 能手改、CLI 給人。成員這邊的牆**一行沒改**：commons 對所有成員只是多一格唯讀掛載。

## 2. 真跑數字

模型全走 LiteLLM `localhost:4000`：投稿方與 B 隊用 `chatgpt-gpt-6-astra`，圖書館員用 `deepseek-chat`。場地 `~/tmp/commons-try/`（腳本 `exp.py`、`lib_only.py`，daemon 已 `aos down`）。人做的只有腳本裡的兩句 `aos-team ask`（一隊一句）。

| 次 | 結果 | 投稿→入庫 | B 隊完工 | A 隊（lead-a） | 圖書館員 | B 隊（lead-b＋worker-b） | B 的成品引用了 |
|---|---|---|---|---|---|---|---|
| r1 | done | 22 秒送到、**機械直接入庫** | 77 秒 | 4 次、18,533 token | **0 次** | 5＋4 次、48,716 token（B 隊 55 秒） | `lesson-0001` |
| r2（先放一條很像的舊條目） | done | 22 秒送到、28 秒**機械直接入庫**（本該叫模型，漏了） | 91 秒 | 5 次、23,231 token | **0 次** | 5＋3 次、43,689 token（B 隊 61 秒） | `seed-relative-paths`、`lesson-0001` |
| 單跳（不是端到端） | 判對 | r1 那條丟進 r2 的館藏，改過的判法認出「像 `lesson-0001`」 | — | — | **3 次、6,370 token、6.4 秒**：退回，理由「同一件事換句話說，無新做法或新適用場合」 | — | — |

- **每一跳**（`aos_hops.py report`，兩次合計）：等模型 HTTP 佔絕大部分——lead-a 9 次共 37.6 秒、lead-b 11 次 47.8 秒、worker-b 8 次 51.6 秒；每次跑工具約 30 毫秒，fork／import、kernel 開格等機械開銷每跳幾十毫秒。**瓶頸是模型本身**，commons 這層（抄檔、檢查、入庫、查）量不出來。
- **astra 挑經驗挑得對**：notes.md 三條（絕對路徑的坑、寫到 /tmp、便當訂太多），兩次都投第一條、把第二條併進「做法」、跳過便當。
- **B 隊真的用上了**：兩次 checklist 都有一條明寫「依據 lesson-0001：done_when 一律寫相對專案的路徑」，r2 還同時引用了種子條目。
- **r2 抓到的弱點**：種子標題「done_when paths must be relative to the project」、astra 寫「Use project-relative paths in task acceptance checks」——同一件事，標題字重疊 0.21（門檻 0.5），程式當成新的直接入庫。已改成再比「標題＋標籤＋適合」的關鍵字（交集／較小那邊，這一對 0.625），真跑那一對寫進回歸測試 `test_similar_by_keywords_real_pair`。**改完沒有再跑端到端**（限額 2 次），只用單跳驗了圖書館員那一段。
- 館藏長相（r1 入庫的那條）：開頭三行「來自 ta/lead-a、適合…、日期 2026-09-25」＋坑／做法／經驗三段。`from.task` 是空的：這次是 `ask` 直接叫領隊投，沒有單子。

## 3. 圖書館部怎麼當一個 aos 團隊掛進公司

公司＝同一個上層資料夾裡的幾支 aos 團隊（部門），董事＝`human`。圖書館部就是其中一支，跟別的部門平級：

```text
company/
  commons/                 館藏（圖書館部的郵差寫；所有部門成員唯讀看 /work/commons）
  library/                 圖書館部＝一支 aos 團隊
    team.json
    members/librarian/     唯一的成員（正式員工）
    team/…                 信、紀錄（跟別的團隊一樣）
  p-library/               圖書館部的專案（空的；名冊一定要有 project）
  sales/  factory/  qa/ …  其他部門（各自的團隊資料夾＋專案）
```

| 誰 | 種類 | 做什麼 | 資源 |
|---|---|---|---|
| `librarian` | **正式員工**（常駐、服務所有部門；記憶就是館藏本身） | 只判「像既有條目」的投稿 | 1 個正式員工名額；只在被叫時佔一格 llm cpu，一次幾秒；便宜模型 |
| 圖書館部的郵差 | **純機械**（不是員工） | 收投稿、檢查、入庫、叫圖書館員、寫結果 | 跟每個部門的郵差一樣，`aos-team start` 登記、走 default 池 |
| 臨時工 | 不需要 | — | — |

放進初期新創規模（正式員工 ≤ 10、cpu ≤ 20、llm cpu ≤ 5）：圖書館部只用 1 個正式員工名額、平常 0 格 llm cpu。

最小可用的名冊與指令：

```sh
mkdir -p company/library company/p-library
cat > company/library/team.json <<'EOF'
{"project": "../p-library", "members": {"librarian": {"template": "librarian", "mail_to": ["human"]}}}
EOF
aos-team init --target company/library && aos-team start --target company/library
aos-team commons import proto5/playbook --target company/library   # 開館先把 playbook 的經驗匯進來（可省）
```

**跨部門分享的信怎麼寄**：不用部門之間互寄信（`mail_to` 只在一支團隊裡）。任何部門的成員 `commons_submit` → 自己部門的郵差搬進 `company/commons/inbox/` → 圖書館部的郵差審、入庫 → 投稿部門的郵差把結果寄回投稿者。董事直接 `aos-team commons add／rm`。

**其他部門怎麼接**：團隊資料夾放在 `company/` 底下（或名冊寫 `"commons": {"dir": "../commons"}` 指到同一個），跑一次 `aos-team init`。新生的家自動有唯讀掛載與兩支工具；已經生好的家，`init` 會補掛載，工具要 `aos-team rm 名字` 再 `init` 才裝（同 spawn 的限制）。不想讓某部門看：名冊加 `"commons": false`。

## 4. 代裁（附預設，翻案回這條）

1. **commons 放哪**：預設「團隊資料夾的上一層 `commons/`」，名冊 `commons.dir` 可改；沒做成固定的 `~/.aos/commons`。理由：跟團隊資料夾放一起，搬家、刪掉、測試都簡單；「一台一份」靠大家放同一個上層。
2. **「寫信給圖書館員團隊」的做法**：不是跨隊寄信，而是投稿隊郵差把投稿放進公共的 `inbox/`，圖書館員隊郵差去收（§4 的經驗 14）。`inbox/` 對成員唯讀看得到（透明，也讓圖書館員讀投稿全文）。
3. **能不能投稿跟著 commons 開關走**，不看模板 `may`（跟 spawn 一樣是名冊可開關的例外）；只有「判」要模板 `may` 有 `commons_write`，名冊改不到。
4. **完全重複＝種類＋內容＋附件一樣**，標題不算；只換標題也退。
5. **「像」寧可多叫**：同 slug、或標題重疊 ≥ 0.5、或關鍵字交集／較小那邊 ≥ 0.5。多叫一次＝幾秒幾千 token；漏掉＝館藏多一條噪音。
6. **執行位**：只准 `#!` 開頭的檔有執行位；二進位執行檔一律不收。
7. **圖書館員沒開 `notes`**：它的「記憶」就是館藏本身（隨查）；要跨任務筆記，模板加 `notes: true`。
8. **`import` 以 playbook 為準**：同 id 內容變了就換新（playbook 是人寫、進 git 的正本）。
9. **改了別隊的測試期望值**：commons 預設開以後每個成員多兩支工具、多一格掛載，`test_team_init`、`test_team_notes_compact`、`test_team_w2a`（importer 工具表）照新預設更新；task 包整包描述上限 7000 → 9000 字元（沒人全裝，每人多約 1500 字元）。

## 5. 留下一輪

- **改過「像」的判法後，再跑一次端到端**（這次只用單跳驗了圖書館員那段）。
- **commons → playbook** 的 `export`（現在只有 playbook → commons 的 `import`）。
- **從 commons 裝工具**：`tools/<id>/` 能投、能入庫，但「成員拿館藏的工具裝到自己身上」還沒接（該走 `access_request`／人 `aos-agent tools add`，要想清楚誰批）。
- `inbox/` 處理完的投稿會一直留著，沒有封存；館藏大了 `commons_search` 的排名只數字詞，沒有語意。
- 已生好的家要 `rm`＋`init` 才拿到兩支工具（掛載會自動補）。
- 新手試玩（只拿 README／教程 08 §11 玩）。

## 6. 要使用者拍的題

1. **commons 預設開還是關？** (a) 開：每個成員都看得到、都能投，多兩支工具（描述約 1500 字元）；(b) 關：名冊寫 `"commons": true` 的隊才有。**我的預設 (a)**，照原話「隊伍之間交流經驗」。
2. **commons 放哪？** (a) 團隊資料夾的上一層（現在）；(b) 一台機器固定一處（例：`~/.aos/commons`），名冊不用寫也共用。**我的預設 (a)**，公司結構（`company/` 底下放各部門）剛好就是 (a)。
3. **「像」要偏哪邊？** (a) 寧可多叫笨模型（現在）；(b) 寧可少叫、偶爾讓重複的進館。**我的預設 (a)**，r2 顯示漏掉比多叫更傷。

## 7. 測試與審查

- 新測試 `lib/test/test_team_commons.py` 29 條：掛載三層（預設開、團隊關、成員蓋過、重跑 init 拿掉、自訂位置與壞值、commons 在專案裡被擋）、投稿端擋（缺欄位、絕對路徑、`..`、不在、符號連結、太大、經驗附檔）、圖書館端機械擋（缺欄位、壞路徑 4 種、太大、執行位、符號連結、完全重複）、入庫後 index 與 INDEX.md、像的叫一次、真跑那一對、非圖書館員寄判決被郵差退、沒叫判的不收、兩隊＋圖書館員隊經真郵差走一圈、工具與 lib 查法一致、**成員在真 bwrap 牢裡寫 commons 被擋**（對照：自己 outbox 寫得進）、CLI、匯入 playbook 兩次。
- 全套結果、astra 唯讀審查：見下面 §7.1（收尾時補）。

## 8. 沉澱

1. **經驗**（已接進 [playbook/lessons.md](../../playbook/lessons.md)「圖書館」段，第 15～17 條）：
   - 判「重複」別只比標題：同一件事換個說法，標題重疊只剩兩成；要比標題＋標籤＋適合的關鍵字，寧可多叫一次笨模型。
   - 把關的隊先拆「形狀」和「判斷」：形狀全給程式、放在模型前面；模型只拿二選一的窄題、只有回判決的工具，笨模型就夠。
   - 跨團隊交流不開新通道：變成一種新申請，讓兩邊的郵差各做一半，成員的牆一行都不用改。
2. **團隊組織架構**：[examples/commons/](../../examples/commons/README.md)（投稿隊、查閱隊、圖書館員隊三份名冊），已在 [playbook/teams/](../../playbook/teams/README.md) 索引表指過去；掛進公司的做法見 §3。
3. **工作流架構**：[playbook/workflows/commons-flow.md](../../playbook/workflows/commons-flow.md)——投稿→審→入庫→查閱九步，哪些純程式、哪兩處要模型（寫的用強模型、判重複用笨模型）。
4. **可複用工具**：`commons_search`（任何成員查公共資料夾，純程式）、`commons_submit`（任何成員投稿）、`commons_verdict`（圖書館員判決），在 [tools/task/](../../tools/task/README.md)；人用 `aos-team commons …`。
