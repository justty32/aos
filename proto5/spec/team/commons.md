← [team](README.md)｜報告 [2026-09-25-commons](../../notes/2026-09-25-commons/README.md)｜調度層的另一半 [playbook/](../../playbook/README.md)

# 跨團隊公共資料夾 commons ＋ 圖書館員團隊

2026-09-25 第 1 版。程式：[`lib/aos_team_commons.py`](../../lib/aos_team_commons.py)；工具 [`tools/task/commons_search`](../../tools/task/commons_search)、[`commons_submit`](../../tools/task/commons_submit)、[`commons_verdict`](../../tools/task/commons_verdict)；模板 [`templates/librarian/`](../../templates/librarian/)。

一句話：**一台機器一份公共資料夾，所有團隊的成員都能唯讀查；誰都能投稿，但只有圖書館員那一隊寫得進去。** 圖書館員隊幾乎全是機械：格式、大小、路徑、重複都由郵差用程式判，只有「新投稿跟舊條目很像」這一種才叫模型，而模型只能回「入庫／退回＋一句理由」。

```text
A 隊成員 commons_submit ──► 自己 outbox 一份 kind: contribute
A 隊郵差 on_contribute：驗欄位 → 附件從 outbox 抄進 commons/inbox/c-<隊>--<申請 id>/ → 回信「送到了」
圖書館員隊郵差每輪 desk()：
   ├─ 機械檢查不過（缺欄位、路徑、太大、執行位、符號連結、完全重複）→ 寫 result.json（退回）
   ├─ 乾淨、也不像既有條目 → 直接入庫（寫條目檔＋index.json＋INDEX.md）
   └─ 像既有條目 → 寫 judge.json、寄一封「請判」給圖書館員（模型）
          └─ 圖書館員 commons_verdict → kind: commons_write → 郵差照判決入庫或退回
A 隊郵差每輪看自己送出去的投稿：result.json 出來了就寄信給投稿者（入庫附路徑；退回附理由）
B 隊成員 commons_search（純程式查 index.json）→ read /work/commons/<路徑> 看全文
```

## 1. 放在哪、誰看得到（名冊三層）

- 位置：預設是**團隊資料夾的上一層** `commons/`（`~/teams/a/`、`~/teams/b/` 共用 `~/teams/commons/`）。名冊可改：`"commons": {"dir": "~/aos-commons"}`（相對團隊資料夾，可用 `~`）。
  「一台機器一份」靠大家把團隊資料夾放在同一個上層、或都寫同一個 `dir`；程式不強制。
