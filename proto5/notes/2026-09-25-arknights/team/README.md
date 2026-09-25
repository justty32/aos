← [arknights 索引](../README.md)｜設定檔：[examples/arknights](../../../examples/arknights/README.md)｜樣板：[playbook](../../../playbook/README.md)

# 第 2 段：強模型版團隊設定與試跑（2026-09-25）

**一句話**：搭好一支 4 人隊（領隊、寫手 2、審查員，全用 `gpt-6-astra`），讓它對真專案「補次要人物」從頭做到驗收過。
單人（老何塞）**第 2 次交件過**（第 1 次是我設定錯、不是寫手錯）；一批 3 人（老木頭、老薑、老財）**@@BATCH_ONE_LINE@@**。
過程中修了 proto5 四處（都附測試，全套 2681 條綠）。

模型：LiteLLM `localhost:4000` 的 `chatgpt-gpt-6-astra`（**預設檔位**，沒用 `-low/-medium/-high`），`max_tokens` 32000、逾時 10 分。沒碰 LM Studio／ollama。

## 1. 名冊長什麼樣（精簡）

```json
{"project": "~/tmp/arknights-try",
 "members": {
   "lead":     {"template": "…/templates/lead",     "model": "gpt-6-astra", "mail_to": ["writer-1", "writer-2", "reviewer", "human"]},
   "writer-1": {"template": "…/templates/writer",   "model": "gpt-6-astra", "mail_to": ["lead", "human"],
                "mounts": {"arknights-corpus": {"$opt": "ro", "$val": "~/tmp/arknights-corpus"}}},
   "writer-2": "（同 writer-1）",
   "reviewer": {"template": "…/templates/reviewer", "model": "gpt-6-astra", "mail_to": ["lead", "human"], "mounts": "（同上）"}},
 "limits": {"stale_minutes": 30, "max_members": 4},
 "spawn": {"templates": []},
 "cmd_ok": [{"run": ["python3", "scripts/check_links.py", "lore"], "mounts": {"arknights-corpus": "~/tmp/arknights-corpus"}},
            {"run": ["python3", "scripts/check_simplified.py", "lore/characters/<名>.md", "lore/evidence/characters/<名>.md"]},
            {"run": ["python3", "scripts/verify_split.py", "aos-drafts/<名>/證據草稿.md", "lore/evidence/characters/<名>.md", "lore/evidence/characters/<名>"]}]}
```

- 全文：[team.json](../../../examples/arknights/team.json)。白名單要整串相等，所以「單檔檢查」每個人一條（這次登記了 6 人：老何塞、老木頭、老薑、老財、老天師、老成的杜林人（雙月密錄））。`verify_split` 登記了但沒放進驗收（它檢查「一行都沒少」，而寫手本來就要改內容，兩者衝突；只適合「不改內容的純拆檔」）。
- **成員不 commit**：寫手的權限只有「專案可寫」（`project: rw`），沒有 git 工具；牢裡 `git` 也跑不起來（副本的 `.git` 指到牢外）。commit 留給人。
- **換成本尊要改的**：`team.json` 的 `"project"` 一行改成 `"~/repo/narratives/arknights"`，三個成員的 `mounts` 拿掉（corpus 就在專案裡）、`cmd_ok` 裡 `check_links` 那條的 `mounts` 也拿掉；`cmd_ok` 的人名換成那一批。其他不用動。**還沒做，要你點頭**（見 §9）。
- 副本怎麼搭、corpus 為什麼用相對符號連結：[examples/arknights/README.md](../../../examples/arknights/README.md)。

## 2. 人格從哪裡抄

三份人格在 [templates/](../../../examples/arknights/templates/)（自訂模板的 `system.md`，init 時換好 `{name}` 之後就是 `aos-agent persona show` 看到的全文；之後要改用 `aos-agent persona set`）。每份都是「proto5 內建那份規矩，照抄」＋「專案規矩」兩段。專案規矩的出處：

