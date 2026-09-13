# 任務書 fix-r3：試玩第二輪的清單——rm 當第一個 syscall、驗欄位、ls 欄位、文件收尾

你在 repo `/home/lorkhan/repo/simple_tools/aos`。先讀 `proto4/notes/play/README.md` 的「r2 兩份合起來的要改的清單」（#1–#6 這輪做，#7、#8 不做）與兩份報告 `proto4/notes/play/2026-09-13-r2-opus.md`、`2026-09-13-r2-gptsol.md`（看「現象」）。**只准改**：`proto4-3/aos_kernel.py`、`aos_kernel_tick.py`、`aos_kernel_add.py`、`aos_kernel_boot.py`、`aos_kernel_init.py`、`aos_daemon_ctl.py`（只准動 `ask()` 加一個 quiet 參數）、新檔 `proto4-3/aos_kernel_syscall.py`、`proto4-3/test/test_kernel.py`、`proto4-3/README.md`、`proto4-3/docs/kernel.md`、新檔 `proto4-3/docs/files.md`、`proto4-4/src/step.janet`、`proto4-4/test/step.janet`、`proto4-4/README.md`。其他一律不碰。**不要 git commit、不要 push。** 不要開其他 agent。不要順手重構。開工前先跑兩邊測試確認綠的（Python 205、Janet 34/12/34）。

## A. `aos-kernel rm [K] NAME`＝第一個 syscall（清單 #1）

設計理由（照做）：tick 每回合在動 `cpus/`、`procs/`，rm 若直接動同一批檔會跟 tick 搶。所以 rm **只寫一張單**，tick 每回合開頭先處理單子。這就是筆記 §19.5 說的「行程對 kernel 的 syscall 入口」的第一個。

- 家裡多一個資料夾 `K/syscalls/`（`aos-kernel-init` 建；tick 沒看到也自己建）與 `K/syscalls/done/`。
- `aos-kernel rm [K] NAME`（位置參數規則跟 `ls`／`add` 一樣）：寫 `K/syscalls/<time.time_ns()>-rm-NAME.json`＝`{"op":"rm","pid":"NAME"}`（先 `.tmp` 再 `os.replace`），然後等 `K/syscalls/done/<同檔名>` 出現（上限 `3 × interval_ms`，至少 3 秒），讀它 `{"ok":bool,"msg":str}`，印 msg，`ok` 假＝退出碼 1，讀完把 done 檔刪掉。等不到＝印「kernel 沒回應（daemon 在跑嗎？aos-kernel ls K 看看）」退出碼 1，單子留著（下次 tick 還是會處理）。
- tick 加一步「處理 syscalls」，放在 `poll_cpus` 之後、`check_queue` 之前，程式放新檔 `aos_kernel_syscall.py`（`handle_syscalls(h, cfg, st, notes)`），tick 只 import 呼叫：
  - 按檔名排序逐張讀；不是 JSON 物件／沒 `op`／不認得的 `op` → 寫 done `{"ok":false,"msg":"看不懂這張單：…"}`、刪單、記 notes。
  - `rm`：NAME 正在某顆 cpu 上 → 寫 idle 到 `cpus/n.json.tmp`、`os.replace` 蓋過去（**不留 done 檔、不 link 去任何地方——拿掉就是拿掉**）、`st["cpus"][n]=None`；NAME 在佇列（`procs/NAME.json` 存在）→ `os.unlink`；兩邊都沒有 → `{"ok":false,"msg":"找不到這個行程：NAME（佇列、cpu 上都沒有；done/ 與 bad/ 裡的檔你自己刪）"}`。成功 msg：`"rm NAME（原本在 cpu2）"`／`"rm NAME（原本在佇列）"`。notes 加一句。
  - 寫 done 檔一樣先 `.tmp` 再 replace；處理完刪單。
- `USAGE` 補 `rm`。`aos-kernel-init` 印的提示補一行 `拿掉行程：aos-kernel rm K NAME`。

## B. 驗欄位＋連續 125 進 bad（清單 #2）

- `aos_kernel_add.py`：路徑轉完、寫進暫存檔之後、`os.replace` 之前，用 aos-exec 自己的驗證器驗一次——看 `aos_exec._run_inst` 怎麼叫 `aos_inst.load(target, base)`，對暫存檔照樣叫；丟 `aos_inst.InstError` 就刪暫存檔、`_fail("inst.json 過不了 aos-exec 的檢查：<錯誤原文>")`。這樣 Opus 那份多了 `timeout_ms` 的檔在 add 就被擋。
- `aos_kernel_tick.bad_reason()`：現有四條檢查之後再加 `aos_inst.load` 那一關（InstError 的字串就是退件原因）。手放進 `procs/` 的壞檔也會被退、原因精確。
- 跑起來才壞的（cwd 之後被刪、stdout 的資料夾不存在…）：`_one_cpu()` 裡在 done 判斷之後加：`ent["last_kind"]=="aos"` 而且 `runs_now - cur["runs_at"] >= 2` → `cur["aos_ticks"] = cur.get("aos_ticks",0)+1`，否則歸 0；`aos_ticks >= 2` → 搬去 bad：跟 `_finish` 同樣兩步（idle 寫 tmp、`os.link(cpus/n.json, procs/bad/NAME.json)`、replace），`st["cpus"][n]=None`，notes：`"退件 NAME（cpu%d 上連續回 125：aos-exec 自己失敗；原因跑 aos-exec K/procs/bad/NAME.json --stderr - 看）"`。**為什麼 runs_at+2**：跟 done 那條同一個理由（換人那一刻手上那次還是舊行程的）。

