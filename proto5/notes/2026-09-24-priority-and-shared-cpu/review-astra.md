提案的主要現況判讀正確：派工由 kernel 帳本決定、agent 已共用 exec cpu、工具目前只能在 agent 層選池。但「專屬池永遠不用排隊」「單一 VIP 很難餓死別人」及規模估算有重要誤導，不能直接據此承諾延遲或公平性。**必修 10 條、建議 6 條**。以下行號以目前工作樹為準；提案檔名簡稱均指 `proto5/notes/2026-09-24-priority-and-shared-cpu/`。

1. **〔必修〕(c) 隔離了其他 agent，沒有消除 amy 自己的排隊。**  
   **位置：** `priority.md:54、67、72`；`README.md:30`。  
   **現象：** 操作把 amy 的 tick 與全部工具放在同一顆 `amy` cpu，卻聲稱「每格都派得到」「永遠不用排隊」。一批多件工具仍須逐件跑；長工具執行中，amy 的 tick 也進不去。  
   **依據：** `proto5/lib/aos_kernel_engine.py:99–115` 每顆只派一件；`aos_agent_batch.py:75–108` 一批逐件送出；kernel 先收 syscall、再收回音，因此整批工具也可能排在重新入隊的 tick 前面。  
   **建議改法：** 改成「不與其他 agent 爭用這些 cpu」，明列自家工具與 tick 的競爭。若要隔離 tick，另設 `amy-tick` 池；仍不能保證同批所有工具立即開始。

2. **〔必修〕單一 VIP 就有可構造的餓死情境，並行上限也寫錯。**  
   **位置：** `priority.md:53`。  
   **現象：** 「1 格 tick＋1 次問模型＋一批工具」不是正常狀態機的同時在途組合；think 與 act 共用一個 batch，二者互斥。更重要的是，單顆 default 池、VIP tick 最高優先且 `interval_ms=0` 時，即使 VIP 閒置、一直退 101，也能每次收回後立即再被選中，讓普通工作永遠等。  
   **依據：** `aos_agent.py:72–83`、`aos_agent_batch.py:17–33`；`aos_kernel_info.py:176–183` 對 0／101 都重新排程；`aos_kernel_engine.py:153–155` 同格先 collect 再 dispatch。工具件數沒有規範上限（`spec/agent/info.md:48–49`）。  
   **建議改法：** 上限改為「一個 tick，加上一個 think batch 或 act batch」。公平性依據應是「派工當下是否一直存在可派的高優先工作」，不能用 VIP 數量推斷；正的 `not_before` 可能提供空檔，多個 VIP 則可能填滿空檔。

3. **〔必修〕(d) 的等待上限與「不會餓死」都缺少成立條件。**  
   **位置：** `priority.md:53–54`；`README.md:28`。  
   **現象：** amy 借出的 cpu 不可搶占，須等借用工作完成；「最多約兩分鐘」不是通用上限。工具可設 600000 ms 或 0，tick 的工作 timeout 預設也可為 0。低順位池若只剩可借用的 cpu，高順位工作持續可派時仍會餓死。  
   **依據：** `spec/agent/info.md:26、73`、`spec/kernel/home.md:45`、`spec/aos-llm/timeouts.md:7–10`；`spec/aos-agent/collect.md:18` 明定排隊等待無上限。  
   **建議改法：** 寫成「正常運作下，至少受借用工作剩餘執行時間及收回／派工格延遲限制；沒有統一有限上限」。若保留一般池的獨立 cpu，應明說這是一般工作仍能前進的條件；借用與最短 VIP 延遲之間有取捨。

