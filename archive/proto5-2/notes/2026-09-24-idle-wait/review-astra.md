唯讀審查完成，未修改任何檔案，也未執行會建檔、啟動行程或清場的實驗。以下將「提案尚未定義的必要條件」與「已能確認的錯誤」分開說明。位置皆相對 repo 根目錄。

1. **〔必修〕喚醒資訊必須跟著回音進出貨箱，否則崩潰後會真的漏喚醒。**

   **位置：** `proto5-2/notes/2026-09-24-idle-wait/README.md:46–50`

   **現象：** 現有 `collect` 會把 once 的結果放進 `replies`、刪掉 once 行程，再存帳本。若新增的 `wake` 只留在 once 行程或當格記憶體，崩在這次存帳本後、出貨前，下一格雖能補放回音，卻已不知道要叫醒誰；停車的 agent 只能等保底。提案列的兩條時序沒有交代這條持久化鏈。

   **依據：** `proto5/lib/aos_kernel_engine.py:30–42`；`aos_kernel_ledger.py:25–27,118–137`。現有 `replies` 只有名稱、id、body，沒有喚醒對象。

   **建議改法：** 明訂 `wake` 隨回音待辦一起持久化；回音成功落地後，把「目標排程／`woken` 更新」與「移除該回音待辦」放在同一次帳本提交。重播也必須走同一條路。這是「崩在任意兩步之間仍不漏」成立的必要條件。

2. **〔必修〕喚醒不能只掛在「工具正常執行完」那條路，取消與退件也要涵蓋。**

   **位置：** `proto5-2/notes/2026-09-24-idle-wait/README.md:28,46–53`

   **現象：** agent 等的是一次 add 的最終回音，可能是正常結果，也可能是 `Removed`、`Stopping` 或 add 當場退件。只在收 cpu 回音時安排喚醒，已停車的 agent 遇到 once 被 `rm`，就收不到喚醒；取消後也不一定還有 cpu 回音可補救。

   **依據：** `proto5/lib/aos_kernel_ledger.py:29–31,69–87,90–116`；`aos_kernel_engine.py:118–127`；`proto5/spec/aos-agent/collect.md:31–33`。

   **建議改法：** 將事件定義成「這張 add 的終局回音已交付」，涵蓋成功、失敗、取消、停機與可辨識喚醒對象的退件。`wake` 資訊應一路傳到這些回音待辦，不能只存在成功建立的 once 行程。

3. **〔必修〕「每次喚醒推一笔 `ready`」不能直接套現有舊格規則。**

   **位置：** `proto5-2/notes/2026-09-24-idle-wait/README.md:36,53,67`

   **現象：** `delayed` 會比時間，**`ready` 不會**。兩個工具回音先後叫醒同一個 queued agent，就可能留下兩筆完全相同的 `[NAME, request]`。第一筆派出後，若池已沒有空位，第二筆會留著；下一格 agent 回到 queued、甚至重新停車時，這筆殘留 `ready` 又符合現有判定，能提早派工。

   **依據：** `proto5-2/spec/kernel-ledger.md:55–66` 明定只有 delayed 比 `not_before`，且 queued 行程只能有一個有效格；`kernel-tick.md:33–38` 在沒有 free cpu 時停止配對。

   **建議改法：** 已在 ready 的目標收到重複喚醒應合併；或讓 ready／delayed 都帶排程版本，喚醒時換版本。另須把喚醒造成的舊 delayed 格納入壓縮計數，現有「成本攤到每次 rm」的說明也要補上。

4. **〔建議〕補完整的目標生命週期規則；只說「stop 後略過」還不夠。**

   **位置：** `proto5-2/notes/2026-09-24-idle-wait/README.md:49–53,58`

   **現象：** `stop` 後正在跑的行程仍留在帳本，只是 cpu 槽標 `discard`；因此「目標存在」不表示還能喚醒。舊工具也可能在 agent 同名重 add 後才回來，單靠 `wake: NAME` 會叫到新登記。另未定義 `bad`、`done`、once 目標是否可被喚醒。

   **依據：** `proto5/spec/kernel/syscall.md:25–30`；`proto5/spec/aos-agent/register.md:44–51`；`proto5-2/spec/kernel-ledger.md:61–66` 已用 add 的 `request` 分辨同名不同代。

   **建議改法：** 明訂 discarded／bad／done 不復活；running 只設旗標、不另排一格。決定喚醒是跟「名字」還是「該次登記」綁定；若選後者可沿用 add request 當代號，但 restart 後接手舊批也要另訂規則。`woken` 的消耗與清除應跟當次回音判定原子提交。

