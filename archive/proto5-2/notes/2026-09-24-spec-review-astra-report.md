草稿有把「池表、宣告式管理、回音通知」寫進主流程，但目前還不能直接交給實作者照做。主要缺口在池宣告的確認與重送、縮池途中又改數字，以及停機／開機的交接；照文字實作，可能出現工作被提前收掉、池永遠不收斂或停機後自行復活。每格 O(有事) 也尚未成立，除了已承認的整份帳本寫入，還漏算多個讀取、佇列與摘要維護成本。以下是唯讀審查，沒有修改檔案；涉及執行結果的判斷是按規範推演，沒有把尚未實作的流程當成已測通。

**R1【中｜六點】六點不是全部落實，其中有額外限縮與尚未達到的承諾**

位置：`proto5-2/spec/choices.md` §1～2，以及下表所列各節。

| 原點 | 判斷 | 缺口或建議 |
|---|---|---|
| (a) 池表、envs 決定能力 | 大致落實 | `kernel-info.md` §2 有需要的欄位；但 `kernel-home.md` §2 又允許實作失敗時改成「envs 只影響新建的家」，會改變環境更新契約，見 R14。 |
| (b) daemon 自行補足、重拉、收掉 | 方向落實，收斂未完成 | kernel 不記 pid，daemon 有退避；但 boot 強制對帳與 pending 恢復不完整，見 R3、R4。 |
| (c) 多池、四種狀態、小檔、批次階梯 | 大致落實 | 小檔與階梯有寫；`restarting` 被定義成「已重拉且尚未穩定」，不是所有等待重拉的孩子，四種狀態不能直接當互斥分類，見 R23。 |
| (d) 動態 add／rm／ls、下一格生效 | 部分落實 | `kernel-cli.md` 把 `NAME` 定成 `P/<i>`，並賦予永久退休語意；既有池禁止 `--env`。這兩項是草稿新增的選擇，不是原文已定。 |
| (e) init 只有参数與池，可空 | 工作 cpu 可空已落實 | `kernel-cli.md`「init」仍隱含一顆 kernel cpu；建議明寫「工作池可空」，避免把「cpu 可空」理解成連 tick 執行者都沒有。 |
| (f) 每格 O(有事)，派工不掃全體 | 尚未達成 | 通知與 free 堆疊方向符合；實際成本與例外見 R17～R21。不能只把「寫帳本」列為唯一常態例外。 |

建議把「使用者已定」與「草稿自行補的政策」分清楚，尤其不要把 (f) 標成已完成。

**R2【高｜協定／要猜】第一次 boot 的縮零單不符合 scale 契約**

位置：`handoff.md` §1 第 2 步；`protocol.md` §1。

boot 不論池是否存在，都先送 `scale {count:0}`；但協定要求「池不在時 target 必填」。第一次 boot、正常 halt 已刪池後再 boot，都會遇到不存在的 kernel 池。

建議明定：不存在的池收到合法的 `count:0`，直接成功且不建立池；或 boot 的 down 單也帶完整模板。前者更符合「確保它不存在」的用途，並應一併定義回傳的 `ver`。

**R3【高｜協定】boot 宣稱重送全部宣告，實際送單條件會擋住**

位置：`handoff.md` §1 第 3 步；`kernel-pools.md` §2 第 2～3 步；`protocol.md` §4。

boot 把 `want` 設 null，只會迫使重算 W、T。真正送單還要求 `T ≠ S`。若帳本認為 S 有八顆、info 也要八顆，但 daemon 的池已不存在，重算仍是 `T=S`，不會重送。文件承諾的「池不見了，跑 boot 修復」因此不成立。

建議增加明確的「必須重新宣告」狀態，boot 時設起來，成功確認後才清除；不能把集合相同當作 daemon 已收到的證據。`Interrupted` 後的重送也應走這條規則。

**R4【高｜協定】縮池單在途時，改回原數量會把正在被收掉的 cpu 重新拿來派工**

位置：`kernel-pools.md` §1、§2；`kernel-ledger.md` §2 的 free 規則。

例：S 是 `{0,1}`，縮成 `{0}`，縮池單已送出但尚未收回音；此時 info 又改回兩顆。照 `free=S∩W−busy`，1 號會重新進 free，但 daemon 可能已經在停止它。新工作會派到正在退場的 cpu，違反「先做完再收」。