| 規矩 | 抄自 |
|---|---|
| 一律繁體、原文引用放 backtick／〈〉可留簡體、檔名沿用原文 | arknights `CLAUDE.md` 鐵律 3、`workflows/common/conventions.md` |
| 全劇透 | `CLAUDE.md` 鐵律 4、`workflows/lore-extraction/README.md` |
| 證據附檔名＋行號、推論要標明、⚠ 標待決 | `conventions.md`〈內容慣例〉 |
| 同名不等於同一人也不等於不同人、speaker 首句會誤導、活動撞名、跨檔拼寫 | `workflows/common/gotchas.md`〈查證與判讀〉 |
| 「agent 自報乾淨不可信、主控必須覆核」→ 審查員逐列對原文 | `gotchas.md`〈用字與轉換〉、`workflows/verification.md` §3 |
| 導航維護鏈（證據 > 導航表 > 詞條 > 索引）、計數重新點算不沿用加法 | `conventions.md`〈導航表維護鏈〉、`gotchas.md`〈導航表與計數〉 |
| 證據檔 <5120 位元組、超限拆檔（stub＋子資料夾＋INDEX）、每批只納入明列人物 | `SESSION-LOG.md`〈最新進度〉＋第 143 批 commit `a5eb027` 的實際檔形 |
| 詞條格式（`### 名（定位）`、最後一行「詳見：」）、character_map 列格式 | 第 143 批 commit `a5eb027` 的實際檔（workflows 裡寫的格式已跟實際不同，我照實際的） |
| s2twp 誤轉詞、check_simplified 不可全自動替換 | `workflows/verification.md` §3 |

我自己**加**的只有三條操作性的：「計數怎麼點」（見 §6 第 9 步，專案沒寫公式，我從現有數字反推出來、三個數都對得上）、「單子寫要拿鎖才拿鎖」、「原文很長用 grep 找行號再 read 一段」。

## 3. 一張單的完成條件（done_when，12 條）

寫死在門房規則（[routes.json](../../../examples/arknights/routes.json)，「補人物 X」直接開單給 writer-1，不經領隊）與領隊人格（一批時領隊照抄、只換名字）。

| # | 條目 | 誰驗 |
|---|---|---|
| 0–1 | `file_exists` 詞條、證據檔 | 驗收員（程式） |
| 2 | `last_line_contains` 詞條最後一行有「詳見：」 | 驗收員（**新檢查器**） |
| 3 | `contains` 詞條連到自己的證據檔 | 驗收員 |
| 4–5 | `max_bytes` 證據檔 ≤5119、拆出的子資料夾每檔 ≤5119（沒拆＝算過） | 驗收員（**新檢查器**） |
| 6 | `contains` `lore/characters/INDEX.md` 有 `[名](名.md)` | 驗收員 |
| 7 | `cmd_ok` `check_links.py lore` 退 0 | 驗收員（牢裡，**要掛 corpus**） |
| 8 | `cmd_ok` `check_simplified.py` 詞條＋證據檔 退 0 | 驗收員（牢裡） |
| 9 | judge：證據每列的行號打開後真的說了那件事、推論與明寫分開、未知明講、同名切割有交代 | 審查員（astra） |
| 10 | judge：詞條每句在證據裡有依據、全劇透 | 審查員 |
| 11 | judge：character_map 有一列、五處計數重新點算且一致 | 審查員 |

**索引回填這一段先讓寫手做**（character_map 加一列、`characters/INDEX.md` 加一行、改 `characters.md`／`characters/INDEX.md`／`lore/INDEX.md`×2／`evidence/README.md`×2／`character_map.md` 的數字）。**這是純機械、第 3 段要換成程式**（見 §6）。

已知漏洞：`check_simplified` 只吃檔案參數、不吃資料夾，所以拆出來的子檔掃不到（白名單又要整串相等，沒辦法事先寫好子檔名）。這次三人都沒拆，沒踩到。

## 4. 真跑數字