5. **〔必修〕第二階段的 `say → wake` 有正常崩潰窗口，保底不只是防程式錯與外人。**

   **位置：** `proto5-2/notes/2026-09-24-idle-wait/README.md:65–66,75`

   **現象：** idle agent 已停車；`say` 成功放好輸入，卻在投 `wake` 前被殺掉。輸入完整存在，但沒有後續事件叫醒 agent。這不需要任何程式錯，也不是「外人直接丟檔」。

   **依據：** `proto5/lib/aos_agent_say.py:63–76`，輸入交付是獨立操作；`proto5/spec/aos-agent/idle.md:5–11` 必須有 tick 才會收輸入。

   **建議改法：** 若接受最多等 `park_ms`，就明寫這是通知遺失的正常補救；若要求崩潰後仍可靠喚醒，需有可恢復的交付／通知待辦。不能只把兩個放檔動作接在一起就宣稱不漏。

6. **〔建議〕§4 應補證明邊界：ack／sweep 本身安全，原單存在與門關閉則要說清楚。**

   **位置：** `proto5-2/notes/2026-09-24-idle-wait/README.md:46–53`

   **現象：** 「回音放好」不一定等於 agent 當下可收，因為 agent 先查原單。現有出貨順序是 replies 在 deletes 前。不過正常恢復時，下一格先補出貨、再收 agent 回音與派工，因此不能單憑這點判定漏喚醒。另一方面，「門關著的 agent 沒有單可以等」不符合現況：關門時可以仍有在途批。

   **依據：** `proto5/lib/aos_kernel_ledger.py:118–137`；`aos_kernel_engine.py:148–157`；`aos_agent_batch.py:114–157,194–196`；`aos_agent_runtime.py:163–183`；`proto5/spec/aos-agent/gate.md:12`。

   **建議改法：** 明寫恢復出貨須先於判定／派工，以及只有收批路徑的「未收到」才改退 102。保留先存 `done` 再 ack、結清後才 sweep 的順序：如此 agent 崩在 ack 前後仍有進度可接，不會因清掉回音而失去未完成工作。多工具可合併成一個 `woken`，因為收批會逐筆檢查；不必每件都新增排隊格。

7. **〔必修〕實驗 B 的 CPU 差值不是精確的量測窗口用量，已出現明顯邊界誤差。**

   **位置：** `proto5-2/notes/2026-09-24-idle-wait/exp/b_e2e.py:47–83,175–200`；`measure.md:28–37`

   **現象：** `/proc/stat` 欄位索引沒算錯；穩定存活的 cpu 收完孩子後，用 cutime 歸帳也合理，並沒有直接把每支 agent tick 重算一次。但尚未被收屍的 tick 被 `classify` 排除，CPU 要等收屍後才整筆進父行程。於是跨窗口的 tick 會漏算尾端，或把窗口前的工作算到窗口內。帳本 `last_seq`、log、CPU 快照也不是同一邊界。

   **依據：** `b_e2e.py:65–74` 只分類 daemon／cpu；`175–183` 分別讀取多個快照。`proto5/lib/aos_kernel_engine.py:145–147,159–161` 在格首記 seq、格尾才寫 log。表中單線 kernel「每格 CPU 6.318 秒、牆鐘 6 秒」不能當成一致的穩態精確值。

   **建議改法：** 用完整 tick 邊界量測，或納入仍活著的子行程並處理收屍時的歸帳移轉；延長窗口、重複量測並附範圍。修正前，把 6.3 秒與各池每 tick CPU 標成粗估，不宜用來精密驗證三次存帳本模型。

