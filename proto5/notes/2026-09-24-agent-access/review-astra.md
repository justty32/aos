方向可行：用 directives 描述映射、用 bwrap 執行隔離，符合使用者定調；最小版也確實走得通。現在不能直接採信的是「表外一律碰不到」「模型不會看到真路徑」「開放 self 後蓋幾個唯讀檔就安全」這三個保證。完整版還沒釐清設定在哪一刻解析、怎麼交給 `aos-jail`，因此「下一次叫工具生效」與範例的操作手續尚未閉合。本次只讀文件與程式，沒有改檔或重跑會寫檔的實驗；需要實機驗證的地方另標「待確認」。

以下提案檔名相對 `proto5/notes/2026-09-24-agent-access/`；規範與程式路徑相對 repo 根目錄。

**必修**

1. **沒有 bwrap 時，到底拒跑還是放行，文件互相矛盾。**  
   **問題 →** `README.md` §7 題 1 預設拒跑；`options.md:63` 卻說退回工具檢查＋chdir。  
   **為什麼 →** 後者會讓 bash 恢復宿主權限，原本「不能碰 amy」的設定立即失效；`check` 警告無法補救。  
   **建議改法 →** 統一成「要求隔離的工具，隔離建不起來就拒跑」。最小版直接執行 bwrap，本來就不需要降級分支。

2. **保護 `access.json` 本身不夠，必須保護所有會決定權限與執行內容的來源。**  
   **問題 →** `README.md:48–52` 只列家中的固定檔；`examples.md:73–77` 又允許映射引用共用檔。  
   **為什麼 →** 若 `current-ws.json`、被引用的 `_meta`、工具 JSON 或程式落在可寫 workspace，bash 可以先修改它，下次就由牢外的 aos-agent／aos-jail 讀取。改映射能掛入更多目錄；改工具 `_meta.argv` 更能直接移除 bwrap。相同資料若另有可寫別名，單一路徑上的唯讀掛載也擋不住。共用工具被下毒後，受影響的不只 amy。  
   **建議改法 →** 將工具定義、執行程式、映射及其遞迴 `$ref` 來源列為受信任控制資料；禁止與可寫映射重疊，包括祖先目錄、另一個別名與可替換的 symlink 路徑。保護必須涵蓋全部工具，不能只替 base 七支加牆。既有硬連結風險可以保留為明確限制，不能把一般可寫引用也歸成「人為佈置，不處理」。

3. **`self` 可寫的黑名單漏掉控制檔，也沒處理檔案不存在與原子替換。**  
   **問題 →** `README.md` §7 題 2、`examples.md:61` 沒列 `.tick.lock`、`paused`、`resumed`、輸入與門檔；人格、記憶、工具也不一定放在慣例路徑。  
   **為什麼 →** 工具可以建立 `paused` 讓自己停擺；刪掉再建立 `.tick.lock` 會破壞「所有 tick 鎖同一個檔」的前提。不存在的保護檔若略過掛載，工具之後仍能建立；若不略過，合法的新家可能直接跑不起來。`state.json`、記憶等還會被牢外程式原子替換，實驗 3 只測當下寫、刪、搬，沒驗證替換後的狀態。  
   **建議改法 →** 優先採「整個 self 唯讀，只另開明確的筆記／資料子目錄可寫」。若仍採黑名單，須依解析後的實際路徑保護，並定義缺檔與替換行為。  
   **待確認 →** 在一次持續運行的 jail 中，由牢外以暫存檔＋rename 更新被蓋住的單檔，再檢查牢內讀到哪個 inode、是否仍唯讀，以及其他別名能否寫入。不能把實驗 3 當成這項保證。  
   依據：`proto5/spec/agent/layout.md`、`proto5/spec/aos-agent/tick.md` §2.1；`proto5/lib/aos_agent_runtime.py:40`。

