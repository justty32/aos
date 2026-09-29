# 跨篇共用契約

← [規格入口](README.md)｜[名詞](terms.md)

以下未另標來源均為〔建議預設，未拍板〕。只定跨篇共用資料；inst 另以 [base/inst](base/inst.md) 為正本，不受本篇預設覆蓋。

## C-01．基本型別與版本

node id 是資料夾路徑，依 [T-02](terms.md)。其餘用作檔名的 request／job／attempt／run ID 建議採大小寫敏感字串 `[A-Za-z0-9][A-Za-z0-9._-]{0,127}`（與[協議 P-002](protocol/README.md)一致），不含路徑分隔或空白；它們不是任意檔案路徑，也不證明發件身分。

一般共用紀錄以 `version:1` 起步；inst 及 tasks 用各自的 `_metainfo`，未知版本拒絕猜讀；各領域的實際欄位與未知欄位政策由各篇定義，尚未定的留給協議篇。時間點 `*_at_ms` 為非負 UTC epoch 毫秒，持續時間為非負毫秒；序號為正整數。共用紀錄的整數上限為 9007199254740991，不接受 bool 代替數字，不把空字串與 null 混用。

UTC 用於跨重啟時間點；運行中逾時用經過時間，不因牆鐘倒退無限延長。〔使用者方向 2026-09-29〕排隊先後看所屬 kernel 的持久序號，不靠牆鐘，正本見 [S-204](scheduling/admission.md)。

驗收：共用紀錄的 `seq:true` 或未知版本被拒絕；node 路徑不被誤套短 ID 限制，inst 也不被加上本篇的 `version` 欄位。

## C-02．歸屬與可選 run

涉及父子管理時依可信登記關係核對，不信正文自報身分。node 登記與 IPC 授權以 [daemon](daemon.md) 為正本，執行身分與額度以[身分篇](base/identity-resources.md)為正本。

採用 run 時才留下 run ID、所屬 node 與必要進度／結果，輪次語意見 [S-101／102](scheduling/runs.md)。設定修改與已派材料見 [A-102](agent/configuration.md)；不要求另一套不可變設定庫或全域 owner 表。

驗收：未採用 run 的 node 仍可送工作並核對結果；投件者填另一個 node／UID 不能因此取得其權限。

## C-03．工作、嘗試與結果

結果必須對回 [T-03](terms.md) 的 node、job 與 attempt。結果的 stdout 只給路徑，發件者未必讀得到，風險自負。

共用結果意思是 `succeeded`（成功）、`failed`（確定失敗）、`canceled`（已完成取消）與 `unknown`（沒有足夠證據判定）。不另加結果封套或平行狀態表。程序結果見 [B-103](base/work.md)，agent 任務成功另看 [A-503](agent/README.md)。

〔使用者方向 2026-09-29〕unknown 不自動重做。〔建議預設，未拍板〕可信晚到結果可補清原嘗試；若已選新嘗試，只補舊證據，不覆寫新結果。相同結果重送不重複採計；同一次確定結果的異內容報衝突。實際用量仍按各次嘗試核對。重試條件與次數只在 [S-104](scheduling/runs.md)，人工處置在 [S-401](scheduling/operations.md) 定義。

驗收：unknown 經授權重試會有新 attempt ID；第一個結果晚到仍可保存，但不覆寫第二個，也不重複計量。

## C-04．錯誤與接件

跨篇需要錯誤資料時，最少有穩定 `code` 與人看得懂的 `message`；需要時附 `retryable` 或有界 `details`。不在本篇定 RPC 數字碼、method 全集或通用封套；inst 的錯誤碼另見[正本](base/inst.md)。

`retryable` 只提示可再試的條件，不授權重做 unknown，也不能越過取消或重試上限。確定的 LLM 限流例外只依 [S-303](scheduling/llm.md)。收件、完成、已消費是三種不同確認，正本見 [B-503](base/transport.md)；收到請求不表示工作成功。

驗收：先接件、後執行失敗，兩項事實都保留；錯誤標可重試也不能讓結果不明的工作自動再跑。

## C-05．舊提交交易

（09-29 重寫：已刪；group 與本 repo 的 git 提交／還原見 [tick](tick.md)。）

## C-06．最小例子與保留

（09-29 重寫：已刪／併入[儲存 B-404](base/storage.md)；去重見[投件 B-503](base/transport.md)。）
