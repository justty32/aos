# 任務書：把 `proto4/notes/2026-09-08-ideas.md`（750 行、90 KB）按節拆檔，原路徑留作索引

你在 repo `/home/lorkhan/repo/simple_tools/aos`。**只准動 `proto4/notes/` 底下的檔案**（拆出來的新檔也放這裡）。其他路徑一律不碰。**不要 git commit、不要 push。** 不要開其他 agent。

## 為什麼

repo 的規矩（`wf/STRUCTURE.md`「結構整理原則」）：文檔單檔超過 300 行就拆；**拆的時候原路徑保留當入口，外部連結才不會斷**。這份筆記是使用者的原話＋設計定案，**一個字都不能改、不能漏、不能重排**——拆檔只是把同一段文字搬到別的檔。

## 目標結構

`proto4/notes/` 變成：

```
2026-09-08-ideas.md            索引（原路徑，保留）：檔頭 ＋ 一張「第幾節 → 哪個檔 → 一句話」的表 ＋ 一條「以後怎麼加」規則
01-06-janet-and-direction.md   §1–§6（proto4 Janet 版：runf／kernel／daemon；方向；請求回歸 JSON、inst 直接執行）
07-10-inst-json-cpu.md         §7–§10（proto4-2 那一輪：inst.json、proc 本體、daemon 是硬體、格式沿用 core/inst）
11-15-exec-run-daemon.md       §11–§15（proto4-3：aos-exec、aos-run、aos-daemon、拍板、key 改 inst.json）
16-19-kernel.md                §16–§19（名詞對齊、kernel 管 procs/、kernel 原型定案、拆成 init／tick／boot）
20-21-step-lisp-and-next.md    §20–§21（proto4-4 逐步 lisp、下一步方向）——這是「現在進行中」的檔，新的節之後往這裡加
```

節的邊界就是 `^## N\. ` 這種標題行（先 `grep -nE '^## ' proto4/notes/2026-09-08-ideas.md` 拿到行號：§1 在第 5 行、§7 在 113、§11 在 254、§16 在 489、§20 在 678）。原檔第 1–4 行是檔頭（標題、空行、`← [README](../README.md)`、空行）。

## 怎麼做（一定要用腳本切，不准手打或重新排版）

1. 用 `sed -n 'a,bp'` 或 `awk` 按行號把五段各自寫進新檔。每個新檔前面加 **三行自己的檔頭**：
   ```
   # proto4 想法筆記 §a–§b：<主題>
   ← [索引](2026-09-08-ideas.md)｜[README](../README.md)
   <空行>
   ```
   然後就是原文，**逐 byte 一樣**。最後一段（§20–§21）到原檔的最後一行為止。
2. 把原檔改寫成索引：保留原本前 4 行檔頭，接一段兩三句話說「這份筆記 2026-09-13 拆成五個檔，這裡只留目錄；每節的編號不變、文內提到的 §x.y 照編號到對應檔找」，再一張表：

   | 節 | 檔 | 一句話 |
   |---|---|---|
   | §1–§6 | [01-06-janet-and-direction.md](01-06-janet-and-direction.md) | … |
   …（每列的一句話從各節標題濃縮，不要自己發明內容）

   最後一段規則：「**新的一節接在最後一個檔的尾巴**；那個檔破 300 行就再開一個新檔、在這張表加一列。」
3. **驗證等價**（必做、把結果貼進回報）：
   ```
   cd proto4/notes
   git show HEAD:proto4/notes/2026-09-08-ideas.md | tail -n +5 > /tmp/notes-orig-body.txt
   for f in 01-06-janet-and-direction.md 07-10-inst-json-cpu.md 11-15-exec-run-daemon.md 16-19-kernel.md 20-21-step-lisp-and-next.md; do tail -n +4 "$f"; done > /tmp/notes-split-body.txt
   diff /tmp/notes-orig-body.txt /tmp/notes-split-body.txt && echo SAME
   ```
   必須印 `SAME`。若段與段之間因為切法多了或少了一個空行，調整切點讓它 SAME，而不是改內容。
4. 檢查文內連結：`grep -n '](' proto4/notes/*.md | grep -v 'http'`。原檔裡的相對連結（例如 `../README.md`、`../../proto4-3/...`）搬到新檔後**相對位置沒變**（同一個資料夾），所以應該都還對；但若有 `](#錨點)` 這種同檔錨點、目標節現在在別的檔，就改成 `](檔名#錨點)`。每個相對連結目標都 `ls` 一下確認存在。
5. 檢查外面連進來的：`grep -rn '2026-09-08-ideas.md' --include='*.md' . | grep -v '.claude/worktrees'`——它們連的是原路徑（現在是索引），沒帶錨點，不用改。**不要去改那些檔。**

## 回報（十行以內，大白話）

- 五個新檔各幾行。
- `diff … && echo SAME` 的輸出原文。
- 有沒有改到任何連結、改了哪個。
- 索引檔最後長什麼樣（貼那張表）。
