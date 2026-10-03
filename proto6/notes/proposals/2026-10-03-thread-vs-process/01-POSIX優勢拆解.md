# 一、把「POSIX 的優勢」拆開看

← [入口](README.md)｜下一份：[分層](02-分層.md)

「捨棄 POSIX 的優勢」不是一件事，是十幾件。下面逐項看：現在靠什麼得到、thread 版（B）會不會失去、失去了有沒有別的方法補。選項定義見入口：**A** 全程序、**B** tick 進 daemon 當 lib、**C** 混合（兩種都收）。

「任務」在三個選項下都還是子程序（`aos_tick_run.py` 第 75 行 `subprocess.Popen`），所以**任務層的優勢三個選項都在**。差別只在 tick 這一層。

## 逐項

| # | 優勢 | 現在怎麼得到 | A | B | C | 備註 |
|---|---|---|---|---|---|---|
| 1 | 任務用任意語言 | 任務＝inst 的 argv | 留 | 留 | 留 | 三案相同 |
| 2 | tick 本身可換語言／換實作 | daemon 只叫 `aos-exec <inst>`，inst 的 argv 寫什麼都行 | 留 | 失 | 留（argv 路） | B 下 tick 必須是 daemon 能 import 的 lib |
| 3 | tick 當掉不拖垮 daemon | 另一個程序 | 留 | 失 | lib 路失 | Python 例外可以包；segfault、OOM、`os._exit`、無限迴圈包不住。C++ 改寫後風險變大 |
| 4 | tick 可殺 | `kill <pid>` | 留 | 失 | lib 路失 | thread 殺不掉。只能殺它正在等的任務程序，讓 wait 回來 |
| 5 | 資源邊界（prlimit、nice、cgroup 一框） | 包在 argv 外面 | 留 | 失 | lib 路失 | B 下 tick 跟 daemon 同一份限制 |
| 6 | 帳號邊界 | 帳號模組／包 sudo | 留（外面包） | 失 | lib 路失 | 使用者已定：要切帳號就外面另開 daemon。B 的失去與此方向一致 |
| 7 | 每程序獨立的 cwd、env、umask、signal mask | 作業系統給 | 留 | 失 | lib 路失 | 現行 tick 靠 `os.chdir`（`aos_tick.py` 第 132 行）與 `os.environ`（`aos_tick_run.py` 第 35 行），B 要全改成傳參數 |
| 8 | fd 表隔離（鎖 fd、漏掉的 fd） | 作業系統給 | 留 | 失 | lib 路失 | thread 共用 fd 表；一個 tick 漏 fd 全 daemon 一起漏 |
| 9 | 可觀察（`ps`、`top`、`/proc/<pid>`、`strace -p`） | 一格一個 pid | 留 | 半失 | 半 | thread 在 `ps -L` 看得到，但名字要自己設；`strace -p daemon` 看到全部混在一起 |
| 10 | 可組合（`timeout`、`bwrap`、`systemd-run`、`env -i`、`strace` 包一層） | 改 inst 的 argv 就行 | 留 | 失 | 留（argv 路） | 這是 inst JSON 最大的價值 |
| 11 | 可單獨測試、人手跑 | `bin/aos-tick <dir>` | 留 | 留（保留 CLI 薄殼） | 留 | 但 B 下 daemon 走 lib、人手走 CLI，是兩條路，測試要各測 |
| 12 | 換新版 tick 不重開 daemon | 下一格 exec 新檔 | 留 | 失 | lib 路失 | B 要加 reload 或重開 |
| 13 | daemon 重開時格的語意 | tick 程序握 flock，daemon 死了格照跑、鎖照握 | 留 | 失 | lib 路失 | B 下 daemon 死＝tick thread 死、鎖立刻放；setsid 的任務還活著，新 daemon 下一格會跟孤兒任務重疊。補法：鎖 fd 傳給任務（翻 B-602 一句） |
| 14 | 多核真並行 | 各自一個直譯器 | 留 | 半失 | 半 | Python GIL；tick 幾乎都在 `wait()`，影響小。C++ 無此事 |
| 15 | inst JSON 是統一單位 | daemon 的一項＝一份 inst | 留 | 變 | 兩種 | B 下「一項」要重新定義（資料夾？函式？） |
| 16 | C++11 改寫可分開做 | tick 與 daemon 是兩支程式 | 留 | 失 | 留一半 | B 下兩支要同時改寫，或 C++ daemon 嵌 Python |

## B 真正換到的

| 換到什麼 | 多大 | 說明 |
|---|---|---|
| 每格省一次程序啟動 | Python aos-tick 17 ms（現行鏈連 aos-exec 共 42 ms）、C／C++ 0.07～0.43 ms（[實測](03-實測.md)） | 跟一次 LLM 呼叫的秒級比，看不見；而且 42 裡的 25 用 A′ 就省掉 |
| 每格省一份直譯器記憶體 | 一支 aos-tick 約 16 MB RSS（[實測](03-實測.md)） | 同時 100 格差 0.4～1.6 GB；同時數小時看不見 |
| 程序內共享狀態 | 真的有 | daemon 能直接看到 tick 跑到第幾項、不用經檔案；但使用者的 FUSE 方向本來就要把狀態攤成檔 |
| 鎖「比 .lock 檔好處理」 | 幾乎沒有 | flock 在同程序不同 fd 之間一樣互斥（[實測](03-實測.md)）；而且只要人手還能跑 `aos-tick`（B-627），檔案鎖就省不掉 |
| FUSE 認身分 | 不需要 B | 用路徑認（`me` 連結）兩案都行；用 pid 認，A 是 pid、B 是 tid，都分得出（已實測，[分層](02-分層.md)） |

## 一句話

B 失去的是 tick 這一層的 2～13、16，共十二項；換到的只有啟動時間、記憶體與程序內共享，三項在現在的量級下都看不到。任意語言那條（1、2、10）**任務層不受影響**，受影響的只是「有沒有人要把 tick 本身換掉」。
