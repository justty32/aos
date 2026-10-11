← [thinking](README.md)｜astra（gpt-6-astra high，唯讀）審 PLAN，2026-10-11

# proto8 規劃提案審查

以下以 [restart.md §2](/home/lorkhan/repo/simple_tools/aos/proto8/thinking/2026-10-11-restart.md:41) 為最高依據；九月草稿只作補充，PLAN 的候選設計不視為已拍板。

## A. PLAN 哪裡違背或偷渡

- **把「冪等性」從任務特性變成入場條件。** [PLAN L120](/home/lorkhan/repo/simple_tools/aos/proto8/PLAN.md:120) 說「任務要自己冪等」，但 restart **§2.7、§2.9** 接受一般 POSIX 行程，並把副作用、冪等性列為各自不同的特性；可以不做自動恢復，不能因此要求所有任務都能安全重跑。

- **把「數模型節點」偷換成「量出可預測性」。** [PLAN L91](/home/lorkhan/repo/simple_tools/aos/proto8/PLAN.md:91) 用節點數驗證「可預測性可量」，但 restart **§2.14、§2.16** 說的是對誰可預測、流程哪些部分已知，以及進入不確定節點的可能性；一個模型節點迴圈一百次，不會因為只算一個節點就比較可預測。

- **`capacity` 欄位本身不構成「核心多認第二種東西」。** [PLAN L132](/home/lorkhan/repo/simple_tools/aos/proto8/PLAN.md:132) 明說容量由資源任務自己管，符合 restart **§2.8、§2.9**；真正的缺口是排序結果如何影響資源取件，不能光憑多了一個標籤就判違背。

## B. PLAN 漏掉了什麼

- **缺「哪件工作先交給哪個資源」，目前只有「先起哪個行程」。** [PLAN L72、L89](/home/lorkhan/repo/simple_tools/aos/proto8/PLAN.md:72) 的 `order.json` 排資料夾，沒有交代 `llm/in/` 已有兩個請求時誰先被處理；restart **§2.7、§2.18、§2.19** 要排的是資源使用，尤其是昂貴的模型與工具呼叫。

- **daemon 的責任沒有落點。** [PLAN L122](/home/lorkhan/repo/simple_tools/aos/proto8/PLAN.md:122) 把 daemon 延後，§3 卻已由 tick 起行程、追蹤退出；依 restart **§2.5**，可以先縮小實作，但應交代這些 Linux 操作屬於基建層，之後時空層透過什麼介面使用。

- **「停止時間」與「看指定 tick 的世界」只剩 zip 檔名。** [PLAN L75、L92](/home/lorkhan/repo/simple_tools/aos/proto8/PLAN.md:75) 沒說何時確認停妥、仍在跑的任務能否繼續改檔，也沒說哪些 tick 可以回看；restart **§2.11、§2.12** 要的是可辨認的時間點，`unzip -l` 只能驗證壓縮檔列得出內容。

- **「生成排序程式的程式」尚未成為體系內的任務。** [PLAN L90](/home/lorkhan/repo/simple_tools/aos/proto8/PLAN.md:90) 只說「讓模型生成一版」，沒有指出是哪個 POSIX 任務呼叫模型、產出程式；若只是開發 AI 在外面代寫，就還沒驗證 restart **§2.8、§2.10** 說的那個生成器。

- **任意資源的範圍沒有安排驗證。** [PLAN L45、L88–92](/home/lorkhan/repo/simple_tools/aos/proto8/PLAN.md:45) 放了 `human/`，實驗卻只有模型容量一；restart **§2.3、§2.4、§2.7** 特別提出能力不同、會休息、可能等很久的人類資源，PLAN 至少應標明這部分尚未驗證。

## C. ≤200 行的 tick 做得出來嗎

**做出受限的玩具迴圈是合理的；目前不足以承諾整份 PLAN 的行為都能裝進去。** [PLAN L78](/home/lorkhan/repo/simple_tools/aos/proto8/PLAN.md:78) 把差異說成「順序表和打包」，但 restart **§2.5、§2.11、§2.12** 要的時間邊界，還有以下決定沒寫清楚：

- **排序表何時生效：** [PLAN L72](/home/lorkhan/repo/simple_tools/aos/proto8/PLAN.md:72) 先讀表才起排序器，日記 L24 卻當回合產表、當回合使用；最簡是明訂本回合產表、下回合生效，第一回合才按名稱掃描。（restart **§2.8、§2.10、§2.12**）

