# 工作與結果

← [共用約定與分工](README.md)｜[工作材料](../base/work.md)｜[LLM 代發](llm-work.md)｜[LLM 池](../scheduling/llm.md)

LLM 代發（P-405～P-407：池設定、LLM 請求、LLM 結果與重試）在 [llm-work](llm-work.md)；本篇其餘條號不變。

## P-400．兩個入口〔使用者方向 2026-09-29〕

工具由 `tools.target_node` 選路：是 node id 就以 `kernel.work.submit` 交該 kernel；是 null 就由 agent 自己登記 once（可信 parent_id 是自己）、保存用量，kernel 用收集 module 讀。LLM 以 `llm.chat` 投 `llm.target_node`；填 null 是「直連」檔，agent 自己打 endpoint、不經本篇的池（[S-301](../scheduling/llm.md)）。開 agent 的 kernel 決定地址與權限。

兩種檔案請求的 params 都是完整 inst，argv 分別以 `aos kernel work submit`、`aos llm chat` 開頭；業務材料是 inst.stdin 指向的 JSON 檔，命令核對見 [messages P-306](messages.md)。材料的 node_id 是最初發起 node，job_id 是邏輯工作，attempt_id 是嘗試；仍須核對可信來源。命令完成才回執行結果，不先回 ACK；內層工作／LLM 結果是命令的 stdout JSON。

## P-401．工作材料〔建議預設，未拍板〕

[`work-request`](schemas/work-request.schema.json) 定義請求；stdin 的工作材料：

| 欄位 | 意思 |
|---|---|
| `node_id`、`job_id`、`attempt_id` | P-400 的配對識別 |
| `inst` | [inst 第 1 版](../base/inst.md) 原始物件；引用 [node-inst schema](schemas/node-inst.schema.json)，仍須在目標身分展開後驗證 |
| `base` | 原 inst 的絕對基準資料夾；複製材料不能偷偷換成工作資料夾 |
| `timeout_ms`（可省） | 放行後逾時，預設 60000，正整數 |
| `output_limit_bytes`（可省） | 每條捕獲串流上限，預設 1048576，正整數 |

kernel 接納時固定 inst 與必要輸入。需要固定 stdin bytes 就保存副本並使用該副本路徑；外部 `$ref`、程式及 workspace 不因此凍結，見 [B-101](../base/work.md)。工具呼叫先依 [A-401](../agent/tools.md) 驗參數、轉 inst；run／tool_call 對照留在發起 node。

## P-402．once 與工作材料〔使用者方向 2026-09-29〕

once 目標依 [P-010](README.md)，資源歸屬與最小啟動失敗證據依 [daemon P-104／110](daemon.md) 的第十一批裁定。

〔使用者方向 2026-09-29，第十六批〕**工作目錄名要加發件者前綴**：不同成員都可能用 `attempt-1`，同一個 kernel 裡會撞名。目錄名一律是 `<前綴>-<attempt_id>`，前綴是「配出這個 attempt_id 的 node」（工作材料的 `node_id`；自己配的就是自己）絕對路徑 UTF-8 bytes 的 sha256 前 16 個小寫 hex。node 路徑不能直接當目錄名，雜湊長度固定、只有 `[0-9a-f]`；碰撞機率可忽略，讀目錄時仍核對裡面 request 的 node_id。例：`/srv/aos/top/a` 的 `attempt-1` → `94a18415f07a8c0d-attempt-1`。全篇及 kernel／agent 篇路徑裡的 `state/work/<attempt_id>/`、`.aos/jobs/<attempt_id>/`，`<attempt_id>` 都指這個目錄名；檔案內容與 RPC 裡的 attempt_id 欄位不加前綴。

〔建議預設，未拍板〕本篇為保存請求與結果，在安排工作的 node 建 ignored `.aos/jobs/<attempt_id>/`，以其中的 `inst.json` 單檔登記；資料夾只是材料布局。每次實際嘗試使用不同資料夾，內含：

```text
.aos/jobs/<attempt_id>/
  inst.json          # daemon 跑的外層 inst
  request.json       # 已接納請求的固定副本
  input/             # 只有需要固定輸入時才有
  stdout.bin         # 有捕獲才有
  stderr.bin         # 有獨立捕獲才有
  result.json        # 執行器完整發布的 B-103 結果
  usage.json         # 已裝 module 的可信收尾量測；量不到可省
  launch-started     # 首次 register 前落地，恢復不盲重跑
```