每次都：`aos down` → 帶 `AOS_HOPS` 重開機（default 5 顆、llm 4 顆）→ 副本退回基線 commit → 刪掉重建團隊 → 丟一句話。紀錄在 `~/tmp/arknights-try/aos-runs/<時間>-<one|batch>/`（`hops.jsonl`、`hops-report.txt/json`、`score.json/txt`、`score-per-task.json`、`tasks.json`、`tasks/`（單子原檔）、`mail.txt`、`route.log`、`project.diff`、`lore-after/`（交件快照）、`members/*/log/`、`result.json`）。

| 次 | 內容 | 結果 | 交件次數 | 模型呼叫（領隊／寫手／審查） | token | 牆上時間 | 人插手 |
|---|---|---|---|---|---|---|---|
| one r1 `20260925-110707-one` | 補人物 老何塞 | **done** | 寫手 2 次（第 1 次驗收擋，是我的錯）、審查 1 次過 | 40（0／30／10） | 1,582,012（寫手 1,133,665、審查 448,347） | 17 分 39 秒（**其中約 11 分是寫手 BLOCKED 後在等我修設定**；扣掉約 6.5 分） | 1 次：修名冊＋寄一封 REQUEST |
@@BATCH_ROW@@

**每一跳（`aos_hops.py report`，one r1）**：寫手 880 秒裡，等模型 260 秒（30 次，中位 7.2 秒、最久 47.6 秒）、跑工具 1.7 秒、起 Python 等排程雜項合計約 20 秒；另有 2 次「停車 300 秒」＝在等我。審查員 1022 秒裡等模型 114 秒（11 次）、其餘是停車等審查單。**模型以外的開銷只有幾十秒，時間幾乎全在模型與人。**

- 量測小落差：寫手回 BLOCKED 是「寄給人的信」而不是「提問」，所以 `score` 的「等人」是 0，這 11 分鐘被算進「排隊與郵差（其他）651 秒」；`hops` 則算成兩跳 300 秒的 ⑱（停車等 `park_ms`）。兩邊都沒標「這是在等人」。留下一輪（§8）。
@@BATCH_HOPS@@

### one r1 的交件內容去哪了

交件快照（`lore-after/`）漏抓了新檔：`git status` 預設把中文路徑跳脫成 `"\346…"`，腳本對不上路徑就沒複製；接著批次試跑把副本退回基線，老何塞的詞條與證據檔就沒了（改過的五個索引檔、審查判語、驗收結果都還在）。`run.py` 已改（`core.quotepath=false`），批次那次有抓到。所以老何塞**沒辦法**再拿評分隊的 mech／evidence 檢查補評。

## 5. 驗收擋了什麼、審查員抓到什麼

| 次 | 驗收員擋 | 審查員 |
|---|---|---|
| one r1 第 1 次 | 第 7 條 `check_links.py lore` 退 1：5 條 `story_map` 連到 `corpus/extracted/…` 的連結斷了。**原因是我**：驗收員的牢只掛專案、沒掛 corpus（成員有掛）。**寫手判斷正確**：它自己跑是 0，回 BLOCKED 說「疑為唯讀驗收環境未掛載完整 corpus」、而且沒去亂改別人的檔。 | — |
| one r1 第 2 次 | 12 條機械全過 | 3 條全 PASS：「已逐一回原文核對全部 10 列……涵蓋 5 個原文檔」、「明寫胡安已死、何塞送別時存活與最終生死未知」、「重新點算為 612 條人物詞條、615 列人物證據入口及 751 個全部證據入口，與指定五處計數一致」。**沒抓到錯**（我沒辦法獨立覆核：交件內容沒留住，見上）。 |
@@BATCH_REVIEW@@

## 6. 哪些步驟是純機械、哪些要語感、哪些要強模型（第 3、4 段的依據）

照一個人從頭到尾的順序：