- **誰讓排序器和新任務繼續被發現：** [PLAN L33](/home/lorkhan/repo/simple_tools/aos/proto8/PLAN.md:33) 有表後可能永遠漏掉新資料夾，甚至漏掉排序器自己；最簡是排序器每次重掃任務，並把自己列入下一回合清單。（restart **§2.8、§2.10**）

- **同回合寫出的檔能不能立刻被讀：** [PLAN L73、L80](/home/lorkhan/repo/simple_tools/aos/proto8/PLAN.md:73) 的依序啟動不能保證「下回合問模型、再下回合讀回覆」；最簡是請求帶產生回合，各任務只讀早於目前回合的完整請求。（restart **§2.11–§2.13**）

- **資源究竟照什麼挑請求：** [PLAN L132](/home/lorkhan/repo/simple_tools/aos/proto8/PLAN.md:132) 的「不排兩個」沒有解決同一個 `llm/in/` 裡的競爭；最簡是排序器輸出請求先後，由資源任務照表取件、自己限制容量。（restart **§2.7、§2.18、§2.19**）

- **兩個寄件者如何避免撞名和半份 JSON：** [PLAN L130](/home/lorkhan/repo/simple_tools/aos/proto8/PLAN.md:130) 的 `<回合>-<序號>` 沒保證跨寄件者唯一；最簡是加寄件者識別，先寫暫存檔再改名，收件者只讀完成檔。（restart **§2.6、§2.18**）

- **期限到了、行程卻沒退出怎麼算：** [PLAN L74](/home/lorkhan/repo/simple_tools/aos/proto8/PLAN.md:74) 沒決定終止、留跑或阻擋下一回合；最簡是標成「仍在跑」、不重起同一任務，並讓排序器看見它仍占用資源。（restart **§2.7、§2.11**）

- **tick 重起時怎麼辨認舊行程：** [PLAN L32、L120](/home/lorkhan/repo/simple_tools/aos/proto8/PLAN.md:32) 的 PID 清單與「重起就好」不足以防止重複啟動；最簡是異常結束後先拒絕自動續跑，確認舊任務已停再重新開始。（restart **§2.5、§2.7、§2.9**）

- **模型生成的排序程式交出壞表怎麼辦：** [PLAN L90](/home/lorkhan/repo/simple_tools/aos/proto8/PLAN.md:90) 沒說非法 JSON、重複名稱或不存在任務的處理；最簡是檢查這三項，失敗時保留上一份有效表並留下可讀錯誤。（restart **§2.6、§2.10**）

- **tock 究竟等退出還是只通知：** [PLAN L74、L131](/home/lorkhan/repo/simple_tools/aos/proto8/PLAN.md:74) 說等任務退出，L98 卻說沿用「只通知不收」；最簡是先用有限任務驗證「回合完成後世界停穩」，把未退出任務的情況另列限制。（restart **§2.11、§2.12**）

- **打包時誰還能寫世界、打包包含什麼：** [PLAN L34、L75](/home/lorkhan/repo/simple_tools/aos/proto8/PLAN.md:34) 把快照放在世界裡，還允許任務跨回合存活；最簡先等寫入者停妥才打包，排除 `snapshots/` 自身，等不到就回報尚未完成快照。（restart **§2.11、§2.12**）

## D. §7 哪些「不做」會在第 2～4 步碰壁

- **「上鎖、並行不做」至少得補檔案交接規則。** [PLAN L121](/home/lorkhan/repo/simple_tools/aos/proto8/PLAN.md:121) 說只有 tick 寫 `.aos/`，L33 卻讓排序器寫 `order.json`，第 3 步還有兩個 agent 共寫 `llm/in/`；唯一檔名與完整檔案發布是必要的，不代表要做一套鎖系統。（restart **§2.6、§2.8、§2.18**）

- **「崩潰恢復不做」可以，「tick 重起就好」不行。** [PLAN L120](/home/lorkhan/repo/simple_tools/aos/proto8/PLAN.md:120) 在第 3 步遇到模型呼叫未完就重起，可能重複呼叫並超過容量；至少要辨認上次未正常結束，不能默認重跑安全。（restart **§2.7、§2.9、§2.19**）

- **不做 grant／holder 可以，但 `usage.json` 不能代替請求狀態。** [PLAN L119](/home/lorkhan/repo/simple_tools/aos/proto8/PLAN.md:119) 的 token 紀錄分不出待處理、處理中、已回覆，第 3 步再次執行 `llm/` 就得避免重複取件；最簡讓資源任務自己保存這三種狀態。（restart **§2.7、§2.8、§2.18**）