4. **〔必修〕路徑圖少一個 agent tick，且箭頭不都代表一格 kernel tick。**  
   **位置：** `priority.md:36–41`。  
   **現象：** 收模型回音、寫記憶後，不會同一次 tick 再建工具批次；必須等下次 agent tick。另一方面，kernel 收 add 後可以在同一格派工，HTTP 與伺服器處理也不以 kernel 格為單位。  
   **依據：** `aos_agent.py:72–83` 收批直接 return；`aos_agent_batch.py:160–204` 結清只切換 state；`aos_kernel_engine.py:151–155` 同格收單並派工。  
   **建議改法：** 分開畫「收批／切成 act」與「下一次 tick 建批／送件」。另說明 interval 從 **kernel 收回音判定時**起算；預設 kernel 約一秒一格時，200 ms 通常不會比 1000 ms 少等一格，0 才可讓剛收回的 tick 當格再派。調小也會增加空轉、讀檔與競爭。

5. **〔必修〕(d) 漏掉必要驗證修改，行數估計不足以支持方案成本比較。**  
   **位置：** `priority.md:50–51、74`；`README.md:28`。  
   **現象：** `pool` 改陣列不是只改派工。現行 info 驗證直接拒絕陣列；`_add` 與 check 把 pool 收進 set，也不能直接接受 list。proto5-2 的多池借用還涉及實體 cpu 所屬池與工作目標池的區分。  
   **依據：** `aos_kernel_info.py:71–76`、`aos_kernel_ledger.py:49–51`、`aos_kernel_check.py:261`；`proto5-2/spec/kernel-ledger.md:47、52–56` 及 `kernel-tick.md:29–35`。  
   **建議改法：** 補列 `aos_kernel_info.py`、保留 kernel 池的限制、池存在性與顯示修改。proto5-2 要明定 cpu 完成後回哪條 `free`、縮池如何計算，以及優先使用一般池自己的 cpu。將 10～15／20～30 行標為未驗證的核心邏輯粗估，不能當完整修改量；(a) 在池式下也要交代 delayed 到期後進哪級 ready，O(級數) 只描述選取部分。

6. **〔必修〕只把 check 改成尋找 `AOS_LLM_CONFIG`，仍修不好模型池驗證。**  
   **位置：** `priority.md:65–66、79–80`；`README.md:33`。  
   **現象：** 現況判讀正確，但建議修法不完整：仍有「缺名為 llm 的池就 bad」；模型代號被合併成全域集合，可能拿另一池的模型替 amy 判通過。另外，實際 agent/tool 檢查在 `aos_kernel_check.py`，不在提案所列的 `aos_agent_check.py`。  
   **依據：** `aos_kernel_check.py:202–210、265–275`；`aos_agent_check.py:49–51` 僅呼叫共用檢查。  
   **建議改法：** 模型表按池保留，agent 依自己的 `llm.pool` 驗證可被派到的 cpu；移除強制池名。工具 `_pool` 檢查應涵蓋有效 fallback `tool_pool`，並排除 `kernel`。`--probe` 通過也不代表 agent 的 params／tools 請求必定可用，它可能只做 GET models。

7. **〔必修〕「1000 個 agent＝每秒起 1000 支 Python」不是目前排程的實際速率。**  
   **位置：** `shared-cpu.md:76–77`；`README.md:49`。  
   **現象：** `interval_ms` 是收回音後的最早再派時間，不是固定頻率。一顆工作 cpu 每個 kernel 格最多接一件，即使工作幾毫秒就完成，也要等 kernel 收回才能接下一件。因此不能只按 Python 執行時間推出「上百顆就夠」。  
   **依據：** `aos_kernel_info.py:183`、`aos_kernel_engine.py:96–116`；`spec/kernel/tick.md:21` 指出实际格長還包含做事時間。  
   **建議改法：** 區分期望頻率與實際吞吐；以每格可派 cpu 數、agent interval、工具占用時間估算。10～20 MB 也應標為未實測估值，容量評估需區分 RSS 與共享頁。