| # | 步驟 | 分類 | 為什麼／換成什麼 |
|---|---|---|---|
| 1 | 從候選名單挑下一批（`character_candidate_pool_recompute_remaining.tsv` 照順序取 3 人） | **純機械** | 讀 TSV 前 3 列；專案 SESSION-LOG 已經把 144～146 批排好了 |
| 2 | 把草稿搬到工作位置、開單（done_when 12 條只換名字） | **純機械** | 門房規則已經做到（單人不叫模型）；一批時領隊（astra）只是照樣板抄三遍——**第 3 段換成一條門房規則或一支小程式開三張單**，省掉領隊 |
| 3 | 同名查重：grep `lore/characters/`、`lore/evidence/characters/` 有沒有同名或近似名 | **機械找、語感判** | grep 是機械；「何塞」有三個不同的何塞，要不要合併要讀原文，這是判斷 |
| 4 | 讀草稿、逐句回原文找行號（grep 關鍵句→read 那幾行） | **語感，笨模型可試** | 大部分是「找這句話在哪一行」，可以先用程式把草稿裡每個「檔名 L行號」抽出來、打開原文那幾行貼給模型，模型只判「對不對」。**這步最吃 token**（寫手 113 萬／人，大半是讀原文） |
| 5 | 改正草稿、寫推論／未知段、同名切割 | **要強模型** | 草稿本身有錯時要判斷原文到底說了什麼、哪些只是推論；身分合併（泛稱、共用立繪）是本專案最常出錯的地方（gotchas 一半在講這個） |
| 6 | 詞條寫成 9～19 行白話敘事 | **語感** | 中等模型應該做得到；證據已經對好，只是改寫 |
| 7 | 量大小、>5120 就拆（stub＋子資料夾＋INDEX） | **判斷切點要語感，其餘機械** | 「照 `##` 標題切」可以程式做（專案 2026-07-10 的拆檔就是照標題切的），`verify_split.py` 驗無損；只有沒標題的散文要模型挑切點 |
| 8 | character_map 加一列（敘事線、人物、連結、一句摘要＋⚠邊界、整理狀態） | **格式機械、摘要語感** | 前三欄與最後一欄是機械；「一句摘要＋⚠邊界」是從證據檔尾「事實、推論與未知」濃縮，笨模型可試。「分片滿了續開 `_N.md`」是機械 |
| 9 | `characters/INDEX.md` 加一行、五處計數重新點算 | **純機械** | 公式：詞條數＝`characters/INDEX.md` 裡 `- [` 開頭的行數；人物證據入口＝`character_map/` 各檔連到 `../characters/` 的列數；全部證據入口＝前者＋40＋18＋73＋5。**第 3 段第一個換成程式**：寫手與審查員都在這步花模型呼叫，審查員還要自己 grep -c 覆核 |
| 10 | 跑 `check_links`、`check_simplified` | **純機械** | 已在驗收員 |
| 11 | 簡體殘留修正 | **語感（少量）** | 專案明講不可全自動替換，要看上下文與 repo 多數寫法 |
| 12 | 審查：逐列對原文行號 | **要強模型（或重工程）** | 「這幾行有沒有說這件事、有沒有把推論寫成事實」。能先用程式做「行號沒超過檔長、檔名存在、引號裡的原文字串真的在那幾行」（評分隊的 `evidence_check.py` 就是這個），模型只看程式對不上的列 |
| 13 | 審查：詞條每句有依據 | **強模型** | 跨檔對照、要懂「沒寫＝不能寫」 |
| 14 | 審查：計數與導航一致 | **純機械** | 同第 9 步；做成程式後這條 judge 可以改成 check |
| 15 | commit（只 add 明列人物＋索引，嚴禁 `-A`） | **純機械** | 名單已知，程式照名單 `git add` |

**大白話**：真正要強模型的只有「判斷原文說了什麼、身分能不能合併」（第 5、12、13 步）；找行號、寫白話可以試中等模型；剩下開單、點算、索引、檢查、commit 都是程式。

## 7. proto5 缺什麼

### 修了（都附測試；全套 **2681 條綠**，原 2665＋16）

