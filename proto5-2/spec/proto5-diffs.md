# 跟 proto5 不變那幾份的差句

← [spec 導航](README.md)｜哪幾份「不變」見 [proto5-2 README](../README.md) 的表

proto5-2 決定不改 proto5 的規範，這份只列：README 那張「不變」表列的幾份裡（cpu、agent、aos-agent、aos-llm、
aos-exec、inst-posix、directives，以及 kernel 的 syscall／判定／鏈、daemon 的拉孩子），哪一句話落地時其實要換、
換成什麼、依據 proto5-2 哪一檔。**proto5 那邊的字一個字沒動**，這裡只是先記著。

被 proto5-2 整節取代的節（例如 kernel §1／§1.1／§1.2／§3／§6、daemon §1／§1.2／§3／§4／§5／§6.1）
不逐句列在這裡，見 [spec/README.md](README.md) 各檔「取代 proto5」欄。

## kernel：syscall、判定、鏈（不變的三節）

| proto5 位置 | 原句（短引） | proto5-2 的新說法 | 依據 |
|---|---|---|---|
| [kernel/syscall.md §2](../../proto5/spec/kernel/syscall.md) | `add` 的 `pool`「預設 `default`，必須是 info.cpus 裡有的、且不是 `kernel`」 | 必須是 `info.pools` 的 key、且不是 `kernel` 池 | [kernel-info.md §1、§3](kernel-info.md) |
| [kernel/no-overlap.md §7](../../proto5/spec/kernel/no-overlap.md) | 「boot 不跑格、先把舊 kernel cpu 收掉等它從孩子表消失才開新鏈」 | 改成先把 kernel 池縮到 0，等 daemon 的 `summary.json` 顯示這池 `running 0`、`killing 0`（或整個消失）才開新鏈——daemon 那邊已經沒有「孩子表」可偷看 | [handoff.md §1 第 2 步](handoff.md) |

`kernel/echo.md`（§4 回音怎麼判）沒有要換的句子，判定規則一字不改（[kernel-tick.md 第 6 步](kernel-tick.md) 也這樣寫）。

## cpu 範式與 exec cpu

| proto5 位置 | 原句（短引） | proto5-2 的新說法 | 依據 |
|---|---|---|---|
| [cpu/stop.md §5.4](../../proto5/spec/cpu/stop.md) | 「**kernel**：往它管的每顆 cpu 放 `stop-*.json`（kernel.md §3），不發訊號」 | 這句作廢：kernel 不再往每顆 cpu 放 `stop-`；停機改成把每個工作池的宣告縮到 0，讓 daemon 用批次階梯收，一池一張單 | [handoff.md §3](handoff.md) |
| [cpu/lifecycle.md §6.1 第 3 步](../../proto5/spec/cpu/lifecycle.md) | 「fd 0 接 `/dev/null`、fd 1 接 fd 2」（前提是父行程給了一對 pipe 當控制通道） | 補充：父行程（daemon）給的 fd 1 現在本來就可能是 `/dev/null`，不一定是 pipe；cpu 照樣把它搬到高位，程式不用改（`aos_exec_cpu.py` 的 `Control.relocate()` 已經這樣做） | [daemon-reconcile.md §5](daemon-reconcile.md) |

## agent 資料夾

| proto5 位置 | 原句（短引） | proto5-2 的新說法 | 依據 |
|---|---|---|---|
| [agent/info.md §3](../../proto5/spec/agent/info.md) | `llm.pool`：「問模型的工作派去哪個池；K 的 `info.cpus` 裡要有這個池的 cpu，否則 kernel 退件」 | 改成「是 `info.pools` 的 key，否則 kernel 退件」；`tool_pool`、`tick.pool` 兩格照同一條驗法換（原文沒單獨寫驗法，但送單時 kernel 用同一套 pool 檢查） | [kernel-info.md §1、§5](kernel-info.md)、[kernel-cli.md `check`](kernel-cli.md) |

## aos-agent

| proto5 位置 | 原句（短引） | proto5-2 的新說法 | 依據 |
|---|---|---|---|
| [aos-agent/collect.md §6.1](../../proto5/spec/aos-agent/collect.md) | `result.kind=aos` 那列：「aos-llm call 沒跑起來（kind=aos），看 `<K>/cpus/<llm 池的 cpu>/cpu.log`」 | 路徑改成 `<K>/pools/<池>/cpus/*/cpu.log` | [kernel-home.md §1](kernel-home.md) |
| [aos-agent/cli-status.md §1.3](../../proto5/spec/aos-agent/cli-status.md) | 「K 知道且 [kernel 健康](../kernel/README.md) 不是 ok」，判定共用 `lib/aos_kernel_health.py` | 這行字不用改，但它呼叫的判定邏輯換了：改看池摘要（`k1-kernel` 的 `running` 是 0 才算 kernel cpu 不在，工作池少了改印 warn） | [kernel-cli.md `ls`](kernel-cli.md) |
| [aos-agent/register.md §11](../../proto5/spec/aos-agent/register.md)、[pause-clean.md §10](../../proto5/spec/aos-agent/pause-clean.md) | 兩份都靠偷看 `K/state.json` 的 `procs`／`replies`，或 `done_exit`／`bad_after` 兩個退出碼設定 | **不用改**：帳本第 2 版的 `procs` 一字不改，`acks`／`replies`／`deletes` 也同 proto5（astra 核對過） | [kernel-ledger.md §2](kernel-ledger.md) |

## aos-llm

| proto5 位置 | 原句（短引） | proto5-2 的新說法 | 依據 |
|---|---|---|---|
| [aos-llm/usage.md §1](../../proto5/spec/aos-llm/usage.md) | 「`envs` 只在那顆 cpu 第一次建家時抄進去；之後要改得照 kernel.md §1.1 的步驟（stop、改 `K/cpus/<c>/inst.json`，boot）」 | 改成「改池的 `envs.json`，之後（重）拉的 cpu 生效；要讓活著的立刻換，用 `aos-daemon kill --pool <dpool> --all`」 | [kernel-home.md §2](kernel-home.md)、[daemon-cli.md `kill`](daemon-cli.md) |

## daemon：拉一個孩子（不變的那節，只是拿掉 `spawn`）

| proto5 位置 | 原句（短引） | proto5-2 的新說法 | 依據 |
|---|---|---|---|
| [daemon/spawn.md §2](../../proto5/spec/daemon/spawn.md) | 「**fd 0、fd 1 一律接成控制 pipe**（範式 §3）：fd 0 daemon 寫、孩子讀；fd 1 孩子寫、daemon 讀」 | 只留 fd 0 那條（daemon 寫、孩子讀 `go`／`stop`、看 EOF）；孩子的 fd 1 接 `/dev/null`，開檔數減半 | [daemon-reconcile.md §5](daemon-reconcile.md) |
| [daemon/spawn.md §2](../../proto5/spec/daemon/spawn.md) | 「客戶收不到回音會重送 `spawn`，同名同目標 → 回它的 pid（冪等）」 | 沒有 `spawn` 這個 method 了：daemon 照 `pool.json` 的宣告，自己每一圈把孩子補到位、照節流慢慢拉，不用客戶重送；撞名判斷搬進 `scale` 回音的 `NameTaken` | [protocol.md §1](protocol.md)（拿掉 `spawn`）、[daemon-reconcile.md §2、§4](daemon-reconcile.md) |

拉的順序本身（fork → 寫孩子的檔 → `go` 握手 → 回音）、process group 的分法、`target` 每次重讀，這些沒變。
