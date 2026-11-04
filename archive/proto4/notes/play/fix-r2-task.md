# 任務書 fix-r2：試玩第一輪剩下的三件——`aos-exec --stderr`、`aos-kernel-boot`、`aos-kernel add`

你在 repo `/home/lorkhan/repo/simple_tools/aos`。先讀 `proto4/notes/play/README.md` 的清單（#3 後半、#5、#9 這三條，使用者已拍板「做」）、`proto4/notes/16-19-kernel.md` 的 §19.3（boot 的語意是使用者自己定的，照那個）。**只准改**：`proto4-3/aos_exec.py`、`proto4-3/aos_run.py`、`proto4-3/aos_kernel.py`、`proto4-3/aos_kernel_init.py`、新檔 `proto4-3/aos_kernel_boot.py` 與 `proto4-3/aos-kernel-boot`（照 `aos-kernel-init` 那個薄殼的寫法，記得 `chmod +x`）、需要的話新檔 `proto4-3/aos_kernel_add.py`、`proto4-3/test/test_targets.py`、`proto4-3/test/test_kernel.py`、`proto4-3/README.md`、`proto4-3/docs/exec.md`、`proto4-3/docs/kernel.md`、`proto4-4/README.md`。其他一律不碰。**不要 git commit、不要 push。** 不要開其他 agent。不要順手重構。

工作樹裡已經有上一輪（fix-r1）改好的東西，**先跑一次兩邊測試確認是綠的再開工**，最後也要綠。

## A. `aos-exec --stderr PATH|-`（#3 後半）

新手最常鬼打牆的一點：inst.json 沒寫 `stderr`，子程式的錯誤全進 `/dev/null`，畫面一片空白。

- `aos-exec XXX --stderr -`：子程式的 stderr **繼承 aos-exec 自己的 stderr**（就是印到畫面）。`--stderr 路徑`：寫到那個檔（相對路徑以**aos-exec 被呼叫時的 cwd** 為中心，不是 inst 的 cwd——因為這是使用者在命令列打的）。
- 只蓋 `stderr` 這一條；`stdin`／`stdout`／`exit` 不做。蓋掉 inst.json 的 `stderr`，**也蓋掉 `{"$opt":"merge"}`**。
- 普通檔案目標（不是 .json、不是資料夾）三條流本來就繼承，`--stderr -` 等於沒事、`--stderr 檔` 照樣把 stderr 導去檔（用得到）。
- 實作：`run_target(..., stderr=None)` 多一個關鍵字參數（預設 None＝照 inst.json），`_run_inst` 開串流那段：`stderr == "-"` → `ferr = sys.stderr`（**不要 close 它**）；字串 → `open(路徑, "wb")` 進 `opened`；開不起來一樣是 125 那條路。`main()` 加 `--stderr`。
- `aos-run` 也收 `--stderr` 原樣轉給 `run_target`（它每回合都叫這個），用法字串補一句。daemon／ctl **不動**。
- 測試（`test/test_targets.py` 加 4 條，照那檔的風格）：inst 沒寫 stderr ＋ `--stderr -` 看得到子程式的錯字；`--stderr 檔` 檔裡有；inst 寫了 `merge` ＋ `--stderr 檔` → stdout 檔裡沒有錯字、`--stderr` 的檔裡有；`--stderr /不存在的目錄/x` → 125。
- 文件：`README.md`「沒做什麼」第一條「沒有覆蓋串流的旗標」改成「只有 `--stderr` 一個覆蓋旗標（`-`＝印到畫面），stdin／stdout／exit 不蓋」；「怎麼跑」aos-exec 那幾行加一行 `./aos-exec /path/to/folder --stderr -   # 看不到錯誤時先加這個`；`docs/exec.md` 退出碼那節前面加一小段「看不到錯誤？加 `--stderr -`」三四行。`proto4-4/README.md` 手動跑 aos-step 那段若有 aos-exec 的例子也補上。

## B. `aos-kernel-boot K`（#5 前半）

語意**照 §19.3 使用者定的**，不要照 §19.2：

1. `K` 不是 kernel 的家（沒 `config.json`／`inst.json`）→ stderr「aos-kernel-boot: K 還沒灌作業系統，先跑：aos-kernel-init K --ncpu N」，退出碼 1。
2. daemon 沒在跑（`aos_home.Home(resolve_home()).alive()` 為假）→ stderr「aos-kernel-boot: daemon 沒在跑（硬體沒上電），先跑：aos-daemon &」，退出碼 1。**boot 不開 daemon**（§9：daemon 的生死是使用者管的）。
3. daemon 的 `state.json` 的 `runs` 裡已經有 `realpath(K/inst.json)` 這把 key 而且 `state` 是 running／paused → 印「kernel 已經在跑了（pid N）」，退出碼 0（重複 boot 無害）。
4. 不然就做 `aos-daemon-ctl add K/inst.json --interval-ms <config.json 的 interval_ms>`——直接 import `aos_daemon_ctl` 呼叫 `ask(home, {"op":"add", "target": 絕對路徑, "args": ["--interval-ms", str(ms)]})`，不要 spawn 子行程。`--timeout-ms` 若 config 裡非 0 也帶。成功印「開機了：kernel 上了 daemon（K/inst.json，每 N ms 一回合）；看狀態：aos-kernel ls K」。
5. 旗標只有 `--home H`（跟 ctl 一樣，用 `aos_daemon_ctl._pop_home` 或同樣邏輯）；其他一律吃 config.json，不重複給。
6. `aos-kernel-init` 最後印的「開機：…」那行改成 `開機：aos-daemon & ； aos-kernel-boot K`（K 用真正的路徑）。

