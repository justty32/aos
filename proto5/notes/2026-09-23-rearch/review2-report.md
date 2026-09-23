**1. 總評**

**這版仍不能直接當實作契約。**
params／base／退出碼已大致對齊；`current` 身分、ack、先記後派也確實修掉部分第一輪問題。
主要阻塞是：鏈的世代沒有固定在 request、EEXIST 可能撞自己、兩次查檔會誤重派，以及 syscall／once 的多檔提交仍不可恢復。
兩階段停機方向成立，但 queued once、部分送出 stop 後崩潰、`restart:true` 與正常退出的關係尚未閉合。
以下接受所有已拍板前提；全程唯讀，未修改檔案。

**2. A 驗收表**

「已解」指第一輪指出的問題已處理，不表示相關流程已完全沒有其他洞。

| 項目 | 判定 | 剩餘問題／本輪對照 |
|---|---|---|
| C-1 | 已解 | 先讀舊 state 對帳，再寫新主人狀態。 |
| C-2 | 已解 | 收件者不再自行刪回音；跨世代同名問題另見 C2-2。 |
| C-3 | 部分解 | 完成順序統一、四組存在狀態列全；漏了 notification 維度，見 C2-3。 |
| C-4 | 已解 | current 保存 name、id、notify，足以恢復協議身分。 |
| C-5 | 部分解 | 執行中監看 pipe／訊號已補；掃到檔案 stop 後仍可能多取一件，見 C2-4。 |
| C-6 | 已解 | EOF 改為所有寫端關閉，並要求父行程不得洩漏寫端。 |
| C-7 | 部分解 | 發布失敗保留 current、退 1；復原持續失敗與 restart 的契約未完，見 C2-5。 |
| C-8 | 解法本身引入新問題 | 承認時間戳不唯一，卻容許刪後重名；延遲 ack 會跨世代誤刪，見 C2-2。 |
| K-1 | 解法本身引入新問題 | chain 取代 next 守門，但先放後記會讓下一格撞自己的原單而斷鏈，見 K2-2。 |
| K-2 | 部分解 | boot 不再跑整格；current 快照競態、可變 tick.json 仍破壞交接，見 K2-1、K2-3。 |
| K-3 | 已解 | req→proc 已補，同名重加也受在途紀錄限制。 |
| K-4 | 部分解 | 先記後派、提交後 ack 有效；查檔競態與判定內的跨檔副作用仍未解，見 K2-5、K2-7。 |
| K-5 | 部分解 | 穩定 name 修正回覆不明時的重送；同名不同 target、停止中／重啟中仍待定，見 X2-3、D。 |
| K-6 | 已解 | CPU 復活已有鏈外 daemon；CPU 活著但鏈斷則明訂人工 boot。 |
| K-7 | 部分解 | pending 保存檔名與 id；接受及終局轉交仍有提交縫，見 K2-6、K2-7。 |
| K-8 | 已解 | 已交付工作的 discard 與同名阻擋成立；尚未交付便 rm 是另一個新洞，見 K2-8。 |
| K-9 | 部分解 | stopping 不再派工，但 queued once 會永久擋住 stopped，見 K2-9、K2-13。 |
| K-10 | 已解 | syscall 已移到 daemon 操作之前，過度承諾的 interval 上限也撤掉。 |
| K-11 | 部分解 | once 分流、error 套用 bad_after 已補；runs／stopped 與 aos 連續性仍矛盾，見 K2-11。 |
| K-12 | 已解 | once 不等時自行取名／印識別、stop 只確認投件、等待旗標均已補。 |
| K-13 | 部分解 | 靜態合法性已補；boot 驗證時機、池消失及 kernel CPU 換名仍缺契約，見 K2-3、K2-12。 |
| X-1 | 已解 | timeout 明訂非負整數、0 不限、bool 不算。 |
| X-2 | 已解 | params 不再包 inst，原先 `$ref` 吃掉 timeout 的結構消失。 |
| X-3 | 已解 | C 負責定位 target，inst base／cwd 交回 aos-exec。 |
| X-4 | 已解 | CPU 不再把 params 當 inst 文件根。 |
| X-5 | 已解 | child 126／127 恢復；API aos code 1 與 CLI 125 已分清。 |
| X-6 | 部分解 | 標準串流已隔離；高位控制 fd 的繼承限制仍未寫，見 X2-5。 |
| X-7 | 部分解 | 合法 notification 已補；壞 JSON／壞信封仍與 notification 混寫，見 C2-6。 |
| X-8 | 已解 | 禁止 info 頂層整份 `$ref`，daemon 綁定不再被吞掉。 |
| R-1 | 已解 | 開頭已突出「跑一次，反覆交 kernel」。 |
| R-2 | 已解 | 資料夾與 pipe 兩條路已分清。 |
| R-3 | 部分解 | 名詞改善，但 request 仍被概括成指向 inst，見 R2-1。 |
| R-4 | 已解 | 主人、外人接口與啟動前初始化的邊界已補。 |
| R-5 | 已解 | procs 統一為 target＋政策。 |
| R-6 | 已解 | 狀態範例統一保存含 `.json` 的檔名。 |
| R-7 | 部分解 | 表與標籤有幫助，但最重要的提交步驟仍藏在「副作用／判定」，見 R2-3。 |
| R-8 | 部分解 | 實際週期已說清；kernel 仍把檔名字典序稱 FIFO，見 R2-6。 |
| R-9 | 沒解 | kernel CPU 的 req 仍混入一般收件及停機條件，見 K2-10。 |
| R-10 | 部分解 | §9／§10 已分開，但已拍板的 target 欄位仍列待確認，見 R2-4。 |