| 缺 | 修法 | 檔 |
|---|---|---|
| 驗收員驗不了「最後一行是什麼」「檔案不超過幾位元組」 | 加兩支檢查器 `last_line_contains`、`max_bytes`（檔或資料夾、`missing_ok`） | `lib/aos_team_verify.py`、`spec/team/verify.md`；10 條測試 |
| 模板 `llm` 不收 `params`：推理型模型沒辦法在團隊裡開大 `max_tokens`（名冊也沒這欄） | 模板 `llm.params`（物件）原樣進 `info.json` | `lib/aos_team_format.py`、`spec/team/templates.md`；2 條 |
| **自訂模板的領隊、審查員認不出來**：郵差、門房只認名冊 `template` 字面等於 `lead`／`reviewer`；用自訂模板路徑，門房說「沒有領隊」、審查單會開不出去（`no_reviewer`） | 自訂模板看資料夾名，叫 `lead`／`reviewer` 就算 | `lib/aos_team_format.py` `members_by_template`、`templates.md`；1 條 |
| **驗收員跑 `cmd_ok` 的牢只掛專案**：專案裡連到專案外資料（原文庫）的連結在驗收時全斷，寫手自己跑卻是 0 | `cmd_ok` 白名單每條可寫 `mounts`（人寫、一律唯讀） | `aos_team_format.py`、`aos_team_verify.py`、`wall.md`、`roster.md`；3 條（含真牢） |

### 沒修（留下一輪）

1. **自訂模板路徑是照「跑指令當下的資料夾」解的**，不是照 team.json：郵差（kernel 叫的，cwd 不同）讀模板 `may` 時會找不到→`may` 空→所有申請被擋。我用絕對路徑繞過（`run.py` 展開）。該改成相對 team.json，要動 `template_dir` 的所有呼叫點。
2. **人沒有寄信的指令**：要回 REQUEST 給卡住的成員，只能手放一個 JSON 到 `team/outbox/human/`（我這次就是這樣解鎖的）。教程也沒寫。建議加 `aos-team say 成員 "…" [--task t-0001]`。
3. **「在等人」量不出來**：寫手回 BLOCKED 給人（信，不是提問）之後的等待，`score` 算進「其他」、`hops` 算成停車 300 秒；應該照單子 `blocked` 期間算「等人」。
4. 領隊一輪只開一張單（三人要三輪、約 70 秒）；可以在人格裡叫它一次叫三個 handoff，或乾脆第 3 段換掉領隊。
5. `check_simplified` 不吃資料夾：拆檔的子檔在驗收掃不到（專案腳本的事，不改 proto5；第 3 段做成程式時一起處理）。

## 8. 六軸打分（one r1；@@BATCH_AXES_NOTE@@）

| 軸 | 分 | 依據 |
|---|---|---|
| L 模型參與 | 2 | 40 次／人（寫手 30、審查 10）；單人時領隊 0 次（門房直接派） |
| S 穩定 | — | 跑不到 10 次不給；1/1 過，但要人插手 1 次（我的設定錯） |
| R 資源 | 1 | 158 萬 token／人，大半是寫手讀原文 |
| F 快 | 2 | 扣掉等我約 6.5 分／人；含等我 17.6 分 |
| H 人易懂 | 3 | `aos-team mail`、`task show` 看得懂誰做了什麼、擋在哪；寫手的 BLOCKED 一句話就說中原因。扣分：人要回話得手寫 JSON |
| B 邊界 | 4 | 寫手只碰得到副本、corpus 唯讀（牢裡 touch 被擋）、沒有 git、`cmd_ok` 只跑白名單；寫手被擋時沒去改不該改的 `story_map` |

## 9. 代裁、留下一輪、要你拍的

**代裁**（我先這樣做，你可以翻）：
1. 試跑人選：單人用 144 批第一個（老何塞），一批用 145 批（老木頭、老薑、老財）——都在剩下 70 人裡、不在基準集 15 人裡，照專案 SESSION-LOG 排好的順序。
2. 草稿放副本的 `aos-drafts/<名>/`、不放進 `lore/`：讓「寫成正式檔」這件事真的要做，不然 `file_exists` 一開始就白過。
3. 副本補了一個「aos 試跑基線」commit（aos-try 分支，沒合回、沒 push）：本尊 HEAD 有 7 條斷鏈（已 commit 的檔連到 5 個沒 commit 的草稿），不補的話 `check_links` 永遠不過、錯不在寫手。**這本身是本尊的一個不一致**，值得你知道。
4. `verify_split` 登記在白名單但不放進驗收（理由見 §1）。
5. 單人時不拿鎖；一批時才叫寫手搶 `lore/索引` 這把鎖。
6. 評分隊的 `eval.sh` 只認 golden 裡的批（都是已 commit 的人），而我照指示從基準集以外挑人，所以**沒跑 eval.sh 的評審那塊**；@@EVAL_NOTE@@

