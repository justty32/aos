# 2026-11-05 晚 不靠 pid 找東西、`--env` 只收 .env、工具要想到環境變數脫鉤（no-pid，使用者方向；未實作）

← [thinking README](../../../README.md)｜日 [2026-11-05](../README.md)｜相關：[arch-refactor](../arch-refactor/README.md)（S6 照本條走）、[small-thought § 使用者裁定](../small-thought/README.md#使用者裁定11-05-夜排在大重構之後做)

## 使用者原文（11-05 晚，逐字）

> hmmm，其實我一直覺得，靠着pid來找東西，不太符合我們aos體系的概念。除去daemon本身與linux原生proc有所接觸，可能會透過pid來強行控制一些東西，或是弄一些linux原生的特殊機制外，其他人若有相關需求，最好都是透過daemon進行轉接。至於如何找到daemon，大多時候是透過環境變數。對了，tool那塊我突然想到，--env後面接啥？你要是跟我說接一堆xxx=yyy，那很醜，建議是限制只能接.env，除此之外也建議，工具在設計之初，最好是要考慮到環境變數可能會脫鉤這件事。

## 使用者補充（11-05 晚，逐字）

> 1.糟糕，看來這個得重構了。具體等明天吧，今天距離睡覺不到三小時，就都先聊一聊，做規劃就好。2.hmmm，其實在一些需求不大的場景，稍微覆蓋一兩個環境變數也是可以，或者改成--env-file xxx搭配--envs K=V...也不錯，兩者並存吧。

## 定下的方向

1. **只有 daemon 碰 pid**：daemon 本身可以用 pid 對 Linux 行程做強制控制或特殊機制；其他人（aos-agent、aos-daemon-ctl、lib 工具、範本）要找東西、判斷死活、控制，都**請 daemon 轉接**。找 daemon 靠環境變數（`AOS_DAEMON`）。
2. **`--env-file FILE` 與 `--envs K=V`（可重複）兩種並存**（補充 2 取代原文「限制只能接 .env」）：aos-tools 今晚加的「`--env K=V` 可重複」改成這兩個；「`aos-agent tools add` 也帶 env」那題（值不給腦看）也照這個形狀做。明天做。
3. **工具設計原則**：一開始就考慮環境變數可能脫鉤（借給 thought 的子、進沙箱、搬家）——寫進 conventions 或 lib/docs。

## 現在靠 pid 的地方（隊長 11-05 晚 grep 盤點，未細分）

| 誰 | 做什麼 | 處理 |
|---|---|---|
| `aos-daemon-ctl` | `proc_alive`：拿 `procs_state.json` 的 pid＋started_at_ticks＋boot_id 對 `/proc` 判 daemon 活著（ls、寄信前提醒） | S6：改請 daemon 回答（或只看 daemon 自己寫的心跳），不自己對 `/proc` |
| `aos-agent` | 讀 state 的 pid 對 `/proc/<pid>/stat`（約 :192）判活著；`/proc` 掃 argv＋`AOS_STACK` 找行程（約 :489）；paused 判斷比 pid（約 :457）；暫時回信信箱名帶 pid、kill -9 殘留靠 pid 不在才清（:308～:343） | S6：判活著、找行程、paused 走 daemon；暫時信箱清理另想（不靠 pid） |
| `lib/agent/thought` | 子的 state 記 `running <pid>`、`pid_alive` 用 `kill 0` 對帳 | 明天：改問 daemon（子本來就掛在 daemon 下） |
| `lib/agent/agents`、`self_tools`、`memory`、`base/bash`、`run_python`、`aos-mcp`、`agent-fsm/brain.py`、`aos-tools` | `killpg(自己剛開的子行程)` 逾時收拾；tmp 檔名帶 `getpid()` | 自己生的子行程收拾與 tmp 檔名不算「找東西」，代定**不改** |
| 沙箱（11-05 第二輪邊緣） | thought 在沙箱裡看不到 daemon 的 pid → 誤判 daemon 不在 | 隨 thought 改問 daemon 一起解；沙箱裡先不支援（已裁） |

## 排程（補充 1：今晚只規劃、不改程式）

- 第 1 條**明天先做規劃**（daemon 怎麼轉接「找東西、判活著、控制」；派 fable），定案後才做程式。
- **S6**（arch-refactor）**今晚不開工**，等第 1 條規劃定案後照新設計做；S0～S5 照原計畫。
- 第 2、3 條：明天做。
