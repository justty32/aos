# 身分與資源

← [基底](README.md)｜[kernel 樹](../scheduling/README.md)｜[架構與裁定](../../notes/2026-09-29-kernel-tree.md)

## B-301：權限與額度歸屬〔使用者方向 2026-09-29〕

通用 user 預設是啟動 daemon 的 user，可另設；沒 helper 時全樹共用它，不承諾成員間的 UID 隔離。〔使用者方向 2026-09-30，第二十批〕UID 隔離由普通程式 `aos-as` 經 helper 落實（B-303）；沒有 helper 只算功能受限。需要隔離時一 node 一 Linux 帳號；kernel node 也一樣用自己 inst 的 `user`，不另設服務帳號（第九批）。工具沿用呼叫 node 的身分、權限及資源範圍。〔第十九批，疑點裁定 4；第二十批疑點裁定 6〕任務表的任務也可以帶自己的 `user`，但核心不切帳號：跟 tick 的帳號不同時那一項回 125；要用別的帳號跑就包 `aos-as`，同樣要在該 node 的額度內（[B-620](../settled/tick.md)）。〔使用者方向 2026-09-30，第十八批〕投件權就是執行權而且會傳遞（[B-501](transport.md)、[T-08](../terms.md)），所以 UID 隔離與 key 保護**只對整條投件鏈以外的帳號**成立；key 保護的部署邊界見 [LLM 池](../scheduling/llm.md)。

身分宣告、繼承與授權失敗的執行結果，以 [inst 的 `user`](inst.md) 為正本；**身分不由 node 資料夾位置決定**（省略時繼承的「上層」怎麼判見 [B-628](../settled/tick.md)）。

上層向 daemon 註冊成員時一併給「身分額度」，只能給自己已有的身分（〔使用者方向 2026-09-30，第十八批〕額度可以用前綴或 UID 範圍寫，子額度要被父額度包含，規則見 [B-606](../settled/daemon.md)）；最頂層額度在 daemon 設定檔，沒 helper 時只含通用 user。額度隨 daemon 登記保存；重啟讀回狀態，缺失時由各 kernel 重新註冊恢復。宣告或繼承所得身分都要在額度內；不能改用 daemon 帳號偷偷執行。

身分額度管「准用誰」，資源 module 管「能用多少」。資源分配以 [S-203](../scheduling/admission.md) 為正本（各 kernel 可自訂資源名，cgroup 與身分額度維持巢狀），cgroup 層級見 [B-605](../settled/daemon.md)；多個工具共用呼叫 node 的合計上限。

**驗收：**通用 user、身分額度與路徑無關的情境見 [V-03](../conformance.md)。

## B-302：可信註冊與部署

註冊關係、node 路徑 ID、IPC 授權及重啟重建以 [daemon](../settled/daemon.md) 為正本。

〔建議預設，未拍板〕部署只驗證實際配置的能力：要切 UID 就驗 helper 與切換，要 cgroup 限制就驗相應 controller；CPU、記憶體等 module 沒裝不因此拒絕整套部署。已配置卻做不到時明確報錯，不能假裝已隔離。〔使用者方向 2026-09-30，第十九批，改寫第十四、十五批「cgroup v2 必要」；第二十批改主詞〕cgroup v2 子樹是 daemon 的 node 框與上限、以及 `aos-cg` 每項一框要的；tick 核心不需要。拿不到時不拒絕啟動。〔使用者方向 2026-09-30，第二十批進行順序〕本輪假設沒有 cgroup；daemon 那側與 `aos-cg` 怎麼用 cgroup，下一步納入（[B-605](../settled/daemon.md)、[B-202](execution.md)）。

〔建議預設，未拍板〕另設通用 user 時，部署須安排 daemon 的直接啟動路徑實際用該身分；非 root 程序不能只改一個設定就冒稱已切 UID。做不到就報部署錯誤。

〔使用者方向 2026-09-29〕擔任頂層 kernel 的 node 沒有天生特權，權限由設定授予。

〔建議預設，未拍板〕已開始的 attempt 不中途換身分與資源範圍；設定更新見 [A-102](../agent/configuration.md)。〔使用者方向 2026-09-30，第十八批〕調高或調低 cgroup 上限值不算中途換資源範圍，隨時可改（[B-609](../settled/daemon.md)）。

**驗收：**偽造 payload 帳號不能註冊別人的資料夾；未啟用磁碟 module 不必驗 quota。重啟註冊遇一個壞成員，其餘仍長回來。

- B-303．可選 root helper 與 aos-as：已搬到[整理區](../settled/helper.md#b-303可選-root-helper-與解析分界使用者方向-2026-09-29)，條號不變。

## B-304：磁碟與可寫位置〔使用者方向 2026-09-29〕

磁碟是可選 module，額度只記帳，不是硬上限或安全邊界；不綁 XFS 或其他檔案系統，也不強迫沒裝 module 的部署提供 quota。〔使用者方向 2026-09-29 晚〕project quota 有就用；是否可用在 daemon 啟動時自動偵測，設定檔可強制關（[B-605](../settled/daemon.md)）。〔第十八批〕沒有 quota 時，用量由磁碟資源任務（kernel 定義的資源，[S-203](../scheduling/admission.md)）定期量；多久量一次是那項任務的設定，aos 不另定。node 放在不支援某功能的檔案系統上，那個功能就不支援，不做白名單。只報實際能計量的位置，不能把觀測不到的外部路徑說成已限額。多 node 共寫外部 workspace 由工具自行協調，aos 不保證跨 node 寫入一致。

〔建議預設，未拍板〕暫存按實際掛載歸屬：普通磁碟目錄仍占磁碟，tmpfs 按其掛載限制與適用的記憶體計量處理；不能因路徑叫 `/tmp` 就算成 tmpfs。`TMPDIR` 只是預設路徑，不能當成限制寫入位置的機制。只有可信 I/O errno 或診斷才標 EDQUOT／ENOSPC，不從任意退出碼猜磁碟已滿。

〔使用者方向 2026-09-29〕滿碟、commit 失敗與清理見[儲存](storage.md)。避免大量 commit 與 submodule 的邊界見 [tick](../settled/tick.md)。

**驗收：**磁碟 module 缺席可啟動；啟用時用量與實際落點相符。commit 失敗不宣告新狀態已生效。