8. **〔必修〕實驗 B 沒保證「三顆模型永遠掛住、全員進入純等待」。**

   **位置：** `proto5-2/notes/2026-09-24-idle-wait/exp/b_e2e.py:125–127,149–175`；`measure.md:6,27`

   **現象：** 腳本把模型 client timeout 設成一小時，但 agent init 仍給工作單 **125 秒**逾時，cpu 會先中止它。暖機等滿 120 秒後，即使 `waiting < n` 也照樣開始量；`batch.sent` 也不代表 kernel 已收掉全部 add。不能保證表裡只有空轉。

   **依據：** `proto5/lib/aos_agent_init.py:29–33`；`aos_agent_batch.py:104–108` 將 agent 的 timeout 寫進 once；`aos_exec.py:474–498` 執行逾時處理。

   **建議改法：** 在測試家明確設定足夠長或不限時的工作 timeout；暖機未達條件就判失敗。量測前後驗證三顆 llm 仍是同一批工作、沒有 timeout／結清／重送，並保留原始報表。另外，腳本的 `INTERVAL_MS` 沒覆寫 init 明寫的 agent 1000 ms；要測不同 interval 也須修正。

9. **〔建議〕三次存帳本與 56 ms 算對了，但應標明是反覆空轉的邊際成本。**

   **位置：** `proto5-2/notes/2026-09-24-idle-wait/measure.md:57–58,67`；`README.md:12–13,70`

   **現象：** 穩態反覆 tick 確實各有一次 collect、dispatch、cpu ack 出貨的整份存檔，`3 × 18.5 = 55.5 ms` 正確。可是一般有 id 的 think once 完整生命週期是 **六次**：收 add、刪 add 原單、派工、收結果、出 cpu ack、出呼叫者回音；此外每格還有固定存檔。

   **依據：** `proto5/lib/aos_kernel_ledger.py:14–15,63–67,113–137`；`aos_kernel_engine.py:30–42,90,114,145–158`。agent 對 K 的 ack 由 `aos_home.py:206–232` 清檔，不是再存一份 kernel 帳本。

   **建議改法：** 保留「三次」結論，但加上適用範圍；README 的每秒 0.3 秒 CPU 估算應列出保底 tick、實際 agent tick、once 完成率與固定成本，避免讓讀者以為所有單都只乘三。

10. **〔必修〕E 節前三列大致算對，後兩列的格長與「14 顆核」缺推導。**

    **位置：** `proto5-2/notes/2026-09-24-idle-wait/measure.md:67–78`；`README.md:15–16,22`

    **現象：** 照文件自己的公式重算：

    | 情境 | 一格 | 每 agent 再訪時間 | kernel 平均 CPU |
    |---|---:|---:|---:|
    | proto5，E＝16 | 1.928 秒 | 120.5 秒 | 0.481 核 |
    | proto5，E＝100 | 6.590 秒 | 65.9 秒 | 0.848 核 |
    | proto5，E＝500～1000 | 28.79～56.54 秒 | 57.58～56.54 秒 | 0.965～0.982 核 |

    因此「一到兩分鐘」符合所列情境，但 100 顆那列不是「滿 1 核」，「不管開幾顆」也過廣：少於 16 顆會更慢。proto5-2 的四次存檔只給約 74 ms；即使加原式的 40 ms，也不能導出隨 E 變成 1.15／1.4 秒。`500 × 40 ms ÷ 1.4 s = 14.29` 算術正確，分母卻沒有依據。

    **依據：** `measure.md:67–78`；`proto5-2/spec/kernel-tick.md:61–64` 只給操作量，沒有每事件耗時。

    **建議改法：** 將 proto5-2 格長列為明確假設，補逐事件成本或改列不同格長下的範圍。「14 核」改成「假設每格 1.4 秒時，估需約 14 CPU 秒／秒」，不能當作已量到的效能。

11. **〔建議〕A、C、D 的量測標籤應收斂，避免把小型基準說成完整成本。**

    **位置：** `proto5-2/notes/2026-09-24-idle-wait/measure.md:5,21–23,48–63`；`exp/c_ledger.py:20–33`；`README.md:39`

    **現象：**
    - A 的「不寫任何檔」不正確：成功拿 tick 鎖會截短並寫入 `.tick.lock` 的 pid。
    - C 只放大 procs／queue，保留樣本的 cpu 表及出貨箱；不是各種 cpu 數下都有效的完整帳本模型，量到的也是牆鐘時間。
    - D 的 3 µs 是**空回音目錄**；有大量回音時還有列舉、歸屬、去重與查原單成本。

    **依據：** `proto5/lib/aos_agent_runtime.py:40–58`；`exp/c_ledger.py:23–33,44–54`；`exp/d_peek.py:49–58`。

    **建議改法：** 改成「除鎖檔外不寫業務狀態」；C 標示為序列化樣本估算，並另量 CPU 時間；D 清楚限定空目錄。tmpfs 與無 fsync 的 ext4 接近，只能支持本次測試不是同步落盤主導，不能證明完全沒有檔案系統成本。

