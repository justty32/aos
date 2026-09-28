cpu的數量未來應該會上千，用於應付上千個agent
只是說考慮到llm cpu注定只會有少少幾個，所以agent們會有很大一部分都在等llm
對於處在這種狀態的agent來說，cpu處理他們，就是一直在...有點像是空轉
所以我在想，是不是對於這種狀況來說，可以弄一個特殊cpu，他就是專門看這個
然後等看到了，再去喚醒相關cpu，或是之類...
    理論上這應該是kernel的責任，或許可以弄成lib？
    我會希望kernel能夠簡單一些，但看起來很難

然後我覺得地基差不多了。可以開始考慮最令人興奮的"工具大開發時代"
比如記憶管理工具，prompt history管理工具(/context, /compact)
agent交流工具，特定檔案修改工具(json, 指示詞, ...)
agent團隊與管理工具，agent創造與修改工具
創造工具的工具，讀取一個python檔，將其納入工具的工具
...各種各樣。總之，從這塊開始，可以自由揮灑創意
...就開一大堆subagent去玩玩看吧(codex/claude code都可以，想開誰就開誰)
    啊不過在開始之前，建議是先把權限之類的設置弄好，不然亂玩會出事
    弄權限，可以從json協定下手，也可以從其他地方下手
    要不然弄沙盒，弄docker都可以，隨意。

創造新工具的時候別忘了，使用者也會想用
所以也要考慮到人類的方便使用，比如：
我可能哪天心血來潮，想給amy添加新工具，或是管理工具（包括別名）
或是刪除工具（但不刪除工具所指向的程式本體）
這些，都麻煩提供一些cli工具。
或是在設計json協議的時候，方便我使用文字編輯器來修改或存取。

在大開發的時候要有目標。我這邊簡單給個：
去看看~/repo/workflows吧，如果能將其化爲一個agent團隊，那該有多好。
對了，我這邊給個工具好壞的評估標準：去看~/repo/ai_core中所提到的九軸（現在可能剩六軸）
    這不只是工具好壞，也是一整個agent團隊的評判標準。
：llm參與的越少越好，工具越穩定越好，整體跑起來資源占用量越少越好，越快完成越好
：人類能愈輕鬆理解愈好。

## 2026-09-27：/tmp/haha 試用建議（待處理）

使用者已完成 daemon／kernel、第一個 agent、掛載權限與基本工具的試用，狀態良好。以下先記錄，之後再處理：

- `aos-agent say`／`listen` 不支援串流，無法讓回覆一個字一個字出現；希望支援串流顯示。
- listen 的預設應為 `--last 5 --show-calls-full`（使用者原話寫 `aos-listen ...`；目前使用的指令是 `aos-agent listen`）。
- `aos-agent access`／`tools` 的相關操作都應有說明手冊。
- 各類 `aos-xxx help` 都不夠詳盡，需要補強。
- `aos-daemon scale` 需要解釋用途與操作。
- 各類 `aos-xxx check --probe` 的 `--probe` 需要解釋。
- 希望 `aos-agent access` 增加 `--force`：有時使用者想讓 agent 存取自己的資料（例如 `prompts/`），卻被 access 的保護規則擋住；應允許使用者明確指定 `--force` 解除阻擋。此處先記需求，尚未實作。

試用進度（使用者回報）：自製工具這一輪已成功，完成 parent 寫程式與測試、使用者包裝安裝、parent 呼叫自己寫的工具；父子 agent 試用於 09-28 依使用者要求暫緩，先理解單個 agent。


## 2026-09-28：沙盒筆記（待處理）

來源：使用者指定的 `/tmp/haha/proj/sandbox-notes.md`。以下保留原筆記的觀察、評估與建議；本次只收錄，尚未重新實測或裁定其中的安全性判斷。

### 沙盒隔離觀察與建議

#### 背景
在 bwrap 容器內（bubblewrap 0.12.0、`--unshare-all`、uid 1000、CapEff=0）做的唯讀偵察。

#### 現況評估（防護其實不錯）
| 面 | 狀態 | 說明 |
|---|---|---|
| 網路隔離 | 良好 | 只有 `lo`，無網卡、無 `resolv.conf`；`--unshare-all` 生效 |
| 提權 | 良好 | `CapEff/Bnd/Amb = 0`、`NoNewPrivs=1` |
| 根檔案系統 | 良好 | `--remount-ro /`，含白名單 `/etc/*` 全唯讀 |
| 宿主路徑 | 良好 | 命名空間遮蔽，容器內看不到 `/tmp/haha`、`/root` |
| userns 逃逸 | 可接受 | `unshare -U` 成功但無害（userns 內 CapEff 仍為 0、無法 mount、無法 join pid1 ns） |

#### 發現的設計縫隙

##### 1. fence 只管工具層，`bash` 沒有柵欄
- `AOS_TOOL_FENCE=/work` 的註解宣稱「掛進來的全部資料夾」都可達。
- 但只有 `read`/`write`/`edit`/`grep`/`find`/`ls` 實作了路徑比對；`bash` 只設 `cwd=root` 後自由執行。
- 後果：`bash` 可 `cd /etc`、讀 `/usr` 等宿主真實檔案，fence 形同虛設。
- **風險不在 /usr**，而在**安全敘事不一致**：註解描述了一道牆，實作只是多數工具門口的門簾。
- 多 agent 共用掛載時，這種不對稱會成為未來的漏洞溫床。

##### 2. 環境可觀測性洩漏宿主佈局
- `/proc/1/cmdline` 直接暴露 bwrap 完整參數：`/tmp/haha/proj`、`/tmp/haha/refs`、`agent1` 編號。
- `/opt/tool/config.json` 可讀（內容為 `{"root": "/tmp/haha/proj"}`）。
- 容器內的探針能反推宿主架構，對多租戶環境不理想。

