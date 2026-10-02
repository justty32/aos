> 封存 2026-10-02：09-30 審稿與第十八～二十批（含 cgroup／git）改寫計畫、交接、核對報告，批次已結束；結論已由 proto6/spec（settled/ 與 settled/deferred/）與裁定紀錄 proto6/notes/verdicts/09～11 吸收

← [審稿索引](README.md)

# astra 核對第十九批落 spec（2026-09-30）

以 **10 號裁定的最後版本為準**，用 Python 讀完 map 的 **112 列**，平行核對主規格、協議、schema、範例、交接中的暫定項，以及上一輪 astra 的 15 項；再交叉覆核問題證據。沒有改檔、沒有 commit。

**結論：第十九批的主幹已落，但還不能算完整完成；主要缺口是備援與跨帳號任務的銜接、上下層規則，以及協議搬移未收乾淨。**

以下按修正主題計 **14 項問題**，相同問題不重複計數。協議搬移剩下的 8 組合算一項，第四節另逐項交代。

**一、沒落或落錯**

**1. 已裁定「兩父同意」，正文卻允許略過未登記的舊父**

依據：10 號疑點裁定 5。已有資料夾上層時，覆蓋應取得新舊兩個上層同意。

現在 [proto6/spec/daemon.md:176](../../../spec/settled/daemon.md) 寫：資料夾推得的上層不在這個 daemon 登記時，「只要新上層同意」。但 [proto6/spec/tick.md:80](../../../spec/settled/tick.md) 的驗收又要求只有新上層同意時拒絕。

這個例外雖標「暫定」，仍直接放寬了已裁定的必要條件。**建議：無法取得既有舊父同意時，不應直接准許覆蓋；暫定只能補機制，不能取消兩父同意。**

**2. 部分交接中的暫定，被寫進「使用者方向」段落**

依據：`batch19-handoffs.md` 的暫定不是使用者裁定。

| 暫定內容 | 現在的正文 |
|---|---|
| 通道外層嚴格、內層放寬；通道只傳請求，回應走檔案 | [proto6/spec/daemon.md:400](../../../spec/settled/daemon.md) 直接當成 B-614 規則；[proto6/spec/tick.md:228](../../../spec/settled/tick.md) 也在使用者方向句內規定回應一律走檔案 |
| 池 node 必須跑在 daemon 底下 | [proto6/spec/scheduling/llm.md:125](../../../spec/scheduling/llm.md) 在第十九批使用者方向句內直接定下這個前提 |

**建議：補回局部「暫定」標記，分清使用者裁定與工程選擇，不必重新討論選哪個方案。**

其他如登記時固定上層、kind 分段、有 tick 的判準、unknown 份額、git 恢復時 adopt 等，已有「暫定」或「建議預設，未拍板」標記，沒有因它們尚未定案就判成漏項。

**3. map 要求的 notes 收尾尚未完成，入口仍把 cgroup／git 寫成必要條件**

依據：map `筆-01、筆-04、筆-05`，以及疑點裁定 8、9。

- [proto6/README.md:5](../../../README.md) 仍說標準配備「需要 cgroup v2 與 git」。
- [proto6/notes/README.md:16](../../../notes/README.md) 仍把 cgroup v2 列為標準配備必要依賴。
- [proto6/notes/verdicts/10-tick-minimal-core.md:5](../../../notes/verdicts/10-tick-minimal-core.md) 仍說「尚未落進 spec」，沒有補這次實際落點；同檔第 80 行的衝突說明也仍說標準配備環境需要 cgroup v2。
- [proto6/notes/base.md:25](../../../notes/base.md) 的日常啟動必經特權點舊說法，未加第十九批取代指引。

**建議：現行入口改成「完整級需要；不能用時有備援，仍算全掛」，補實際落點與完成狀況。歷史內容保留，旁邊加取代註，不改寫歷史裁定。**

**4. 上一輪要求的協議搬移，仍有 8 組未搬完**

依據：第十八批方案 A，以及本輪計畫明列一併處理 astra 15 項。

不是只有欄位語意留下來；協議篇仍有可直接照做的操作流程，例如：