**3. B 發現**

先列核對通過的跨文件項目，避免誤報：

- `target:"jobs/x.json"` 先相對 C 定位，再由 aos-exec 以 `C/jobs` 作為 inst base；兩者相容。
- params 的 `stderr:"err.log"` 相對呼叫者 cwd＝C，符合 aos-exec。
- `args` 僅普通檔可用的限制相容；問題在 kernel 的 `null` 轉換。
- `kind=aos, code=1` 是 API 結果，CLI 才換成 125，沒有打架。依據：[cpu §4.1](/home/guanyu/projs/aos/proto5/spec/cpu.md:138)、[aos-exec 三種目標與旗標](/home/guanyu/projs/aos/proto5/spec/aos-exec.md:25)、[退出碼](/home/guanyu/projs/aos/proto5/spec/aos-exec.md:53)。

**C2-1｜ack 本身的消耗與恢復順序沒有寫完**

**在哪：**[cpu §3.3](/home/guanyu/projs/aos/proto5/spec/cpu.md:116)、[§6.3](/home/guanyu/projs/aos/proto5/spec/cpu.md:254)。  
**時序：**

- 收件者讀回音後、ack 前崩潰：回音還在，可以重讀；若已持久記錄，重啟後只須補 ack。這條成立。
- ack 已放、主人尚未處理便死：ack 留在 requests，重啟可以接著處理。這條成立。
- ack 指向不存在的回音：規範明訂 no-op，成立。
- 但「處理 ack」只寫刪 response，沒寫何時刪 ack 原單。若先刪 ack 再崩，response 永留；若不刪 ack，則永久重掃。

**後果：**協議缺少最後一段可重入清理；前三個情境的保證取決於實作者自行補對順序。  
**建議：**明訂「刪 response，ENOENT 視為成功 → 刪 ack 原單」，並寫出兩步間崩潰的重入行為。  
**嚴重度：要修。**

**C2-2｜同名重用使舊回音與延遲 ack 污染下一件工作**

**在哪：**[cpu 身分與放單](/home/guanyu/projs/aos/proto5/spec/cpu.md:94)、[ack](/home/guanyu/projs/aos/proto5/spec/cpu.md:116)。  
**時序：**A 的 X 已回音、原單已刪 → B 再放同名 X → CPU 執行 B，覆寫 A 尚未 ack 的 response；另一條是 A 的重複／延遲 ack 在 B 回音生成後才被處理，刪掉 B 的結果。kernel「ack 已放但 ledger 尚未清便崩」正會產生重複 ack。  
**後果：**結果覆寫、錯世代刪除，連 §6.2 都不能再假定同名 request／response 屬於同一次工作。`epoch ns＋pid` 也不是唯一性證明：同一行程仍可能取得重複時間值。  
**建議：**禁止不同工作重用運輸身分，或讓 request／response／ack 帶可驗證的世代；僅「等一份 ack 處理完」不足以防延遲副本。  
**嚴重度：擋。**

若舊 ack 已全部消耗、同名新 request 明確代表新工作，CPU 會正常再跑一次；若它其實是舊工作的重送，目前沒有歷史紀錄可去重。這兩種語意也應明分。

**C2-3｜五列表列全二檔組合，但「不可能」那列其實可達**

**在哪：**[cpu §6.2](/home/guanyu/projs/aos/proto5/spec/cpu.md:238)。  
**時序：**合法 notification 寫 current → 執行 → 跳過回音 → 刪原單 → 清 current 前崩潰；此時 current=X、request／response 都不存在。開機對帳 notification 時，刪原單後再次崩潰也會得到同樣狀態。  
**後果：**第五列的處置「清 current」可以正確，但成因「不可能」錯誤；「每組唯一對應一段」也不成立，例如在／不在還可能是寫 current 後尚未開始執行。  
**建議：**保留存在狀態表，但補 notify 維度、改稱「可能停在哪裡」，列出不重用身分、單主人及 ack 處理位置等前提。  
**嚴重度：要修。**

