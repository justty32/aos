# prune 已完成自檢、舊列預覽與共用 rm 下表，測試和 scratch 實測通過，檔案保留，已進 `9edcf15d5`。

← [11-07](../README.md)

## 使用者原話（11-07，逐字）

> 給aos-daemon-ctl添加一個子指令，用於自檢與清理上次修改是很久以前的

本次依指定設計施工，已進 `9edcf15d5`。

## 設計與結果

`aos-daemon-ctl [--daemon D] prune [--older-than DUR] [--apply]`。沿用 aos_flags／P-44：共通旗標在子命令前；英文 help 與程式輸出、繁中文件。

每次先讀 procs_state（含切檔），自檢 stack 不在、既有 ctl 非 JSON 物件、running／stopping 的 pid＋started_at_ticks 與 /proc 不符、stopped 的 reason。ctl 沿用 B：daemon 寫的 loop 設定裡非空 ctl，否則 ctl.json。不解讀子項私有檔案。正常列不印；可疑列一行 `NAME: PHASE: PROBLEM`，仍退 0。

只對 stopped／sleeping 算 stack 資料夾本身與直接底下檔案的最新 mtime，不遞迴；stack 不在算無限久。（11-07 晚審註：這句已修正；目前缺 stack 的列不入選，只列自檢問題。）門檻只收正整數加 s／m／h／d；嚴格早於門檻才入選。沒門檻只自檢；`--apply` 沒門檻與錯時長均 ArgumentsBad、退 1。running／stopping 永不入選。

乾跑印 `NAME: would remove (last change TIME)`；apply 與 rm 共用 remove → deliver → send 的完整路徑，直寄 procs_removed，stack／ws 不刪檔；印 `NAME: removed`。rm 原有信名輸出不變，prune 隱去信名。寄信錯誤同 rm。

## 代定（可翻案）

- 同列多個問題以 `; ` 接起，控制字元換空白，維持一列一行。ISO 時間使用 UTC、`+00:00`。
- prune 收 rm 同款 `--timeout-s`／`--reply-to`，互斥及錯誤照舊。`removed` 表示移除請求已寄出；預設等信被認領，給 reply-to 只寄不等。這是 rm 的既有語意，實際下表看 ls。
- 每封移除信寄出前重讀該列及 mtime，已 start／wake 或最近有改的略過；仍是檔案快照與非同步 rm，沒有跨程序鎖住 start／wake 的原子保證。
- ctl 讀不了列為自檢問題；mtime 查不了則 StateBad、退 1，不把權限錯誤當很舊。缺 ctl 正常；缺 stack 才算無限久。（11-07 晚審註：這句已修正；目前缺 stack 不入選。）
- Python 沒有現成 pid 比對介面，因此照 aos-util 的 proc_started_at_ticks 算法：從 /proc/PID/stat 最後右括號後數到第 20 欄。只有 prune 自檢讀 /proc，ls 等原有指令仍不判活。
- 03 原已超標，新增說明放 04（改後 7955 bytes），未擴大整理範圍。

## 改了哪些檔

- 指令：[aos-daemon-ctl](../../../../cmd/aos-daemon-ctl/bin/aos-daemon-ctl)。
- 共用模組：[table.py](../../../../py/daemon_ctl/table.py)、[__init__.py](../../../../py/daemon_ctl/__init__.py)。
- 測試：[test_ctl.py](../../../../impls/aos-daemon/tests/test_ctl.py)，新增九項。
- 文件：[cmd README](../../../../cmd/README.md)、[指令 README](../../../../cmd/aos-daemon-ctl/README.md)、[04](../../../../cmd/docs/04-aos-daemon-ctl續.md)、[py README](../../../../py/README.md)、[建置與測試](../../../../impls/aos-daemon/docs/07-建置與測試.md)。
- 導航：[手寫 code map](../../../../../wf/workflows/common/code-map.md)；[生成冊](../../../../../wf/workflows/common/code-map/proto8/README.md) 的 README.md、cmd.md、impls.md、py.md。
- 紀錄：本 README、[當日索引](../README.md)、[日誌](../../../../../wf/session_logs/2026-11/2026-11-07.md)。沒有新增未完待辦。

## 測試與建置

從 repo 根跑，停用 bytecode；相關 pycache 殘留已清理。

```sh
PYTHONDONTWRITEBYTECODE=1 python3 proto8/impls/aos-daemon/tests/test_ctl.py
# Ran 16 tests ... OK; exit 0
PYTHONDONTWRITEBYTECODE=1 python3 proto8/impls/aos-daemon/tests/test_lifecycle.py
# Ran 17 tests in 33.943s ... OK; exit 0
```

共 33 項，涵蓋自檢、mtime 邊界與睡眠列、rm 路徑與錯誤、reply-to、apply 前重查、help 與用法錯誤。

完整 impls 建置：一般 cmake configure 因沙箱不准寫 `~/dev/vcpkg/buildtrees/vcpkg-running.lock` 退 1；使用已安裝相依、不再跑 vcpkg install 後通過：

```sh
(cd proto8/impls && cmake -B build -DVCPKG_MANIFEST_INSTALL=OFF && cmake --build build)
# [100%] Built target aos-llm_main; exit 0
```

`python3 wf/tools/codemap_gen.py --apply` 已跑；生成冊檢查及 `git diff --check` 通過。生成器原有兩個檔頭提醒（agent-fsm 的 llm.json、system.txt）與本次無關。

## scratch 五種列實測

以獨立工作區與真 daemon 驗過兩列舊 stopped、一列缺 stack、一列新 stopped 及一列 running。當時自檢、預覽、apply 與錯誤參數均符合實作；apply 後舊列與缺 stack 列下表，新列與 running 保留，既有 stack／workspace 的檔案與 SHA-256 不變，scratch daemon 已收工。這是 `9edcf15d5` 當時的結果；缺 stack 列當時會入選。

原始輸出見 git 歷史 `9edcf15d5`。