8. **〔必修〕「每個 agent 每格讀整份 K 帳本」不符合實作；kernel 重寫成本反而被淡化。**  
   **位置：** `shared-cpu.md:78–79`。  
   **現象：** 沒有 sweep 待辦、沒有送新 call 的 idle tick 不讀 K 帳本。送件與清檔時則可能每個 call 都重讀一次。kernel 也不是每格只重寫一次，而是每則 syscall、回音、派工及出貨項目反覆存整份。  
   **依據：** `aos_agent_runtime.py:163–183`、`aos_agent_batch.py:37–44、104`；`aos_kernel_ledger.py:115–137`、`aos_kernel_engine.py:42、114`。proto5-2 的四個提交點見 `kernel-ledger.md:68–81`。  
   **建議改法：** 將 O(N²) 限定在大量 agent／call 同時觸發全帳本讀取的負載，並明列 proto5「事件數 × 帳本大小」的寫入成本。不要直接繼承 scale 草稿「每格都讀」的不精確描述。

9. **〔必修〕proto5-2 的單行 `cpu add` 不足以建立可用的 amy LLM 池。**  
   **位置：** `priority.md:55、73`。  
   **現象：** `cpu add --pool amy-llm --count 1` 只新增 count，沒有模型設定環境；也不是執行後立即可派。  
   **依據：** `proto5-2/spec/kernel-cli.md:36–42`；`kernel-pools.md:64–67` 要等 scale 成功才進 free，成功仍不代表 cpu 已啟動。  
   **建議改法：** 新池範例補 `--env AOS_LLM_CONFIG=/abs/llm.json`，交代 PATH／金鑰與 daemon 繼承前提；提醒既有池不能再用 `cpu add --env` 修改。改成「一行宣告池，後續由 kernel／daemon 建立」。

10. **〔必修〕共用工具例子加 `_pool` 後，還需要撤回 agent 層的 `tool_pool=gpu`。**  
    **位置：** `shared-cpu.md:56、70`。  
    **現象：** 第 56 行已將 amy、bob 全部工具指向 gpu；第 70 行說只加 `_pool`，其他工具就回 default，並不成立。  
    **依據：** 提案第 65–67 行自己的 fallback 規則：沒 `_pool` 仍用 `info.tool_pool`。  
    **建議改法：** 明寫兩個動作：在工具陣列中的 `gpu_run` 元素加 `_pool:"gpu"`；將兩個 agent 的 `tool_pool` 恢復 `default` 或省略。

11. **〔建議〕FIFO、輪流及「只有一張單」應加上範圍。**  
    **位置：** `priority.md:7–13`；`README.md:18`。  
    **現象：** 正確語意是同池、已到 `not_before` 的工作依 queue 順序選取，不是全域按提交時刻 FIFO。同格 syscall 按檔名字典序，agent 名也會影響先後；輪流不代表平均 cpu 時間。工作 cpu 也可能同時有 ack／stop 控制檔。  
    **依據：** `aos_home.py:200–202`、`aos_kernel_engine.py:105–106`；`spec/kernel/ledger.md:45–48`。  
    **建議改法：** 寫成「同一管理鏈正常運作時，每顆工作 cpu 最多一件尚未結清的 kernel 工作；控制單另計」。同步 LLM、一顆一次一問的核心結論成立。

12. **〔建議〕`llm.params` 並非全部原樣送出，生效時間也不完全是『下一批』。**  
    **位置：** `README.md:26`；`priority.md:32、56、64`。  
    **現象：** `model/messages/tools/stream` 被忽略，其餘才併入。LLM params 在 `aos-llm call` 真正執行時讀，已排隊但未執行的請求也可能用新值；池則在送 add 時選定，半批恢復時尚未送出的 call 可能用新池。  
    **依據：** `aos_llm_call.py:17、65–78`、`aos_agent_batch.py:104–108`。  
    **建議改法：** 區分「登記時」「送件時」「模型呼叫執行時」。`priority` 不在保留鍵內，因此可傳入 body 的結論成立；端點是否接受、如何排序仍須另外驗證。