在這些前提下，有 id 的工作由「在／不在」補回音，再經「在／在」刪單，最後「不在／在」清 current，復原再次崩潰可以重入。

**C2-4｜stop 設旗標後仍能多跑一件，強停的結果截點也未定**

**在哪：**[cpu §5.1–5.3](/home/guanyu/projs/aos/proto5/spec/cpu.md:185)、[§6.3](/home/guanyu/projs/aos/proto5/spec/cpu.md:254)。  
**時序：**迴圈頂端旗標未設 → 掃 stop 檔並設旗標 → 沒有再次檢查 → 直接取普通單 Y 執行。另一路：子程式已自然結束、CPU 尚未發布結果，第二次訊號到達，§5.2 又要求寫 `stopped:true`。  
**後果：**第一條違反「旗標一設不再取新的」，也可能消耗 kernel 刻意留下的殘格；第二條使已完成工作是否算 stopped 由實作者猜。  
**建議：**所有控制來源處理後、取新單前必須重查旗標；定義強停與完成競爭時，以哪個事件決定 stopped。  
**嚴重度：要修。**

KILL 也不是一律補 Interrupted：若已發回音，§6.2 應保留原結果；只有尚未發回音才補 Interrupted。§5.3 的概括句應跟表一致。

**C2-5｜回音寫不出去後，restart 可能永久循環**

**在哪：**[cpu §6.3–§7](/home/guanyu/projs/aos/proto5/spec/cpu.md:266)、[kernel daemon 契約](/home/guanyu/projs/aos/proto5/spec/kernel.md:183)。  
**時序：**工作完成 → response 遇持續 ENOSPC／EACCES → 留 current、退 1 → daemon 重拉 → 開機補 Interrupted 仍寫失敗 → 再退 1 → 重複。強停後的回音發布失敗也走同一路。  
**後果：**工作不必重跑，但 CPU 可無限重啟、刷 log；收件者一直沒有終局回音。短暫故障恢復後補 Interrupted 的路徑則成立。  
**建議：**CPU 明訂對帳寫失敗仍保留原資料並退 1；daemon 必須回答節流、永久失敗的狀態及重啟條件。  
**嚴重度：要修。**

**C2-6｜壞 JSON／壞信封仍可能被當成 notification 靜默刪除**

**在哪：**[cpu §3 信封與錯誤表](/home/guanyu/projs/aos/proto5/spec/cpu.md:89)、[§4.3](/home/guanyu/projs/aos/proto5/spec/cpu.md:174)。  
**時序：**收到不可解析 JSON，或 JSON 陣列／缺 method 的物件 → 無法取得 id → 按 §4.3「沒 id 的壞了只刪不回」處理。  
**後果：**與 §3.2 的 ParseError／InvalidRequest 回音規則衝突；交件者等不到預期錯誤。  
**建議：**分開不可解析、可解析但非合法信封、合法 notification 三類；只有最後一類的 method／params 錯誤適用不回音。  
**嚴重度：要修。**

**K2-1｜舊殘單沒有固定舊 chain，boot 改檔會把它變成新鏈**

**在哪：**[kernel §3 第 2 步](/home/guanyu/projs/aos/proto5/spec/kernel.md:126)、[第 9 步](/home/guanyu/projs/aos/proto5/spec/kernel.md:149)、[boot](/home/guanyu/projs/aos/proto5/spec/kernel.md:203)。  
**時序：**stop 留下舊鏈 k-42，內容只有 `target=K/tick.json` → boot 覆寫同一 tick.json，argv 改為新 chain B → CPU 執行舊 k-42 時才讀 inst → 實際執行的是 chain B，通過守門。  
**後果：**「舊殘格帶舊 chain 自滅」不成立；殘格與新 k-1 都能接後繼，形成多條排隊鏈。CPU 仍串行，但單鏈假設已失效。  
**建議：**每份已排入的 tick 必須固定其 chain；用符合 target 契約的不可變目標等方式承載，不能依賴共用可變 inst。  
**嚴重度：擋。**

**K2-2｜EEXIST 可以撞自己，不能證明後繼已放好**

**在哪：**[kernel §3 第 2 步](/home/guanyu/projs/aos/proto5/spec/kernel.md:126)、[CPU 刪單順序](/home/guanyu/projs/aos/proto5/spec/cpu.md:258)。  
**時序：**k-1 放 k-2 → 寫 next=3 前崩潰 → k-2 執行，磁碟 next 仍為 2 → link k-2 撞到自己仍存在的原單 → EEXIST 被當成後繼存在 → next 改 3 → k-2 結束、原單被刪，沒有 k-3。  
**後果：**崩在「放檔之後」仍會斷鏈。若同名檔是舊鏈殘單，EEXIST 同樣不能證明它是本鏈後繼。  
**建議：**區分目前格與後繼的持久身分；EEXIST 必須驗證世代、內容及角色。  
**嚴重度：擋。**

