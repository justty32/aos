# decide-page — 把一批要使用者裁的題做成離線互動頁，收回答、落回各線

[WORKFLOWS](../WORKFLOWS.md)｜[INDEX](../INDEX.md)｜看板 [aos-teams/04](dispatch/aos-teams/04-進度回報.md)｜資料檔契約 [data-files](common/data-files.md)

一批題目寫成一份**題目資料檔**（`wf-table/1`），用產生程式做成桌面上的離線互動頁；使用者點選、寫備註、按「複製」，把一行回覆貼回對話或看板；agent 用同一支程式把回覆讀回資料檔、印出各線要貼的裁定段。使用者 11-07：「好，就這樣做」（sol 審查那頁之後）、「兩個舊的代辦可以同時進行」。

**何時用**：審查、設計規劃、實驗收尾後，攢了 **3 題以上**要使用者裁，或題目要附背景、原話、來源才裁得了。
**何時不用**：做到一半臨時冒出 1～2 題、一句話問得清 → 直接 `progress_post.sh <線> ask …` 放看板「待你裁」（[aos-teams/04](dispatch/aos-teams/04-進度回報.md)），照推薦往下走。純通知、不用他選 → `progress_post.sh … progress`。

## 跟看板怎麼分（不另起第三套）

<!-- wf-nav -->
- **看板「待你裁」是唯一的收件匣**：每一批互動頁發出時，也在看板放**一題不帶選項的 ask**（「X 批 N 題待你裁，頁在桌面」＋頁面路徑），使用者在看板就看得到有一批在等。
- **題目格式共用**：選項一律「代號＋做法＋後果」，代號規則跟看板相同（英數 1～8 字）、推薦必須是其中一個；看板單題就是互動頁一列的縮小版（`text`＝`question`、選項 `text`＝`label`＋`consequence`、`eli5` 同名）。
- **回答殊途同歸**：互動頁的回覆是一行字，可以貼回對話，也可以貼進看板那題的「意見」框送出；兩條路都用同一支 `parse` 讀。看板單題的回答照舊用 `progress_answers.sh` 讀。

## 題目資料檔

放在**出題那條線自己的資料夾**（跟它的 README 同層），檔名 `decide_<YYYYMMDD>[_<短名>].json`；`source` 指那份 README。契約照 [data-files](common/data-files.md)，頂層另有這些鍵：

- `kind`＝`decide-page/1`；`batch`＝這批的短名（英數、`-`；回覆開頭會帶 `[batch]`，也拿來當瀏覽器暫存的鍵）；`line`＝看板線名。
- `title`（頁面大標）、`kicker`（大標上一行小字，可省）、`lead`（2～3 句結論，字串陣列）；`overview_svg`＋`overview_caption`（可省，有就取代自動畫的總覽圖）。
- `sections`：`[{id, title, intro, figure_svg, caption}]`，照順序排；`intro` 一句白話、可省；`figure_svg` 是隊長自己畫的 inline SVG、`caption` 是圖下那句結論（都可省；SVG 用頁面的 `s-*`／`t*` class 才跟得上深淺色，class 表見程式 README）。程式另外自動畫一張「各節幾題、推薦落在哪」的總覽圖。
- `appendix`：`[{title, items}]`，頁尾摺起來的附錄（例如「直接修、不用你裁的」），可省。

每列一題，欄位：

| 欄 | 說明 |
|---|---|
| `id` | 題號，英數開頭、可含 `-` `.` `_`；回覆裡用它 |
| `section` | 屬於哪一節（`sections[].id`） |
| `question` | 一句話的問題，白話 |
| `eli5` | 問題下方一兩句比喻或背景（可空） |
| `options` | `[{key, label, consequence}]`；可空陣列＝只收意見的題 |
| `recommend` | 推薦代號（可空） |
| `why` | 推薦的一句理由，顯示在選項下方 |
| `quotes` | 使用者原話 `[{text, cite}]`，第一則直接顯示、其餘摺起；沒有就寫一則「沒有針對這題的原話」＋最相關的一句 |
| `details` | 摺起來的細節，字串陣列（agent 做了什麼、commit、檔案位置） |
| `source_path`、`source_lines`、`source_excerpt` | 來源檔（相對資料檔、連結欄）、行號、逐字原文（摺兩層） |
| `answer`、`answer_state`、`answer_note`、`answered_at` | 出題時留空，`apply` 填 |