另外，pending 期間有縮池工作完成，文件沒有持久保存「要重算」標記；pending 結清後也沒有一律重新計算的規則，可能漏掉下一張縮池單。

建議把 pending 宣告納入可派工條件：被在途宣告移除的號先隔離，重新納入的宣告確認後才放回 free。每次 pending 結清，都以最新 W、確認後的 S 和 busy 重新決定下一步；需要跨格保留的標記必須進帳本。

**R5【高｜協定】停機完成的判準不足，可能回報 stopped 後又拉回孩子**

位置：`kernel-cli.md`「halt」；`kernel-tick.md` 第 9 步；`handoff.md` §3。

CLI 只等 `phase=stopped`、各池 `running=0`、`killing=0`。但一個宣告仍是 N 顆、全部處於 pending／dead／failed 的池，也符合這個條件。尤其多 daemon 時，kernel 池已停，不代表另一個 daemon 已接受工作池的縮零單。

若使用者接著 halt 那個 daemon，它會優先進 stopping，未處理的 scale 可能回 `Stopping`，舊的非零宣告卻留下；下次 daemon boot 又拉回來。

建議停機完成必須包含「每池縮零宣告已成功確認，且實際孩子已清空」。kernel 池最後才停，或由 halt CLI 接手完整的確認流程；不能只依兩個狀態計數判斷。

**R6【高｜協定】halt／boot 沒有完整處理已出貨的舊宣告**

位置：`handoff.md` §1 第 3 步、§3；`kernel-ledger.md` §3；`protocol.md` §1、§5。

§1 說 `sends` 照舊，§3 又說 boot 丟掉所有 scale sends，兩處直接衝突。即使採後者，也只處理帳本內的單；已放進 daemon 家的舊單、舊 pending 回音與 boot 新宣告之間，仍缺完整的先後規則。

`scale A → scale B → 重放 A` 不會保持 B，所以「同一份宣告可重送」不足以證明跨 boot 冪等。daemon 自己加的 `ver` 也不能判斷送件者的哪張宣告較新。

建議集中寫一份 boot 恢復規則：先結清或隔離舊 pending，再發布新宣告；或加入送件者的世代與遞增序號，讓 daemon 拒絕過期宣告。並明訂 kernel 池舊 pending 如何讀、ack、清帳，而非只說「順手讀掉」。

**R7【高｜協定】daemon 停機時，收屍規則仍會把孩子排回重拉**

位置：`daemon-reconcile.md` §2 第 3、5 步、§7。

第 3 步規定：killing 的孩子死了，若仍是成員，就回 pending。daemon halt 又刻意保留非零的 pool.json，因此這些孩子仍是成員。第 5 步沒有明寫 stopping 時禁止拉；§7 只說進入停機時清掉 pending，擋不住之後收屍新加回來的 pending。

建議把 stopping 判斷放在收屍與 spawn 的最前面：停機期間所有退出的孩子只移除執行狀態，絕不重新排隊；spawn 步驟完全跳過。否則照逐步文字實作可能永遠停不完。

**R8【高｜協定】搬池只等 sent 歸零，不代表舊 daemon 已放掉同一批家**

位置：`kernel-info.md` §4；`kernel-pools.md` §2；`protocol.md` §1。

文件叫人先縮零，看到 `cpu ls` 那池 0 顆再換 daemon／dpool。但 scale 成功只表示接受宣告，舊孩子可能仍在 killing。此時新 daemon 若拉起相同 cpu 家，就有機會同家兩個主人。

池從 info 刪掉又立刻加回，也有相同問題：帳本可能已忘記舊池，daemon 尚未收完。

建議搬池與刪池保留退場紀錄，直到舊 daemon 確認該世代的池已完全移除；新位置在此之前不得啟動。並統一 §4 的說法：它先說搬移「只在 boot 生效」，後面又像是縮零後可以動態搬，兩種行為需要選定一種。

**R9【高｜要猜】kernel 池允許 skip，卻到處寫死使用 0 號**

位置：`kernel-info.md` §2～3；`kernel-home.md` §1、§3；`kernel-ledger.md` §2；`handoff.md` §1。

kernel 池只限制 `count=1`，沒有禁止 `skip:[0]`。按成員公式，這時 daemon 應拉 1 號；但 boot、tick 與帳本都使用 `kernel/0`，鏈不會開始。