## C. `aos-kernel add [K] INST.json [--name NAME]`（#5 後半＋#9）

排行程進佇列的正式指令，取代 `cp 你的.json K/procs/<名字>.json`。

- 位置參數跟 `ls [DIR]` 同一套規則：兩個＝第一個是 K；一個＝K 是 cwd。K 不是家 → 跟 `ls` 一樣的錯。
- 讀 INST.json（用 `json.load`，不是 `aos_inst.load`——只是要幫忙轉路徑，不是要解析指示詞）。**幫忙轉絕對路徑**（#9）：
  - `cwd` 沒寫 → 用 INST.json 所在的資料夾；相對 → 以 INST.json 所在的資料夾為中心轉成絕對。
  - `argv[0]` 若含 `/` 且是相對 → 以（轉完的）cwd 為中心轉成絕對；不含 `/`（像 `sh`、`python3`）不動。
  - `stderr` 沒寫 → **不幫填**，但 stderr 印一句提醒「這份 inst.json 沒寫 stderr，出錯會看不到；建議加 "stderr":"err.txt"」（`{"$opt":"merge"}` 算有寫）。
- 檢查後才排：`cwd` 不是資料夾 → 拒收（退出碼 1，說哪個路徑）；`argv` 缺／空 → 拒收；`argv[0]` 含 `/` 但檔不存在 → 拒收。不要排進去讓 kernel 再退件。
- 取名：`--name NAME` 給了就用（不能含 `/`、不能已存在於 `procs/`、`procs/bad/`、`procs/done/` 或正在 cpu 上）；沒給就找 `procs/`、`procs/bad/`、`procs/done/` 與 `state.json` 的 `cpus`／`queue` 裡所有純數字名字的最大值 +1，從 1 起。
- 寫檔：先寫 `procs/.NAME.json.tmp` 再 `os.replace` 到 `procs/NAME.json`（kernel 掃佇列只收檔案，`.tmp` 這種暫存名 kernel 會不會誤收？去看 `check_queue()`，會的話就改成寫在 `K/` 底下再 replace 進 `procs/`）。
- 印一行：`排進去了：K/procs/7.json  cwd=/abs/…  argv=[…]`。
- `aos_kernel.py` 若因此超過 300 行，把 `cmd_add` 放到新檔 `aos_kernel_add.py`，`aos_kernel.py` import 它；用法字串（`USAGE`）補 `add`。
- `aos-kernel-init` 最後印的「把行程丟進佇列：cp …」改成 `排行程：aos-kernel add K 你的.json（cwd／argv 相對路徑會幫你轉絕對）`。

## 測試（`test/test_kernel.py`，照既有寫法；boot 那幾條要真開 daemon 的放 `KernelDaemonTest`）

至少 9 條：
- boot：沒 init → 1 且訊息含「aos-kernel-init」；daemon 沒跑 → 1 且訊息含「aos-daemon」；正常 → 0、daemon `state.json` 的 `runs` 有 kernel 那把 key、`args` 含 `--interval-ms` 與 config 的值；再 boot 一次 → 0、訊息含「已經在跑」、pid 沒換。
- add：相對 cwd／argv 轉成絕對（讀回 `procs/1.json` 比對）；沒寫 cwd 用 inst.json 所在資料夾；自動編號跳過 `procs/done/3.json` 與 `procs/bad/5.json` 給 6；`--name foo` 生 `procs/foo.json`、同名再 add 拒收；cwd 不存在拒收且 `procs/` 沒多檔；沒 stderr 有提醒句；從別的目錄 `add K x.json` 也行。
- 至少一條端到端：`init` → 真開 daemon → `boot` → `add` 一個回 100 的行程 → 幾回合後在 `procs/done/`（可以改寫既有 `test_done_exit_moves_the_proc_to_done_and_idles_the_cpu` 讓它改走 boot＋add，不要另外抄一份）。

全綠：
```
cd /home/lorkhan/repo/simple_tools/aos/proto4-3 && python3 -m unittest discover -s test 2>&1 | tail -2
cd /home/lorkhan/repo/simple_tools/aos/proto4-4 && for t in test/*.janet; do janet "$t" || echo "FAIL $t"; done
```

## 文件（大白話，繁體中文）

- `README.md`「怎麼跑」kernel 那段改成四行：`aos-daemon &`（上電）→ `aos-kernel-init K --ncpu 2`（灌一次）→ `aos-kernel-boot K`（開機）→ `aos-kernel add K my-proc.json`、`aos-kernel ls K`。「四支工具」表格 aos-kernel 那列的一句話補 boot／add。README 保持 300 行以下。
- `docs/kernel.md`「指令：一支系列」加 `aos-kernel-boot`（開機＝把 kernel 放上 cpu，重複跑無害，不開 daemon、不 init）與 `aos-kernel add`；「開機順序」那段用新的四行；「沒做什麼」拿掉已經做了的、補「add 只轉 cwd／argv[0]，stdin／stdout／stderr／`$ref` 的相對路徑不轉（那些本來就是以 cwd 為中心）」。
- `proto4-4/README.md` 丟進 kernel 那段改用 `aos-kernel add`。
- 文件裡每個相對連結目標 `ls` 得到。

## 回報（十二行以內，大白話）

- A／B／C 各一行：做了什麼、改哪些檔、幾行。
- 測試數與最後一行原文（Python 一套、Janet 三支）。
- 自己決定的事、撞到的坑、沒做到的，一條一句。
