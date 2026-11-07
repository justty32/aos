# 晚審必修 10～18：memory_write 兩個會悄悄壞資料的錯、sol 裁定落進條文時的失真、brain 的 usage

← [入口](README.md)｜上一份 [01](01-必修-daemon與判官.md)｜下一份 [02b](02b-必修-thinking與文件.md)

## 10. 在 JSON 葉底下 add 子節點，原本的 JSON 會被悄悄改成 README.md

- **檔:行**：`proto8/lib/agent/memory_write/writing.py:84`、`:93-101`
- **問題**：父節點如果是 `j.json`，程式照樣走「葉升級成資料夾」：把 JSON 原文寫進 `j/README.md`，再刪掉 `j.json`。工具回報成功。可是 61a7ed360 剛加的 `read j#/x` 從此變成 `TargetBad`，`ls` 的摘要也變成整串 JSON。審查員 D 實測過。
- **對照**：K7 圖紙 `proto8/thinking/2026-11/05/knowledge-write/02-寫入設計.md:15` 只說「父節點是葉（**父.md**）時先升級」；C-56。
- **建議**：父節點是 `.json` 葉時直接報 `PathBad`，不升級。補一條測試。

## 11. rm 一個資料夾節點的同時在它底下 add，兩邊都回成功，新寫的節點卻被刪掉

- **檔:行**：`writing.py:128-129`（rm 鎖父資料夾）、`:137-143`（判斷有沒有子、rename、rmtree）；add 鎖的是節點自己（`:85`）
- **問題**：兩把鎖不同、不互斥。不帶 recursive 的 rm 也完全不看 `d/.lock`。D 實測 60 輪出現 1 次。`edit d` 撞上 `rm d` 是同一個洞。
- **對照**：圖紙 `04-邊緣狀況.md:12` 第 2 條寫「同鎖」，可是 `02-寫入設計.md:45` 的鎖表本身就造成這個洞，圖紙前後自相矛盾。W4 只測了「父節點原本是葉」的情況。
- **建議**：rm 資料夾節點時，先拿父資料夾的鎖、再拿節點自己的鎖，一律由上往下拿。拿到之後再判斷有沒有子。補「父節點本來就是資料夾」的並發測試。

## 12. 落實時的代定被標成「11-07 使用者裁定 sol 審查 #N」

- **檔:行**：
  - #15-2「比 `ctl_seq` 去重」：`proto8/docs/NORMS/05-基礎設施-窗/01-N-06～N-08.md:6`、`:15`，`04-基礎設施-loop與daemon/03-N-54.md:17`，`05-基礎設施-窗/07-細則.md:9`，`NORMS/主題.md:15`，以及 thinking 7 處（ctl-commands、procs、no-pid、portable-flow、edge-round2、apply-ideas、lift-to-norms 各 README）
  - #3 開關細節：`proto8/kernel/docs/02-kernel-modes.md:22`
  - #22：`proto8/docs/CONVENTION/02-題目stack停錯腦/07-P-44.md:7`、`:21`
  - #29：`06-P-41.md:17`
  - #19：`proto8/docs/CONCEPTS/01-設計理念/09-C-83.md:6`、`:10`
- **問題**：使用者 15-2 選的 B 只有一句：「起來後第一拍就照做」。seq 去重是落實的人為了讓 stop 之後還能 start 才加的。sol 審查 `11-使用者裁定.md` 第 49～61 行的「代定（可翻案）」段，自己就把這些列成代定。這正是上一輪 sol 審查白話總結裡的「第三種」毛病，再犯了一次。#28 代定的 `StateMissing` 只寫在 `11-使用者裁定/01-落實結果.md:55`，代定段沒有。
- **建議**：代定那半句改標「（11-07 #N 落實代定，可翻）」，使用者裁定的標記只留在他選的那句上。#28 的 StateMissing 補進代定段。

## 13. #23 的標記接在「沒問過的範圍句」後面

- **檔:行**：`proto8/docs/CONCEPTS/01-設計理念/03-續-C-52-例外.md:33`、`:38`
- **問題**：第 33 行是「不只 C-52，條文與程式裡所有『一般規則＋例外』都照這幾條：（使用者裁定 #23）」，讀起來像「全 repo 通則」是使用者定的。第 38 行的規矩 4 也沒問過。
- **對照**：sol 審查頁面 #23 原文寫「範圍沒問過；規矩 4 也沒問過」；23A 只講判準。
- **建議**：第 33 行的標記刪掉（判準第 2、3 條已經各自標了）。範圍句和規矩 4 註明「agent 補、可翻」。

## 14. `AOS_TICK_INTERVAL` 什麼時候往下傳，兩條條文說法相反

- **檔:行**：`proto8/docs/NORMS/10-基礎設施-定義與工作區/07-hub-型環境變數與父子交代/03-AOS_-變數的四種性質.md:20`（「不是 1000 時設給子樹」）；`proto8/docs/NORMS/04-基礎設施-loop與daemon/02-N-28.md:80`（「明寫就…一起設（#10 改）」）
- **建議**：四種性質那一行照 N-28:80 改，並標 #10。

## 15. 四種性質第 24 行說 `AOS_KERNEL` 的 warning「另排」，其實已經做了

- **檔:行**：同檔 `:24`；程式在 `proto8/impls/aos-llm-kernel/src/daemon/daemon.cpp:45`
- **建議**：改成「已實作；aos-agent 這一路照 #8 維持 `MailboxMissing`」。

## 16. 「直接修」只改了條文，thinking 裡被判錯的舊說法還在

- **檔:行**：
  - #26：`proto8/thinking/2026-11/03/procs/11-實作時代定-11-03-晚-實作者照原則.md:22`、`proto8/thinking/2026-11/06/lift-to-norms/README.md:20`，兩處還寫「11-06 改讀」
  - #24：`proto8/thinking/2026-11/06/special-cases/04-升格建議與慣例草稿.md:68`（K7 多出的例外還在）
  - #8：同檔 `:52`（K3「照退路走」）；同檔 `:7` 卻自稱「已同步裁定」
- **建議**：改成跟 N-28:71 一樣的說法（11-06 是翻案，不是改讀）。K3、K7 各加一行註，或把第 7 行的「已同步」收窄。

## 17. #3 的 thinking 裁定段把使用者的備註刪掉了

- **檔:行**：`proto8/thinking/2026-11/05/kernel-daemon/README.md:70`、`proto8/thinking/2026-11/06/os-impl/README.md:68`，兩處都只寫「3B*」
- **對照**：原文是「3B*（備註：我希望這是可選的。默認是不帶有序。）」；user/03 規定 thinking 只留原文。
- **建議**：兩處都逐字補上括號裡的備註。

## 18. brain 的錯誤提示沒跟上兩個新旗標

- **檔:行**：`proto8/templates/agent-fsm/brain.py:70`、`:74`（usage 少了 `--history`、`--max-tool-calls`）；`:78`、`:82`（新加的兩個 ArgumentsBad 沒附 usage）；`proto8/impls/aos-llm/src/main.cpp:4-5`（檔頭還寫只印 `body.message`）
- **對照**：P-44：「原因裡附 usage」「`(usage: …)` 放最後」。審查員 C 實跑確認。
- **建議**：這四處的 usage 都換成 HELP 第一行那份完整用法；main.cpp 的檔頭註解補上 `--full`。
