# 任務書 3：aos-step 做完回 100，接上 kernel 的「行程做完」；補文件

你在 repo `/home/lorkhan/repo/simple_tools/aos`。**只准改**：`proto4-4/src/step.janet`、`proto4-4/test/step.janet`、`proto4-4/test/cpu.janet`、`proto4-4/test/fx/`、`proto4-4/README.md`、`proto4-3/docs/kernel.md`。其他一律不碰（尤其 `proto4-3/*.py`、`proto4-3/test/`——kernel 那邊已經做好了，你只是接上去）。**不要 git commit、不要 push。** 不要開其他 agent。

## 背景

kernel 剛加了應急版「行程做完」：行程某一次跑完回**退出碼 100**（`config.json` 的 `done_exit`，`aos-kernel-init --done-exit N` 可改，0＝關），kernel 下一回合（要 `runs − runs_at ≥ 2`，因為換人那刻正在跑的一次還是前一位的）就把它的 inst.json 搬到 `procs/done/<pid>.json`、cpu 換回 idle，`aos-kernel ls` 多印一行 `done: …`。細節看 `git show 1d539e5 -- proto4-3/aos_kernel_tick.py proto4-3/aos_kernel.py` 與 `proto4-3/test/test_kernel.py` 新加的三條（那裡示範了怎麼在測試裡真開 daemon＋kernel）。

`aos-step`（`proto4-4/src/step.janet`）現在所有 form 跑完之後每次都回 0。要改成回 100，這樣放進 kernel 就會自己下車。

## 要做的

1. **`src/step.janet`**：`pc >= form 數` 那條路改成退出碼 **100**（仍然不印東西、確保 `done` 檔存在）。加一個旗標 `--done-exit N`（預設 100）讓人改；`--status` 的輸出不變。第一次跑完最後一個 form 的那次仍回 0（那次是真的做了事），**下一次**才回 100。
2. **`test/step.janet`**：原本「第 5 次：退出 0、done 存在、stdout 空」改成退出 100；加 2 條：`--done-exit 0` 時回 0；`--done-exit 7` 回 7。
3. **`test/cpu.janet`**：加一條**真的走 kernel** 的整合測試（照 `proto4-3/test/test_kernel.py` 的做法，用 `os/spawn`／`os/execute`）：
   - 暫存家 `AOS_DAEMON_HOME=/tmp/…`，背景開 `proto4-3/aos-daemon`；`proto4-3/aos-kernel-init K --ncpu 1 --interval-ms 200 --quantum 50`；`proto4-3/aos-daemon-ctl add K/inst.json --interval-ms 200`。
   - 一個行程資料夾 `P/prog.janet` 三個 form（各 append 一行到 `log.txt`），寫 `K/procs/1.json`＝`{"argv":["<絕對路徑>/aos-step","prog.janet"],"cwd":"<P 的絕對路徑>","stdout":"out.txt","stderr":"err.txt"}`。
   - 等最多 15 秒，輪詢直到 `K/procs/done/1.json` 出現；然後檢查：`P/.aos-step/done` 存在、`log.txt` 恰好 3 行（做完後多被叫的那幾次都沒再寫）、`K/cpus/0.json` 內容是 idle（跟 `proto4-3/aos_kernel.py` 的 `IDLE_INST` 一樣）、`aos-kernel ls`（cd K 跑）輸出含 `done: 1`。
   - 收尾：`aos-daemon-ctl stop`（或 SIGTERM daemon），刪暫存。**測試失敗也要收尾**（用 `defer` 或 `protect`），不要留殭屍 daemon；開始前先 `pkill -f "aos-daemon"` 之類的別做——只殺你自己開的那個 pid。
   - 這條測試比較慢，控制在 20 秒內。
4. **`proto4-4/README.md`**：「怎麼跑」加一小段「放進 kernel」（上面那個 inst.json 形狀＋「做完回 100，kernel 會自己把它收走」）；「沒做什麼」裡那條「做完後 cpu 還是會一直來叫…」改成描述現況（會被 kernel 收走；直接用 aos-run 跑的話還是會一直來叫，只是回 100）。保持 170 行以內。
5. **`proto4-3/docs/kernel.md`**：
   - 「家長什麼樣」補 `procs/done/`、`config.json` 多 `done_exit`。
   - 「指令」補 `aos-kernel-init … [--done-exit N]`。
   - 「每回合五步」裡排程那步補一句「先看做完沒：`last_kind=child` 且 `last_exit=done_exit` 且 `runs−runs_at≥2` → 搬 `procs/done/`、換 idle；再看 quantum 換人」。
   - 「這一版沒做什麼」第一條「行程不會自己結束」改寫成現況：應急版＝保留退出碼 100，行程回這個碼就會被收走；沒有的是「行程主動叫 kernel」（syscall）、`procs/done/` 不自動清、做完的 cwd 不動。
   - 其餘文字不動。加完後 `wc -l` 給我。

## 驗證

```
cd /home/lorkhan/repo/simple_tools/aos/proto4-4 && for t in test/*.janet; do janet "$t" || echo "FAIL $t"; done
cd ../proto4-3 && python3 -m unittest discover -s test 2>&1 | tail -2      # 188 條、OK（確認你沒弄壞）
```
連結：`proto4-3/docs/kernel.md` 與 `proto4-4/README.md` 裡每個相對連結目標 `ls` 得到。

## 回報（十行以內，大白話）

- 改了哪些檔、各幾行。
- 三支 Janet 測試最後一行原文；proto4-3 那行原文。
- kernel 整合測試實際花幾秒、做完後 log.txt 幾行、`ls` 那行長什麼樣（貼原文）。
- 自己決定的事、撞到的坑、沒做到的。