13. **〔建議〕(c) 操作方向可行，但應補齊建家與切換前提。**  
    **位置：** `priority.md:60–66`；`shared-cpu.md:45–57`。  
    **現象：** 新增 cpu 不需 boot、tick 池要 stop／start 的描述正確，等待 `agent-amy` 消失也正確。但新增名字若已有 cpu 家，info 的 envs 不會覆寫舊 inst；daemon 名字若被別的 K 使用會撞名。  
    **依據：** `spec/kernel/home.md:53–61`；`aos_kernel_engine.py:78–83`；`spec/aos-agent/register.md:44–50`。  
    **建議改法：** 補「原子替換 JSON、選未使用名字、確認有效 inst／環境、池已存在再切換」。保留 stop 後等行程消失的步驟；直接重複 start 可能印 already started，但不更新池與 interval。也提醒 stop 不取消已送出的工具／LLM 批次。

14. **〔建議〕補列更便宜的隔離方案，並限定 (b)『不成立』的意思。**  
    **位置：** `priority.md:45–55`；`shared-cpu.md:60`。  
    **現象：** 漏掉「所有 agent 的 tick 與長工具分池」這個零程式方案，也漏掉小組共用 VIP 池、僅隔離目前真正擁塞的資源。  
    **依據：** `spec/agent/info.md:25–29` 已有三個独立池設定；`spec/cpu/methods.md` 規定目前同步一次一件。  
    **建議改法：** 將 (b) 改成「維持現行一顆一件協定，只改 llm cpu 無法重排 kernel 尚未交付的工作」。若改成集中接件服務／代理佇列，架構上仍可行，但不是小改，也不涵蓋工具優先。資源只需互斥時，可另列工具 wrapper 共用鎖的折衷，說明等待會占用 exec cpu、也不保證公平。

15. **〔建議〕明說 `_pool` 的有限批次不會自行造成永久餓死，也別把单顆池等同無條件資源鎖。**  
    **位置：** `shared-cpu.md:29、40–41、65–70`。  
    **現象：** 一個 agent 送很多 call，FIFO 下其他工作可能等完整批次，但有限、會終止的工作不會單凭件數造成永久卡死；agent 等回音的 tick 會退出，並不持續占住工具 cpu。真正無限等待來自不限時工作、cpu 起不來、池消失，或工具內嵌同池等待。  
    **依據：** `aos_agent_batch.py:127–157`；`spec/aos-agent/collect.md:18`；`spec/aos-agent/tick.md:23–27` 列出孤兒行程等保證外情況。  
    **建議改法：** 區分長等待、餓死與循環等待。單顆池只能序列化經它派發的工作；外部程式或未清乾淨的子行程仍可能同時碰資源。嵌套 `--wait-ms` 有限時，還應說明 CLI 逾時不取消內層工作，不能一概叫永久卡死。

16. **〔建議〕瓶頸表補上輪詢、掃隊與檔案累積。**  
    **位置：** `shared-cpu.md:74–83`。  
    **現象：** 尚缺 cpu 閒置輪詢、每顆閒 cpu 掃 queue、單鏈吞吐、行程／fd 上限、記憶與目錄／log 成長。  
    **依據：** `aos_kernel_engine.py:49、99–106`：新 cpu 預設 **20 ms** 輪詢，派工逐顆掃 queue；`aos_exec_cpu.py:197`；`proto5-2/spec/scale.md:33–40`；`spec/agent/info.md:21、52`。  
    **建議改法：** 補列這些成本，尤其不要把 scale 的 200 ms 範例當現行預設。LLM 池也應改成「並行數提高到端點容量前可能增加吞吐，超過後才主要增加端點排隊」，而非暗示多開始終只搬移隊伍。

**我沒看的：** 本次只做指定提案、相關規範與實作的靜態核對，沒有修改檔案、跑測試、啟動 daemon／kernel／模型，也沒有量測記憶體或吞吐、查驗實際部署環境與端點優先權功能。`kind=aos` 的分類、工具經 posix inst 交给 exec cpu、工具私有鍵送模型前移除等敘述，與所讀規範及實作相符；proto5-2 仍只按未實作草稿評估。