文字欄只認兩種行內記號：`` `code` `` 與 `**粗體**`；其餘照字面顯示、不接受 HTML（`figure_svg` 除外）。頁面不放任何外部連結，路徑一律當文字顯示。

## 回覆格式

頁面自動組出、使用者不用手打：`[batch] id:代號、id:代號*（備註：…）、id:代號?`

- `*`＝跟推薦不同；`?`＝**沒點開過**（沒選、沒寫備註、沒開細節、沒按「看過」），**仍算待定**：不寫進答案、不算裁定，留在未裁清單，下一批或看板繼續追（使用者 11-08：「互動頁上我沒看過的就仍算待定」）；只收意見的題代號寫 `-`；備註裡的換行變 ` / `。

## Done when

- 資料檔過 `decide_page.py check`、頁面在桌面、看板有那題 ask；
- 收到回覆後：資料檔每列 `answer_state` 填滿，出題線 README 有使用者原話與逐題裁定，SESSION-LOG 那條改成只剩照裁定要做的事。

## 流程

1. **出題**（出題線的 opus 隊長；gpt 只能幫忙抄來源、填 `source_*`，不定選項與推薦）：寫資料檔，跑 `python3 wf/tools/decide_page/decide_page.py check <資料檔>`。
2. **出頁**：`decide_page.py build <資料檔>`（預設寫到 `~/Desktop/aos-<batch>-待你裁.html`），用瀏覽器開一次看圖與選項；然後 `progress_post.sh <線> ask '<批名>：N 題待你裁，頁在桌面' <頁面路徑> --eli5 '<一句白話>'`；README 寫一句「已抽到 decide_….json（N 題）」，SESSION-LOG 記一行 open。各線照推薦往下走、記代定，不停線。
3. **收回答**：使用者貼在對話裡的，存成文字檔；貼在看板的，用 `--from-board <ask id>` 直接讀。`decide_page.py parse <資料檔> <回覆>` 先看讀得對不對（未知題號、代號不在選項裡、缺題都會提醒），再 `apply` 寫回資料檔。
4. **落回各線**：出題線 README 加「使用者裁定（日期）」段，**回覆原文逐字貼上**（[討論紀錄只留原文、決定、結論](common/user/03-討論紀錄與規劃.md#討論紀錄只留原文決定結論2026-10-12-夜改)）；`decide_page.py land <資料檔>` 依 `source_path` 分組印出每題一行「選了什麼、白話、備註原話」，貼到各來源檔原本那題的位置（把「未裁，暫照推薦」改成結果）。`land` 把 `?` 的題列在 `pending` 段：來源檔那題維持「未裁」，放進下一批或看板再問。跟推薦不同（`*`）與有備註的題，照裁定要改的事列進 SESSION-LOG 或該線交棒。

程式怎麼跑、旗標與錯誤代號見 [`wf/tools/decide_page/README.md`](../tools/decide_page/README.md)。

## 交接

- 裁定落地後的施工 → 回到出題那條線（feature-dev、refactor…）；卡在使用者 → [WAIT_USER](../WAIT_USER.md)；跨 session → [SESSION-LOG](../SESSION-LOG.md) 一行。

## 代定（11-08 開線時，使用者補眠、不能問；可翻案）

- 單檔型工作流、產生程式放 `wf/tools/decide_page/`；資料檔跟著出題線走，不設集中的批次目錄（開著的批靠看板 ask 與 SESSION-LOG 找）。
- 看板當唯一收件匣、整批也發一題 ask；回覆可貼看板意見框，所以看板意見上限從 4000 字放寬（見程式 README）。
- 回覆加 `[batch]` 開頭。

## 使用者裁定（11-08，看板兩題，經頂層轉述）

> 互動頁上我沒看過的就仍算待定，按鈕與說明確實要用中文

- 沒點開的題（`?`）：仍算待定、不記代定（跟原推薦 A「照推薦記代定」不同）。
- 頁面按鈕與說明字用繁中；命令列訊息、錯誤、程式碼註解照規矩英文（照推薦 A）。
- 有小題的題（sol 審查的 15-1、15-2…）拆成各自一張卡，不做「一卡多小題」。