建議直接禁止 kernel 池的非空 skip，並在 info 讀驗與 `cpu rm` 都明確拒絕 kernel 池。這是內部不變條件，不需要另問使用者。

**R10【高｜協定】懶刪只看 NAME，無法辨認同名重新登記的行程**

位置：`kernel-tick.md` 第 8 步；`kernel-ledger.md` §2；對照 `proto5/spec/kernel.md` §2、§4。

queued 行程被 rm 後，舊 ready／delayed 條目還留著。同名、同池重新 add 時，新行程也是 queued，因此舊條目會通過全部檢查，並不會像文件說的被丟掉。

這會讓新行程繼承舊排隊位置；若舊 delayed 條目之後到期，而新行程已跑過一次、正在等下一次，舊條目還可能讓它早於新的 `not_before` 再跑。

建議條目帶登記世代，例如沿用 `procs.NAME.request`，並核對目前的排程期限；不能只用 NAME、status、pool 判定。

**R11【高｜協定】兩個正常 cpu add 仍可能互相覆蓋數量**

位置：`kernel-cli.md`「cpu rm」後的 info 寫入規則。

「rename 前再讀一次」不是原子的比較後更新。兩個 CLI 可以同時讀到 count=8、都通過再讀檢查、各自寫成 9；兩次成功的 add 最後只增加一顆。文件只把「人手改檔與 CLI 同跑」列為保證外，沒有排除兩個正常 CLI。

建議 CLI 之間使用同一把寫入鎖，鎖住讀、改、驗、rename 全段；暫存檔也要各自唯一。人手編輯不配合鎖的限制可另外保留。

**R12【中｜協定】「拉不起來」的建議救法不會解除 running**

位置：`kernel-pools.md` §3～4；`scale.md` §4；對照 `proto5/spec/kernel.md` §2 的 rm。

草稿建議先 `cpu rm P/i`，再 rm 那個行程。但 cpu 若始終起不來，工作原單仍在它家裡。行程 rm 只會標 discard、保留 procs；cpu rm 又要等 busy 結清，兩者會互相等。

建議更正救援說明：現有保守契約下，必須先修復那個家，讓 cpu 能處理或對帳原單，才能完成退休。若要新增「放棄未啟動的工作」能力，必須另訂能證明沒有執行者的取消協定。

**R13【中｜協定／要猜】新池的初始帳本與模板建立流程沒接完整**

位置：`kernel-pools.md` §2 第 2～4 步；`kernel-home.md` §2～3；`kernel-ledger.md` §2。

第一次 boot 帳本從空開始，執行中也允許新增池；但步驟直接使用 sent、want、free，沒有定義新池初值。建家又說每顆 inst 是池模板的複本；模板只明列 boot／envs 變更時重寫，動態新池的建立順序不夠明確。

建議列出一個不可省略的初始化步驟：建立池帳本、空 sent、null pending、空 free，建立模板及 envs，補新成員的家，最後才把 scale 放入出貨箱。每個斷點都要能重做。

**R14【中｜矛盾】envs 的 fallback 改了契約，而且 PATH merge 範例本來就不合法**

位置：`kernel-home.md` §2；`choices.md` §2 第 3 條；對照 `proto5/spec/inst-posix.md` §3.2～3.3、`directives.md` §3.2。

現有 inst 規範已允許整包 envs 經 `$ref` 取得，再使用 `$opt:"clear"`；`proto5/lib/aos_inst.py` 的 `_envs()` 也是先 resolve，再解選項。沒有理由因這個合法用法改成逐顆複製。

草稿舉的「PATH 的 merge」則不合法：envs 的值不吃 `$opt`，`merge` 是 stderr 選項。拿它驗證會得到預期中的失敗，卻可能誤觸 fallback。

建議刪除改變語意的 fallback，修正測試例子。另外寫清楚：巢狀 `$ref` 的中心仍是 cpu 的 cwd，不會因 envs 搬進池目錄就改成池目錄；`$ref:""` 則指當前的 envs 文件。

**R15【中｜矛盾】check 把 llm 池寫死，和 agent 可自選池的契約不合**

位置：`kernel-cli.md`「check」；對照 `proto5/spec/agent.md` §3、`aos-llm-call.md` §0～1。

