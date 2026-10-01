# 暫緩區：tick 協議先不做的條

← [暫緩區](../README.md)｜[tick 暫緩區](../tick.md)｜[現行 tick 協議](../../protocol/tick.md)｜[慣例](../../conventions.md)

> **這篇整篇在暫緩區**（2026-10-01）。[tick 協議](../../protocol/tick.md)裡先不做的條搬到這裡，原文照留，條號保留、不重用。行為那側見 [tick 暫緩區](../tick.md)。

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