**K2-3｜boot 偷看 current 不是交接保證，而且寫死 CPU 名 k**

**在哪：**[kernel boot 第 1–3 步](/home/guanyu/projs/aos/proto5/spec/kernel.md:203)、[不重疊宣稱](/home/guanyu/projs/aos/proto5/spec/kernel.md:220)。  
**時序：**boot 讀 current=null → 舊 CPU 認領下一格，tick 讀入 chain A／state 並通過守門 → boot 寫 chain B → 舊 tick 繼續派工，最後寫回自己的舊 state。兩個 boot 同時讀到 null 也有同類問題。  
**後果：**boot 與 tick 同時修改 K，會覆蓋鏈與排程狀態。反方向也會誤拒：CPU 已死但 current 殘留，不等於舊 tick 還在跑。另 info 允許 kernel CPU 叫 scheduler，boot 卻讀 `cpus/k/state.json`。  
**建議：**定義 boot 與舊主人的完整交接條件及失敗復原；由唯一 kernel 池找到實際 CPU，不用快照推定存活或互斥。  
**嚴重度：擋。**

**K2-4｜boot 重設 next，但運輸名稱沒有 chain**

**在哪：**[kernel req 命名](/home/guanyu/projs/aos/proto5/spec/kernel.md:145)、[boot 保留狀態並重設 next](/home/guanyu/projs/aos/proto5/spec/kernel.md:206)。  
**時序：**舊 k-3-0 回音已提交、req 已清、ack 已送，但 worker 還沒處理 → boot 把 next 重設 2 → 新鏈派出同名 k-3-0 → kernel 先讀到舊 response，當成新工作的結果。  
**後果：**錯計數、錯轉交 once、提前清 req；舊 ack 也可能刪新回音。這是 kernel 正常命名規則自行製造 C2-2，不能歸咎外人亂重名。  
**建議：**tick 與工作 request 的運輸身分納入不可重用的鏈世代；boot 重設序號不得重用歷史名字。  
**嚴重度：擋。**

**K2-5｜第 6 步把兩次查檔當同一時刻，正常完成也會重派**

**在哪：**[kernel §3 第 6 步](/home/guanyu/projs/aos/proto5/spec/kernel.md:136)、[cpu 發布與對帳](/home/guanyu/projs/aos/proto5/spec/cpu.md:242)。  
**時序：**kernel 查 response 不在 → CPU 寫 response、刪 request → kernel 查 request 不在 → 推論「從沒放出去」，重新 link。CPU 開機補 Interrupted、刪原單若落在兩次查詢之間，也一樣。  
**後果：**已完成或已判 Interrupted 的工作被再次執行；這不需要任何行程在此時崩潰。  
**建議：**定義符合 CPU 發布順序的觀察／複查規則，證明看到的狀態足以補放；兩次 exists 不能當原子快照。  
**嚴重度：擋。**

**K2-6｜add／rm 的副作用先做，重掃卻沒有完成未提交狀態**

**在哪：**[kernel syscall 與重掃規則](/home/guanyu/projs/aos/proto5/spec/kernel.md:104)。  
**時序：**

- add 寫 procs/X → queue／pending 尚未寫 state 就崩 → 重掃命中相同 request，照文字只補回音、刪原單。
- rm 刪 procs/X → queue 移除、discard／pending 清理及 Removed 尚未完成就崩 → 重掃只回 NotFound。

**後果：**add 可回成功卻沒有排程；once 沒 pending 而失單。rm 可留下孤立 queue、未標 discard 的在途工作，或永遠沒有 Removed。省略 name 的直接 add 若重掃重新分配數字名，也可能再建一個行程。  
**建議：**保存可恢復的接受／刪除進度及已決定的 NAME；重掃必須完成 state 與終局回音，不能只看 procs 檔存在與否。  
**嚴重度：擋。**

**K2-7｜once 轉交及 done／bad 搬檔不是「重判一次就冪等」**

**在哪：**[kernel 第 6 步](/home/guanyu/projs/aos/proto5/spec/kernel.md:136)、[§4 判定](/home/guanyu/projs/aos/proto5/spec/kernel.md:158)。  
**時序：**收到 once 結果 → 寫 K 的終局回音 → 刪 procs/X → 清 pending／req 的 state 尚未提交就崩 → 下格仍有 req／pending，但判定用政策檔已消失。搬 done／bad 後、提交 state 前崩潰也同樣。  
**後果：**下格缺資料而卡住；若客戶已讀 K 回音並放 ack，下格第 5 步可先刪回音，第 6 步又從舊 state 重建已消費的結果。  
**建議：**持久保存終局決定與待轉交／待清理進度，再依該紀錄重入；CPU response 有 ack，不代表 K 的其他副作用自動冪等。  
**嚴重度：擋。**