#### 建議方向
1. **模糊化環境**：別讓容器內看到有意義的宿主路徑名（`agent1`、`haha` 這種一眼看穿的）。
2. **明確區分「唯讀參考」與「自我描述」**：self-prompts 屬於後者，性質不同於 `/work/ref`，應分開處理。
3. **統一 fence 語意**：若 fence 是安全邊界，就要在所有工具（含 `bash`）一致強制；若它不是，就別在註解裡寫成牆。
4. **封環境可觀測性**：光擋特定資料夾入口不夠，同樣資訊會從 `/proc` 與掛載表漏出。

#### 核心結論
安全保證應放在**核心層（bwrap namespace）**，而非應用層的 fence。
目前架構這點做對了——只要不把 fence 的註解當真。

## 2026-09-28：agent 預設沙盒、權限群組與工具介面（歷史建議）

同日後續已改採員工 Linux 權限與工具繼承身分；下面逐工具沙盒／權限 group／`_jail` 建議保留脈絡，已不是新架構的必要項目。見[後續已定方向](notes/2026-09-28-employee-identity.md)。`--without` 與 agent 工具介面的建議不因此取消。

使用者希望整個 agent 有一份通用的預設沙盒，以 agent 目前的 cwd 作為預設可存取資料夾。註冊工具時，若沒有指定可存取哪些資料夾，就沿用這個 cwd；個別工具仍可明確指定自己的沙盒。逐支工具各配一份雖然靈活，但工具大量增加後難以管理。

沙盒預設開啟，因此希望把 `_jail` 改成表達「例外在沙盒外執行」的欄位，例如 `_outside_the_jail` 的意思，但實際名稱應更短，名稱尚未定案。

未來增加沙盒／權限 group（例如 tools group）：工具註冊時可指定所屬群組，該組工具僅能存取群組設定允許的資料夾，共享同一份權限與沙盒設定；改一次就能套用到多支工具。個別設定、群組與預設值的完整優先序留待實作時釐清，不在此替使用者定案。

工具篩選除了 `--only`，也應提供 `--without`，用來排除指定工具。

未來把這些管理指令提供給 agent 使用時，要另行設計適合 agent 的工具介面，不能直接把目前這套人用的 argv 操作原樣交給 agent。

以上先記錄，尚未實作。現行實作已由 agent 的 `access.json` 共用掛載設定，但 cwd 只是起點，不限制其他掛載的可達性；目前沒有這裡提出的逐工具沙盒與權限 group。

## 2026-09-28：正式員工身分與固定 tick worker（新方向，未實作）

使用者希望沿用 Linux 使用者與權限：正式員工 agent 有自己的 Linux 身分與專屬固定 CPU worker 負責 tick，其餘全是工具／外包。root daemon 最初考慮放在 VM，後續也在探索直接放宿主機；部署尚未定案。完整語意、現況差距與未定範圍見 [方向紀錄](notes/2026-09-28-employee-identity.md)。

後續要求：先只考慮 Linux，深入評估具體實作可行性、宿主機 root daemon 的第二道牆，以及新增的開發、部署和維護複雜度。已記錄[設計草案](notes/2026-09-28-host-root-design.md)、[實作成本調查](notes/2026-09-28-linux-employee-implementation.md)、[外牆方案比較](../wf/workflows/investigations/proto5-linux-wall-feasibility.md)與[局部隔離實測](notes/2026-09-28-linux-isolation-probes.md)。候選方案與實驗不等於產品規格已定案，也未啟動 root daemon。

## 2026-09-28：工具繼承員工權限（已定方向，未實作）

工具通常繼承委託員工的 Linux UID／群組權限，包括內部 LLM 與再呼叫工具；員工是權限單位，接受工具出錯影響員工權限範圍的語意。新架構不需要逐工具 bwrap、mount／權限 group／`_jail`，共享交給 Linux group／ACL，cwd 只是起點。外層隔離仍包住整套 aos／daemon 保護宿主。現行 bwrap 尚未移除，需與員工身分及外牆一起遷移。見[完整決定](notes/2026-09-28-employee-identity.md)。

## 2026-09-28：Linux 資源與任務層排程（後續討論，未實作）

先放下員工／工具分類：一 agent 一 Linux 使用者，cgroup v2 管執行資源、project quota 管自有容量，工具沿用委託 agent 的權限與資源。另討論 tmpfs、取消 CPU worker、kernel 的任務層策略、通知與檔案 JSON-RPC；Docker／FUSE 不是基本架構前提，FUSE 延後，每 agent tick-daemon 提案撤回。完整已定方向、候選、現行事實與未定語意見[資源與任務排程紀錄](notes/2026-09-28-linux-resources-and-task-scheduling.md)。

後續工作負載前提：一台家用機承載 10,000 個 agent，共用十幾個雲端 LLM endpoint，一小時活躍不到 100 個，其餘保持不動。以事件／到期喚醒、idle 無常駐程序與按活躍工作付出調度成本為方向；這是工程目標，尚非現版已驗證規模。併發、資源與容量語意見同篇「家用機上的一萬個 agent」。

依此負載的具體改動與引入機制已整理成[萬 agent 改動計畫](notes/2026-09-28-ten-thousand-agents/README.md)，含三條詳細分線與分階段完成標準；只是規劃，尚未實作或變更系統設定。

2026-09-28 使用者要求開 proto6：上述本輪架構筆記、計畫、外牆調查與探針已完整收錄至 [proto6 notes](../proto6/notes/README.md)，作為後續入口。原始資料保留為歷史；proto6 目前仍只有規劃筆記與調查探針。