4. **牢外開好的標準串流是明確例外，不能仍宣稱「表外完全碰不到」。**  
   **問題 →** `experiment.md:41` 正確說串流能穿過 bwrap，但沒有交代留下的能力。  
   **為什麼 →** 工具本來就持有寫入 `work/N.out`、可能寫入 `log/` 的 FD，唯讀覆蓋 `work/` 不會撤銷這些既有 FD。`aos-exec` 開輸出檔會跟隨 symlink；若工具能事先改到 work、log 或其其他可寫入口，就可能讓牢外執行器替它開啟錯誤目標。反過來說，在這些路徑受保護時，模型 arguments 只是 `.in` 的內容，**不會單憑一段路徑文字就改變 stdout 目的地**。  
   **建議改法 →** 明列「受控 stdin／stdout／stderr」為例外；保護輸出檔及父目錄、禁止非必要 FD／目錄 FD 流入。若需要嚴格隱藏宿主路徑與限制檔案操作能力，使用牢外代理的 pipe，而非直接交入一般檔案 FD。  
   **待確認 →** 以實際 base bash 的行程樹測 `/proc/*/fd`：能否看到宿主檔名、重新開啟原本唯讀的 `.in`、接觸父工具的串流。能否重開還受 inode 權限與 proc 存取檢查影響，不能直接斷言可任意寫宿主。  
   依據：`proto5/lib/aos_agent_batch.py:47–65`、`proto5/lib/aos_exec.py:366–397`；[Linux 的 proc FD 說明](https://man7.org/linux/man-pages/man5/proc_pid_fd.5.html)。

5. **執行環境的額外掛載與通訊入口必須納入邊界。**  
   **問題 →** `README.md:31、41` 的保證過強；`exp/exp2.sh` 整份唯讀掛 `/etc`，`exp/exp4.py:26–30` 則掛 `/usr`、新 proc、dev。  
   **為什麼 →** 唯讀只防寫，不防讀設定或憑證。`/usr` 也不能取代其他隔離參數；新 PID namespace＋新 proc 和直接掛宿主 `/proc` 是不同結果。即使 `net:false`，映射目錄若含可連線的 pathname Unix socket，仍可能透過宿主服務執行操作；唯讀掛載不等於禁止連 socket。`net:true` 更是共用宿主網路，不只是「可以下載套件」。  
   **建議改法 →** 明列「使用者映射＋固定執行環境＋受控串流」三類可見資源；避免整份掛 `/etc`，保留 `--proc /proc`、`--dev /dev` 的精確做法；列出 socket／FIFO 等通訊入口限制。真路徑保證改成「提供穩定工具路徑」，不要保證 proc 資訊、錯誤或檔案內容永遠不洩漏宿主路徑。  
   依據：`options.md` §b2 與逃逸表；[bubblewrap 官方安全限制](https://raw.githubusercontent.com/containers/bubblewrap/main/README.md) 明確將安全邊界交由參數與掛入資源決定，特別提醒 socket 能帶來牢外執行能力。

6. **最小版與完整版目前具有不同的生效時機，不能共用同一句承諾。**  
   **問題 →** `README.md:49`、`examples.md:22` 說下一次叫工具生效、已送出的批照舊；但完整版又說 `aos-jail` 執行時讀表。  
   **為什麼 →** 最小版在產生 `work/N.inst.json` 時將 `$ref` 解成字面參數；檔案一旦存在，崩潰恢復直接沿用，即使尚未成功送單也不重解。完整版若只把表的路徑寫入 inst，已排隊但尚未執行的工具反而會讀到新設定。同一批逐件產生 inst，也可能跨越一次設定更新，混用新舊映射。正在跑的 jail 則不會因改表而撤銷舊 mount。  
   **建議改法 →** 明選一種完整版契約：送件時解析並保存快照，或執行時解析最新設定。分別說明排隊、半批送件、重送與正在運行的情況；若要求整批一致，須使用同一份解析快照。緊急撤權另訂取消／終止步驟，不能靠改表；`aos-agent stop` 也不會停止已送出的工具。  
   依據：`proto5/spec/aos-agent/send.md` §5.2–5.3、`register.md`；`proto5/lib/aos_agent_batch.py:81–108`。

7. **刪除目前 cwd 的操作不完整；實際修改次數應如實列出。**  
   **問題 →** `examples.md:40–49` 先 `rm ws` 再 `set other`，輸出卻直接顯示 `cwd: other`，沒有任何規則或指令負責這次變更。  
   **為什麼 →** 中間狀態必然缺少 cwd 映射；第二個 set 之後，原本的 `cwd:"ws"` 也不會自然變成 other。多工具並行或下一格 tick 恰好介入時，就會跑不起來。  
   **建議改法 →** 提供一次原子更新 mounts＋cwd 的方式，或明訂刪除目前 cwd 時拒絕操作並給修法。將各例手續補成：

   | 情境 | 實際需要的修改／指令 |
   |---|---|
   | 例 1 甲、例 3：保留 ws 換來源 | 一個映射檔，一次編輯；完整版可一次 `set` |
   | 例 1 乙：ws 改成 other | 同一檔須改 mounts 和 cwd；現有兩次修改指令不足，`ls` 只是查詢；通知另一次 `say` |
   | 例 2：開放 self | 完整版一次 `set`；前提是第 3 點的保護契約完成 |
   | 例 3：多 agent 共用映射 | 初次每個 agent 都要配置引用；完成後才是改一個共用檔 |
   | 例 4：模型工具別名 | 每個需要別名的 agent 各改一次 `info.json`；目前版本不支援 |
   | 最小版增加其他映射 | 一份工具 JSON 內七條 argv 都要調整；可能另改 base root，不能只算改 access |

8. **完整版沒有接通宿主路徑、牢內路徑與解析環境。**  
   **問題 →** `examples.md:86` 讓 `AOS_TOOL_DIR` 拼出宿主程式路徑，再直接交給 `aos-jail --`；`README.md` §6 沒定義它如何找到 agent 家與 access。  
   **為什麼 →** 程式即使在宿主存在，掛成 `/work/util` 或 `/opt/tools` 後，原本的絕對路徑在牢內也不存在。若由 aos-jail 解析 `$env`，它看到的是工具池經 `clear` 後的環境，並非現行 `_meta` 的 tick 環境；`AOS_AGENT_HOME`、`AOS_TOOL_DIR` 又被定義為只供送件解析使用。  
   **建議改法 →** 寫出一份完整可執行契約：誰解析 access、相對路徑中心、`$env` 來源、如何傳 agent 家／表的位置、工具程式掛在哪裡，以及最後使用的牢內 argv。外層 inst cwd 與 bwrap 的 `--chdir` 要分開，不能把 `/work/ws` 填進牢外 inst.cwd。  
   依據：`proto5/spec/agent/info.md` §3.3、`directives.md`；`proto5/lib/aos_inst.py:123–142`。

9. **「共用工具夾可改名」還沒被實際案例涵蓋。**  
   **問題 →** `examples.md` 例 4 處理的是 `function.name` 別名，不是把 `util-tools/` 改成另一個資料夾名。  
   **為什麼 →** 實體改名後，每個 agent 的 `info.tools` 路徑都可能失效；access 的 util 來源、硬編碼的程式路徑也可能要改。只新增 `AOS_TOOL_DIR` 不能修復「工具 JSON 已經找不到」這一步。  
   **建議改法 →** 補一個實體資料夾改名案例，逐項列出引用。可以由受保護的共用設定提供工具檔路徑字串，讓各 agent 透過 `$ref` 取得；初次接好後，才有機會做到一次搬移＋一次共用設定更新。`$ref` 應取路徑字串，不能直接取工具陣列放進 `info.tools` 的元素。

10. **新版 `$opt` 與工具來源資訊要同步兩端讀取契約。**  
    **問題 →** `README.md:89–94` 有列部分修規範工作，但「新增選項」不只是把目前的空選項表填滿。  
    **為什麼 →** 現行 `info.md` 明訂沒有欄位吃 `$opt`；程式先遞迴解 `tools`，並在 `_ContentContext` 拒絕選項。`aos-llm call` 和 aos-agent 共用這份工具載入流程，兩邊必須看到相同別名。為了提供 `AOS_TOOL_DIR` 而記錄來源時，若塞進一般 key，現行規範會把它送給模型；放進 `function` 內的底線 key 也不會被目前的頂層過濾去掉。  
    **建議改法 →** 修改 tools 元素的專用解析流程，定義 `only`／`as` 的順序與錯誤；兩端共用改名結果。來源資訊存內部結構，或會被剝除的工具頂層私有 key。保留 `_meta` 禁寫 stdin／stdout 的規定；新增 `access` 在舊程式會被忽略，也應明說不是已經有效。  
    依據：`proto5/spec/directives/opt.md`、`proto5/spec/agent/info.md` §3–3.3；`proto5/lib/aos_agent_home.py:61–100、173–175、237–242`。**物件型 `$opt` 本身符合 directives 機制，衝突在 agent 宿主規範。**

**建議**

1. **實驗 1 #3 的結論成立，但適用範圍寫太大。**  
   **問題 →** `README.md:60` 概括成共用檔內路徑都相對 agent 家；`experiment.md:22` 又說改 cwd 後「不能」再用相對 `$ref`。  
   **為什麼 →** 實驗的引用位於 `cwd`，所以確實相對 agent 家；之後 argv／envs 的引用以解析後 cwd 為中心。相對 `$ref` 仍然可用，只是中心變了；實驗 #9 已示範。`$ref:""` 則是目前文件，不能混為同一件事。  
   **建議改法 →** 改成三條精確規則，保留 #3 成功結論。實驗只直接呼叫解析器／送件函式，也應避免將它描述成已驗完整 tick、排隊和恢復流程。依據：`proto5/lib/aos_inst.py:109–142`、`aos_directives.py:241–267`。

2. **環境圖將「同池」誤寫成「繼承 tick 的環境」。**  
   **問題 →** `env-flow.md:23`、`README.md:72` 說工具因此拿得到 tick 的 `AOS_KERNEL_HOME`。  
   **為什麼 →** tick.json 的 envs 只加到那次 tick 子行程，不會回寫 cpu；同池工具是另一個工作。工具是否拿到 K，仍取決於 daemon／cpu 原本的環境與工具 envs。  
   **建議改法 →** 改成「可能繼承 cpu 的敏感環境」；保留 clear 建議。另修 `env-flow.md:48`：既有 cpu 改環境，要改 `K/cpus/<c>/inst.json` 再重拉，單改 kernel info 後 halt／boot 不會覆蓋既有設定。依據：`proto5/spec/cpu/methods.md` §4.1、`kernel/home.md` §1.1。

3. **`check` 應分辨外層包裝可執行與牢內工具可執行。**  
   **問題 →** 加上 bwrap 後，現行 check 主要只能驗到 argv[0] 的 bwrap／aos-jail。  
   **為什麼 →** 綠燈不代表牢內 python、程式、動態函式庫或 cwd 存在；CLI 的解析環境也未必等於 tick／工具池。  
   **建議改法 →** 補查映射與受信任程式的靜態契約；bwrap 可用性探測使用固定無副作用命令，不執行任意工具、不建立 workspace，維持 check 唯讀約定。不能確認的環境依賴印 warn。依據：`proto5/spec/aos-agent/cli-check.md` §1.7。

4. **還需區分資料夾隔離、並行正確性與資源限制。**  
   **問題 →** `options.md` 的「擋住」容易被理解成不會影響其他 agent／kernel。  
   **為什麼 →** 兩個工具仍可同時改同一 workspace、互相覆蓋成果或交換路徑；可寫空間、輸出、程序數與記憶體也沒有因 bwrap 自動取得配額。這些不一定是逃出 mount namespace，仍可能拖垮其他工作。  
   **建議改法 →** 明說共享可寫資料的競態仍存在，先寫再跑應分批；將磁碟／輸出上限、程序與記憶體限制列成另一層保證。不要把「模型一次只叫一支」當作強制同步機制。依據：`options.md` §b2；另一隊 `proto5/tools/README.md` 的平行工具說明。