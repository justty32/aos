## 1. 結論

**可以收：九份規範的正文完整、逐字比對通過，未發現壞掉的 spec 檔案或錨點連結；有幾處拆後的方位措辭與跨節導航可改善，但不構成必修。**

審查對象為 `4d6f35b`、`6626887`、`7f78961` 三個 commit，全程唯讀，未建置、改檔、commit 或連接模型端點。

審查時 `main` 已另有四個平行整理 commit。正文依要求與 `main:proto5/spec/<名>.md` 比對；判斷外部文件哪些變更出自拆檔時，另核對 `4d6f35b^..HEAD`，避免把平行整理的差異誤報成拆檔退步。

## 2. 逐字抽查表（20 段）

新檔路徑均省略 `proto5/spec/`；舊檔均為 `main:proto5/spec/<名>.md`。逐行比較保留段內空白，只正規化允許變動的標題層級及連結目標。

| # | 段落位置（新檔:行） | 舊檔:行 | 結論 |
|---|---|---|---|
| 1 | `kernel/cli.md:25–38`，init、JSON 範例及切點前尾段 | `kernel.md:317–330` | 完全一致 |
| 2 | `kernel/boot.md:5–24`，切點後 boot 五步 | `kernel.md:332–351` | 完全一致 |
| 3 | `kernel/boot.md:26–27`，下一切點前兩段 | `kernel.md:353–354` | 完全一致 |
| 4 | `kernel/cli-ops.md:5–12`，切點後 add／ack | `kernel.md:356–363` | 完全一致 |
| 5 | `kernel/README.md:18–22`，已拍板的前提 | `kernel.md:406–410` | 完全一致 |
| 6 | `aos-agent/cli-talk.md:3–22`，say | `aos-agent.md:88–107` | 僅標題層級差異 |
| 7 | `aos-agent/tick.md:17–37`，同時兩個 tick | `aos-agent.md:174–194` | 僅標題層級、連結目標差異 |
| 8 | `aos-agent/send.md:46–73`，act／think 的 inst 程式碼區塊 | `aos-agent.md:260–287` | 僅標題層級差異 |
| 9 | `agent/state.md:36–53`，waits 範例及規則 | `agent.md:188–205` | 僅標題層級、連結目標差異 |
| 10 | `agent/README.md:13–18`，已拍板的前提 | `agent.md:253–258` | 完全一致 |
| 11 | `daemon/home.md:23–37`，info.json | `daemon.md:63–77` | 僅標題層級差異 |
| 12 | `daemon/shutdown.md:3–25`，停機階梯 | `daemon.md:172–194` | 僅標題層級差異 |
| 13 | `cpu/messages.md:30–41`，error.code 表 | `cpu.md:123–134` | 僅標題層級差異 |
| 14 | `cpu/methods.md:5–54`，aos-exec params／回音 | `cpu.md:148–197` | 僅標題層級、連結目標差異 |
| 15 | `directives/fmt.md:11–40`，字串模板 | `directives.md:59–88` | 僅標題層級差異 |
| 16 | `directives/ref.md:3–20`，ref／at 語法 | `directives.md:90–107` | 僅標題層級差異 |
| 17 | `inst-posix/fields.md:3–24`，整體 JSON 形狀 | `inst-posix.md:57–78` | 僅標題層級差異 |
| 18 | `inst-posix/exec.md:3–30`，執行語意 | `inst-posix.md:231–258` | 僅標題層級差異 |
| 19 | `aos-llm/config.md:3–26`，模型表 | `aos-llm.md:48–71` | 僅標題層級差異 |
| 20 | `aos-exec/exit.md:3–27`，退出碼表及理由 | `aos-exec.md:52–76` | 僅標題層級、連結目標差異 |

20 段均未發現改字、少句、多句或段內順序錯誤。kernel 兩個切點亦沒有截斷程式碼區塊、表格或列表。

## 3. 完整性檢查方法與結果

使用記憶體內的 Python 比對，沒有產生檔案：