- [proto6/spec/protocol/ops.md:81](../../../spec/protocol/ops.md) 起仍有設定修復、重驗、取鎖、提交、標完成的流程。
- [proto6/spec/protocol/kernel-tasks.md:109](../../../spec/protocol/kernel-tasks.md) 仍有 prepared → 下一格建 inst／啟動標記 → mount → 等結果的完整流程。
- [proto6/spec/protocol/agent-tasks.md:110](../../../spec/protocol/agent-tasks.md) 仍規定工具設定的取鎖、驗證、安裝、提交步驟。

**建議：把剩餘操作流程搬到既定主規格，協議留下格式、介面與一句引用。**八組位置列在第四節；這是未完成既定搬移，不是挑文風。

**二、三層架構不一致**

**5. git 備援已接好寫入端，讀取與清理端仍要求 git commit**

依據：疑點裁定 9；[proto6/spec/terms.md:18](../../../spec/terms.md) 明定，沒有另寫備援限制的保證，兩級都成立。

[proto6/spec/tick.md:171](../../../spec/settled/tick.md) 已明說備援沒有歷史、回溯與同版本讀取，只能讀目前檔案。但下列功能仍硬性要求 commit：

| 功能 | 尚未接上備援的位置 |
|---|---|
| unknown 保留期 | [proto6/spec/base/storage.md:37](../../../spec/base/storage.md)：從首次 git commit 時間起算 |
| 用量收集與避免重複累加 | [proto6/spec/scheduling/admission.md:116](../../../spec/scheduling/admission.md)：固定同一 commit 讀；下一行依相同 commit 判斷不重加 |
| 摘要發布 | [proto6/spec/protocol/messages.md:78](../../../spec/protocol/messages.md)：固定 commit 取內容再發布 |
| replies／context 查詢 | [proto6/spec/protocol/agent-tasks.md:147](../../../spec/protocol/agent-tasks.md)：只讀同一 commit |
| listen | [proto6/spec/cli/commands.md:100](../../../spec/cli/commands.md)：每 200 ms 等新 commit |

**建議：逐個接上備援證據來源與讀法**，例如完成紀錄時間、目前檔案，以及相應的去重依據；明示不再保證一致快照。否則「無 git 仍全掛」成立，但這些功能照規格做不出來。

**6. 任務可以切帳號，但標準配備沒有把核心鎖交給它**

依據：疑點裁定 4，任務現在就可帶 `user`。

- [proto6/spec/tick.md:106](../../../spec/settled/tick.md)：跨帳號任務經 `node.mount` 開，**不繼承鎖 fd**，原 tick 等它結束。
- [proto6/spec/protocol/agent-tasks.md:66](../../../spec/protocol/agent-tasks.md)：`aos-agent-step` **必須繼承並核對 `AOS_TICK_LOCK_FD`**；第 75 行規定鎖不符回 125。
- [proto6/spec/protocol/kernel-tasks.md:9](../../../spec/protocol/kernel-tasks.md)：kernel 任務同樣核對繼承鎖；若改自行取鎖，又會被仍持鎖的原 tick 擋住。

所以 schema 已允許帶 `user`，但跨帳號的 agent／kernel 任務會卡在必要前置條件。

**建議：補上跨帳號任務如何可信地沿用原格鎖的契約，再同步 module 入口。**這不是反對暫定的 mount 做法，而是目前兩端接不起來。

核心三件事本身已明確寫成不依賴 daemon、git、cgroup、helper；沒有找到仍普遍要求「先有 daemon／git／cgroup，tick 才能跑」的核心主條文。cgroup 備援的完整／備援保證表也已寫出。主要未收完的是上述跨層銜接，以及第一節的舊入口文字。

**三、新引入的矛盾**

**7. 再次換父時，「舊上層」有兩個答案**

- [proto6/spec/tick.md:71](../../../spec/settled/tick.md)，B-628：資料夾推得的上層。
- [proto6/spec/daemon.md:176](../../../spec/settled/daemon.md)，B-606：目前有效上層。
- [proto6/spec/scheduling/admission.md:29](../../../spec/scheduling/admission.md)，S-202：又要求資料夾推得的上層同意。

例如資料夾父 A 已覆蓋成 B，再改成 C，前者要求 A＋C，後者要求 B＋C。