只要沒有名叫 `llm` 的池就 bad，但 agent 可以把 `llm.pool` 設成 `gpu` 或其他名字。純工具 kernel、合法的空工作池 kernel，也會被當成設定錯誤。

而 `--agent` 雖然檢查自選池是否存在，模型設定仍寫成只查 `pools.llm.envs`，可能查錯 daemon 環境或錯誤的模型表。

建議有 `--agent` 時，以該 agent 的 `llm.pool` 驗有效環境與模型；沒有 agent 時，不強制存在固定名稱的 llm 池。count=0 保持 warn，與允許空池排隊的契約一致。

**R16【中｜矛盾】「其他全部不變」的清單仍有必須覆寫的舊引用**

位置：`proto5-2/README.md`「跟 proto5 的關係」；`kernel-cli.md`「ls／check」；對照下列 proto5 節。

至少需要列出這些相容修訂：

- `kernel.md` §2：add 的池驗證仍指向 `info.cpus`。
- `kernel.md` §6：health／check 的目錄檢查仍要求 `K/cpus/`；新草稿只改部分 health，卻說其餘照舊。
- `agent.md` §3：`llm.pool` 的合法性仍以 `info.cpus` 描述。
- `aos-agent.md` §6.1：錯誤路徑仍是 `K/cpus/.../cpu.log`；§1.3 又共用 kernel health。
- `aos-llm-call.md` §1：仍說 envs 只在第一次建家時複製，修改方式也指向舊路徑。
- `cpu.md` §5.4：仍說 kernel 對每顆 cpu 放 stop，與新停機方式不同。

核對結果：`aos-agent.md` §5.2、§10 的核心依賴是 `procs`／`replies`，§11 只解 kernel 的兩個退出碼設定；沒有找到這三節必須依賴 queue／cpus 的問題。建議保留這個相容結論，但另列上述診斷、路徑及文字契約的替換清單。

**R17【中｜O(N)／六點】每格成本漏了整份帳本讀取，寫入次數也和沿用條款衝突**

位置：`kernel-tick.md` 第 1、5、8～10 步；`kernel-ledger.md` §3～4；`scale.md` §1～2；對照 `proto5/spec/kernel.md` §2。

tick 是每格重啟的程式，因此每格都要讀取、解析包含 free、busy、procs 的整份 state；空閒一萬顆也有 O(N) 成本，不只是寫檔。

另外，舊 syscall 契約要求每則一次帳本寫入，新草稿卻說 syscall 不變、一格最多四寫。第 8 步派工寫、第 9 步停機寫、第 10 步再寫，哪些合併、哪些略過也沒有統一定義。

建議把讀取與解析列入成本，重寫完整的提交邊界表，明確取代舊 syscall 的逐筆寫法。若仍接受整份帳本，就把承諾改成「逐顆查檔已消除，帳本處理仍 O(N)」。

**R18【中｜O(N)】delayed 二分插入不是 O(log N)，懶刪也可能累積成大掃描**

位置：`kernel-tick.md` 第 8 步；`kernel-ledger.md` §2；`scale.md` §1～2。

二分搜尋只省找位置；往排序陣列插入仍要搬移 O(排隊數) 個元素，多件回音一起重新排程可能接近 O(回音數×排隊數)。ready 若直接從陣列頭移除也有相同問題。

被 rm 的條目沒有壓縮規則。尤其 free 為空的池，不會進配對迴圈清 ready；長期 add／rm 可以留下遠大於活行程數的殘留。

建議明定 heap、deque／頭索引等操作契約，加上有預算的失效條目清理；成本式另計清理量，不能只算真正派出去的工作。

**R19【中｜O(N)】want 更新不完整，縮池可能每格重算全池**

位置：`kernel-pools.md` §1、§2 第 2～3 步；`kernel-ledger.md` §2。

want 說是「上次處理過的 info」，但步驟只在送 scale 時更新。若縮池要拿掉的號都還忙，T 仍等於 S，不送單，want 就一直是舊值；下一格又認為 info 改了，再掃全池。

即使補上 want，縮池中的每顆依次完成，都會觸發全池集合與 free 重整。縮一萬顆可能累計 O(N²)，比「偶爾改數量才 O(N)」嚴重。

建議處理完 desired 變動就更新 want，另記尚未完成的對帳狀態；退場成員完成時以增量方式移除，或至少合批重算並列明成本。