**K2-8｜rm 遇上「已記 req、尚未送出」，會刪掉補派依據**

**在哪：**[kernel rm](/home/guanyu/projs/aos/proto5/spec/kernel.md:105)、[第 5–8 步](/home/guanyu/projs/aos/proto5/spec/kernel.md:135)。  
**時序：**上一格先存 req／proc，link 前崩 → 下格先處理 rm，刪 procs/X、標 discard → 第 6 步見兩檔皆無，要求補放 → target／args／timeout 的來源已被刪。  
**後果：**無法補放，也無回音可解除 discard，同名 add 持續被擋；若硬補放，則 rm 後才開始原本未交付的工作。  
**建議：**定義已保留但未交付工作的取消終局及恢復依據，不能把 req 非 null 一概稱為「正在跑」。  
**嚴重度：擋。**

已真正交付的那條路則成立：rm 標 discard → CPU 死亡、daemon 重拉 → 補 Interrupted → kernel 先看 discard 丟棄並清在途，同名才可重加。仍受 K2-5 的查檔競態影響。

**K2-9｜queued once 令 stopping 永遠到不了 stopped**

**在哪：**[kernel pending 接受](/home/guanyu/projs/aos/proto5/spec/kernel.md:113)、[第 8–9 步](/home/guanyu/projs/aos/proto5/spec/kernel.md:145)。  
**時序：**once 已接受，pending 存好但還在 queue → stop 改 stopping → 第 8 步不再派 → 第 9 步要求 pending 全空。  
**後果：**即使沒有任何在途工作，kernel 與 once 呼叫者也永久等待。  
**建議：**明訂已接受、未派 once 的停機終局：完成它或交付明確取消結果，使 pending 能收斂；不必改變兩階段停機前提。  
**嚴重度：擋。**

另有 ack 尾端未交代：once 回音一轉交便清 pending，kernel 可以 stopped；客戶稍後才向 K 放 ack，此時沒有 tick 消耗它。應說明會留到下次 boot，或由哪個既定收尾階段處理，不能宣稱完整清理已完成。

**K2-10｜kernel CPU 還在一般工作收件表裡**

**在哪：**[kernel state 範例](/home/guanyu/projs/aos/proto5/spec/kernel.md:65)、[第 4–6 步](/home/guanyu/projs/aos/proto5/spec/kernel.md:133)、[停機條件](/home/guanyu/projs/aos/proto5/spec/kernel.md:149)。  
**時序：**k.req=k-41、proc=null → 第 4 步 ack tick 回音 → 第 6 步仍遍歷每顆 req 非 null 的 CPU。  
**後果：**回音還在就拿 proc=null 套工作政策；回音已刪則可能補送 tick；第 9 步還可能因 k.req 未清而停不了。文件也沒定誰維護這個 req。  
**建議：**明列 tick 回音的獨立流程，以及第 6、8、9 步各自遍歷哪些 CPU；範例同步。  
**嚴重度：擋。**

**K2-11｜計數表仍沒有唯一結果**

**在哪：**[kernel §4](/home/guanyu/projs/aos/proto5/spec/kernel.md:163)。  
**時序：**收到 stopped → 先 runs+1 → 表又說計數不動；另收到 aos → Interrupted/error → aos，error 分支沒有清 aos，第三次便達 2。  
**後果：**停止是否算 runs 有兩種實作；非連續 aos 被算成連續兩次退件。  
**建議：**逐列列出完整 runs／fails／aos 更新，並定義 stopped 是否中斷各種「連續」計數。  
**嚴重度：要修。**

**K2-12｜池的合法性寫了，但驗證時機與配置變更未定**

**在哪：**[kernel info.cpus](/home/guanyu/projs/aos/proto5/spec/kernel.md:50)、[add](/home/guanyu/projs/aos/proto5/spec/kernel.md:104)、[tick](/home/guanyu/projs/aos/proto5/spec/kernel.md:125)、[boot](/home/guanyu/projs/aos/proto5/spec/kernel.md:203)。  
**時序：**add once pool=llm 驗證成功 → info 把最後一顆 llm CPU 改池／移除 → 下格再也找不到可派 CPU。另一條是非法 kernel 池配置進 boot，文件未明訂在寫 chain、建家、spawn 前完整驗證。  
**後果：**已接受 once 無人執行並卡停機；boot 可能產生副作用後才由首格發現無效配置。移除帶在途 req 的 CPU，也沒有明確的接手規則。  
**建議：**明訂 boot 的完整驗證點、info 可修改的生命週期，以及配置變更對 queue／在途／pending 的處置。  
**嚴重度：要修。**