**建議：在正本分清首次覆蓋與再次換父，其他篇統一引用。**C-02、T-02 的預設包含與管轄跟資料夾說法已對齊，分叉發生在細部授權。

**8. 設定裡的 root 可以直接清掉資料夾上層**

[proto6/spec/daemon.md:179](../../../spec/settled/daemon.md) 說設定載入的頂層「上層固定是 null」；B-628、T-02 卻規定最近包含且有 tick 的資料夾就是上層。

例如設定只列 `/a/b` 為 root，而 `/a` 已有 cron 跑的 tick：daemon 判 null，核心判 `/a`。禁止「設定內兩棵 root 相互包含」擋不住此例。

**建議：明訂設定 root 如何遵守預設上層及覆蓋同意規則，不能只因列入 roots 就默默取消上層。**

**9. kernel 一律帶 token，會撞上不收 token 的 method**

[proto6/spec/protocol/kernel-tasks.md:21](../../../spec/protocol/kernel-tasks.md) 要 daemon 開的格「請求帶 token」。

但 [proto6/spec/protocol/daemon/channel.md:14](../../../spec/settled/deferred/protocol/daemon/channel.md) 只允許 register／unregister／wake／mount／kill／send／take 帶 token，其他 method 帶了回 `invalid_params`。kernel 自己又必須呼叫 `daemon.info`、`node.show`、`node.provision`。

**建議：P-801 明寫只對允許清單附 token，其他 method 沿既有 socket 帳號授權。**

**10. 接件任務切帳號後，取消權限到底記誰的 UID 不一致**

[proto6/spec/base/execution.md:40](../../../spec/base/execution.md) 已補：接件任務帶自己的 `user` 時，記該任務有效 UID。

但以下仍定成 node inst／tick 的 UID：

- [proto6/spec/protocol/work.md:115](../../../spec/protocol/work.md)
- [proto6/spec/protocol/kernel-tasks.md:117](../../../spec/protocol/kernel-tasks.md)
- [proto6/spec/protocol/schemas/kernel-work-state.schema.json:22](../../../spec/protocol/schemas/kernel-work-state.schema.json)

tick 是帳號 A、接件任務是 B 時，兩套規則會讓 `work.cancel` 認不同主人。

**建議：`owner_exec_uid` 的三處說明統一跟 B-203，保留該細節的暫定標記。**

**11. 要問 y／n，stdin 卻寫「不讀」**

[proto6/spec/tick.md:121](../../../spec/settled/tick.md) 要在 stdin、stderr 都是終端機時問 y／n；[proto6/spec/protocol/node.md:70](../../../spec/settled/protocol/tick.md) 卻仍規定 tick stdin 不讀。

**建議：介面表補「一般不讀，B-630 的互動確認除外」。**

**12. once 舊登記說法仍殘留**

[proto6/spec/protocol/node.md:33](../../../spec/settled/protocol/tick.md) 還說「once 可直接登記一份 inst 檔」；[proto6/spec/daemon.md:383](../../../spec/settled/daemon.md) 已明定改成 `node.mount`，不是登記種類。

**建議：改成掛載目標可指定單檔 inst，引用 B-613／P-118。**其他查到的 `once:true`、`once.clear`、`once-*` 多屬歷史改名說明或刻意無效的範例，沒有算成問題。

**13. registration schema 的根入口指向已刪除的定義**

[proto6/spec/protocol/schemas/daemon-registration.schema.json:429](../../../spec/protocol/schemas/daemon-registration.schema.json) 仍引用 `#/$defs/Registration`，但該定義已不存在。

直接驗根入口會失敗。既有範例走其他 fragment，因此整套 validate 仍能通過。

**建議：根入口改指現行正確定義，補直接使用根入口的驗證。**

**14. node.mount schema 少了「無 token 必填 parent_id」條件**

[proto6/spec/protocol/daemon/channel.md:22](../../../spec/settled/deferred/protocol/daemon/channel.md) 明定：沒有 token 時，`parent_id` 必填。