**R20【中｜O(N)】skip、busy 查找與巡檢順序都缺少支撐成本承諾的規則**

位置：`kernel-info.md` §3；`kernel-pools.md` §1；`kernel-tick.md` 第 6 步；`scale.md` §1～2。

`count+skip` 相等比較不是固定 O(1)，成本至少跟 skip 長度有關。永久退休累積後，skip 可以遠大於目前 count；宣告與帳本大小也就不是只跟現有 cpu 數有關。`scale.md` 還把它寫成「回音裡的 skip」，實際協定回音沒有這格，長的是請求與持久狀態。

巡檢若為了取前 sweep 顆先做 `list(busy)`，仍掃全部 busy；rm 要由行程找 cpu，procs 又沒有反向索引，也可能每次掃 busy。輪轉還依賴 JSON 物件順序跨讀寫保持不變。

建議明訂 skip 正規化、大小限制、反向索引與巡檢 cursor／佇列；若用物件順序，必須禁止寫入器重新排序 key。成本式應加入 skip 長度。

**R21【中｜O(N)】daemon 摘要與計時器也可能偷偷掃全池**

位置：`daemon-home.md` §4、§6；`daemon-reconcile.md` §2～4、§6；`scale.md` §1。

「有變才重寫 summary」只限制寫入頻率，沒有保證計數是增量更新。若一顆死掉就從記憶體重數全池，一樣是 O(N)。

`restarting` 在活過 stable_ms 時要減少，卻沒有對應的到期事件；若每圈掃 running 判斷穩定時間，又回到 O(N)。dead／failed 的到期挑選、跨池輪流拿令牌，也未規定如何跳過大量沒有待辦的池。

建議明訂各狀態計數隨轉移增減，穩定時間與退避使用到期佇列，只排有可執行項目的池；否則縮小成本承諾。

**R22【中｜O(N)／要猜】requests 目錄的成本與通知上限估計不成立**

位置：`kernel-tick.md` 第 5 步；`cpu-notify.md` §3；`scale.md` §3 第 7 點。

每格列目錄的成本是「目錄所有項目」，不是只有這格的新 syscall／通知。沿用檔名排序時還要算排序成本；原子投檔留下的 `.tmp` 雖不處理，也仍會被列到。

「通知上限約等於忙的 cpu 數」也不是保證：cpu 開機會替所有未 ack 回音補通知，包含 kernel 已結帳但 ack 尚未被 cpu 處理的歷史回音。

建議改用目錄項目總數 Q 描述成本與積壓；通知數上限應依未確認回音數計算。並說明過期通知、暫存殘檔和過大批次的處理預算。

**R23【中｜六點／要猜】daemon 狀態計數公式錯誤，重拉中的名稱也容易誤讀**

位置：`daemon-home.md` §3～4；`daemon-cli.md`「ls」。

文件說成員數等於 running＋pending＋dead＋failed，卻漏掉「仍是成員、正在 kill 後重拉」的 killing。整池 kill 時，這個等式直接不成立。

`restarting` 是 running 的子集，dead／failed 則是等待重拉，這不是直覺上的四種互斥狀態。`ls --pool` 說讀 kids 檔，卻又要列沒有 kids 檔的 pending，也缺了補列規則。

建議區分「成員中的 killing」與「已移出宣告的 draining」，寫出正確總數公式；把 restarting 的重疊關係直接放進 CLI 說明，pending 由宣告成員減去已有孩子紀錄取得。

**R24【中｜協定／要猜】max_children 只算宣告數，不能保證實際 fd 不超限**

位置：`daemon-home.md` §1；`protocol.md` §1 第 4 步；`daemon-reconcile.md` §4～5。

池 A 從一萬縮到零，孩子還在 killing，但宣告數已經是零。此時池 B 宣告一萬會通過容量檢查；daemon 若繼續 fork，實際仍握有 A 的 fd，可能超過宣稱的容量。

建議分清「宣告容量」與「目前可啟動容量」：scale 可接受 desired，但 spawn 每次必須依實際存活／killing 孩子與 fd 預算保留空位，等舊孩子收完再拉新的。

**R25【中｜協定／要猜】pid、gen 與舊版 daemon 家的恢復契約不完整**

位置：`daemon-home.md` §1、§3、§6；`handoff.md` §2。