**留下一輪**：§7「沒修」5 條；評審（opus）對這批產出的分數；@@LEFT_EXTRA@@

**要你拍的新題**：**要不要拿本尊直接跑？**
選項：(a) 繼續只在副本 `~/tmp/arknights-try` 跑，產出由你人工挑進本尊；(b) 名冊的 `project` 改指本尊，寫手直接寫本尊工作樹（本尊有 143 個沒追蹤的草稿，寫手會跟它們同資料夾），commit 仍由人做。**我的預設是 (a)**：本尊的草稿和已 commit 的檔互相連結（見代裁 3），直接跑容易把沒審過的草稿一起捲進去。

## 10. 沉澱

**① 經驗（下次一開始就該知道的）**
- 在牢裡跑的團隊，**每一種牢都要單獨確認看得到什麼**：成員的牢、門房 `tool` 的牢、驗收員 `cmd_ok` 的牢是三套掛載。我只確認了成員那套，驗收員那套少掛 corpus，害寫手白扣一次。開跑前用 `aos-jail` 照驗收員的掛法把每條 `cmd_ok` 手跑一次。
- 資料夾在專案外（原文庫）：專案裡用**相對**符號連結、掛載名＝連結裡那一段，主機和牢裡都解得開。
- 「全庫」類檢查（斷鏈、全庫簡體）先量基線；真專案的基線常常不是 0（本尊 HEAD 就有 7 條斷鏈、1460 個簡體殘留字）。
- 真專案的 workflows 文件跟實際檔形會漂移（詞條格式、證據路徑都跟文件寫的不同），**照最近一批 commit 的實際檔寫人格**。
- 試跑腳本碰中文路徑：`git -c core.quotepath=false`，不然 `status` 的路徑是跳脫過的。
- 強模型寫手很守規矩：第 1 次被擋時自己重跑、判斷出是環境問題、回 BLOCKED 而沒亂改別人的檔。人格裡「卡住回 BLOCKED 說試過什麼」這句值得保留。

**② 團隊組織架構** → [playbook/teams/arknights-strong.json](../../../playbook/teams/arknights-strong.json)
通用的部分：「領隊 1＋寫手 2＋審查員 1」、全員唯讀掛原文庫、寫手專案可寫但沒有 git、`spawn.templates: []`、`cmd_ok` 只放專案自己的檢查腳本（要讀原文的那條加 `mounts`）、推理模型 `max_tokens` 32000／逾時 10 分。**適合**：有原文可查、產出要附出處、一個條目一張單的資料整理活。

**③ 工作流架構** → [playbook/workflows/lore-entry.md](../../../playbook/workflows/lore-entry.md)
單一個用門房規則直接開單（不叫領隊）；一批給領隊照 done_when 樣板抄；done_when 先機械（檔在、格式、大小、索引、專案檢查腳本）後模型（逐列對原文、每句有依據、計數一致）；共用索引用 lock。

**④ 可複用工具**
- 兩支新檢查器 `last_line_contains`、`max_bytes` 已經在 proto5 驗收員裡（`lib/aos_team_verify.py`），任何團隊都能用。
- `cmd_ok` 的 `mounts`、模板 `llm.params`、自訂模板認領隊／審查員，也都在 proto5 本體。
- [examples/arknights/run.py](../../../examples/arknights/run.py)：「開機帶 AOS_HOPS→專案退回基線→重建團隊→丟一句話→等單子結束→存一整包紀錄」。目前綁 arknights 的路徑與句型；一般化成 `playbook/` 的通用試跑腳本（參數：專案、團隊設定、句子、基線 commit）留下一輪。