12. **〔必修〕方案 (a) 少了投單去重與 ack 的責任約定；不是單純改成 `add --once`。**

    **位置：** `proto5-2/notes/2026-09-24-idle-wait/README.md:28–35,41–42`

    **現象：** 若沿用 `agent-<名>` 且舊反覆行程還在，once 一律撞 `AlreadyExists`；即使已撤掉，喚醒員重複掃到同一個回音，也可能在上一格 once 尚未收尾前重投。once tick 的執行回音是另一張回音，現有 agent 只會 ack batch calls，不會代喚醒員清它。

    **依據：** `proto5/lib/aos_kernel_ledger.py:54–67`；`proto5/spec/kernel/syscall.md:7,13`；`aos_agent_batch.py:114–123`。

    **建議改法：** 定義每 agent 一筆在途 tick、穩定且可恢復的 request 身分、完成後由喚醒員 ack；或明確採無 id notification 並說明如何追蹤完成。比較表也應修正：once 仍可沿用 kernel 的池選擇與派工；真正不能直接沿用的是跨多次 tick 的 fails／bad 等持續狀態，不是所有池邏輯都要重做。

13. **〔建議〕D 的 `peek` 只能拿來量成本，不能直接當喚醒判斷。**

    **位置：** `proto5-2/notes/2026-09-24-idle-wait/exp/d_peek.py:24–31`

    **現象：** 三種可恢復狀態都可能得到 false：`sent=false` 尚未送完；全部 call 已 done 但還沒 ack；全部已 ack 但尚未 settle。它們可能已沒有可掃到的新回音，照這支函式排程會一直睡。

    **依據：** `proto5/lib/aos_agent_batch.py:127–156` 分別先補 ack、補 send、最後 settle；`proto5/spec/aos-agent/collect.md:7–12`。

    **建議改法：** 在腳本與量測結論明寫這只是「純等待樣本」基準。若拿來實作 (a)，上述狀態都須保守叫醒；最好與 agent 共用判定，避免另維護一份不完整狀態機。

14. **〔建議〕收斂延遲承諾與修改規模；cpu-notify 相容不等於保證下一格執行。**

    **位置：** `proto5-2/notes/2026-09-24-idle-wait/README.md:31–36,59,64,67`

    **現象：** (b) 與 cpu-notify 的分工沒有根本衝突：通知／巡檢負責找到工具回音，出貨後再喚醒 agent。但巡檢與 `recent` 只查 busy cpu，救不了已停在 delayed、且喚醒遺失的 agent。喚醒也只是提早取得排程資格，池滿或 `woken` 被轉成普通 interval 時，不保證下一格派出。「20～30 行」則未涵蓋出貨資料、取消、去重、版本相容等必要改動。

    **依據：** `proto5-2/spec/kernel-tick.md:23–38,49–59`；`cpu-notify.md:59–62`；`proto5/lib/aos_kernel_info.py:160–183`；`aos_agent.py:91–108` 目前沒有停車能力探測。

    **建議改法：** 改寫成「喚醒後最早下一格可派，仍受池容量限制」；列出完整狀態轉移、能力標記與崩潰測試後再估工。(c) 也應區分調大 interval 與前置快退：後者不必讓有事的每一步都變慢，只是仍解不了 kernel 的三次存檔。

總評：(b) 的方向可行，「落地後喚醒＋running 時記旗標」是正確核心，但目前還不足以宣稱不漏喚醒。必須補齊喚醒的持久化、所有終局回音路徑，以及 ready 去重，才能延伸到崩潰與池式排程。三次存帳本、約 56 ms 與 proto5 一至兩分鐘的粗估有依據；實驗 B 的精確數值與 proto5-2 的 14 核則需要降格標示或補量測。現有 ack／sweep 順序沒有發現會吞掉未收結果的問題，無須為了停車而重寫這部分。