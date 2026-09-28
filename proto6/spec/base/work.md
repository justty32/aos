# 工作描述

← [基底](README.md)｜[共用契約](../contracts.md)

## B-101：固定工作材料〔建議預設，未拍板〕

Owner：控制層持有工作快照；agent 只提出候選。`job_id` 是邏輯工作，重試使用新的 `attempt_id`。每次准入前驗證並固定以下 JSON；未列欄位拒絕，所有字串禁止 NUL，物件不得有重複 key。

| 欄位 | 型別／必填／預設 |
|---|---|
| `version` | integer，必填，固定 1 |
| `agent_id,run_id,job_id` | 共用 ID，必填，由可信上下文核對；僅維護／空收件探查 tick 的 run_id 可 null |
| `argv` | 非空 string array，必填，首項非空；直接 exec，不隱式 shell |
| `cwd` | string，必填，絕對路徑；降權後驗證可進入 |
| `env` | string→string，省略為 `{}`；key 符合 `[A-Za-z_][A-Za-z0-9_]*` |
| `stdin_blob` | BlobRef 或 null，省略 null，控制層核准的 BlobRef |
| `timeout_ms` | integer，省略 60000，範圍 1..86400000，從放行開始 |
| `output_limit_bytes` | integer，省略 1048576，範圍 1..16777216，各 stdout／stderr 分開限制 |

JSON UTF-8 上限 256 KiB；stdin 上限 16 MiB。stdin 與描述以 SHA-256 摘要固定，排隊後改檔不能改既有 job。程式檔、cwd 內資料不是自動快照；結果記錄此限制。若需可重現程式，呼叫方提供唯讀版本化產物。拒絕 UID、GID、cgroup、redirect、shell 展開、`$ref` 等未定欄位；shell 是明示 argv 中的程式。

**Given** 已提交工作而來源 JSON 被修改；**When** 准入執行；**Then** 使用原摘要材料，不能靜默採新內容。超限或偽造 owner 的請求在接件階段失敗。

## B-102：特權與解析分界〔建議預設，未拍板〕

啟動器輸入僅含可信 `attempt_id`、登記版本、執行種類及受控檔案描述符；由控制帳本查 `agent_id` 與固定描述摘要，禁止從 agent payload 推導身分。管理者持有快照並以唯讀 fd 交給降權後 runner。root 不開 argv 指定程式、cwd、stdin 路徑或 redirect，不展開員工 inst。runner 降權後解析、進 cwd、開程式；不存在／不可讀均產生啟動失敗，不提升權限補救。控制端可驗證限長的純資料 envelope，不能因此載入 plugin／執行描述中的程式。

環境由乾淨集合建立，預設 `PATH=/usr/bin:/bin`、`HOME` 指向登記 home、`TMPDIR` 指向 quota scratch、`LANG=C.UTF-8`；描述 env 僅作用於降權後工作，不能覆寫 HOME／TMPDIR。清除所有繼承憑證、loader env 與非核准 fd；管理控制 socket 不傳給工作。

**Given** cwd／stdin 指向只有 root 可讀的檔案；**When** 執行；**Then** 以 agent 權限失敗，root 沒有代讀；測試亦核對工作 fd 與 env 不含控制憑證。

## B-103：結果格式〔建議預設，未拍板〕

Owner：可信 supervisor 產生 envelope；stdout 內容一律不可信。詳細 ExecResult 必填 `version:1`、`attempt_id,job_id,agent_id`、`state`（共用 attempt 終態）、`reason`（`exit|signal|spawn_error|timeout|canceled|oom|quota|output_limit|lost`）、`exit_code`（0..255 或 null）、`signal`（正整數或 null）、`started_at_ms`（UTC epoch 毫秒或 null）、`finished_at_ms`（UTC epoch 毫秒）、`stdout_blob,stderr_blob`（BlobRef 或 null）、`stdout_bytes,stderr_bytes`（非負整數）、`truncated`（boolean）。ExecResult 以 BlobRef 裝入 C-03 Outcome.result_ref；Outcome.status 對應此 state，失敗／取消／未知另填 C-04 Error，成功 error=null。ExecResult 不是另一份權威 Attempt，也不替代 Outcome。不得由退出碼推斷任務成功。退出 0 且完整收尾為 succeeded；非零／signal／限制違反為 failed；無可信執行證據為 unknown。

輸出到達上限仍持續排空 pipe 並丟棄超額資料，發起取消收尾，終態 failed／output_limit；不得堵死子程序或無限寫控制磁碟。資料截斷必須可見。上層接收終態後按任務語意轉換 job/run 狀態，基底不自行重試。

**Given** 程式無限輸出或退出 7；**When** 完成收尾；**Then** 分別保存有界的 failed／output_limit 或 failed／exit、exit_code=7，未宣告 run 成功。

## 待使用者拍板與現況

本篇所有 schema 與限額均為預設，尚未實作；首版不提供重導向檔案與指示詞展開，未承諾逐字串流。