## C. `ls`／`boot`／`add` 的輸出（清單 #3、#6）

- `ls` 表頭 `PID` 改 `PROC`；多一欄 `LAST_EXIT`：daemon 那筆的 `last_exit`，`last_kind=="aos"` 時印成 `125(aos)`，沒資料印 `-`。
- `ls`／`add`／`rm` 遇到「不是 kernel 的家」（資料夾不存在或沒 `config.json`）統一一句：`aos-kernel: X 不是 kernel 的家（還沒灌？先跑：aos-kernel-init X --ncpu N）`，退出碼 1。`here_or_die` 與 `cmd_ls` 裡的 `os.chdir` 失敗訊息都改成這句。
- `boot`：`aos_daemon_ctl.ask()` 加 `quiet=False` 參數，`quiet=True` 時不印 `ok=… result=…` 那行；boot 用 `quiet=True`。
- `add` 印完「排進去了」再一行 `（下一回合才會出現在 aos-kernel ls）`。

## D. 文件（清單 #4、#5；大白話）

`proto4-3/README.md`：
- 開頭那段規格連結（`../proto4/notes/…` 那五行）搬到檔尾新節「出處」。
- 「怎麼跑」：`./aos-daemon &` 那行改成兩行：`setsid -f ./aos-daemon   # 上電（腳本／非互動 shell 用這個，不會被帶走）` 與 `./aos-daemon &            # 互動終端可以這樣`；kernel 四行後面加 `./aos-daemon-ctl stop   # 關機`。
- inst.json 範例旁補三句：`cwd` 用 `aos-kernel add` 排可以省略（＝inst.json 所在資料夾），手放 `procs/` 就一定要寫、沒寫會退件；相對路徑的基準：`cwd` 以 inst.json 所在資料夾為準、`argv[0]` 以（轉完的）cwd 為準；`add` 會用 aos-exec 的規則驗一遍，多寫的欄位會被擋。
- 「檔案」那整節（Python 檔職責表）搬到新檔 `docs/files.md`，README 留一行連結。README 保持 300 行以下。
- 「四支工具」表 aos-kernel 那列補 rm。

`proto4-3/docs/kernel.md`：家的清單加 `syscalls/`、`syscalls/done/`；「每回合五步」變六步（第 2.5 步處理 syscalls）；`procs/done/`＝「回 100 收工的」，rm 拿掉的不會進去；`procs/bad/` 補「跑起來連續 125 的也會進來」；「沒做什麼」拿掉已做的、補「syscall 目前只有 rm；rm 不會殺正在跑的那一次（跟搶佔一樣，手上那次會跑完）」。

`proto4-4/README.md`：`:json` 那段加「解出來的 key 是字串，`(get v "count")`」；aos-step 那段加「每格會把那個 form 的值印到 stdout」、範例後面加 `echo $?   # 全部跑完那次回 100`；加一小段「卡住了怎麼看」：`aos-step prog.janet --status` 的 `:error` 有全文、跑在 kernel 上就 `aos-exec 你的.json --stderr -`。

`proto4-4/src/step.janet`：失敗時 stderr 只印第一行（`aos-step: 第 N 個 form（0 起算）失敗：<錯誤第一行>`），後面加 `（全文：.aos-step/error 或 --status）`；stacktrace 全文照舊寫進 `.aos-step/error`。測試字串跟著改。

## 測試（`test/test_kernel.py` 照既有寫法）

至少 8 條：rm 佇列中的（不用開 daemon：直接叫 `handle_syscalls`）；rm 正在 cpu 上的（真開 daemon，之後 `cpus/n.json` 是 idle、`state.json` 那顆 null、`done/` 裡沒有它）；rm 不存在 → done 檔 ok false、指令退出碼 1；看不懂的單 → ok false；add 多一個 `timeout_ms` 欄位被擋且 `procs/` 沒多檔；手放含未知欄位的檔 → 退件、log 有 aos-exec 的錯誤字；連續 125 → 進 `bad/`、cpu 回 idle（inst 的 `stdout` 指到不存在的資料夾就會每回合 125）；`ls` 有 `PROC` 與 `LAST_EXIT`；`ls 不存在的家` 訊息含 `aos-kernel-init`；boot 輸出不含 `ok=`。

全綠：
```
cd /home/lorkhan/repo/simple_tools/aos/proto4-3 && python3 -m unittest discover -s test 2>&1 | tail -2
cd /home/lorkhan/repo/simple_tools/aos/proto4-4 && for t in test/*.janet; do janet "$t" || echo "FAIL $t"; done
```
`aos_kernel_tick.py` 若超過 300 行就把 `_finish`／搬 bad 的共用兩步抽到 `aos_kernel_syscall.py` 或新檔 `aos_kernel_swap.py`。文件裡每個相對連結目標 `ls` 得到。

## 回報（十二行以內，大白話）

- A／B／C／D 各一行：做了什麼、改哪些檔。
- 測試數與最後一行原文（Python 一套、Janet 三支）。
- 自己決定的事、撞到的坑、沒做到的，一條一句。
