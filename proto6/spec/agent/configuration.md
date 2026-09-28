# 設定與版本

← [Agent](README.md)｜[共用契約](../contracts.md)

## A-101 設定資料與責任〔建議預設，未拍板〕

控制層持有 agent 登記及設定版本指標；設定管理入口可申請更新，tick 只能讀取。`agent_id` 使用共用 ID 型別且建立後不變，不以目錄名稱推導身分。Linux 身分引用由底座提供，設定內容不得改 UID、群組或排程優先權。

每份不可變設定必填 `version:1`、`model_ref:string`（非空，無預設）、可省 `system_prompt:string`（預設空字串）、`context_policy_ref:string`（非空，無預設）、`tool_manifest_ref:string`（非空，無預設；可指向空清單）、`cwd:string`（無預設，絕對路徑）。各 ref 指向存在且驗證過的不可變內容，版本 revision 使用共用 ID，每個 revision 指向一份 BlobRef。秘密憑證不寫進 prompt 或版本內容；模型引用由 client 的受控設定解析。

前置條件是已登記 agent、身分與 home 有效。建立時缺模型、cwd 不存在或依該身分不可進入、引用缺失、schema 不支援，一律拒絕建立，不發布半成品。未知設定欄位拒絕並回欄位路徑。工具路徑的執行可行性另外由底座於每次啟動確認。

驗收：Given 有效 agent 與缺少的模型引用；When 提交設定；Then 回結構化 `config_invalid`，舊有效版本與 run 不變。

## A-102 每輪版本固定與更新〔建議預設，未拍板〕

run 建立為 queued 時，控制層必填並固定 `config_revision`、`context_revision`、`tools_revision` 三個版本引用。更新設定須先完整保存及校驗新內容，再由控制層原子切換 agent 的「後續 run 預設版本」。合法更新是有效版本 → 另一有效版本，無法原地修改已發布版本。已有 queued 或 active run 不跟著換；修正必須取消舊 run 再建立新 run，不偷換其輸入。

控制層負責版本引用的存活性：非終態 run 所引用內容禁止回收；重啟載入原引用，不自動用最新版替代。若原版本遺失或摘要不符，run 轉 needs_attention，agent 轉 error，記 `config_unavailable`；修復原內容並經人工 resume 後重新驗證，再回 active／think。版本錯誤不得觸發 LLM 或工具。

驗收：Given run R 固定工具版本 V1；When 管理者發布 V2 並重啟；Then R 仍只見 V1，新建立 run 才使用 V2。

## A-103 人格與權限分界〔使用者方向 2026-09-28，連 notes〕

來源：[工具繼承委託身分](../../notes/2026-09-28-employee-identity.md)。prompt、工具描述與模型回覆均無權新增 Linux 權限；工具通常沿用呼叫 agent 的身分。cwd 只表示起點，不表示存取邊界。具體身分準備及外層隔離由基底契約承接，agent 不另造逐工具授權系統。

驗收：Given prompt 寫著「使用 root」但 agent 為普通 UID；When 提交工具工作；Then 底座接到的 owner 仍為該 agent，模型文字不改變身分。
