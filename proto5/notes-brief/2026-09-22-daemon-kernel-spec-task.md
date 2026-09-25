# 任務書：daemon／kernel 規範草稿（2026-09-22）（精簡版）
完整版：[../notes/2026-09-22-investigations/2026-09-22-daemon-kernel-spec-task.md](../notes/2026-09-22-investigations/2026-09-22-daemon-kernel-spec-task.md)

## 目的與範圍

使用者要求：「開 agent 去看看 proto4 的 daemon 和 kernel，然後一樣在 spec 寫規範，我要審閱。」交出的應是 **依 proto4-3 真正行為整理、對齊 proto5 的規範草稿**，讓使用者逐條審，不重新發明架構。

| 元件 | 必須查清楚的範圍 |
|---|---|
| aos-daemon | 怎麼管理多個 daemon 行程、家目錄與 ctl 控制介面。 |
| aos-kernel | tick 排程、module、syscall、add／status。 |
| aos-run | 判斷是否真有獨立職責，值得另寫程式規範。 |

使用者已定：**JSON 格式與程式各寫一份**。格式管「檔案長怎樣」，程式管「拿到檔案後做什麼」；兩邊互相連結，同一件事不重複寫。沿用 `inst-posix.md` 對 `exec.md`、`agent.md` 對 `aos-agent.md`／`aos-llm-ask.md` 的分法。

## 產出哪些檔

| 產出 | 必須包含 |
|---|---|
| `proto5/spec/<daemon 的格式>.md` | daemon 家目錄、請求檔、狀態檔、記錄等的形狀。逐項交代欄位、型別、預設、是否解指示詞、錯誤代號。檔名按內容自訂，例如 `daemon-home.md`，回報說明命名。 |
| `proto5/spec/aos-daemon.md` | aos-daemon、aos-daemon-ctl 的命令列、生命週期、行為與退出碼。 |
| `proto5/spec/<kernel 的格式>.md` | kernel 家目錄、行程表、module 形狀、syscall 請求／回應；同樣交代欄位、型別、預設、指示詞與錯誤代號。可叫 `kernel-home.md`；syscall 內容夠多時可另拆一份。 |
| `proto5/spec/aos-kernel.md` | boot／init／tick／add／status 等子命令；一次 tick 做什麼、怎麼選工作、怎麼呼叫 module、退出碼。 |
| `proto5/spec/aos-run.md`（有條件） | 只有 aos-run 在 proto4-3 真的是獨立一層、值得單獨說明才寫；否則併為 aos-kernel 的一節，回報原因。 |
| README 表列建議 | 只寫在回報，交由 Claude 整合；**不要直接改 `proto5/README.md`**，另一個 agent 也會動它。 |

## 先讀什麼、怎麼核對

| 次序 | 閱讀內容 | 用途 |
|---|---|---|
| 1：proto5 既有規範 | README、`spec/exec.md`、`inst-posix.md`、`directives.md`、`agent.md`、`aos-agent.md`。 | 先統一術語。exec 就是「依 proto4-3 現況整理」的範本：仿它的開頭提醒、一句話、表格、退出碼、末尾暫選清單。特別記住 aos-agent 退 101 表示在等，kernel 後續要靠它排程。 |
| 2：proto4-3 現況 | README、`docs/daemon.md`、`kernel.md`、`run.md`、`files.md`；再核對 `aos_daemon*.py`、`aos_kernel*.py`、`aos_run*.py`、`aos_home.py`，以及 daemon／kernel／run 測試。 | 不能只照文件抄；要找出程式真正的行為與文件漏掉的地方。 |
| 3：後續使用方式 | proto4-5 README 的 llm-cpu 掛 kernel module；proto4-7 README 的 agent LLM 排程與 101 讓出 CPU。 | 只看相關片段，確認 kernel 能支撐這些用法；**不把這些後續設計寫進規範主體**。 |

## 全部寫作規則

| 規則 | 具體做法與理由 |
|---|---|
| 只講現在 | 不放修訂歷史，也不重述 proto4-1／4-2 的演變。 |
| 差異明列 | 每份末尾放「跟 proto4-3 差在哪」，逐條一行列出為對齊 proto5 所做的調整，讓使用者有得核對。例如逾時歸 aos-run／kernel 而非 inst、`.json` 不存在為 125、`run_target()` 回 `(code, kind)`、家目錄環境變數名。這些是要核對的差異例子。 |
| 不暗中拍板 | 拿不定時主體先沿 proto4-3 的做法，末尾另列「我自己選的、使用者可以推翻的」。真沒依據的地方就在當處標「（待使用者定）」。 |
| 保持簡單 | 每份目標 150～250 行；中文大白話、表格為主。命令列、檔案形狀、狀態轉換、退出碼、錯誤代號要保留；Python 函式怎麼選、鎖怎麼拿等細節不寫。 |
| 連結 | 一律相對路徑；可仿 exec 開頭的「← proto5 README」導覽。格式與程式規範互連，但不要重複內容。 |
| 修改範圍 | 只新增上表規範檔。不碰 `proto5/README.md`、`proto5/lib/`、`proto5/cli/`，也不碰既有 `agent.md`、`aos-agent.md`、`aos-llm-ask.md`；另一個 agent 正在實作 agent。 |
| 版本操作 | 不 commit。 |

## 最後怎麼回報

用中文條列交付：寫了哪幾份、各幾行；各份「跟 proto4-3 差在哪」與「我自己選的」內容；proto4-3 文件與程式對不上的地方；建議使用者優先審的三個問題。另附要加進 README 的規範表列，並說明自訂檔名與 aos-run 是否獨立成篇。

這份是調查與起草任務書，本身沒有先替使用者定好新的 daemon／kernel 方案；所有需要選擇的結果，都必須在草稿與回報中攤開。