**K2-13｜送出 stop、提交 stopped、daemon restart 三者尚未接合**

**在哪：**[kernel 第 9 步](/home/guanyu/projs/aos/proto5/spec/kernel.md:149)、[restart 契約](/home/guanyu/projs/aos/proto5/spec/kernel.md:185)、[CPU 正常停退 0](/home/guanyu/projs/aos/proto5/spec/cpu.md:194)。  
**時序：**

- 已向 kernel CPU 放 stop → 向其他 CPU 放單失敗或寫 stopped 前崩 → kernel CPU 收尾後退出，磁碟仍 stopping。
- 正常全部完成 → CPU 收 stop、退 0 → 若 restart:true 包含正常退出，daemon 又全部拉回。

**後果：**若不重拉，部分停機可能沒有接手者；若一律重拉，stopped 後 CPU 又活著。現文不能自行選任一 daemon 語意。  
**建議：**daemon 先回答主動停止與 restart 的優先關係；kernel 據此補第 9 步逐顆送出與最終提交的恢復規則。  
**嚴重度：擋。**

**X2-1｜kernel 的 `args:null` 不能直接照抄成 CPU params**

**在哪：**[kernel 行程紀錄](/home/guanyu/projs/aos/proto5/spec/kernel.md:91)、[派工](/home/guanyu/projs/aos/proto5/spec/kernel.md:145)、[cpu args 型別](/home/guanyu/projs/aos/proto5/spec/cpu.md:144)。  
**時序：**add 省略 args → 按範例存 `args:null` → 派工「params 照行程紀錄」保留 null → CPU 按字串陣列驗證失敗。  
**後果：**正常無參數工作可能被拒；實作者若自行省略 null，又是在補未定契約。`[]` 不能一併省略，它代表有給 `--`，inst 目標應拒絕。  
**建議：**明列 procs→params 轉換，區分未給、null、空陣列。  
**嚴重度：要修。**

**X2-2｜接受不存在的 `.json`，不等於會等它出現**

**在哪：**[cpu 缺檔分類](/home/guanyu/projs/aos/proto5/spec/cpu.md:147)、[kernel aos 退件](/home/guanyu/projs/aos/proto5/spec/kernel.md:169)、[aos-exec 缺檔用途說明](/home/guanyu/projs/aos/proto5/spec/aos-exec.md:38)。  
**時序：**agent 先 add job.json → 檔案尚未產生，第一次回 aos／1 → 第二次仍未產生，搬 bad → agent 才寫好檔。once 則第一次缺檔就終結。  
**後果：**檔出現後不會自然恢復，同名 add 又受 bad 同名限制；與 aos-exec 所述「先收未出現 inst，檔出現自然跑」的用途不一致。  
**建議：**明分「接受缺檔目標」與「等待就緒」，對齊跨層說明／政策。若要區分暫時缺檔，現有 result 只有 kind／code，也不足以區分 ReadFailed 與其他 aos 失敗。  
**嚴重度：要修。**

**X2-3｜兩個 kernel 共用 daemon，裸 CPU 名會互撞**

**在哪：**[kernel spawn 契約](/home/guanyu/projs/aos/proto5/spec/kernel.md:183)、[預設 daemon](/home/guanyu/projs/aos/proto5/spec/kernel.md:216)。  
**時序：**K1 向 D spawn `name:k,target:K1/...` → K2 向同一 D spawn `name:k,target:K2/...` → 依「同名已活著回 pid」，取得 K1 的孩子 → K2 把首格放進沒有主人的 K2 CPU 家。  
**後果：**K2 boot 表面成功，實際永不執行；0／1 等 CPU 也一樣。規範沒有「一個 daemon 只服務一個 kernel」限制。  
**建議：**定義 name 作用域及同名不同 target 的判斷，不能只用名字存在作為等價證明。  
**嚴重度：要修。**

**X2-4｜真實 timed_out 尚未接上公開 API**

**在哪：**[cpu result](/home/guanyu/projs/aos/proto5/spec/cpu.md:159)、[aos-exec API](/home/guanyu/projs/aos/proto5/spec/aos-exec.md:93)。  
**時序：**工作自行退 143，或 timeout 發 TERM 後退 143 → 公開 API 都只回 `(143,"child")` → CPU 要輸出不同 timed_out。  
**後果：**光靠目前列出的回傳值無法遵守「真實旗標，不從碼猜」；on_spawn 只承諾行程身分，沒有 timeout 原因。  
**建議：**明列取得真實終止原因的接口／監控責任，並與 aos-exec API 同步。  
**嚴重度：要修。**

