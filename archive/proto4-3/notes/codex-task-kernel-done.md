# 任務書：kernel 應急版「行程做完了」——用一個保留退出碼，KISS

你在 repo `/home/lorkhan/repo/simple_tools/aos`。**只准改這四個檔**：`proto4-3/aos_kernel.py`、`proto4-3/aos_kernel_init.py`、`proto4-3/aos_kernel_tick.py`、`proto4-3/test/test_kernel.py`。**`proto4-3/README.md` 與 `proto4-3/docs/` 現在有另一個人在拆檔，絕對不要碰**（文件我之後補）。其他路徑一律不碰。**不要 git commit、不要 push。** 不要開其他 agent。

## 背景

kernel v1（`proto4-3/aos_kernel_tick.py`）的行程永遠輪流、沒辦法自己結束（README「kernel 這一版沒做什麼」第一條）。使用者說：「你想個應急用的處理方法，先做，我們之後再來看看怎麼樣更好。盡量簡單一點，維持 KISS 原則。」

先讀：`proto4-3/aos_kernel_tick.py` 全檔（201 行）、`proto4-3/aos_kernel.py` 的 `KHome`／`DEFAULTS`、`proto4-3/aos_daemon_entry.py` 第 85–120 行（daemon `state.json` 每顆 cpu 那一筆有 `runs`／`last_exit`／`last_kind`，`runs` 是 status-fd 上 `done #n` 的 n，`last_exit` 是那次的退出碼）、`proto4-3/test/test_kernel.py`（怎麼真開 daemon 測 tick）。

## 定案（照做，不要另想設計）

**一個保留退出碼＝「我做完了，別再排我」。** 行程（inst.json 的程式）某一次跑完回這個碼，kernel 下一回合看到就把它從 cpu 上拿下來、搬去 `procs/done/`，cpu 換回 idle。就這樣。

- 碼是 **100**（`aos-exec` 自己用 125／2，shell 用 126／127／128+N，100 沒人用），放 `DEFAULTS["done_exit"] = 100`，寫進 `config.json`（`aos-kernel-init` 加 `--done-exit N` 旗標，預設 100；`0` ＝關掉這個功能，因為 0 是正常結束不能拿來當訊號）。
- 判斷寫在 `_one_cpu()` 裡、換人（quantum）那段**之前**：
  ```
  ent = ready[n]                    # daemon 那一筆（poll_cpus 回的）
  cur 有人 而且
  cfg["done_exit"] != 0 而且
  ent["last_kind"] == "child" 而且 ent["last_exit"] == cfg["done_exit"] 而且
  runs_now - cur["runs_at"] >= 2    # 見下面「為什麼是 2」
  → _finish(h, st, notes, now, n, cur["pid"])
  ```
  **為什麼是 2**：`runs_at` 是換人那一刻 daemon 已經跑完的次數；換人只影響「下一次開跑讀到誰」，當時正在跑的那一次還是舊行程的，它跑完 `runs` 會變 `runs_at+1`、`last_exit` 也是舊行程的。所以要 `runs_at+2` 以後的 `last_exit` 才確定是現在這位的。代價是做完的行程會多被叫一次，沒關係。
- `_finish()`：
  1. 先把 idle 寫成暫存檔 `cpus/n.json.tmp`（`IDLE_INST`），`os.link(h.cpu(n), h.proc_done(pid))` 讓做完的 inst.json 在 `procs/done/<pid>.json` 有名字（`procs/done/` 不存在就建；同名已存在就先 unlink 再 link），再 `os.replace(tmp, h.cpu(n))` 原子蓋過去——跟 `_swap()` 一樣的兩步、一樣的退路（link 失敗就不換；replace 失敗就 unlink 剛才那個 done 檔、留原狀）。**不留空窗**這件事要跟 `_swap` 一樣認真。
  2. `st["cpus"][str(n)] = None`；`notes.append("cpu%d 上 %s 做完了，收進 procs/done/" % (n, pid))`。
  3. `procs/done/` 是 `procs/` 底下的資料夾，`check_queue()` 掃佇列只收檔案，自然不會把它當行程（`procs/bad/` 已經是這樣），確認一下就好。
- `KHome` 加 `proc_done(pid)` 路徑；`aos-kernel-init` 建家時順便建 `procs/done/`（跟 `procs/`、`cpus/` 一起）。
- `ls`（`aos_kernel.py`）順手加：`config` 那行印 `done_exit=100`；佇列表下面若 `procs/done/` 有檔就多印一行 `done: 3, 7`（pid 照 `pid_key` 排）。就一行，不要多。

## 測試（`test/test_kernel.py`，照既有的 `KernelDaemonTest` 寫法，真開 daemon）

至少加 3 條：

1. **做完會被收走**：一個行程的 inst.json 跑一支腳本，`sh -c 'exit 100'`（或先跑兩次回 0 再回 100，用 cwd 裡的計數檔控制）。連續 tick 幾回合（看 interval 調），最後 `procs/done/<pid>.json` 存在、`procs/<pid>.json` 不存在、`state.json` 那顆 cpu 是 `null`、`cpus/n.json` 內容是 idle、`ls` 有 `done:` 那行。
2. **前一位的退出碼不會殺錯人**：cpu 上先跑一個回 100 的行程 A，被收走後上 B（回 0）；B 不能被誤收。或者更直接：B 剛上去、`runs_now - runs_at == 1` 時即使 `last_exit == 100` 也不動。想辦法做出這個時序，做不出來就用單元測試直接叫 `_one_cpu()` 餵假的 `ready`／`st`（可以不開 daemon）。
3. **`--done-exit 0` 關掉**：同 1 的行程回 100 也不會被收，一直輪流。
4. `aos-kernel-init` 建出 `procs/done/`；`config.json` 有 `done_exit`。

全套要綠（185 條 → 至少 188 條）：
```
cd /home/lorkhan/repo/simple_tools/aos/proto4-3 && python3 -m unittest discover -s test 2>&1 | tail -3
```
你只跑得到 test_kernel 那幾條也行（`python3 -m unittest test.test_kernel -v`），但最後整套一定要跑一次。

## 回報（十行以內，大白話）

- 改了哪些函式、加了哪些。
- 測試幾條、最後一行原文。
- 你自己決定的事（例如做完的檔同名衝突怎麼處理）、撞到的坑，一條一句。
- 沒做到的。
