# 身分與資源

← [基底](README.md)｜[kernel 樹](../scheduling/README.md)｜[架構與裁定](../../notes/2026-09-29-kernel-tree.md)

## B-301：權限與額度歸屬〔使用者方向 2026-09-29〕

通用 user 預設是啟動 daemon 的 user，可另設；沒 helper 時全樹共用它，不承諾成員間的 UID 隔離。需要隔離時一 node 一 Linux 帳號；kernel node 也一樣用自己 inst 的 `user`，不另設服務帳號（第九批）。工具沿用呼叫 node 的身分、權限及資源範圍。〔使用者方向 2026-09-30，第十八批〕投件權就是執行權而且會傳遞（[B-501](transport.md)、[T-08](../terms.md)），所以 UID 隔離與 key 保護**只對整條投件鏈以外的帳號**成立；key 保護的部署邊界見 [LLM 池](../scheduling/llm.md)。

身分宣告、繼承與授權失敗的執行結果，以 [inst 的 `user`](inst.md) 為正本；**不由 node 資料夾位置決定**。

上層向 daemon 註冊成員時一併給「身分額度」，只能給自己已有的身分（〔使用者方向 2026-09-30，第十八批〕額度可以用前綴或 UID 範圍寫，子額度要被父額度包含，規則見 [B-606](../daemon.md)）；最頂層額度在 daemon 設定檔，沒 helper 時只含通用 user。額度隨 daemon 登記保存；重啟讀回狀態，缺失時由各 kernel 重新註冊恢復。宣告或繼承所得身分都要在額度內；不能改用 daemon 帳號偷偷執行。

身分額度管「准用誰」，資源 module 管「能用多少」。資源分配以 [S-203](../scheduling/admission.md) 為正本（各 kernel 可自訂資源名，cgroup 與身分額度維持巢狀），cgroup 層級見 [B-605](../daemon.md)；多個工具共用呼叫 node 的合計上限。

**驗收：**通用 user、身分額度與路徑無關的情境見 [V-03](../conformance.md)。

## B-302：可信註冊與部署

註冊關係、node 路徑 ID、IPC 授權及重啟重建以 [daemon](../daemon.md) 為正本。

〔建議預設，未拍板〕部署只驗證實際配置的能力：要切 UID 就驗 helper 與切換，要 cgroup 限制就驗相應 controller；CPU、記憶體等 module 沒裝不因此拒絕整套部署。已配置卻做不到時明確報錯，不能假裝已隔離。〔使用者方向 2026-09-29 晚〕cgroup v2 子樹本身是必要的，拿不到就不啟動，見 [B-605](../daemon.md)。

〔建議預設，未拍板〕另設通用 user 時，部署須安排 daemon 的直接啟動路徑實際用該身分；非 root 程序不能只改一個設定就冒稱已切 UID。做不到就報部署錯誤。

〔使用者方向 2026-09-29〕擔任頂層 kernel 的 node 沒有天生特權，權限由設定授予。

〔建議預設，未拍板〕已開始的 attempt 不中途換身分與資源範圍；設定更新見 [A-102](../agent/configuration.md)。〔使用者方向 2026-09-30，第十八批〕調高或調低 cgroup 上限值不算中途換資源範圍，隨時可改（[B-609](../daemon.md)）。

**驗收：**偽造 payload 帳號不能註冊別人的資料夾；未啟用磁碟 module 不必驗 quota。重啟註冊遇一個壞成員，其餘仍長回來。

## B-303：可選 root helper 與解析分界〔使用者方向 2026-09-29〕

root helper 本質上是 daemon 的一部分，切成小程序是為了安全，緊急時可以 kill；不需 UID 隔離的部署可不裝。主 daemon 非 root，目標就是通用 user 時由 daemon 自己開；需要其他身分才交 helper。任務表裡的系統性任務也不是 root，要 root 的固定步驟留在 helper。

