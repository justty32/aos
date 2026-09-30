# 跨篇共用契約

← [規格入口](README.md)｜[名詞](terms.md)

以下未另標來源均為〔建議預設，未拍板〕。只定跨篇共用資料；inst 另以 [base/inst](base/inst.md) 為正本，不受本篇預設覆蓋。

## C-01．基本型別與版本

node id 是資料夾路徑，依 [T-02](terms.md)。其餘用作檔名的 request／job／attempt／run ID 建議採大小寫敏感字串 `[A-Za-z0-9][A-Za-z0-9._-]{0,127}`（與[協議 P-002](protocol/README.md)一致），不含路徑分隔或空白；它們不是任意檔案路徑，也不證明發件身分。

一般共用紀錄以 `version:1` 起步；inst 及 tasks 用各自的 `_metainfo`。版本怎麼升、不認得的欄位怎麼處理，一律依 [C-07](#c-07版本演進與永遠禁止的鍵)。格數、第幾格與序號為正整數；毫秒時間點 `*_at_ms` 為非負 UTC epoch 毫秒，毫秒時長為非負整數。共用紀錄的整數上限為 9007199254740991，不接受 bool 代替數字，不把空字串與 null 混用。

〔使用者方向 2026-09-30，第二十批〕**時間以 tick 為基準**（[T-07](settled/terms.md)）：

- **aos 內部自己決定的時長改成格數**：保留期、失聯判斷、重試間隔、預算這類，以「幾格」計。
- **外部世界規定的保留毫秒**：LLM 供應商的限流窗口、HTTP 逾時、daemon 叫醒 tick 的週期 `interval_ms` 這類。
- **算誰的格**：算安排它的那一層的格；上下層週期不同造成的落差不管。一格的標準長度是那個 tick 的 `interval_ms`，「N 格」大約等於 N 個週期。
- 〔第二十批疑點裁定 7〕**起算點直接換成格數**：拿來計算的時間點（例如保留期、失聯從哪一格起算）記「第幾格」，不另留毫秒版。

〔建議預設，未拍板〕寫法：

- 欄位名：時長 `*_ticks`、第幾格 `*_seq`、毫秒時長 `*_ms`、毫秒時間點 `*_at_ms`；schema 型別見 [P-002](protocol/README.md)。
- 本 node 的格數是核心結束碼紀錄的 `seq`（[B-633](settled/tick.md)），沒 daemon 也有、跨重啟接著數；斷電不倒退只在開了 `--firstdo-fsync` 時保證，否則不保證；daemon 登記的 `tick_seq` 只用在「叫醒後等新格」，不拿來算時長。
- 〔記錄者理解〕任務表上的任務由它那個 tick 安排，所以任務自己用的時長（保留期、清理間隔、鬧鐘）算本 node 的格；kernel 對成員的判斷（失聯、重試）算 kernel 的格。
- 〔astra 審整理區裁定裁-2〕daemon 的計時：叫醒週期、收尾寬限、排空上限這類外部／作業系統層的保留毫秒；政策性保留期（掛載診斷保留期）改用所屬上層的格數；逐項見 [daemon 篇「時間」](settled/daemon/README.md)。作業系統與 cgroup 的時間、量測數字、只給人看的紀錄時間也保留原單位。
- 〔暫定，第二十批疑-12〕預設值直接用格數訂，說明裡附「週期 1 秒時約等於…」，不從毫秒換算。

UTC 只用於給人看與外部規定的時間點；運行中逾時用經過時間，不因牆鐘倒退無限延長。〔使用者方向 2026-09-29〕排隊先後看所屬 kernel 的持久序號，不靠牆鐘，正本見 [S-204](scheduling/admission.md)；格數本身就是序號，天然不怕牆鐘。

驗收：共用紀錄的 `seq:true` 或比自己新的版本被拒絕；node 路徑不被誤套短 ID 限制，inst 也不被加上本篇的 `version` 欄位；aos 內部決定的時長欄位都以 `_ticks` 或 `_seq` 結尾，`_ms` 只出現在外部規定、daemon 本身或給人看的時間；牆鐘倒退時以格數計的保留期不提早也不延後到期。

## C-02．歸屬與可選 run

〔使用者方向 2026-09-30，第十九批〕涉及上下層管理時看**有效上層**：預設是資料夾包含推得的上層，在 daemon 底下可用登記覆蓋；覆蓋要新舊兩個上層都同意，〔使用者方向 2026-09-30，第十九批疑點裁定 11〕舊上層沒在 daemon 登記時只要新上層同意（aos 管不著沒登記的），覆蓋後檔案上的管轄權仍跟著資料夾，只改管理關係（[T-10](settled/terms.md)；判定以 [B-628](settled/tick.md)、登記以 [B-606](settled/daemon/registration.md) 為正本）。都不信正文自報身分。IPC 授權以 [daemon](settled/daemon/README.md) 為正本（通道上以憑證認 tick，見 [B-612](settled/daemon/channel.md)），執行身分與額度以[身分篇](base/identity-resources.md)為正本。

採用 run 時才留下 run ID、所屬 node 與必要進度／結果，輪次語意見 [S-101／102](scheduling/runs.md)。設定修改與已派材料見 [A-102](agent/configuration.md)；不要求另一套不可變設定庫或全域 owner 表。

驗收：未採用 run 的 node 仍可送工作並核對結果；投件者填另一個 node／UID 不能因此取得其權限；不在 daemon 底下的 tick 仍依資料夾包含算出上層；資料夾上層由 cron 跑、沒在 daemon 登記時，只有新上層同意的覆蓋照收。

## C-03．工作、嘗試與結果

結果必須對回 [T-03](terms.md) 的 node、job 與 attempt。結果的 stdout 只給路徑，發件者未必讀得到，風險自負。

共用結果意思是 `succeeded`（成功）、`failed`（確定失敗）、`canceled`（已完成取消）與 `unknown`（沒有足夠證據判定）。不另加結果封套或平行狀態表。程序結果見 [B-103](base/work.md)，agent 任務成功另看 [A-503](agent/README.md)。

unknown 依 [S-401](scheduling/operations.md) 放著。可信晚到結果保留在原嘗試的證據旁，不改寫 unknown；相同結果與用量不重複採計，同一次確定結果的異內容報衝突。同 ID 重送與補投原回應見 [B-503](base/transport.md)。可重試的確定失敗依 [S-104](scheduling/runs.md)。

驗收：unknown 不因晚到證據自動改狀態或重做；相同結果重送不重複計量。

## C-04．錯誤與接件

跨篇需要錯誤資料時，最少有穩定 `code` 與人看得懂的 `message`；需要時附 `retryable` 或有界 `details`。不在本篇定 RPC 數字碼、method 全集或通用封套；各處的錯誤碼與結束碼在哪裡定，見[集中碼表](protocol/README.md#集中碼表)，inst 的錯誤碼另見[正本](base/inst.md)。

`retryable` 只提示可再試的條件，不授權重做 unknown，也不能越過取消或重試上限。確定的 LLM 限流例外只依 [S-303](scheduling/llm.md)。收件、完成、已消費是三種不同確認，正本見 [B-503](base/transport.md)；收到請求不表示工作成功。

驗收：先接件、後執行失敗，兩項事實都保留；錯誤標可重試也不能讓結果不明的工作自動再跑。

## C-05．舊提交交易

（09-29 重寫：已刪；git 提交／還原與組見 [B-630、B-622](settled/tick.md)。）

## C-06．最小例子與保留

（09-29 重寫：已刪／併入[儲存 B-404](base/storage.md)；去重見[投件 B-503](base/transport.md)。）

## C-07．版本演進與永遠禁止的鍵

〔使用者方向 2026-09-30，第十八批〕格式版本演進**兩層並用**：

1. **小改不升版**：加可選欄位、放寬值域，以及在寫明「開放」的列舉加值（例如 kernel 自訂的任務種類與資源名稱，見 [T-06](terms.md)）。讀的一方遇到不認得的欄位直接忽略。
2. **不相容的大改才升版**：刪欄位、改意思、改成必填、收窄值域、在沒寫明開放的列舉加值，都要升 `version`（inst 與 tasks 升 `_metainfo._version`）。新程式讀目前版與前一版、寫目前版；遇到比自己新的版本仍拒絕，不猜讀。
3. **批次轉檔指令 `aos migrate`**：把舊版檔一次轉成目前版，範圍含 node 裡的持久檔，以及 daemon 的 `state.json` 與設定檔。指令形狀見 [H-004](cli/commands.md)。〔建議預設，未拍板〕node 裡的檔在 node 鎖內轉（不自己提交，同 `aos-config-add`；`.aos/` 底下的改動由下一格的 `aos-git close` 跟著提交，[B-602](settled/tick.md)）；daemon 的 `state.json` 只在 daemon 停著時轉。〔使用者方向 2026-09-30，第二十批疑點裁定 8〕這類在 tick 之外取鎖改檔的指令當成外部世界，aos 不管。

〔使用者方向 2026-09-30，第十八批〕**哪裡放寬**：

| 範圍 | 不認得的欄位 |
|---|---|
| 持久檔：node 裡的設定、狀態、事項、清理報告、`.err` 旁檔；daemon 的設定檔與 `state.json` | 忽略 |
| 檔案 RPC：node 之間的請求、回應與其 payload | 忽略 |
| daemon IPC（socket 上的請求與回應，含 tick–daemon 通道）、helper 私有通道、runner 回報 | 拒絕（維持嚴格） |

〔建議預設，未拍板〕通道上送訊息時，外層的通道請求照 daemon IPC 嚴格；夾帶的訊息本身跟檔案收件同一個格式（〔使用者方向 2026-09-30，第十九批〕），收件任務取走後照檔案 RPC 放寬（[B-614](settled/daemon/messaging.md)）。

〔建議預設，未拍板〕程式改寫整份持久檔時，原樣保留不認得的欄位，不因為不認得就刪掉。daemon 設定檔出現不認得的欄位，啟動與熱重載時照樣忽略，但在 stdout 印一行列出這些欄位名，免得拼錯被默默吃掉。

〔使用者方向 2026-09-30，第十八批〕**永遠禁止的鍵**：放寬以後，下列鍵只要出現，整份仍然拒收，不能當成「不認得就忽略」：

| 鍵 | 出現在 | 為什麼 |
|---|---|---|
| `api_key` | LLM 池設定 | key 只能用 `key_ref` 指到檔案，不寫進設定（[S-301](scheduling/llm.md)） |
| `argv` | 事項（attention） | 事項只給人或 agent 看的建議，不會被自動執行（[S-405](scheduling/operations.md)） |

這張清單只收已經裁定的安全規則；要加新的鍵，須經使用者裁定。〔使用者方向 2026-09-30，第十九批〕任務表的 `user` **已從清單移除**：任務是 inst 的超集，可以帶自己的 `user`；省略時照舊用 node inst 的身分。〔使用者方向 2026-09-30，第二十批疑點裁定 6〕核心不切帳號：`user` 跟 tick 的帳號不同時那一項回 125，要切帳號就在 argv 包普通程式 `aos-as`，額度照 inst 核（[B-620](settled/tick.md)、[B-303](settled/helper.md)）。schema 的寫法見 [P-007](protocol/README.md)。

驗收：持久檔與檔案 RPC 多一個不認得的欄位照樣讀得進來、改寫後欄位還在；daemon IPC 多一個欄位被拒；帶禁止鍵的檔整份拒收，任務表的項目帶 `user` 照收（跟 tick 帳號不同時那一項回 125）；舊版檔經 `aos migrate` 後新程式照讀，比自己新的版本被拒。