1. 用 `git show main:proto5/spec/<名>.md` 取得九份原文。
2. 讀取拆後全部 **86 個檔案**（九個 README、77 個子檔）。
3. 排除新增導航、「各節」表，以及 kernel 兩個獲准新增的續篇標題。
4. 按真正的 Markdown 標題切成區塊，避開 fenced code block；正規化標題的 `#` 數與 Markdown 連結目標。
5. 每個新區塊必須在對應原文中找到唯一、連續且逐行相同的區段；保留區塊內空白，只去掉區塊邊界空行。
6. 回頭檢查每一條原文非空行的覆蓋次數，必須恰好一次。另以行內容及出現次數比較補驗。

**結果：159 個區塊全部匹配；原文 2,083 條非空行全部恰好覆蓋一次。零遺失、零額外正文、零重複。**

README 前提／範圍的前移，以及 `cli-talk`、`cli-status` 等按主題重組的節次，均能還原到原文位置；區塊內沒有重排。

## 4. 導航試走紀錄與摘要檢查

以 `proto5/spec/README.md` 為起點計算點擊；若從 `proto5/README.md` 的規範表直接進入相同資料夾，次數相同。

| 查找目標 | 路線 | 點擊數 | 找到的內容／是否卡住 |
|---|---|---:|---|
| kernel `ls` 第一行 health | 總導航 → kernel README → `cli-ops.md` | 2 | `cli-ops.md:31–32`：`ok`、`dirs`、`stopped`、`daemon`、`cpus`、`stall`、`broken` 七種 code，附對應文字與判定順序。未卡住 |
| agent state.json 的 waits | 總導航 → agent README → `state.md` | 2 | `state.md:36–53`：外人設的等待門；沒寫或空陣列表示沒有門，並說明檔案到達、all、consume 等規則。未卡住 |
| aos-exec 退出碼 125 | 總導航 → aos-exec README → `exit.md` | 2 | `exit.md:11、19、25–27`：規範定義為 aos-exec 自身失敗，列出讀驗、指示詞、目錄及重導向等原因。未卡住 |

九個 README 的「各節」表均已與子檔標題、內容核對：

- 沒有漏列子檔，也沒有摘要指向錯誤主題。
- 拆散的節次有交代，例如 `aos-agent` §1.2／§1.5、§1.3／§1.4／§1.6，以及 `inst-posix` §3.3。
- 留在 README 本身的前提、範圍等節，標題仍可直接找到，不算漏節。
- 純文字節號能靠 README 查回。例如 agent §4.1 → `state.md`；aos-agent §9 → `pause-clean.md`；kernel §6 → 表中三個分檔。子檔回 README 再進目標，通常多兩次點擊。

主要導航弱點是「下面」「檔尾」等原文方位詞已不符合實體檔案位置，詳見建議清單。

## 5. 連結抽查與全面掃描

### 外部連結抽查（15 條）

以下縮寫：

- **P**＝`proto5/README.md`
- **L**＝`proto5/lib/README.md`
- **A**＝`proto5/notes/2026-09-22-act-report-astra.md`
- **D**＝`proto5/notes/2026-09-22-daemon-kernel-report-astra.md`

新目標均省略 `proto5/spec/`。這 15 條新目標均無錨點，且檔案全部存在。

歷史行號的核對有越過 `8172a68e` 那次純路徑修正，以 blame 追到報告原始 commit：A 為 `8b5ece09`，D 為 `c554ae32`，再讀取當時的 spec。

| # | 來源:行 | 舊引用 | 新目標 | 主題核對 |
|---|---|---|---|---|
| 1 | P:44 | `kernel.md §1.1、§6` | `kernel/home.md` | §1.1 正確；§6 需回 README 另找，見建議 |
| 2 | P:143 | `agent.md §3.3` | `agent/info.md` | 工具檔格式，正確 |
| 3 | L:361 | `kernel.md §6` | `kernel/cli.md` | CLI 參數總表，正確 |
| 4 | A:247 | `inst-posix.md:56` | `inst-posix/fields.md` | 當時 §2 整體形狀／未知欄位，正確 |
| 5 | A:262 | `inst-posix.md:89` | `inst-posix/fields.md` | 當時 §3.1 路徑中心，正確 |
| 6 | D:1168 | `exec.md:7` | `aos-exec/README.md` | 尚未逐條拍板的版本說明，正確 |
| 7 | D:1172 | `exec.md:22` | `aos-exec/usage.md` | 省略目標＝目前資料夾，正確 |
| 8 | D:1173 | `inst-posix.md:36` | `inst-posix/metainfo.md` | `_metainfo` 規則，正確 |
| 9 | D:1174 | `inst-posix.md:179` | `inst-posix/directives.md` | inst 的指示詞規則，正確 |
| 10 | D:1175 | `directives.md:128` | `directives/ref.md` | `$ref`／`$at` 相對位置，正確 |
| 11 | D:1176 | `directives.md:124` | `directives/ref.md` | `$at` 型別，正確 |
| 12 | D:1177 | `inst-posix.md:181` | `inst-posix/directives.md` | 原始 JSON 實體位置，正確 |
| 13 | D:1178 | `inst-posix.md:231` | `inst-posix/exec.md` | cwd／mkdir 執行次序，正確 |
| 14 | D:1179 | `exec.md:59` | `aos-exec/exit.md` | kind／退出碼表，正確 |
| 15 | D:1180 | `inst-posix.md:246` | `inst-posix/exec.md` | process group 逾時終止，正確 |