- **不做完整錯誤契約可以，但失敗不能只有空白。** [PLAN L125](/home/lorkhan/repo/simple_tools/aos/proto8/PLAN.md:125) 的 `out/exit` 沒涵蓋 argv 根本無法啟動，第 2 步就可能遇到；至少要區分啟動失敗、已退出與仍在跑，讓人和任務看得懂。（restart **§2.6、§2.7**）

## E. 日記裡哪些動作會很煩，或照寫法做不到

- **手算回合、手編檔名、猜回覆位置。** [a-day L19、L24–29](/home/lorkhan/repo/simple_tools/aos/proto8/thinking/2026-10-11-a-day.md:19) 要人知道請求叫 `1832-1`，還直接找到 `1835-1.md`，但模型不保證三回合完成；應讓同一請求識別一路指向狀態與結果。（restart **§2.6、§2.12、§2.19**）

- **早上自己挑畫家，下午又得記得改投 scheduler。** [a-day L42–48](/home/lorkhan/repo/simple_tools/aos/proto8/thinking/2026-10-11-a-day.md:42) 把一般需求入口留給使用者猜，再用「本來就有」帶過分派規則；可以保留直接指定畫家的用法，但自動分派要有明確入口與實際程式。（restart **§2.2、§2.3、§2.10**）

- **複製資源時，連舊工作一起複製。** [a-day L53](/home/lorkhan/repo/simple_tools/aos/proto8/thinking/2026-10-11-a-day.md:53) 的 `cp -r llm llm-local` 會帶走 `in/`、`out/` 與可能的進行中狀態，使用者得自己辨認哪些能留、哪些會重跑；新增資源應能只複製程式與設定。（restart **§2.7、§2.8、§2.19**）

- **改標籤被寫成會自動長出能力。** [a-day L54–57](/home/lorkhan/repo/simple_tools/aos/proto8/thinking/2026-10-11-a-day.md:54) 只改 `model`、`capacity: 2` 就能接兩件、被發現且便宜優先，但 PLAN L132 的程式仍一次只處理一件，也沒定義價格與可替代資源的判斷；這些都要有程式實際讀取並執行。（restart **§2.7、§2.10、§2.19**）

- **換掉模型節點，漏掉真正的寫程式工作。** [a-day L68–74](/home/lorkhan/repo/simple_tools/aos/proto8/thinking/2026-10-11-a-day.md:68) 只改 `steps.json`，沒有建立 `understand.py`，也沒交代輸入輸出怎麼接；restart **§2.16** 說的是替換成可運作的程式，不能只換一個檔名。

- **打包是否完成只能反覆查看。** [a-day L82–84](/home/lorkhan/repo/simple_tools/aos/proto8/thinking/2026-10-11-a-day.md:82) 在 `touch` 後立刻 `ls`，沒有區分要求已收到、世界已停止、壓縮已完成；至少應給可查看的完成狀態及快照位置。（restart **§2.11、§2.12**）

## F. 如果只能改 PLAN 三個地方

1. **重寫 §3：把 tick／tock 的邊界說清楚。** [PLAN L67–80](/home/lorkhan/repo/simple_tools/aos/proto8/PLAN.md:67) 補上排序何時生效、訊息何時可讀、逾時仍在跑怎麼表示、何時能安全打包，並標出 Linux 行程操作屬於 daemon；先把這些行為定清楚，再估行數。（restart **§2.5、§2.11–§2.13**）

2. **重寫 §4：用真正的資源競爭驗證主張。** [PLAN L88–92](/home/lorkhan/repo/simple_tools/aos/proto8/PLAN.md:88) 先有最簡排序任務，再讓兩個請求搶一個模型，改排序後確認實際服務順序跟著改，並加入跨回合等待；節點替換則比較實際流程與行為，不再宣稱數節點就量出可預測性。（restart **§2.7、§2.14、§2.16、§2.18、§2.19**）

3. **重寫 §7：把「不做」改成明確限制與失敗行為。** [PLAN L115–126](/home/lorkhan/repo/simple_tools/aos/proto8/PLAN.md:115) 刪掉「所有任務自己冪等」「tick 重起就好」「沒有並行」這些假設，改寫為不自動重送結果不明的工作、異常停止時留下狀態、交件必須完整；請求狀態仍由普通資源任務管理。（restart **§2.7–§2.9、§2.11**）