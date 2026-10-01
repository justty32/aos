# 暫緩區：tick 協議先不做的條

← [暫緩區](../README.md)｜[tick 暫緩區](../tick.md)｜[現行 tick 協議](../../protocol/tick.md)｜[慣例](../../conventions.md)

> **這篇整篇在暫緩區**（2026-10-01）。[tick 協議](../../protocol/tick.md)裡先不做的條（P-207 整條、P-206 的 `aos-publish` 那列）搬到這裡，原文照留，條號保留、不重用。行為那側見 [tick 暫緩區](../tick.md)。

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