外層 inst 的 argv 是 `aos-work --work-dir <絕對工作資料夾>`，`user` 明寫工作所屬 node 已授權的有效身分。內層 `request.json` 的 inst 省略 `user` 時繼承這個身分；寫了或整份指示詞展開後帶了 `user`，必須仍解析成同一 UID。kernel 不可讓工具繼承自己的較高權限；runner 也不能在內層再次切身分。

安排工作的 module 先保存接納請求及材料，tick 提交後，後續一格才建工作資料夾並經 daemon `node.register` 登記 `node_id=W/inst.json,parent_id=材料.node_id,identity_grant=[有效身分],once=true`，再 `node.wake`。agent 自跑工具時 parent_id 固定自己。parent_id 是可信資源歸屬，與 W 的位置無關，核對規則只依 daemon 篇。工作結果及捕獲檔保留，下格核對並保存；有回件便放待送區，由 tick commit 後投回呼叫者。結果只給路徑，發件者未必讀得到；風險由使用者承擔。

首次登記前依 [kernel P-807](kernel-tasks.md) 排他建立並同步 launch-started；已有 marker 就先查證，不重新派出。執行器／已裝 module 在移除 leaf 前保存 [res-usage](schemas/res-usage.schema.json) 到 usage.json，發起者下格收量；量不到不寫 usage.json、用量記 null，不採信工具自報。

安排工作的 node 下格若讀到 `W/inst.json.err`，先核對本次目標與可信 daemon 寫入來源，再合成 started:false／failed／start_failed 的工作結果；不把自報旁檔當證據。LLM wrapper 未啟動可合成 failed／not_sent。其他情況只看 result.json；wrapper exec 126／127、崩潰或自身回 125 卻無結果，均不能只靠登記消失推定內層沒跑，缺可保存的可信證據就 unknown。兩份證據矛盾時保留並報事項，不任取最後一份。重啟與重投依 [messages P-304](messages.md)。

## P-403．結果與串流〔建議預設，未拍板〕

[`work-result`](schemas/work-result.schema.json) 同時驗本地結果檔與回應。`result.json` 為 `version:1` 加結果欄位；所有檔案 RPC 的 `result` 用同一形狀，**不帶 version**。RPC 指令結果的 node_id 是執行指令的 node，job_id、attempt_id 都用 RPC id；業務材料內的工作識別另留在 stdout JSON。

| 欄位 | 意思 |
|---|---|
| `node_id`、`job_id`、`attempt_id` | 配回工作與嘗試；RPC 命令結果依上段 |
| `status` | `succeeded`／`failed`／`canceled`／`unknown`，依 [C-03](../contracts.md) |
| `reason` | `exited`、`signal`、`start_failed`、`timeout`、`canceled`、`oom`、`output_limit`、`descendants_remaining`、`output_incomplete`、`unknown` |
| `started` | `true` 已進入 inst 的執行階段；`false` 根本沒跑；`null` 證據不足 |
| `exit_code`、`signal` | 可得的原退出碼或訊號；無資料填 `null`，兩者不同時有值 |
| `diagnostic`（可省） | 無 key 的有界診斷（最多 4096 字元）；可得時保留原始 errno 代號，例如 EAGAIN、ENOMEM |
| `stdout`、`stderr` | `{path,bytes,truncated}` 或 `null`；path 是絕對路徑，bytes 是實際保存量 |

`null` 表示沒有這份輸出證據；有檔且 `bytes:0` 才是確知空輸出。若 inst 使用 `inherit`，外層將對應 fd 接捕獲 pipe，才由 aos-work 保存為 `.bin`；inst 的一般檔案、append、merge、`/dev/null` 規則照正本，不偷偷改成捕獲。直接寫檔若不能證明這次保存的完整 bytes，結果該串流填 `null`；merge 不虛構獨立 stderr。捕獲上限、OOM 證據與收尾沿 [B-103](../base/work.md)、[B-202／204](../base/execution.md)。

