# 任務書：把 `proto4-3/README.md`（729 行、46 KB）拆成 README ＋ `proto4-3/docs/` 四篇

你在 repo `/home/lorkhan/repo/simple_tools/aos`。**只准動 `proto4-3/README.md` 與新建的 `proto4-3/docs/`**。不碰程式、不碰測試、不碰別的資料夾。**不要 git commit、不要 push。** 不要開其他 agent。

## 為什麼

repo 的規矩（`wf/STRUCTURE.md`）：使用手冊單檔超過 300 行就拆，原路徑留作入口。這份 README 是四支工具（aos-exec／aos-run／aos-daemon／aos-kernel）的使用說明，**文字一個字都不能改、不能漏**——只是搬家。

## 現況（先 `grep -nE '^#{1,3} ' proto4-3/README.md` 自己對一次行號，下面是我看到的）

```
1    # proto4-3 — …（標題＋前言，到 28 行左右）
29   ## 怎麼跑
63   ## 三種目標                 ┐
83   ## inst.json 長什麼樣        │ aos-exec
116  ### envs 的兩種寫法          │
129  ### 指示詞：任何位置都能放    │
173  ## aos-exec 的退出碼          ┘
207  ## aos-run：一直跑同一個目標   ┐ aos-run（含 ### 間隔／status-fd／什麼時候停／印什麼）
327  ## aos-daemon：…              ┐ aos-daemon（含 ### key／五個狀態／七個動作／近況／請求格式／家目錄／CLI）
513  ## aos-kernel：…              ┐ aos-kernel（含 ### 家／指令／五步／開機順序／這一版沒做什麼）
628  ## 檔案
674  ## 沒做什麼
```

## 目標

```
proto4-3/README.md        標題＋前言、怎麼跑、【新增】「四支工具各自的說明」導航表、檔案、沒做什麼   （應該 200 行上下）
proto4-3/docs/exec.md     原 63–206 行（三種目標 → 退出碼）
proto4-3/docs/run.md      原 207–326 行
proto4-3/docs/daemon.md   原 327–512 行
proto4-3/docs/kernel.md   原 513–627 行
```

每篇 docs 檔前面加三行自己的檔頭：
```
# proto4-3／<工具名>
← [README](../README.md)
<空行>
```
然後原文逐 byte 照搬。

## 怎麼做（用腳本切，不准手打或重排）

1. 先 `cp proto4-3/README.md /tmp/readme-orig.md` 留底。
2. 用 `sed -n 'a,bp'` 按行號切四篇到 `docs/`。切點以 `^## ` 標題行為準；每篇最後一行是下一個 `## ` 的前一行（通常是空行）。
3. 新 README ＝ 原 1–62 行 ＋ 一個新小節 ＋ 原 628 行到最後。新小節放在「怎麼跑」之後：
   ```
   ## 四支工具各自的說明

   | 工具 | 說明在哪 | 講什麼 |
   |---|---|---|
   | aos-exec | [docs/exec.md](docs/exec.md) | 三種目標、inst.json 七欄、指示詞、退出碼 |
   | aos-run | [docs/run.md](docs/run.md) | 間隔怎麼算、`--status-fd`、什麼時候停、印什麼 |
   | aos-daemon | [docs/daemon.md](docs/daemon.md) | key、五個狀態、七個動作、請求格式、家目錄、CLI |
   | aos-kernel | [docs/kernel.md](docs/kernel.md) | 家長什麼樣、四支指令、每回合五步、開機順序、這一版沒做什麼 |
   ```
   （「講什麼」那欄照各篇實際的 `###` 標題寫，不要多加。）
4. **驗證等價**（必做、結果貼進回報）：
   ```
   cd proto4-3
   { sed -n '1,62p' /tmp/readme-orig.md; sed -n '628,$p' /tmp/readme-orig.md; } > /tmp/readme-kept.txt
   { tail -n +4 docs/exec.md; tail -n +4 docs/run.md; tail -n +4 docs/daemon.md; tail -n +4 docs/kernel.md; } > /tmp/readme-moved.txt
   sed -n '63,627p' /tmp/readme-orig.md > /tmp/readme-moved-orig.txt
   diff /tmp/readme-moved-orig.txt /tmp/readme-moved.txt && echo MOVED-SAME
   ```
   必須印 `MOVED-SAME`；另外自己確認新 README 去掉那個新小節之後跟 `/tmp/readme-kept.txt` 一樣（同樣用 diff）。行號若跟我寫的差一兩行，以你 grep 到的 `## ` 行號為準，別硬套。
5. **連結修正**（唯一允許改字的地方）：
   - 搬進 `docs/` 的四篇，裡面原本的相對連結（像 `../proto4/notes/...`）現在深了一層，要多加一個 `../`。用 `grep -n '](\.\./' docs/*.md` 全找出來逐個改，改完每個目標都 `ls` 確認存在。
   - 原 README 內若有 `](#錨點)` 同檔錨點、目標現在在 docs 裡，改成 `](docs/xxx.md#錨點)`；docs 裡指回 README 段落的同理。`grep -n '](#' README.md docs/*.md` 找。
   - 外面連進來的（`grep -rn 'proto4-3/README.md' --include='*.md' . | grep -v worktrees`）都是連 README 本身、沒帶錨點，不用動、**也不要去改那些檔**。
6. 最後 `wc -l README.md docs/*.md`，README 要在 300 行以下。

## 回報（十行以內，大白話）

- 五個檔各幾行。
- `MOVED-SAME` 與 README 那個 diff 的輸出原文。
- 改了哪些連結（檔名＋改前改後各一個例子就好）。
- 有沒有任何一行文字被改動（除了連結路徑）——應該是「沒有」。
