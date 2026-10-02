# daemon 收屍／cgroup 模組：每項一個框，跑完清乾淨

← [daemon 目錄](README.md)｜[核心 B-640](core.md)｜[控制 B-641](control.md)｜[重讀設定 B-642](reload.md)｜[記住狀態 B-643](state.md)｜格式：[P-124](../protocol/daemon/cgroup.md)｜舊設計：[暫緩區 B-605](../deferred/daemon/cgroup.md)

本篇只有 B-644，寫收屍／cgroup 模組**做什麼**。設定怎麼寫、stdout 的行、框的名字，寫在格式篇 [P-124](../protocol/daemon/cgroup.md)。

依據：[verdicts 11 篇末「2026-10-01 第十二批：cgroup 與帳號」](../../../notes/verdicts/11-tick-as-unit/14-1001-第十二批.md#2026-10-01-第十二批cgroup-與帳號)、[plan m3m 模組二](../../../plan/m3m-daemon-modules.md#模組二收屍與資源上限modulescgroup)；現行程式 [收屍／cgroup](../../../src/py/README.md#收屍cgroupm3m-模組二)（`lib/aos_daemon_cgroup.py`，有出入以程式為準）。

## B-644：收屍／cgroup 模組〔使用者 2026-10-01 第十二批〕

**每一項一個 cgroup 框；每次 `aos-exec` 開在那一項的框裡，結束後把框裡留下的程序全部殺掉、等清空，才算這次結束。** 任務用 `&`、`setsid`、double fork 留下的背景程序，都在這一刻清掉。它也讓每一項可以有自己的資源上限。它是 daemon 的一個模組（[B-640](core.md)「模組」），設定檔寫了 `modules.cgroup` 才有。

### 子樹從哪來

- **子樹根＝daemon 自己所在的 cgroup**，沒有另外的設定。要求它是委派給 daemon 的 cgroup v2 子樹，例如這樣開：`systemd-run --user --scope -p Delegate=yes aos-daemon --config F`。
- daemon 開起來先在根下開子框 `daemon`，把根上**所有**程序搬進去（cgroup v2 規定開了 controller 的那層不能放程序），再在根上開 `cpu`、`memory`、`pids` 三個 controller 裡根上有的那幾個。
- daemon 開起來時自己已經在某個 `.../daemon` 框裡（例如同一個 scope 裡被重開），就拿它的上一層當根。
- **沒有委派好的 cgroup v2**（例如直接在 WSL 的 `/init.scope` 開、cgroup v1）：照 POC 總原則自然丟錯、回 1，**不退回**沒有 cgroup 的做法（使用者同意 C1）。daemon 不另外檢查是不是真的委派：建得了框、搬得動程序就照用。

### 每一項的框

- 每一項一個葉框，名字是 `i-` 加 inst 字面值的雜湊（[P-124](../protocol/daemon/cgroup.md)；使用者同意 C4：重讀設定後「第幾項」會變，所以不用位置）。字面值有 `/`，不能直接當框名。
- daemon 開起來時就替每一項建好框；框已經在（同一棵子樹裡上次留下的）就**先把裡面的程序殺光**再用。
- **開框時 stdout 印一次對照**：`inst=<inst> cgroup=i-<h>`，在那一項任何 `exit=` 行之前。
- **上限**：那一項設定裡的 `cgroup` 物件，鍵是 cgroup 的檔名、值是字串，**原樣寫進框裡**（例如 `"memory.max": "512M"`）；daemon 不翻譯、不檢查是哪些檔（使用者同意 C2）。沒寫就不設限。寫不進去（檔不在、值不對、那個 controller 沒開）自然丟錯：開起來時回 1。
- 不同項的框互不相干；兩項是同一個 inst 字面值不可能（`insts` 的鍵不重複）。

### 每次跑

1. 開 `aos-exec` 的子程序先把自己放進那一項的框，再變成 `aos-exec`（pid 不變、結束碼原樣）。
2. `aos-exec` 結束（`ms=` 算到這裡）後，框裡還有程序就寫 `cgroup.kill`——**直接 SIGKILL，不先送 SIGTERM**（使用者同意 C3：任務要收乾淨，自己在結束前收）——等框清空。
3. 清空之後才印那一行 `exit=`；有清到東西時接著另印一行 `inst=<inst> reaped`。
4. 下一次才排：「上一次結束」改成「`aos-exec` 結束**而且**框清空」。所以同一項的殘留絕不會跟下一次疊著跑。

殘留的程序如果還拿著 `aos-exec` 輸出的管子（`exec_out_path`／`exec_err_path`），清完它們管子才關；輸出照樣收齊寫出。

### 跟其他模組

- **控制模組**（[B-641](control.md)）：不用改。清框期間 `status` 的 `running` 仍是 `true`。
- **重讀設定**（[B-642](reload.md)）：新加的項建框、寫上限，`added` 之後印對照；還在的項上限改了就重寫新設定裡寫的那幾個檔（新設定拿掉的鍵**不還原**，要還原就寫 `"max"`）；**拿掉的項等最後一次跑完、清完再刪框**（那個 inst 已經又被加回來就不刪，新的一項接著用同一個框）。建框、寫上限出錯算重讀出錯：整份不套用、stderr 一行、舊的照跑（出錯前已經寫進去的不還原）。
- **記住狀態**（[B-643](state.md)）：框不記。暫停、已停的項照樣有框。
- **Ctrl-C**：照核心「直接退出、不殺子程序」；框留著，下次在同一棵子樹開起來時才清。

### 先不做

逃生口（任務自己開子框留常駐程序）、逾時砍、`kill` 指令、量測寫進 status、`aos-cg` 每任務一框（[B-634](../deferred/cg.md)）跟項的框接起來、多個 daemon 用同一棵子樹的偵測、沒 cgroup 時退回程序群組。舊設計的 node 框、交框、`cgroup_root`、`--create-cgroup`、`cgroup=on/off`、子樹鎖都在[暫緩區 B-605](../deferred/daemon/cgroup.md)。

依據：使用者 2026-10-01 第十二批：C1～C4「都先按照建議。」

**驗收：**用 `systemd-run --user --scope -p Delegate=yes` 開：子樹根下只有 `daemon` 與每項一個 `i-<h>`，daemon 在 `daemon` 裡；stdout 每項一行 `cgroup=` 對照、在 `exit=` 之前。任務 `sh -c 'sleep 1000 & exit 0'`（或用 `setsid` 跳出 session）：`exit=0` 之後有 `reaped`，`sleep` 已經不在、框的 `cgroup.procs` 是空的；週期很短時下一次開始前上一次的殘留都已不在；殘留拿著輸出管子時照樣印 `exit=`、輸出照寫。`memory.max: "64M"` 寫進框是 `67108864`；`pids.max: "5"` 時任務 fork 不出第 6 個。同一 scope 裡 daemon 被 `kill -9` 再開：上次留在框裡的程序被清掉。重讀設定加項建框、拿掉項刪框。上限寫不進去：開起來時回 1、重讀時 stderr 一行。直接在沒委派的 cgroup 開：回 1、stderr 有 traceback。沒掛模組：原有測試全過。測試見 `proto6/src/py/tests/test_daemon_cgroup.py`（拿不到委派的 scope 時整組跳過）。