**X2-5｜搬高位 fd 解決標準串流衝突，沒有完成繼承契約**

**在哪：**[cpu §6.1](/home/guanyu/projs/aos/proto5/spec/cpu.md:230)。  
**時序：**CPU 搬控制 fd → 工作啟動時若仍繼承那些 fd → 工作可持有控制讀端或回程寫端 → CPU／daemon 結束時，控制資料與 EOF 的觀察受額外副本影響。  
**後果：**「不會吃控制訊息」仍缺少明文保證；僅換 fd 號不是完整隔離。daemon→CPU 的寫端不能漏給其他孩子，則是 daemon 另外必須做到的事。  
**建議：**明訂高位 fd 的不可繼承／關閉要求，並分清 daemon 與 CPU 各自負責哪些端點。  
**嚴重度：要修。**

kernel §3 十步的崩潰說明，逐步結論如下：

| 步驟 | 驗收 |
|---|---|
| 1 讀與守門 | 不完整：共享 tick.json、boot 並寫使守門不足，見 K2-1、K2-3。 |
| 2 接鏈 | 不成立：放後未記會撞自己；舊鏈 EEXIST 也不能算成功，見 K2-2。放之前崩需人工 boot 的說明本身一致。 |
| 3 睡眠 | 局部成立：前提是第 2 步真的放了後繼；睡＋處理時間的週期說明正確。 |
| 4 補 ack | 局部成立：放後未清 ledger 可重送，但需不重用名稱及明定 ack 消耗順序，見 C2-1、C2-2。 |
| 5 syscall | 不成立：add／rm 的 procs、state、回音仍可分裂，見 K2-6。移到 daemon 前確有改善。 |
| 6 收件／補放 | 不成立：兩次查檔競態、判定內的刪搬／轉交未可重入，見 K2-5、K2-7。 |
| 7 daemon | 條件成立：已交付工作可由重啟補 Interrupted；名稱、restart／stop 等條件尚待 daemon 定義。 |
| 8 派工 | 局部成立：先記後放修正未記帳派工；補放、rm 及跨 boot 名稱仍有洞。 |
| 9 停機 | 不成立：queued once、部分送 stop、restart 與殘格交互未閉合。 |
| 10 寫 state／log | 局部成立：log 失敗不等於 state 回滾；但仍受 boot 舊快照覆寫影響，不能概稱全部可接續。 |

**4. C 發現**

**R2-1｜入口還殘留「request 就是 inst」的說法。**  
[cpu 名詞表](/home/guanyu/projs/aos/proto5/spec/cpu.md:19)說 request 指向 inst；[kernel CLI](/home/guanyu/projs/aos/proto5/spec/kernel.md:213)又把 base 概括為 TARGET 所在資料夾。應統一稱 aos-exec target，並直接連到三種目標表；資料夾目標的 base 是資料夾本身。

**R2-2｜五列表可讀，但把推論寫成唯一歷史。**  
[cpu §6.2](/home/guanyu/projs/aos/proto5/spec/cpu.md:242)的「上一任死在」宜改為「可能停在哪裡」。表應突出觀測條件與必做動作，另列 notify、名稱不重用等前提，避免「不可能」「各對應一段」掩蓋 C2-3。

**R2-3｜十步標籤有幫助，最重要的寫入卻仍藏在動詞裡。**  
[kernel §2](/home/guanyu/projs/aos/proto5/spec/kernel.md:113)的「做副作用」及[§3 第 6 步](/home/guanyu/projs/aos/proto5/spec/kernel.md:136)的「判定」包含寫回音、刪 procs、搬 done／bad。應在各自章節展開提交點與重入子步驟，再由十步引用；「每步都寫了下格怎麼接」目前不實。

**R2-4｜慣例、規定、已拍板仍有三種聲音。**  
[cpu §3.3](/home/guanyu/projs/aos/proto5/spec/cpu.md:124)稱 ack 前綴只是慣例、認 method；[§10](/home/guanyu/projs/aos/proto5/spec/cpu.md:293)又稱前綴是規定。後者還把已拍板的 target 欄位列待確認。依本次前提，正文應統一為前綴規定，並移除重複待確認項。

**R2-5｜kernel 繼承哪些 cpu 方法，沒有明確入口。**  
[kernel syscall 表](/home/guanyu/projs/aos/proto5/spec/kernel.md:100)沒有 ack；tick 只明寫向 CPU 發 ack，沒有明列處理 `K/requests/ack-*` 的位置。應直接說明繼承 cpu §3.3，並在步驟 5 指出；kernel CPU 自己的回音則獨立導引，接上 K2-10。

