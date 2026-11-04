# 任務書 fix-r1：照試玩第一輪的清單修「小」的那批

你在 repo `/home/lorkhan/repo/simple_tools/aos`。先讀 `proto4/notes/play/README.md`（清單）與兩份報告 `proto4/notes/play/2026-09-13-r1-opus.md`、`2026-09-13-r1-gptsol.md`（看「現象」就好）。**只准改**：`proto4-4/src/step.janet`、`proto4-4/test/step.janet`、`proto4-4/test/cpu.janet`、`proto4-4/test/fx/`、`proto4-4/README.md`、`proto4-3/aos_kernel.py`、`proto4-3/aos_kernel_init.py`、`proto4-3/aos_daemon_ctl.py`、`proto4-3/test/test_kernel.py`、`proto4-3/test/test_daemon_cli.py`、`proto4-3/README.md`、`proto4-3/docs/kernel.md`、`proto4-3/docs/daemon.md`。其他一律不碰。**不要 git commit、不要 push。** 不要開其他 agent。

只做清單上標「**這輪修**」的：#1、#2、#3 前半、#4、#6、#7、#8。**不要做** #3 後半（aos-exec 覆蓋旗標）、#5（boot／add 指令）、#9。不要順手重構。

## 逐條

**#1（proto4-4/README.md）**：「函式庫怎麼用」開頭那行 `(import ./src/aos :as aos)` 刪掉，改一句「在 `aos-step` 跑的 form 裡，`aos/*`、`here`、`pc` 已經綁好，直接用；要在別的 Janet 程式裡用這個函式庫才需要 import，路徑是 `<proto4-4>/src/aos.janet` 的絕對路徑」。

**#2（step.janet）**：`.aos-step/` 多存一個 `src`：上次成功那步當時的「form 數＋整份 prog 的 sha256（用 `(string/format "%x" …)` 或 janet 的 `crypto`… 沒有內建就存 form 數＋檔案 bytes 長度＋`os/stat` 的 mtime，能抓到「改過」就好）」。每次跑之前比對：對不上且 `pc > 0` → **stderr 印一行警告**「aos-step: prog.janet 改過了（上次 N 個 form、現在 M 個），pc=k 可能已經錯位；確定要重來就 --reset」，**照跑不擋**，跑成功後更新 `src`。`--status` 多一個 `:changed true/false`。加 3 條測試：改前面插一個 form → 有警告行、pc 照走；沒改 → 沒警告；`--reset` 後 `:changed false`。

**#3 前半**：`aos_kernel_init.py` 最後印的那段「開機：…」後面多印一行範例行程 inst.json（帶 `stderr`／`stdout`）：`把行程丟進佇列：cp 你的.json K/procs/<名字>.json，例如 {"argv":["/abs/程式"],"cwd":"/abs/資料夾","stdout":"out.txt","stderr":"err.txt"}`。`proto4-3/README.md` 與 `docs/kernel.md` 的 inst.json 範例都補 `stderr`（若已有就不動）。

**#4（step.janet／README）**：拿掉 `--done-exit` 旗標（回 100 寫死），舊測試裡用到 `--done-exit 0`／`7` 的兩條刪掉或改成「給了 `--done-exit` 會退出碼 2 並提示『這個號碼由 kernel 的 config.json 說了算』」。README 相應改：「做完回 100，這個號碼跟 kernel 的 `done_exit` 預設一致，要改就改 kernel 那邊（`aos-kernel-init --done-exit`），程式端不給改」。`test/cpu.janet` 若用到就跟著改。

**#6（aos_kernel.py 的 ls）**：
- `aos-kernel ls [DIR]`：給了 DIR 就 `os.chdir(DIR)` 再照舊；沒給照舊用 cwd。用法字串更新。
- 頂上第一行多印 daemon 狀態：讀 daemon 的 `state.json`（`aos_home` 那套已知道家在哪）——有 pid 且活著印 `daemon alive pid=…`，否則 `daemon dead（下面是最後一次的狀態）`。
- 佇列之後多印一行 `bad: n` 並帶最近一件的原因（原因從 `kernel.log` 最後一條「退件」那行撈，撈不到就只印數量；`procs/bad/` 沒東西就不印這行）。
- 測試補 2 條：`ls DIR` 從別的目錄跑得到一樣輸出；有退件時 `ls` 有 `bad:` 行。

**#7（aos_daemon_ctl.py）**：daemon 正常 stop 之後 `ls`／`get` 印「沒有 state.json（daemon 沒起來過）」那句改成「daemon 沒在跑，也沒有留下狀態（正常收工會清掉 state.json）」。`docs/daemon.md` 裡「daemon 沒在跑時 ls／get 讀最後狀態」那句補「（被 kill 才會留；正常 stop 會清掉）」。測試若有比對那句字串就跟著改。

**#8（文件＋一個訊息）**：
- `proto4-3/README.md`「怎麼跑」第一行前加 `export AOS_DAEMON_HOME=~/.aos-daemon   # daemon、ctl、kernel 三支都靠這個找家；用 --home 不會傳給子孫`；`aos-daemon &` 旁加註「非互動 shell 結束會把它帶走，要常駐用 `nohup … &`、`setsid` 或 tmux」；`aos-kernel ls` 那行改 `aos-kernel ls K`（#6 做完就能這樣寫）；加一句「cpu 不用你插，kernel 第一回合會自己把 `cpus/*.json` 掛上 daemon」；`--ncpu N` 旁加「這 N 顆是給行程用的，跑 kernel 自己的那顆不算在內」。
- `proto4-4/README.md`：kernel 那段 inst.json 旁加註「`stdout`／`stderr` 每格會被清空，要留紀錄自己 append 到別的檔」；「沒做什麼」補「`form N` 的 N 是 0 起算的頂層 form 序號，不是行號」。
- `step.janet` 失敗訊息從 `aos-step: form 2 失敗：…` 改成 `aos-step: 第 2 個 form（0 起算）失敗：…`，測試字串跟著改。

## 驗證

```
cd /home/lorkhan/repo/simple_tools/aos/proto4-4 && for t in test/*.janet; do janet "$t" || echo "FAIL $t"; done
cd ../proto4-3 && python3 -m unittest discover -s test 2>&1 | tail -2
```
兩邊全綠。文件裡每個相對連結目標 `ls` 得到；`proto4-3/README.md` 保持 300 行以下。

## 回報（十二行以內，大白話）

- 每一條（#1、2、3、4、6、7、8）一行：做了什麼、改哪個檔。
- 測試數與最後一行原文（Janet 三支、Python 一套）。
- 自己決定的事、撞到的坑、沒做到的。
