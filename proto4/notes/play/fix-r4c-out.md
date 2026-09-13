已完成 fix-r4c，只修改 `proto4-3/`，未 commit、未 push。

改動：

- [aos_kernel.py](/home/lorkhan/repo/simple_tools/aos/proto4-3/aos_kernel.py)：新增 `wait_exit=101`、`bad_after=10` 預設；舊 config 自動補值。
- [aos_kernel_init.py](/home/lorkhan/repo/simple_tools/aos/proto4-3/aos_kernel_init.py)：新增 `--wait-exit`、`--bad-after`；既有家會提示 module 必須在 init 時掛。
- [aos_kernel_schedule.py](/home/lorkhan/repo/simple_tools/aos/proto4-3/aos_kernel_schedule.py)：新增 waiting 計數與讓出 CPU、一般非零退出連敗退件、保留既有 125 規則；`bad_after=0` 永不退件。
- [aos_kernel_status.py](/home/lorkhan/repo/simple_tools/aos/proto4-3/aos_kernel_status.py)：`ls` 顯示 CPU／佇列 waiting 與等待回合；區分 daemon 家未知與 daemon dead。
- [aos_kernel_tick.py](/home/lorkhan/repo/simple_tools/aos/proto4-3/aos_kernel_tick.py)：排程職責拆檔，維持單檔 300 行內。
- [aos_kernel_syscall.py](/home/lorkhan/repo/simple_tools/aos/proto4-3/aos_kernel_syscall.py)：`rm` 同步清除 waiting 狀態。
- [test_kernel.py](/home/lorkhan/repo/simple_tools/aos/proto4-3/test/test_kernel.py)：涵蓋新 config、舊 config、waiting 留駐／讓位／ls、連敗退件、停用退件、特殊退出碼、daemon 家訊息。
- [README.md](/home/lorkhan/repo/simple_tools/aos/proto4-3/README.md)、[kernel.md](/home/lorkhan/repo/simple_tools/aos/proto4-3/docs/kernel.md)、[files.md](/home/lorkhan/repo/simple_tools/aos/proto4-3/docs/files.md)：同步新規則、絕對 K 路徑、PATH 前提、module 提示及 config 欄位表。

測試：

- `proto4-3`：226 → **236，全綠**
- `proto4-4`：42／45／12 → **42／46／12，全綠**
- `proto4-6`：71 → **77，全綠**
- 根目錄 build 成功；ctest **8/8 全綠**
- `git diff --check` 通過，所有程式碼與 README 單檔均未超過 300 行。