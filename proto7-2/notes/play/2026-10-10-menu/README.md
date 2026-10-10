# 2026-10-10 menu 包新手試用（loop14 MN4）

← [試玩紀錄](../README.md)｜藍圖 [blueprint-scaffold1](../../blueprint-scaffold1.md) §6、§7 MN4｜受測文件 [menu README](../../../packs/menu/README.md)

## 怎麼試

- 兩位新手：Claude **Haiku**（Agent 工具，每輪新開）、codex **gpt-6-luna**（`model_reasoning_effort=low`）。只准讀 menu `README.md` 與 `--help`；在 `/tmp/mn4-play/<試用者>/<輪>/` 操作。題目原文 [raw/task-template.md](raw/task-template.md)：照 README 跑 hello（練習用的 AI，不花錢），再故意弄壞四樣——a 不存在的資料夾、b 複本刪掉 who 層 exit、c 複本 practice.json 只留一句、d 做完再跑＋照 README 重走；最後五題理解題＋五條標準打分。
- 門檻（[decisions-2026-10-09](../../decisions-2026-10-09.md) ST3 起）：五題全對＋較差者 ≥6 且 luna ≥7；另記藍圖的 2 指令、≤4 概念。

## 總表

| 輪 | 試用者 | 五題 | 指令 | 概念 | 分數 | ELI5 後複雜？ | 報告 |
|---|---|---|---|---|---|---|---|
| 1 | luna | 全對 | 2 | 4 | 8.6 | 不複雜 | [raw](raw/luna-r1.md) |
| 1 | Haiku | 全對 | 2 | 4（另數約 10） | 5.4 | 使用端簡單、寫選單複雜 | [raw](raw/haiku-r1.md) |
| 2 | luna | 全對 | 2 | 4 | 8.6 | 不複雜 | [raw](raw/luna-r2.md) |
| 2 | Haiku | 全對 | 2 | 約 6 | 5.6 | 基本流程不複雜、寫選單會變複雜 | [raw](raw/haiku-r2.md) |
| 3 | luna | 全對 | 2 | 4 | 8.8 | 不複雜 | [raw](raw/luna-r3.md) |
| 3 | Haiku | 全對 | 2 | 6（4＋出口＋回法） | 6.4 | 不算複雜 | [raw](raw/haiku-r3.md) |

**第 3 輪過門檻**（五題全對、較差者 Haiku 6.4 ≥6、luna 8.8 ≥7）。

## 每輪改了什麼

- 第 1 輪後：「頂多再寫一句」改成「寫字的題目再多回一段字」；「一層」附上範例第一層 AI 實際看到的五行提示；工作資料夾註明「訊息裡叫 node」；新增「沒跑成、停下、重走」一節，寫明「換 --run 重走」＝在 run 那行最後加 `--run 新名字`，或刪掉 `menu/hello` 再跑；結尾明說 JSON 欄位、真 AI、`--help` 其他選項第一次都用不到。
- 第 2 輪後：統一用「出口」一詞（字由寫選單的人定，範例寫「缺少判斷…請人補充」）；practice.json「跟 menu.json 放在同一個資料夾」；「有 AGENTS.md 的那個資料夾」改成「看得到 `proto7-2/` 的那個」；`run` 後面接兩樣（工作資料夾、選單檔）；結尾拿掉 spec 連結。

## 剩下的扣分（沒再改）

- Haiku 三輪都扣「要自己改選單時 JSON 欄位沒教」——這是題目 b、c 要它改 JSON 造成的，README 刻意只帶第一次跑，欄位在 ADVANCED。第 3 輪 Haiku 把「只准讀 README」解讀成連複本 JSON 都不能打開，b、c 沒做。
- `run --help` 列出 `--llm`、`--reply`、`--run`、`--var`、`--brief` 但沒有說明文字（程式問題，見下）。
- node／工作資料夾兩個名字：訊息用 node，README 只能註明是同一個。

## 試用中看到的程式問題（只記不修，MN4 不改程式）

1. JSON 壞掉時訊息是「<路徑> 不在或 JSON 不合。給可讀的 JSON 檔」——檔案明明在，也沒說第幾行（Haiku 第 1 輪）。建議分開「不在」與「JSON 第 N 行第 M 字不合」。
2. 缺出口的錯誤訊息範例寫 `"exit": {"text": "都不是，要你決定"}`，與 hello 範例的出口字不同；新手把它當成第三種說法（Haiku 第 2 輪）。
3. `run --help` 的選項沒有 help 字串。
4. 停下的 run 跑 `status` 退 0、`run` 退 1（spec 沒說 status 的退出碼，記一筆）。
5. 隊長自測：「options 含出口要 2～5 個」沒說目前幾個；「options.next 指不到層」沒說指到哪個名字；`status --prompt` 在已停下的 run 只印狀態行。
