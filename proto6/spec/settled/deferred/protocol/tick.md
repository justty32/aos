# 暫緩區：tick 協議先不做的條

← [暫緩區](../README.md)｜[tick 暫緩區](../tick.md)｜[現行 tick 協議](../../protocol/tick.md)｜[慣例](../../conventions.md)

> **這篇整篇在暫緩區**（2026-10-01）。[tick 協議](../../protocol/tick.md)裡先不做的條（P-207 整條、P-206 的 `aos-publish` 那列、P-212 `aos-as` 整條）搬到這裡，原文照留，條號保留、不重用。行為那側見 [tick 暫緩區](../tick.md)。

## P-207．加入普通設定〔建議預設，未拍板〕

> **暫緩**（2026-10-01）：使用者 2026-10-01 裁定 `aos-config-add` 搬暫緩區。它是 2026-09-29 規劃、從沒寫過程式的指令。行為那段見 [tick 暫緩區「暫緩：B-625 加入普通設定」](../tick.md#暫緩b-625-加入普通設定aos-config-add)。下面原文照 2026-10-01 搬家前的樣子留著，結束碼 75、125 回來時要照 [C-08](../../conventions.md) 重看。

行為以 B-625「改設定」為正本（搬家後在 [tick 暫緩區](../tick.md#暫緩b-625-加入普通設定aos-config-add)）（持鎖、原子替換）；kernel／agent 的領域設定另見 [A-102](../../../agent/configuration.md)。本條只定格式。

- **argv**：`aos-config-add [--dir <工作資料夾>] --from <source> --to <target>`；省略 `--dir` 用 cwd〔使用者 2026-10-01：node 改稱工作資料夾，旗標原叫 `--node <node_dir>`〕。取的鎖是同一把 `.aos/tick.lock`（[B-602](../../tick.md)）。
- `source` 是任意可讀路徑，相對呼叫者的 cwd；`target` 是工作資料夾 `config/` 內的檔案，相對工作資料夾，不准用 `..` 或 symlink 逃出。
- 用呼叫者的帳號跑，沒有自訂環境。
- stdin 不讀；stdout 成功時印 `target`＋LF；stderr 印 `code: 說明`。
- 它不是任務表上的任務；在 tick 之外跑算外部世界（[B-602](../../tick.md)）。

| 結束碼 | 意思 |
|---|---|
| `0` | 已替換，或內容相同、沒寫 |
| `1` | 寫入失敗，或參數、路徑、JSON 不合；目標仍是舊版 |
| `75` | 鎖被占（busy，特別指定的碼） |
| `125` | 前置失敗（例如有擋板檔），沒寫目標（特別指定的碼） |

不自己提交：`config/` 不在 aos 範圍（[B-630](../../tick/git.md)、[B-625](../../tick/recovery.md)），要留歷史就自己 `git commit`。

依據：第十九批依方案 A 縮短；第二十批（不在任務表上、沒有 git）；astra 審整理區必-5（撤掉 git 殘句）。

## 暫緩：P-206 aos-publish 那列（發摘要）

> **暫緩**（2026-10-01）：使用者 2026-10-01 第五批裁定 `aos-publish` 搬暫緩區，總結這一格成 JSON 的 `aos-summarize` 也不做。行為那段見 [tick 暫緩區「暫緩：B-624 發布摘要」](../tick.md#暫緩b-624-發布摘要aos-publish)。原條 [P-206](../../protocol/tick.md) 的 `aos-mq get`／`post` 還在正式篇。條號保留、不重用。

原文（2026-10-01 搬家前，P-206「argv 與結束碼」表的那一列與相關句）：

| 程式 | 任務 id（範本） | 做什麼 |
|---|---|---|
| `aos-publish` | `summary` | 發布摘要 |

- 原文跟 `aos-mq` 共用一段：「三者都是系統級任務，都在工作資料夾（cwd）跑、不收其他參數。在 tick 內靠繼承的鎖；不在 tick 內時自己取同一把鎖，拿不到回 75。」結束碼 `1` 包含「發布摘要失敗」。回來時要照 [C-08](../../conventions.md) 重看 75。
- 發布檔 `published.json` 的格式與權限在 [P-307](../../../protocol/messages.md)（整理區外，就地標了暫緩）；收件區權限 P-208 的「只讀摘要的上層」那列也跟它有關。

## P-212．aos-as：切換帳號〔建議預設，未拍板〕

> **暫緩**（2026-10-01 第十三批）〔使用者 2026-10-01 第十三批：「aos-as弄成暫緩。」〕：原文照 2026-10-01 搬家前的樣子留著，條號保留、不重用。它靠 helper（[B-303](../helper.md)）、daemon 通道與「鎖 fd 傳給任務」（[tick 暫緩區](../tick.md#暫緩b-602-完整互斥的其餘細節)），三樣都在暫緩區。現行切帳號只在 daemon 設定檔做（帳號模組 `modules.account`，[plan m3m 模組五](../../../../plan/m3m-daemon-modules.md#模組五帳號modulesaccount)），單位是 daemon 的一項，不在一格裡面中途換。

普通程式，不是系統級任務。行為正本：[B-303](../helper.md)；`spawn_as` 的參數與限制見 [B-609](../daemon/helper-actions.md)、[P-107](../protocol/daemon/provision-and-runner.md)；runner 回報見 [P-110](../protocol/daemon/provision-and-runner.md)。

- **argv**：`aos-as <帳號> [--] <原指令…>`；帳號是名稱或非負 UID。
- **暫存 inst**：ignored 的 `.aos/jobs/as-<seq>-<pid>.json`，結束後刪掉。`seq` 取結束碼紀錄（`$AOS_TICK_CWD/.aos/tick/current/record.json`）的格數（沒有紀錄時用 `0`），`pid` 是 aos-as 自己的 PID。內容是一份 inst：`argv`、目前 cwd、`envs`＝`{"$opt":"clear","$val":目前的環境}` 但不含 `AOS_TICK_TOKEN`、`AOS_DAEMON_SOCKET`、`AOS_TICK_LOCK_FD`（由 runner 補，[B-609](../daemon/helper-actions.md)）；stdin／stdout／stderr 都寫成繼承。
- **交給 helper 的 fd**，共 5 個（見 P-107）：

  | 順序 | fd |
  |---|---|
  | 1 | 繼承到的鎖 fd（`AOS_TICK_LOCK_FD`） |
  | 2 | 回報 pipe 的寫端 |
  | 3～5 | 〔建議預設〕自己的 stdin、stdout、stderr，讓那一項照任務表寫的 stdio 走 |

  自己在 `aos-cg` 的 `task-*` 框裡時（有 cgroup），另帶 `frame`＝那個框；沒 cgroup 時帶了 daemon 回 `unsupported`（[B-609](../daemon/helper-actions.md)）。

- **stderr 代碼**：`not_available`（〔建議預設，未拍板〕helper 動作關閉，[B-609](../daemon/helper-actions.md)）、`no_channel`、`helper_unavailable`、`user_not_granted`、`user_invalid`、`stopping`（daemon 的錯誤碼照轉）、`result_unknown`（回應成功但 pipe 沒回報就關了）。

| 結束碼 | 意思 |
|---|---|
| 原指令的碼 | 照 runner 回報：正常結束回同一碼；被訊號結束時用同一個訊號結束自己 |
| `1` | 用法錯 |
| `125` | 沒開起來或不知道結果（特別指定的碼）：沒有通道變數、daemon 回錯、`result_unknown`；不寫 `exit`。`result_unknown` 時呼叫它的一方不能重跑 |

依據：〔使用者方向 2026-09-30〕第二十批追答 8。
