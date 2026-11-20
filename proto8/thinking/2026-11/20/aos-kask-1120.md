# 線 aos-kask-1120 紀錄：「寄信問 kernel」基礎協議的調查與發想——只寫 thinking，原型在暫存夾

← [2026-11-20](README.md)｜成品：[aos-kask-1120/](aos-kask-1120/README.md)

頂層派（使用者 11-20「然後寄信問 kernel 的基礎協議可以派線去調查」）。只調查、不施工。

## 做了什麼

- 讀程式（HEAD `e1209424b` 的 `git archive` 乾淨複本）：骨架 `py/tools/aos/kernel/`、問腦那包 `kernel_llm/`、`daemon_ctl/state_path.py`、`kernel_gate/hold`、aos-daemon 的 `mailbox.cpp`、`aos-llm` 說明、`interfaces.json`／`hook_points.json` 的讀者。
- 寫 `aos-kask-1120/` 七份：00 原話、01 現況、02 形狀、03 邊緣、04 原型（＋程式附件）、05 八題。
- 原型：在乾淨複本跑 `install.py`、起兩台（問腦總機、daemon-kernel 範本的站），掛一支 before_verdict hook，實跑六段。輸出原樣在 04。

## 證據

- 實跑輸出：`~/.aos/scratch/aos-kask-1120/run1.out`、`run2.out`（04 節錄）；單跑 hook 的耗時 `timing.sh`。
- 沒跑 repo 的測試（沒改程式）。

## 對不上處

- 調查稿（aos-kres-1120/06 第 5 題）說「像今天問表在哪的那種信」，暗示是 kernel 回的；實際回它的是 aos-daemon 本體，框架站只轉寄；問腦總機還會拒它。
- 第一次跑（`run.sh`）問腦總機那幾段用 `aos-llm send` 寄，全被工具自己擋下（`RequestBad`）；改用 `aos-post send` 直接寄進 `requests/` 重跑（`run2.sh`）。這本身記成一條發現。

## 替使用者做的選擇

- 「這種信」＝「問你吃什麼形狀」的問句信，回的是「另外一個 json」（列成第 2 題，沒當定案）。
- 「kernel 框架」讀成骨架一帶。
- 原型的暫用名、示意宣告的欄位、做法 A／B 的寫法都是示意；不取正式名字。
- 「schema 誰說了算」已在 aos-kres-1120 答先不定，沒重列成題。

## 收尾

- 行程：兩台 daemon 都收掉（問腦那台在 run2 第六段 `shutdown`，站那台 `down.sh`）；`pgrep` 沒有本線的行程。開工時看到的 aos 行程都是別線的（gdb-small、defnew-cp 等）。
- 暫存：`~/.aos/scratch/aos-kask-1120/`（`head/` 乾淨複本已裝、`t/` 暫存樹、`boxes*/`、`timing/`、腳本），沒刪。
