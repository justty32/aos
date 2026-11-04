# T5：實作修正第 1 輪（2026-09-24）

← [rearch README](README.md)｜依據：[impl-review-report.md](impl-review-report.md)（A／B／C／D）、[lmstudio-run.md](lmstudio-run.md) ⑤

隊長派兩條 codex（gpt-6-astra）平行線：X＝exec／cpu／daemon，K＝kernel。
隊長補三份規範、lib README、code-map；run.sh 停 daemon 改用新 CLI。全套 883 → **917 條**，隊長自己連跑 3 次全綠，pgrep 空。

## 程式

| 項 | 狀態 | 做法 |
|---|---|---|
| A-1／B-2 daemon 缺檔 | 已做 | `spawn_target()` 目標不存在、資料夾缺 dir_target 一律 `SpawnFailed`（-32000）；inst 顯式 stdin／stdout 仍 -32602；同步入口不動 |
| A-2 控制 pipe 信封 | 已做 | `aos_exec_cpu` 驗 jsonrpc／method 字串／id 型別，stop 不可帶 id；不合整行忽略、stderr 記 `BadControl` |
| C-1 cpu 家半成品 | 已做 | `_create_cpu()` 與 `init()` 改「缺的補齊、已在不覆蓋」 |
| `aos-daemon stop` | 已做 | 不活不放檔；活的放 stop、等它退出；逾時退 1 |
| `aos-kernel ack` | 已做 | 回音不在＝NotFound 退 1、不放檔 |
| `init --cpu NAME[:POOL]` | 已做 | 可重複；沒 kernel 就自動加 k |
| kernel.log 空格不寫 | 已做 | events 空跳過 |
| `-h`、ls 摘要／`--json` | 已做 | ls 文字摘要，`--json` 等於 `status()` |

## 測試

- 補的崩潰窗口：**C-1**（mkdir 後、info 後各注入故障＋完整家不被覆蓋＋init 半成品）、**C-4**（回音已寫／原單已刪兩窗口真注入崩潰，副作用恰好一次）、**C-5**（閘門卡住「工作已退、回音未寫」再送第二次訊號，code 保留、stopped=false）、**C-6**（已出貨 stop 跨 boot：釘住 B-10 現況，新 kcpu 讀到舊 stop 退出）。
- 修 flaky：**D-1**（等 ready 再推進時鐘）、**D-2**（驗同組忽略 TERM 的後代死亡）、**D-3／D-4**（daemon 階梯與重拉改受控時鐘）、**D-5**（改明確事件同步）、**D-6**（輪詢解析完整 log 行、驗完整 response 與精確門檻）、**D-7**（週期改用受控 sleep 驗，整合測試不再量壁鐘下限）。
- 新 CLI 測試在 `test_daemon_cli.py`、`test_kernel_cli.py`。
- **跳過**：C-2（daemon 握手中段 KILL）、C-3（接手中 daemon 再死）、C-7（log append 前崩潰）、C-8（出貨箱逐箱邊界）——要多段閘門加真 KILL，留下一輪。

## 規範動了哪裡（只補句、不改節號；補句標「09-24 補」，各檔尾加〈實作補記〉總表）

- cpu.md：標頭；§4.1（`run_target_full`，A-5／B-1）；§4.3（B-4）；§5.1（控制 pipe 信封，A-2）。
- daemon.md：標頭；§1.2（B-3）；§2（缺檔 SpawnFailed）；§6（`aos-daemon stop`）；§6.1（B-9）；§7。
- kernel.md：標頭；§1.1 末（家缺的補齊，C-1）；§1.3（ack digest B-5、boot-kill 名 B-6）；§2（B-7）；§3 第 10 步（空格不寫、B-11）；§6 命令列（init --cpu、ack、ls --json、-h）、boot 第 2 步（B-6、B-12）、第 3 步（B-10）、第 4 步（C-1）、ls／ack 段。

## 隊長裁決

1. **控制 pipe 的 `go` 帶合法 id 照樣放行**；只有 stop 必須是 notification。
2. **kernel `init` 的「拒絕覆蓋」解讀為 `info.json` 已在才拒絕**；資料夾在但沒 info＝上次建一半，補齊。
3. **`aos-daemon stop` 在 daemon 不活時不放檔、退 0**——留下的 stop 檔會讓下一任一開機就停。
4. **`init --cpu` 沒給 `:kernel` 就自動加 `k`**；`k` 被別的池佔、兩顆 kernel、重名＝用法錯退 2。info 驗證不過（如空池名）是退 1。
5. `aos-daemon` 改用 argparse，用法錯的 stderr 是 argparse 格式（不是 `aos-daemon: Usage:` 一行），退出碼仍是 2。

## 要使用者拍的

1. **B-10 跨代 stop**：已出貨的 stop 跨 boot 仍有效，新 kernel cpu 可能一開機就停、鏈沒起來（C-6 測試把現況釘住）。要不要讓 boot 去刪 cpu 家裡舊 chain 的 `stop-*`？
2. **kernel.log 輪替**：這輪只做「空格不寫」；有事件的格仍無上限。要不要輪替／限大小？
3. **B-12 kill-tree**：硬砍 kernel cpu 時另組的 tick 子程式可能還活著，現況列保證外；要不要補？