但 [proto6/spec/protocol/schemas/daemon-rpc.schema.json:819](../../../spec/protocol/schemas/daemon-rpc.schema.json) 只要求 `node_id`。記憶體驗證確認，只給 `node_id`、兩者都不帶的請求仍通過 schema。

**建議：補條件必填與對應反例。**

通道環境變數名稱、token 的 32 小寫 hex 格式、send／take 名稱、暫存上限及新增錯誤碼，所查正文與 schema 沒有發現其他名稱不一致。

**四、上一輪 15 項處理狀況**

**7 項已處理，8 項部分處理。**下面的 8 組未完成搬移，都計入本報告問題 4，不再各加一次問題數。

| 項次 | 狀態 | 說明 |
|---|---|---|
| 1 LLM 必須集中同一池 | 已處理 | [scheduling/llm.md:30](../../../spec/scheduling/llm.md) 已交 kernel 決定集中或分片；P-405 一致。 |
| 2 第二次 SIGTERM 來源 | 已處理 | [daemon.md:98](../../../spec/settled/daemon.md) 與 CLI 已另標工程補充。 |
| 3 Q3 仍標未拍板 | 已處理 | [scheduling/admission.md:48](../../../spec/scheduling/admission.md) 已分開裁定與工程細節。 |
| 4 notes 設定不變保證 | 已處理 | [between-ticks-configuration.md:11](../../../notes/between-ticks-configuration.md) 已改軟性原則。 |
| 5 共用協議入口行為 | 已處理 | P-003～006、P-008 主要流程已縮成介面或主規格引用。 |
| 6 daemon 協議流程 | 部分 | [provision-and-runner.md:33](../../../spec/settled/deferred/protocol/daemon/provision-and-runner.md) 起仍有 helper 啟動、收尾、回收後才回覆等流程。 |
| 7 node 協議流程 | 部分 | [protocol/node.md:134](../../../spec/settled/protocol/tick.md) 起仍有完整配權與建立核對步驟。 |
| 8 messages 投件／補投流程 | 部分 | [protocol/messages.md:78](../../../spec/protocol/messages.md) 仍有取 commit、原子發布、失敗留舊值的流程。 |
| 9 work／LLM 流程 | 部分 | [protocol/llm-work.md:46](../../../spec/protocol/llm-work.md) 起仍有收齊回應、失敗／unknown 判定等行為。 |
| 10 resources 政策 | 部分 | [protocol/resources.md:72](../../../spec/protocol/resources.md) 起仍有 hardlink 去重、量不到時的處置、計數器重置政策。 |
| 11 ops 清理／事項流程 | 部分 | [protocol/ops.md:81](../../../spec/protocol/ops.md) 起仍有修復、重驗、取鎖、提交與標完成流程。 |
| 12 agent 狀態機 | 部分 | [protocol/agent-tasks.md:110](../../../spec/protocol/agent-tasks.md)、第 124 行仍有工具設定與 recheck 操作流程。 |
| 13 kernel 同步／排程流程 | 部分 | [protocol/kernel-tasks.md:109](../../../spec/protocol/kernel-tasks.md) 仍完整規定跨格掛載與收結果流程。 |
| 14 排空卻要求全停格 | 已處理 | [protocol/daemon/shutdown.md:13](../../../spec/settled/deferred/protocol/daemon/shutdown.md) 已改引用 B-604。 |
| 15 取消兩套判定 | 已處理 | [base/execution.md:52](../../../spec/base/execution.md) 已統一；TERM 後正常退出且完整發布，照原結果，逾時另外處理。 |

**五、檢查結果**

| 檢查 | 結果 |
|---|---|
| `python3 -B proto6/spec/check_ids.py --strict` | **通過**：引用 2801、定義 236；找不到、重號、只剩索引、預留未寫均為 0。 |
| 系統 Python 執行 validate | 缺 `referencing`，未能完成。 |
| 既有 uv 環境的 Python 加 `-B` 執行同一支 validate | **通過：58 schemas、249 examples**，未安裝套件或建立檔案。 |
| 補查 schema 本地 `$ref` | 發現 **1 個壞引用**，即問題 13。 |
| 補驗無 token、無 parent_id 的 mount | schema 接受，與文字契約不符，即問題 14。 |
| 工作樹 | `git status --porcelain` 無輸出；全程唯讀、未 commit。 |