- 掛法：開了的成員，牢裡多一格 **`/work/commons`，一律唯讀**（保留掛點名，名冊與模板的 `mounts` 不能用 `commons`）。
- 三層，後面蓋過前面（跟 [spawn.md〈誰能生〉](spawn.md#誰能生生了要不要人批名冊逐成員) 同一套）：
  1. 出廠值：**開**。
  2. 團隊層 `team.json` 頂層 `commons`：`true`／`false`／`{"on": 布林, "dir": 路徑}`。
  3. 成員層 `members.<名>.commons`：`true`／`false`。
- 開了＝三件事一起：唯讀掛 `/work/commons`、task 包自動多裝 `commons_search`、`commons_submit`、郵差准它寄 `contribute` 申請。關了三件都沒有。
- 改了開關跑 `aos-team init`：已生的家會**補掛或拿掉** `commons` 那一格（只動那一格）；工具要換得 `aos-team rm` 再 `init`（同 spawn 的限制），但工具的設定快照與郵差的權限每次都重看，所以**關掉**不必重生家就生效。
- `aos-team init` 會建好資料夾與空的 `index.json`；commons 不准在專案或團隊資料夾裡面（工人寫得到專案；團隊資料夾是控制資料）＝`BadCommons`。

## 2. 裡面長怎樣

```text
commons/
  index.json        機器用的索引（縮排 2，人可以用文字編輯器改，改完跑 aos-team commons reindex）
  INDEX.md          人看的索引（每次入庫、rm、reindex 重生；別手改）
  lessons/<id>.md   經驗：一條一檔
  teams/<id>/       名冊樣板：README.md（說明）＋附檔（例：team.json）
  workflows/<id>/   工作流：README.md＋附檔（例：單子與 done_when 樣板）
  tools/<id>/       可複用工具包：README.md＋附檔（腳本可以有執行位）
  inbox/<投稿號>/   投稿：submission.json、files/、（叫模型判時）judge.json、（有結果時）result.json
  .lock             入庫、rm、import 共用的一把鎖
```

`index.json`：

```json
{"_metainfo": {"_type": "aos_commons_index", "_version": 1},
 "entries": {
   "handoff-relative-paths": {
     "type": "lesson", "title": "Use project-relative paths in done_when", "tags": ["handoff", "done_when"],
     "fits": "leads writing handoff tickets", "summary": "前 160 字…", "path": "lessons/handoff-relative-paths.md",
     "from": {"team": "ta", "member": "lead-a", "task": "t-0003"}, "date": "2026-09-25", "sha256": "…"}}}
```

**每條都有**：來自哪一隊哪個成員哪張單（`from`；人加的是 `human`，匯入的是 `playbook`）、適合什麼活（`fits`）、日期（`date`）。條目檔開頭也印這三行，人直接看檔就知道。

## 3. 投稿（`commons_submit` → `kind: contribute`）

| 鍵 | 必填 | 規則 |
|---|---|---|
| `type` | 是 | `lesson`／`team`／`workflow`／`tool` |
| `title` | 是 | 一行，≤ 120 字 |
| `tags` | 是 | 1～8 個，每個 1～24 字、不含空白與 `, / \`；存成小寫 |
| `fits` | 是 | 適合什麼活，一行，≤ 300 字 |
| `body` | 是 | 內容（markdown），≤ 16000 字；經驗就是這一段，其他種類變成條目的 `README.md` |
| `files` | 否 | 只有 `team`／`workflow`／`tool` 能附：相對 **自己 outbox** 的路徑（例 `commons-staging/x/run.sh`），≤ 20 個；不准 `/`、`~` 開頭、`..`、空段、控制字元、`README.md` |
| `task` | 否 | 來源單號 `t-0001` |
| `slug` | 否 | 想要的條目 id（`[a-z0-9][a-z0-9-]{0,47}`）；撞名就自動加 `-0001` |

- **成員寫不到 commons**（牆）：`/work/commons` 唯讀，工具只往自己 `/work/outbox` 放申請與附件。
- 投稿者那隊的郵差 `on_contribute`：驗欄位；附件一檔一檔抄進 `commons/inbox/<號>/files/`——realpath 要在寄件人的 outbox 裡、不是符號連結、是一般檔、一檔 ≤ 64 KB、總共 ≤ 256 KB；有執行位的照抄執行位。先抄進 `.<號>.tmp` 再改名，`submission.json` 最後寫（圖書館員只看有它的）。紀錄 `team/commons/<號>.json`（冪等：同一份申請再來回同一份動作）。
- 投稿號＝`c-<團隊資料夾名>--<申請 id>`，不會撞。

## 4. 圖書館員隊：機械審、只在「像」的時候叫模型

名冊裡有成員的模板 `may` 含 **`commons_write`**（內建模板 `librarian`）的團隊，就是圖書館員隊；它的郵差每輪（投完信之後）走一次 `desk()`，拿 `commons/.lock`：

| 檢查（機械） | 不合 |
|---|---|
| 必填欄位、型別、長度、`lesson` 不能附檔 | 退回 `MissingField`／`FormatInvalid`／`TooLarge` |
| 附件路徑（同上） | `BadPath` |
| 附件是一般檔（不是符號連結、資料夾） | `BadFile` |
| 一檔 ≤ 64 KB、總共 ≤ 256 KB | `TooLarge` |
| **執行位只准給 `#!` 開頭的檔**（可執行檔以外不准有執行位） | `BadMode` |
| 內容（種類＋body＋附件的 sha256）跟既有條目**完全一樣** | `Duplicate`（只換標題也算） |
| 跟既有條目**像**：同 `slug`，或同種類且標題字重疊 ≥ 0.5（英數字詞＋中文單字） | 不退，**叫模型** |
| 以上都沒事 | **直接入庫**（`by: machine`） |

- 叫模型：寫 `inbox/<號>/judge.json`（給誰、像哪幾條、信文），寄一封 `REQUEST` 給圖書館員，信裡有新投稿與像的條目的路徑。每輪都重給這一封、郵差 notice 靠 id 去重（崩在寫 judge 與寄信之間也會補寄）。
- 模型能做的只有 **`commons_verdict {"submission", "verdict": "accept"|"reject", "reason"}`** → `kind: commons_write`。郵差 `on_commons_write` 查：寄件人 `may` 有 `commons_write`、投稿在、**有 judge.json**（機械能判的不收判決＝`NotAsked`）、還沒結果（已有＝`AlreadyDone`；同一份申請重來回同一份動作）。accept＝照樣再跑一次機械檢查後入庫（`by: <隊>/<成員>`）；reject＝寫退回。
- **入庫**＝寫條目檔（先寫 `.tmp` 再改名）＋改 `index.json`＋重生 `INDEX.md`。只有圖書館員隊的郵差（和人的 CLI）做這件事；**各隊郵差只寫 `inbox/` 底下自己新開的資料夾**。
- 結果寫在 `inbox/<號>/result.json`：`{"status": "accepted"|"rejected", "by", "reason", "at", "id"?, "path"?}`。投稿者那隊的郵差每輪看自己 `team/commons/*.json` 裡還沒結的，有結果就寄一封信給投稿者（入庫＝DONE 附 `/work/commons/<路徑>`；退回＝FAILED 附理由），記下已寄。

### 圖書館員是「正式員工」

隊員分兩種（董事 09-25）：**正式員工**＝工具齊全、有跨任務記憶、長期在職；**臨時工**＝為一張單生出來、做完就收（spawn 生的多半是這種）。圖書館員是典型的正式員工：它服務所有團隊、要記得館藏長什麼樣、判「像不像」靠的是熟悉既有條目。這版的記憶就是 commons 本身（index 與條目檔，`commons_search` 隨查），沒另開 `notes`；要給它跨任務筆記，模板加 `notes: true` 即可（留下一輪看需不需要）。

### 為什麼圖書館員可以用笨模型

1. **它幾乎不用想**：格式、大小、路徑、執行位、完全重複全是程式判；乾淨的投稿根本不叫模型。
2. **叫它的時候題目很窄**：「新的這條有沒有舊的沒有的東西」，兩三段字比對，答案只有兩種＋一句理由。
3. **它做不了壞事**：模型沒有寫 commons 的工具，唯一能送的是判決；判 accept 郵差還會再跑一次機械檢查。判錯的代價是「多一條像的」或「少一條」，人用 `aos-team commons rm`／`add` 一行修掉。
4. 所以用 `deepseek-chat`、`claude-haiku-4.5` 這種便宜的就夠；模板 `llm.model` 是 `default`，名冊可逐成員換。

## 5. 查閱（`commons_search`）

純程式、不寫任何東西：讀 `/work/commons/index.json`，

- `query`：關鍵字；拆成英數字詞＋中文單字，跟條目的 id、標題、`fits`、摘要、標籤比，命中標籤的算兩倍分。
- `tags`：全部都要有（AND）；`type`：只找一種；`limit`：1～20，預設 5。
- 回每條：`id [種類] 標題`、`fits`、`tags`、摘要、`full text: /work/commons/<路徑>`。
- `show: id`：直接印那一條全文（`README.md` 或經驗檔，前 12000 字）。也可以用既有的 `read` 工具讀 `/work/commons/…`（檔案工具碰得到整個 `/work`）。
- 查法在牢裡看不到 `lib/`，工具抄了一份；`test_team_commons` 比對兩邊結果一樣。

## 6. 人的指令 `aos-team commons …`

| 子命令 | 做什麼 |
|---|---|
| `ls [--json]` | 一條一行：id、種類、標題、標籤、路徑 |
| `show ID` | 印全文（資料夾型的另列附檔） |
| `search [關鍵字] [--tag T]… [--limit N]` | 跟工具同一套查法 |
| `add TYPE --title --fits --tags a,b --body-file F [--slug S] [--file 附檔]…` | 人直接加，不用投稿；機械檢查照跑，完全重複拒絕、像的只提醒 |
| `rm ID` | 拿掉一條（檔與索引） |
| `reindex` | 用文字編輯器改過 `index.json` 後重生 `INDEX.md`（順便驗每條有 `type`、`path`） |
| `import 資料夾` | 匯入 [playbook](../../playbook/README.md) 形狀的資料夾（§7） |
| `desk` | 圖書館員的機械檢查手動走一輪（平常郵差每輪會走；非圖書館員隊＝`NotAllowed`） |

都照團隊名冊找 commons；加 `--dir 資料夾` 直接指定。

## 7. commons 與 playbook：同一件事的兩層

- **playbook**（`proto5/playbook/`）是**調度層**的圖書館：人與調度者（Claude Code 的隊）收尾時手寫的經驗、團隊編制、工作流，進 git、給人讀。
- **commons** 是 **aos 團隊層**的圖書館：aos 裡跑的 agent 團隊邊做邊投、圖書館員隊收，放在機器上、給 agent 查。
- 兩邊方向：playbook → commons 用 **`aos-team commons import proto5/playbook`** 一鍵匯入：`lessons.md` 每個 `### N（部門）標題` 一條 lesson（id `playbook-lesson-N`，標籤 `playbook`＋部門）；`teams/`、`workflows/` 底下除 README 以外的 `.md` 各一條。重跑安全：同 id 內容一樣＝跳過，不一樣＝以 playbook 為準換新。
- commons → playbook 這版不做自動：人（或文件隊）看 `INDEX.md` 挑值得進 git 的，手抄進 playbook（留下一輪看要不要做 `export`）。

## 8. 牆與保證外

- 保證：成員（含圖書館員模型）寫不到 commons（唯讀掛，`test_team_commons.WallTests` 在真 bwrap 裡試寫被擋）；投稿路徑、大小、符號連結在牢外由郵差再驗；只有 `may` 有 `commons_write` 的成員能送判決，且只能判被叫去判的。
- 保證外：
  - **內容對不對**：機械只管形狀，不管經驗是否正確；館藏錯了靠人 `rm`。
  - **跨團隊的信任**：同一台機器上任何一隊的郵差都能往 `inbox/` 放投稿（這是設計）；惡意的團隊資料夾（人自己設的）不在防範內。
  - **「像」的判法很粗**：標題字重疊，會漏（標題換說法）也會誤叫（標題剛好用字一樣）；誤叫只是多花一次笨模型。
  - 多支圖書館員隊同時跑：用 `.lock` 排隊、`judge.json` 記是哪一隊在判，別隊不插手；但沒有「誰是主館」的設定。
  - `index.json` 被人改壞：`desk`／`search` 讀不到就那一輪不做，`reindex` 會說哪條壞。

## 9. 六軸自評（[score.md](score.md)：L 模型用得少、S 穩、R 省、F 快、H 人好懂、B 邊界）

| 軸 | 自評 | 理由 |
|---|---|---|
| L | 好 | 投稿、檢查、入庫、查閱、回信全程式；模型只在「像」時判一次，且題目二選一 |
| S | 好 | 每一步冪等（紀錄在＝回同一份動作、notice 去重、`.tmp`＋改名）；崩在中間下一輪補做 |
| R | 好 | 乾淨投稿 0 次模型；查閱 0 次模型；圖書館員用最便宜的模型 |
| F | 中 | 一條投稿要走「投稿隊郵差→圖書館員郵差→投稿隊郵差」三輪（預設各 5 秒一輪），入庫到回信約 10～15 秒 |
| H | 好 | `INDEX.md` 一張表、條目檔開頭三行（來自、適合、日期）；`index.json` 縮排 2 能手改；CLI 八個子命令 |
| B | 好 | 唯讀掛、郵差再驗路徑與大小、執行位規則、判決只收被叫的；保證外明列在 §8 |