**錨點抽樣限制：**指定的外部 diff 範圍沒有帶 `#錨點` 的 spec 連結，無法從中抽出三條。實際三條都在 spec 內，另全部核驗如下，未將它們冒充外部樣本：

| 來源 | 新目標（省略 `proto5/spec/`） | 結果 |
|---|---|---|
| `aos-exec/README.md:15` | `inst-posix/exec.md#6-執行語意執行者要做到的` | 檔案、錨點存在；執行語意正確 |
| `aos-exec/exit.md:19` | `inst-posix/errors.md#5-錯誤代號讀驗階段` | 檔案、錨點存在；inst 讀驗錯誤正確 |
| `aos-exec/exit.md:19` | `directives/errors.md#6-錯誤代號` | 檔案、錨點存在；指示詞錯誤正確 |

### 全面掃描結果

合併 `git ls-files` 與 `rg --files --hidden` 的檔案清單，排除 `.claude/worktrees/`，共列舉 **2,468 個檔案**；對可讀文字掃描 Markdown inline link 及 reference definition，解析相對路徑、目錄 README、URL 編碼與標題錨點。

共找到 **743 條指向 `proto5/spec/` 的連結，其中三條帶錨點**：

- 不存在的目標檔案：**0**
- 不存在的錨點：**0**

此掃描確認存在性；主題正確性由上述人工抽樣另行確認。

## 6. 真問題清單

### 必修

**沒有。**未發現違反逐字搬移規則、正文遺失或指向 spec 的壞連結。

### 建議

1. **原文「檔尾」已不再是目前檔案的尾部。**  
   `proto5/spec/{agent,aos-agent,aos-llm,cpu,daemon,kernel}/README.md:7` 均仍說沿革在檔尾，實際已在 `history.md`。另如 `kernel/history.md:10` 的實作補記、`aos-llm/history.md:9` 的裁決，也已在別檔。這是逐字保留造成的導航落差，**不建議改原文**；可在允許調整的導航或摘要中補充位置。

2. **「下面／見下」的目的地有些已跨檔。**  
   具體例子：`proto5/spec/kernel/cli.md:7` 的 boot 說明在 `boot.md`；`aos-exec/exit.md:6` 的「給程式用」在 `api.md`；`aos-exec/usage.md:33` 的退出碼解釋在 `exit.md`；`cpu/terms.md:9` 的 `C/` 目錄圖在 `layout.md`。README 能找回，但直接讀子檔時會短暫找不到。原文維持逐字，僅建議補導航。

3. **同一連結文字涵蓋多節時，現在可能只抵達其中一節。**  
   `proto5/README.md:44` 的「kernel.md §1.1、§6」只連到 `kernel/home.md`，沒有涵蓋 §6。不是壞連結，但可把兩節各自連到對應位置。

4. **少數檔名需要靠摘要辨識。**  
   `proto5/spec/kernel/README.md:41–43` 的 `boot.md` 很直觀，`cli-ops.md`、`no-overlap.md` 則須讀摘要才知道涵蓋哪些操作或哪種重疊；目前摘要已足以補足，無須為命名阻擋收線。

大小方面，全部檔案都低於 8,000 bytes，最大為 `agent/state.md` 的 **7,248 bytes**。最小三份為 `agent/errors.md`（546）、`cpu/impl-notes.md`（751）、`kernel/no-overlap.md`（752）；它們各有獨立主題或原節號，**未發現小到必須合併的檔案**。