〔使用者方向 2026-09-29〕**一支指令、看啟動方式決定模式**：不用 sudo 開 daemon＝沒 helper 模式，整樹用通用 user，要求其他身分一律拒絕。用 sudo（root）開時，daemon 在接 IPC、讀任何 node 之前先 fork 出 helper，主程式隨即永久降權（清掉 root 身分、群組、capabilities 與特權 fd），啟動時在 stdout 印 `helper_pid=...`，並存兩份 pid 檔，細節見 [daemon](../daemon.md)。daemon 死掉時 helper 必須跟著結束（例如 `PR_SET_PDEATHSIG`，並以與 daemon 間的管道斷線為準），不留沒人管的 root 程序。

〔使用者方向 2026-09-29〕用 sudo 開時通用 user 不能預設成 root：取叫 sudo 的原帳號（`SUDO_UID`），直接用 root 或由服務啟動時必須在設定檔明寫一個非 root 帳號，否則拒絕啟動。kill helper＝切斷**新的**特權操作：已開的 tick 照跑到結束，之後需要其他身分的 tick 一律不跑並寫待處理事項；helper 不自動重啟，要恢復得重開 daemon。已做的 chown 不回滾。〔使用者方向 2026-09-29 晚〕systemd 沙盒防護初版不用，見 [B-605](../daemon.md)。

helper 只查可信註冊、安置已配置資源框、切目標帳號、exec 固定 runner，外加固定清單上的佈建動作（〔使用者方向 2026-09-30，第十八批〕動作清單、參數與各動作做什麼以 [B-609](../daemon.md) 為正本）；每次只做清單上的一件，不接任意程式當 root 跑。牽涉 helper 的設定（其他帳號的額度、佈建權）改了要重開 daemon（[B-608](../daemon.md)）。先授權、切身分後解析與開檔的順序，以 [inst](inst.md) 為正本；失敗不能借高權限補救。

〔使用者方向 2026-09-29〕helper 請求綁定 daemon 已授權的註冊項與本次目標 UID，不能以呼叫者自填的 UID 或路徑當授權。切換前清除繼承憑證、非核准 fd 與多餘特權；不把管理 socket 或 LLM key 傳給 runner。runner 環境按目標帳號及部署建立，inst 的 envs 再依其規則疊加；不另禁止工具用一般權限改設定。

**驗收：**授權及切身分後開檔見 [V-03](../conformance.md)；另測切帳號失敗回 125、無 `exit`，kill helper 後不得偷改用通用 user。

## B-304：磁碟與可寫位置〔使用者方向 2026-09-29〕

磁碟是可選 module，額度只記帳，不是硬上限或安全邊界；不綁 XFS 或其他檔案系統，也不強迫沒裝 module 的部署提供 quota。〔使用者方向 2026-09-29 晚〕project quota 有就用；是否可用在 daemon 啟動時自動偵測，設定檔可強制關（[B-605](../daemon.md)）。〔第十八批〕沒有 quota 時，用量由磁碟資源任務（kernel 定義的資源，[S-203](../scheduling/admission.md)）定期量；多久量一次是那項任務的設定，aos 不另定。node 放在不支援某功能的檔案系統上，那個功能就不支援，不做白名單。只報實際能計量的位置，不能把觀測不到的外部路徑說成已限額。多 node 共寫外部 workspace 由工具自行協調，aos 不保證跨 node 寫入一致。

〔建議預設，未拍板〕暫存按實際掛載歸屬：普通磁碟目錄仍占磁碟，tmpfs 按其掛載限制與適用的記憶體計量處理；不能因路徑叫 `/tmp` 就算成 tmpfs。`TMPDIR` 只是預設路徑，不能當成限制寫入位置的機制。只有可信 I/O errno 或診斷才標 EDQUOT／ENOSPC，不從任意退出碼猜磁碟已滿。

〔使用者方向 2026-09-29〕滿碟、commit 失敗與清理見[儲存](storage.md)。避免大量 commit 與 submodule 的邊界見 [tick](../tick.md)。

**驗收：**磁碟 module 缺席可啟動；啟用時用量與實際落點相符。commit 失敗不宣告新狀態已生效。