第一次 SpawnFailed 尚未產生 pid，孩子檔卻沒有說 pid／since／gen 應填什麼。daemon 重開又清空 kids，gen 的「第幾代」是否重新從 1 算、exits 是否歸零，也沒寫。

更重要的是，daemon 明說接受舊版 info，但新啟動只掃 kids；proto5 留下的孩子卻在 `state.json.children`。接受舊 info 不等於能安全接手舊 runtime 狀態。

建議補初值、跨 daemon 世代的計數規則，以及舊家遷移程序：讀舊 children 做交接，或明確拒絕尚有舊執行狀態的家。不能默默略過。

**R26【中｜協定／要猜】错误存檔少了判斷 Stopping 所需的代號**

位置：`kernel-ledger.md` §2；`kernel-pools.md` §2 第 1 步；對照 `proto5/spec/cpu.md` §3.2。

`pools.P.error` 只存 `{"code","message"}`。但 `Stopping`、`TooMany`、`NameTaken` 都使用數字 `-32000`，真正代號在 `error.data.code`。若跨格只剩這兩格，就無法可靠執行「Stopping 每十格重試」的特殊規則。

建議保存完整 error 或明確的符號代號，並新增持久的下次重試序號／時間。不要從白話 message 猜错误種類。

**R27【中｜要猜】通知驗證、名稱與數值邊界需要補一張一致的表**

位置：`cpu-notify.md` §1～3；`kernel-tick.md` 第 5～6 步；`kernel-info.md` §2～3；`daemon-home.md` §1；`protocol.md` §1～2。

實作者目前仍得自行決定：

- `resp-` 壞 JSON、帶 id、method 不對、home 不屬於 K、busy 已不存在時，如何處理及刪除；不能讓一張壞通知每格都使 tick 退出。
- 池名／dpool 是否排除空字串、`.`、`..`、NUL、過長檔名，以及 `{name}`、`#` 等會進入模板或 `$ref` 的字元。
- `P/01` 是否等同 `P/1`；skip 是否排序、禁止重複、允許無效的大號碼。
- `cpu add／rm --count 0`、負數、bool、過大整數；`spawn_per_sec=0`、restart 上限小於起點如何報錯。
- init 可暫無 daemon，但一般 info 表又要求池能解析出 daemon；哪些檢查延後到 boot。

建議用同一份欄位讀驗表定義型別、正規化、預設與錯誤代號。通知須限定映射到已知 cpu 家；通知遺失或重複的正常路徑已有巡檢兜底，問題在壞通知的處理尚未定義。

**R28【低｜矛盾】fd 1 改接 /dev/null 可沿用目前 cpu，但文件應直接修正契約**

位置：`daemon-reconcile.md` §5；`cpu-notify.md` 開頭；對照 `proto5/spec/cpu.md` §0、§6.1。

從 `proto5/lib/aos_exec_cpu.py` 的 `Control.relocate()` 看，fd 1 只是複製到高位，再把工作用 stdout 接到 fd 2；沒有要求 fd 1 必須是 pipe。因此靜態檢查沒有找到會因此直接壞掉的地方，也不會把工作 inst 指定的模型 stdout 一併丟掉。

問題是草稿仍說 cpu「只多 notify，其餘不變」，舊文卻把高位 fd 1 稱為回程控制 pipe。建議明確補一句允許 fd 1 為 `/dev/null`，並保留「工作標準輸出仍照 cpu／inst 規則處理」；不要把已能確認的契約留成「實作先驗」。

## 要使用者拍的

1. **這一版是否接受 kernel 每格仍讀寫 O(N) 帳本？**  
   若接受，應把 (f) 的交付目標寫成「消除逐顆查檔與找閒 cpu」，明列帳本成本。若要求整格都隨有事數量增長，就需要繼續改帳本與索引結構。

2. **既有池的 `cpu add --env` 要怎麼解讀？**  
   草稿選擇直接拒絕。若要允許，建議定成修改池環境、之後啟動的成員繼承；活著的成員是否一起重啟，是另一個動作。這影響日常操作，應由使用者選定。

3. **`cpu rm NAME` 是否真的代表永久退休那個號碼？**  
   草稿選擇 `NAME=P/<i>`，刪除後寫入永久 skip，未來擴池也不再使用。若原意只是指定這次收掉哪顆，永久 skip 就多了一層政策，需要改寫。