既有驗證通過，只代表它涵蓋的條號與範例通過，不能消除上述文字矛盾，也沒有涵蓋所有 schema 入口。

map **112 列全部核過**。以下以「該列要求是否完成」分類；完成不代表相關功能完全沒有其他跨篇問題：

| map 類別 | 完成 | 部分完成 | 已由後裁定解消／本輪不改 |
|---|---|---|---|
| 撤，11 列 | 01、03、05～09、11 | 02、04、10 | — |
| 留，3 列 | 01～03，依最新備援裁定理解 | — | — |
| 前，22 列 | 01～17、20～21 | 18、19、22 | — |
| 核，5 列 | 01、02、04、05 | 03 | — |
| 新，10 列 | 01、03、05、06、09、10 | 02、04、07、08 | — |
| 核對，15 列 | 01～05、14、15 | 06～13 | — |
| 舊，28 列 | 02～10、12～13、16～28 | 14 | 01、11、15 已解消 |
| 原，13 列 | — | — | 01～13 明列本輪不改 |
| 筆，5 列 | 02、03 | 01、04、05 | — |
| **合計** | **73** | **23** | **3 解消、13 不改** |

原型 13 列沒有算漏項。23 列部分完成的缺口，已合併到前述 14 個修正主題。

**六、已確認落實**

「＊」表示主要條文已找到，但仍受前述問題影響，不能整條判完全完成。

| 10 號條目 | 已落條號 |
|---|---|
| 方向 1：定期執行，怎麼啟動不管 | T-07、B-601、B-627 |
| 方向 2＊：cwd 管轄、包含與從屬 | T-10、B-626、B-628；上下層分叉見問題 7、8 |
| 方向 3：任務任意掛載、掛行程與砍掉 | B-620、B-626、B-613 |
| 方向 4：借來的機制不是核心前提 | T-07、B-626、B-629、B-631、B-632 |
| 方向 5：實際管轄權不是運作前提 | T-10、B-626 |
| 方向 6：核心如 aos-exec 加功能 | T-07、B-626、inst |
| 方向 7＊：互斥、路徑識別、daemon 定位、收件非核心 | B-602、B-601、B-623、B-629；跨帳號承鎖見問題 6 |
| 方向 8＊：inst 超集、上下層 | B-620、B-628；needs／git 納核心的部分已被方向 11 推翻，不算漏 |
| 方向 9＊：系統收件與 daemon 通道 | B-623、B-624、B-612～614、P-117～119；接線與格式缺口見問題 2、9、13、14 |
| 方向 10＊：once 不屬核心 | B-629、B-613、P-402；舊登記句見問題 12 |
| 方向 11：needs／git 移出核心 | T-07、B-626、B-620、B-621 |
| 方向 12＊：三層、全掛、人手風險、y／n | T-10、B-629、B-630、B-627；備援讀取與 stdin 見問題 5、11 |
| 疑點裁定 1：同一支 aos-tick | T-10、B-626、B-629 |
| 疑點裁定 2：清單全部算標準配備 | B-629；B-404、B-603、B-604 |
| 疑點裁定 3：helper／通道只功能受限 | T-10、B-629、B-630；cgroup／git 判準已依裁定 8、9 更新 |
| 疑點裁定 4＊：任務現在可帶 user | C-07、B-620、P-202、P-704 及 schema／正例；執行銜接見問題 6、10 |
| 疑點裁定 5＊：兩父同意、管轄跟資料夾 | B-628、B-606、S-202、C-02、T-02；問題 1、7、8 尚未收完 |
| 疑點裁定 6：通道看收件夾寫權 | B-614、B-624、P-119 |
| 疑點裁定 7：收件任務自己取 | B-623、B-614、P-119，使用 `node.take` |
| 疑點裁定 8：cgroup 準備與備援 | B-605 有 systemd 使用者委派及五步檢查；B-631 有 subreaper、程序群組、rlimit 與兩級保證表 |
| 疑點裁定 9＊：git 最低版本與備援 | B-630、B-632、B-622；2.36、檢查、fsync＋rename、Q1／Q2、needs、sent 補投都有，讀取端缺口見問題 5 |