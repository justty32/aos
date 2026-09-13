# 試玩紀錄（play）

← [筆記索引](../2026-09-08-ideas.md)｜規則在 [§21.5](../20-21-step-lisp-and-next.md)

每個段落收線後，開沒看過設計筆記的 agent 只拿 README 當新使用者玩，照五條標準打分（① 容易上手 ② 容易理解 ③ 複雜藏好 ④ 外層簡單但全面 ⑤ 少背）。一輪一列。

| 輪 | 日期 | 玩什麼 | 報告 | 分數（①②③④⑤） |
|---|---|---|---|---|
| r1 | 2026-09-13 | proto4-3（OS 層）＋ proto4-4（逐步 lisp） | [Opus](2026-09-13-r1-opus.md)、[gpt-sol](2026-09-13-r1-gptsol.md)、[任務書](task-r1.md) | Opus 4/4/3/3/3、gpt-sol 3/3/2/4/2 |

## r1 兩份合起來的「要改的清單」（Fable 整理，2026-09-13）

兩個人都撞到的排前面。**小**＝文件或一行警告，**中**＝要加旗標或指令。

| # | 問題 | 兩人都提？ | 大小 | 處理 |
|---|---|---|---|---|
| 1 | README 那行 `(import ./src/aos :as aos)` 照抄必壞；其實 aos-step 每格已經把 `aos/*`、`here`、`pc` 綁好 | 是 | 小 | **這輪修**（fix-r1） |
| 2 | 跑一半改 prog.janet，pc 靜悄悄錯位、沒任何警告（兩人都說最危險） | 是 | 小 | **這輪修**：`.aos-step/` 記 form 數＋內容 hash，對不上印一行警告（不擋） |
| 3 | inst.json 沒寫 `stderr`，出錯畫面一片空白 | Opus | 中 | 分兩半：`aos-kernel-init` 印的範例、README 的範例都帶 `stderr`（**這輪修**）；`aos-exec --stderr` 覆蓋旗標（**等使用者**，之前定過「不做覆蓋旗標」） |
| 4 | `aos-step --done-exit` 跟 kernel `config.json` 的 `done_exit` 兩套，對不上 cpu 被佔死、`ls` 看不出來 | Opus | 中 | **這輪修**：aos-step 拿掉 `--done-exit`，只認環境變數都不要，寫死 100＝跟 kernel 預設一致；README 寫「這個號碼是 kernel 說了算」 |
| 5 | 開機三步沒人包、排行程要自己 `cp` 進 `procs/` 取檔名 | 是 | 中 | **等使用者**：`aos-kernel-boot` 你之前說先不做；`aos-kernel add <inst.json>`（自動配名、檢查 cwd／argv／stderr）要不要做 |
| 6 | `aos-kernel ls` 要先 `cd K`；不顯示 daemon 活著沒、bad 幾件為什麼、最近 done | 是 | 小 | **這輪修**：`ls [DIR]` 可選路徑；頂上加 daemon `alive`／`dead`；多印 `bad: n（最近原因）` |
| 7 | `ctl stop` 之後 `ls` 說「daemon 沒起來過」 | Opus | 小 | **這輪修**：改字 |
| 8 | README「怎麼跑」沒先講 `AOS_DAEMON_HOME`；`&` 在非互動 shell 會跟著死；`ncpu` 不含 kernel 自己那顆；每格會清空 stdout；`form N` 是 0-based 不是行號；cpu 不用自己插 | 是 | 小 | **這輪修**：都是 README 幾句話；錯誤訊息補 `(prog.janet 第 N 個 form)` |
| 9 | 被迫知道 argv 絕對路徑、cwd 寫死、`--home` 不傳子孫 | 是 | 中 | 3 與 5 做了就少一半；其餘**等使用者**看要不要 `aos-kernel add` 幫忙轉絕對路徑 |

兩人都說好的（別動）：daemon＝硬體／`add`＝插 cpu／kernel＝第一個程序這組比喻；`:read`＋`:json` 一次到位；退件進 `procs/bad/` 且 log 寫原因；`form N 失敗` 加 `.aos-step/error` 雙入口；`init` 跑完印下一步。