正常退出 0 且後代清空才可 `succeeded/exited`；退出 7 是 `failed/exited`。125 不足以判定是否執行；`started:false/start_failed` 和子程式已跑、自己退出 125 必須分清。訊號保留 `signal`，不把 inst 的 `128+n` 合成碼當作 wait 的退出碼。工具語意錯誤與產品成功依 [A-403](../agent/tools.md)、[A-503](../agent/README.md)，不改程序證據。

## P-404．unknown 與拒收〔使用者方向 2026-09-29〕

結果不明的工作保持 unknown，沒人處理就隨定期清理清掉，不自動重做。合成 unknown 結果時缺失欄位填 null；已發布 RPC 回應不覆寫。

拒收沿 P-005：參數錯 -32602；業務錯 -32000，data.code 可為 work_not_authorized、input_unreadable、capacity_unavailable、pool_not_found、model_not_found、key_unavailable。只在能確認尚未接納的暫時容量／讀取問題才可 retryable:true；接納後的失敗回結果。配對錯或衝突留原件及事項，不夾 key／認證標頭。

## P-408．程式契約〔建議預設，未拍板〕

| 完整 argv | 讀寫、身分與輸出 |
|---|---|
| `aos-work --work-dir W` | 讀 W/request.json 及目標身分可讀的材料，以 `base` 跑內層 inst；寫捕獲檔、W/result.json。用工作 node 身分，無切身分權限 |
| `aos-llm [--node N] --config C` | 一項 module 任務，node 省略用 cwd（tick 設為 node 根）；直接讀 C、收件、池狀態及既有結果，保存狀態／待送封套。只對已提交的工作材料登記、叫醒 once；tick 負責 commit 後投件、清收件原件，用 N 的 user |
| `aos-llm-call --work-dir W --config C` | C 含本次派出時固定的必要設定；讀 C、私有 key_ref 與 W/request.json，只送一次 HTTP，寫 W/result.json；請求有 stream_path 時邊收邊寫該檔；用池管理 node 的 user |

三支程式 stdin 都是 `/dev/null`，stdout 保留為空（業務輸出走檔案），stderr 只放無 key 的 `代號: 白話` 診斷；內層 inst 的 stdin／stdout／stderr 另依 P-403。不新增必需 `AOS_*` 環境變數，PATH／目標帳號環境及 inst.envs 依 inst 正本，不從呼叫者環境取得池 key。

結束碼：0＝這次處理完成且必要結果已完整發布（工作本身仍可能 failed／unknown）；2＝用法／設定錯，未開始；125＝自身無法開始；1＝已開始處理後自身失敗（包括結果寫不出），不能把未發布結果算成功。aos-llm 的 0 只表示本格步驟完成，不代表 HTTP 工作成功。〔使用者方向 2026-09-29 晚〕串流中途斷線照 [S-305](../scheduling/llm.md)：aos-llm-call 可以非 0 結束，不必另補結果；沒有結果就照下句處理。〔使用者方向 2026-09-29 晚〕stream_path 在送出 HTTP 前就開不了（沒權限、父目錄不在）時不送，結果記 failed／not_sent。重試時這個檔怎麼寫不另規定，由任務自然處理。工作 inst 的內層退出碼只記在工作結果，不能拿 wrapper 的 0 代替。訊號由父程序看 wait 狀態；wrapper 沒寫結果時只按 P-402 的旁檔／unknown 規則處理。

## P-409．schema 與最小範例〔建議預設，未拍板〕

每行範例都在 [examples/work/](examples/work/)。schema 只能驗 JSON 形狀，P-002 的重複 key、有限數、位元組上限與執行授權另驗。

| schema | 正例 | 主要錯誤例與原因 |
|---|---|---|
| [work-request](schemas/work-request.schema.json) | 工作指令 inst 與 stdin 材料 | 零逾時或命令不符 |
| [work-result](schemas/work-result.schema.json) | 本地結果與 RPC 命令結果 | 成功卻 exit 7、雙 result/error |
| [llm-config](schemas/llm-config.schema.json) | 池設定 | 明文 api_key |
| [llm-request](schemas/llm-request.schema.json) | LLM 指令 inst 與 stdin 材料（另有串流正例） | 串流檔用相對路徑 |
| [llm-result](schemas/llm-result.schema.json) | stdout 的 LLM 結果 | 成功漏 message、部分 usage |

## P-410．待決與跨篇

見 [README P-008](README.md#p-008)。