**R2-6｜FIFO 與斷鏈診斷的用語仍會誤導。**  
[kernel §7](/home/guanyu/projs/aos/proto5/spec/kernel.md:224)稱 FIFO，但 CPU 實際按檔名字典序；只有單一後繼時看起來等價。[第 2 步](/home/guanyu/projs/aos/proto5/spec/kernel.md:129)說斷鏈「ls 看得出」，但 CLI ls 本身要活 tick 處理，鏈斷時只會逾時；回傳格式也沒有即時 current／目錄空狀態。應明指讀哪份狀態或哪個目錄。

**5. D 問題清單**

以下只列 daemon 必答問題及既有約束。

| 問題 | 已有約束 |
|---|---|
| **1. daemon 家的主人是誰？重複啟動如何判定已有主人，重啟又如何接手？** | 採 CPU 家範式；外人投件／讀回音／ack，主人管理 state 與清理。 |
| **2. 孩子表哪些內容持久保存，哪些只在記憶體？** | spawn 可能成功後回覆逾時；daemon 崩潰可能落在啟動、記帳、發回音之間。 |
| **3. 同名 spawn 的等價條件是什麼？target／restart 不同仍可回原 pid 嗎？** | kernel 依賴同名重送不會产生第二個主人；逾時不代表未做。[kernel §5](/home/guanyu/projs/aos/proto5/spec/kernel.md:178) |
| **4. name 的作用域是整個 daemon，還是某個 kernel 家？** | kernel 目前直接使用 k／0／1，且多個 CLI 可指向同一預設 D。 |
| **5. 同名孩子正在停止、已死未回收、等待 restart 時，spawn／ls／kill 各回什麼？** | 目前只定「同名已活著回 pid」；kernel 不自行拉已死孩子。 |
| **6. restart:true 包含哪些退出：0、1、2、訊號、stop、EOF？主動停止與 restart 誰優先？** | 所有 CPU 都設 restart；kernel stop 又必須讓 CPU 停下來。 |
| **7. restart 如何節流？持續無法啟動或寫回音時，如何呈現及何時再嘗試？** | CPU 可因永久 I/O 錯誤在啟動對帳時反覆退 1。[cpu §6.3–§7](/home/guanyu/projs/aos/proto5/spec/cpu.md:266) |
| **8. restart 用保存的啟動資料，還是重新讀 target？target 被修改／刪除時怎麼辦？** | kernel 的 target 是 CPU inst；其初始化只允許在主人啟動前進行。 |
| **9. 如何確認孩子是原來那個行程，並判定真正退出？** | pid／alive、kill、restart 必須使用一致身分；CPU state 的 pid 本身不證明存活。 |
| **10. 每條控制 pipe 的各端點由誰持有、何時關閉，如何保證某孩子的寫端不漏給其他孩子？** | CPU 把所有寫端關閉視為 stop；漏端會破壞 EOF。[cpu §5.1](/home/guanyu/projs/aos/proto5/spec/cpu.md:185) |
| **11. daemon 與 CPU 對高位 fd 的不可繼承／關閉責任各是什麼？** | CPU 已搬離 0／1；工作不得取得控制通道，回程也不能被無關後代持有。 |
| **12. pipe 半行、壞 JSON、非 stop 訊息、寫入失敗、回程無人讀時如何處理？** | 一行一則；控制 pipe 只載 stop／EOF，工作走資料夾。 |
| **13. stop 階梯的各段等待、總預算及多孩子處理順序是什麼？** | 先 pipe stop，再等，再訊號；CPU 已有旗標時的訊號可觸發強停，強停另有 2 秒寬限。 |
| **14. kill 是發訊號、終止孩子，還是同時撤銷 restart？停止途中是否還接受 spawn？** | kill／stop／restart 共用孩子表，不能各自定義互相矛盾的終局。 |
| **15. daemon 被 KILL 後，孩子與仍執行的工作如何處理？新 daemon 何時可以接手？** | EOF 只能使 CPU 溫和停；無 timeout 工作可能無限等，CPU 被 KILL 後的工作也可能仍活著。 |
| **16. kernel 改綁另一個 daemon 時，舊孩子的擁有權如何交接？** | boot 會改 info.daemon；舊 daemon 可能仍管理相同 CPU 家，不能形成雙主人。 |
| **17. kernel stop 與 daemon stop 的順序由誰保證？daemon 先停時，誰收完 once？** | kernel stop 不停 daemon；已拍板要求在途與 once 收完才停 CPU。[kernel §2、§3](/home/guanyu/projs/aos/proto5/spec/kernel.md:107) |
| **18. daemon 自己的 request／response／ack 如何跨崩潰恢復？停止後才到的 ack 由誰消耗？** | kernel 與 daemon 也走資料夾，等待上限 5000 ms；遲到回音、重送及收件者崩潰都是正常可能路徑。 |