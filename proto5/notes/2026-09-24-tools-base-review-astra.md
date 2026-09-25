這組工具已能完成基本 coding 工作；七份工具宣告符合 §3.3，必填參數與主要錯誤訊息也大致清楚。但「檔案工具不能越界」「grep 最多 30 秒」「背景行程都會被清掉」目前都有例外，重裝也存在中斷服務與崩潰後不一致的窗口。**必修 7 條、建議 9 條**。以下以靜態推理為主，另用不寫檔的記憶體替身確認了三項行為；未執行會建立檔案的測試套件。

1. **〔必修〕write／edit 的暫存檔可經符號連結覆寫根目錄外檔案。**  
   **位置：** [_common.py:118](../tools/base/_common.py)。  
   **現象／推理：** 暫存檔名固定為 `<目標>.aos-tmp-<pid>`，以 `open(..., 'w')` 開啟，既不排他建立，也不拒絕符號連結。若預先放置該名稱的連結指向外部檔案，開啟暫存檔便會截斷外部目標；之後 `replace` 甚至可能把連結移成正式檔名。這條不需要在 `resolve` 與寫入之間搶換父目錄。  
   **建議修法：** 在受信任的父目錄 fd 下，用隨機名稱、`O_CREAT|O_EXCL` 安全建立暫存檔，再以 fd 相對操作替換。  
   **缺測：** 預先存在的暫存檔、暫存符號連結、外部檔案內容與權限保持不變。

2. **〔必修〕`realpath` 檢查與實際 I/O 分離，不能保證併發情況下不越界。**  
   **位置：** [_common.py:96](../tools/base/_common.py)、`write:17`、`read:23`、`edit:22`、`grep:49`、`find:63`、`ls:21`。  
   **現象／推理：** `/root/sub/file` 驗證通過後，另一行程把 `sub` 換成指向外部的連結，後續 `open`／`makedirs`／走訪仍會重新解析路徑。單純再呼叫一次 `realpath` 只會縮小窗口。  
   **建議修法：** 以 root fd 為起點逐層開啟並約束解析；Linux 可考慮 `openat2` 的 beneath 限制。搜尋外部程式也需要同等邊界，或明確把承諾限定為「無併發路徑變動時的檢查」。  
   **缺測：** 用同步屏障在驗證後替換父目錄／目標，而非靠隨機壓力測試碰運氣。  
   **已核對：** 無競態時，`..`、外部絕對路徑、展開後在外部的 `~`、指向外部的父目錄連結均會被擋；前綴比對有目錄分隔符，不會把 `/work-other` 當成 `/work`。

3. **〔必修〕grep 繼承 ripgrep 設定，靜態符號連結也可能越界。**  
   **位置：** [grep:18](../tools/base/grep)。  
   **現象／推理：** argv 沒有 `--no-config`，也沒有明確禁止 follow。若 CPU 環境的 `RIPGREP_CONFIG_PATH` 指向含 `--follow` 的設定，搜尋根目錄時便會沿其中的連結讀取外部檔案。`resolve` 只驗搜尋起點，不能擋住這條。這兩項旗標語意已核對本機 `rg --help`。  
   **建議修法：** 加 `--no-config`，固定需要的搜尋行為；測試替代程式入口也應明確區分。  
   **缺測：** 含 `--follow`／`--hidden` 等旗標的環境設定，以及搜尋目錄內的外部檔案、目錄連結。正常預設下，rg、`grep -r`、`os.walk` 都沒有主動遞迴跟隨這些目錄連結。

4. **〔必修〕grep 的逾時失效，stderr 還可能造成死鎖；逾時也可能被報成無匹配。**  
   **位置：** [grep:52](../tools/base/grep)、`aos_exec.py:474`。  
   **現象／推理：**
   - `for raw in p.stdout` 等完整一行或 EOF，期間不檢查 deadline；無輸出、沒有換行都可能卡住。
   - stderr 到 stdout 結束後才讀；大量權限錯誤若填滿 stderr pipe，子行程與父行程會互等。
   - 第一行在 30 秒後才到時，程式先判逾時、尚未加入 `lines`，最後卻回成功的 `No matches found`；已用記憶體替身確認。
   - 外層 60 秒逾時不是完整補救：搜尋程式另開 session，而 CPU 的 `_wait_full` 只砍工具 wrapper 的 pgid，搜尋子行程可能留下。
   
   **建議修法：** 同時以非阻塞方式排空兩條 pipe，讓 deadline 獨立於輸出推進；所有退出路徑都 kill／wait 搜尋行程，逾時明確回 `Timeout` 並保留部分結果。  
   **缺測：** 靜默卡住、stderr 塞滿、超長無換行、延遲第一筆、外層取消後無殘留行程。

5. **〔必修〕`--force` 不是整包原子更新，崩潰可能留下舊 schema 配缺失或新版程式。**  
   **位置：** [aos_agent_tools.py:71](../lib/aos_agent_tools.py)、`spec/aos-agent/tools.md:31`。  
   **現象／推理：** 第 84 行移走舊目錄，第 85 行才放新目錄，期間舊 `base.json` 仍有效；tick 可以拿到存在的工具宣告，卻找不到執行檔。第 86 行刪舊版後，`_work_root` 或寫 manifest 失敗，也無法回復。  
   崩潰留下的狀態依位置而異：`.tmp-*` 殘留、`.old-*` 加缺失正式目錄、新程式加舊 manifest，或 manifest 已寫但 `info.tools` 尚未登記。最後一種重跑不帶 `--force` 又會被 `AlreadyExists` 擋住。  
   **建議修法：** 採版本目錄，讓原子替換的 manifest 指向完整版本；舊版本等在途呼叫結束再清。補上安裝鎖、失敗恢復與殘留辨識。只替兩次 rename 加 rollback，仍解不了讀者看到缺口的問題。  
   **缺測：** 在每個 rename／寫 JSON 前後注入失敗或終止，並讓 tick 同時解析與執行工具。

6. **〔必修〕輸出上限不等於讀取資源上限，read／edit／grep 可先耗盡記憶體。**  
   **位置：** [read:23](../tools/base/read)、`edit:22`、`grep:57`。  
   **現象／推理：** read 即使 `limit=1` 也先整檔讀入、解碼及切行；edit 還保留位置陣列與替換後全文。grep 要先讀完一整行，才截成 500 字。大型產物、巨大單行檔或特殊檔案可在 50 KB 輸出限制生效前耗盡記憶體或阻塞。  
   **建議修法：** read 採分塊讀取；edit 訂可操作檔案大小上限；grep 分塊排空並限制行緩衝；檔案工具拒絕不支援的非一般檔案。  
   **缺測：** 大檔配小 limit、超長單行、FIFO、受限記憶體下的可預期錯誤。  
   **已核對：** bash 的 `Tail` 是有界緩衝，持續 `yes` 不會因收集 stdout 而累積無限記憶體或暫存檔；指令自行寫磁碟則不在這個限制內。

7. **〔必修〕bash「背景行程會被殺掉」的承諾超過實作。**  
   **位置：** [bash:25](../tools/base/bash)、`bash:38`、`bash:82`、`base.json:31`。  
   **現象／推理：** TERM／KILL 能處理同一 pgid 的後代，包括 shell 先退出、孩子忽略 TERM 的情況；但 `setsid` 或另建 pgid 的孩子不在其中。程式第 39 行已承認 `setsid` 逃逸，schema 卻無條件承諾清理。外層取消 wrapper 時，也沒有 signal／finally 路徑替它清掉獨立的 shell session。  
   **建議修法：** 至少修正模型描述與 Timeout 訊息，限定為原行程群組；補取消清理。若要保證整棵工作樹終止，需要 cgroup 等可追蹤的工作容器。  
   **缺測：** 忽略 TERM 的孫行程、`setsid`、外層取消、背景行程關閉輸出後繼續存活。120／600 秒搭配 630000 ms 對正常清理路徑有足夠餘裕，主要問題是行程歸屬。

8. **〔建議〕同檔 edit 與安裝設定更新都有遺失更新的競態。**  
   **位置：** [edit:22](../tools/base/edit)、`aos_agent_tools.py:55`、`:63`、`:93`。  
   **現象／推理：** 兩個 edit 同讀舊內容、修改不同區段，各自成功 rename，後寫者會吃掉前者的修改。兩個安裝也可能同時通過同名檢查，或各自用舊 `info.json` 覆蓋對方登記。  
   **建議修法：** 同檔修改序列化或加內容版本檢查；安裝用 agent 家層級鎖。README 的「一次叫一個」可降低機率，但不能約束其他寫入者。  
   **缺測：** 同檔不同區段並行 edit、兩包同名並行安裝、安裝期間人工修改 info。  
   **已核對：** 單次、無併發時，重寫的是原始 `doc.root`，不會因解析 `$ref` 而攤平其他欄位，也沒有只保留已知 key 的問題。

9. **〔建議〕工作根目錄包含 agent 家的警告漏掉符號連結別名。**  
   **位置：** [aos_agent_tools.py:100](../lib/aos_agent_tools.py)、`:117`。  
   **現象／推理：** 安裝以 `abspath` 的字面字串判斷包含關係，工具實際使用 `realpath`。`--root` 若是指向 agent 家或其上層的別名，可能完全不警告。  
   **建議修法：** 對家與 root 都做相同的 canonicalization，再判斷包含關係。  
   **缺測：** root＝家、root＝上層、兩者任一含連結別名。允許使用這些 root 是規範明訂的行為，本身不算違規；bash 原本也沒有檔案沙盒。

10. **〔建議〕grep fallback 的語法與忽略規則會誤導模型。**  
    **位置：** [base.json:40](../tools/base/base.json)、`grep:27`。  
    **現象／推理：** schema 保證 ripgrep syntax、跳過 gitignore，但 fallback 是 `grep -E`，不讀 gitignore，glob 語意也不同。例如 `\d+` 在兩個引擎不等價，可能成功執行卻漏結果，模型收不到修正提示。README 對 rg 的限定比 schema 準確。  
    **建議修法：** 固定使用 rg，缺少時明確報錯；或宣告共同支援範圍並在 fallback 結果標明引擎與差異。  
    **缺測：** 非共同 regex、gitignore、hidden、含 `/` 的 glob、否定 glob，兩引擎逐項比較。

11. **〔建議〕schema 與上限表不完整，read 的 2000 行硬上限也沒有實作。**  
    **位置：** [base.json:4](../tools/base/base.json)、`read:36`、`tools/README.md:29`。  
    **現象／重現：** 記憶體替身給 2100 個短行，呼叫 `read(limit=2100)` 確實回 2100 行。grep 的 limit 上限 2000、find／ls 的上限 5000 也未寫入 schema 描述；schema 沒有 minimum／maximum，且未知參數會被忽略。  
    **建議修法：** 統一硬上限與預設值，補數值約束、非空字串要求；考慮拒絕未知欄位，避免 `ls({"offset":500})` 看似成功卻一直回第一頁。把 project directory 明定為 configured work root，說明 `.`、允許的根內絕對路徑及越界錯誤。  
    **缺測：** 各上限前後一格、null、未知欄位、schema 接受而實作拒絕的值。`read` 的 NUL 判定僅看前 8192 bytes，README 的「含 NUL」也應補上範圍。

12. **〔建議〕部分非法輸入會漏出 traceback，沒有約定的 JSON 錯誤。**  
    **位置：** [_common.py:29](../tools/base/_common.py)、`bash:25`、`grep:52`。  
    **現象／重現：** `bash` 的 command 含 JSON `\u0000` 時，`Popen` 拋出 `ValueError: embedded null byte`；已直接確認。grep 的 pattern／glob 也有同類問題。JSON 接受的孤立 surrogate 亦可能在編碼時觸發未捕捉錯誤。  
    **建議修法：** 在參數邊界驗 NUL／不可編碼字元，轉為具名 `BadArguments`；設定內容則回 `ConfigInvalid`。  
    **缺測：** 各字串參數的 NUL、孤立 surrogate，以及失敗後 stdout 最後一行仍可解析。現有 `NoMatch`／`NotUnique` 的提示已能指引模型重讀、增加上下文或設 replace_all，這部分良好。

13. **〔建議〕find 會把走訪失敗包裝成完整的成功結果。**  
    **位置：** [find:63](../tools/base/find)。  
    **現象／推理：** `os.walk` 沒提供 `onerror`，無權限或走訪期間消失的目錄可能被靜默跳過，最後仍回 `No files found` 或沒有不完整提示的結果。模型容易把「没搜到」解讀成「不存在」。  
    **建議修法：** 收集走訪錯誤，回 `ReadFailed` 或明確的部分結果提示；find／ls 也宜補 byte 上限，僅限制項數仍可能產生很大輸出。  
    **缺測：** 無權限子目錄、目錄消失、長路徑結果、換行檔名。

14. **〔建議〕工具函式同名有驗，但套件名稱共用檔案命名空間，`--force` 可覆蓋別包。**  
    **位置：** [aos_agent_tools.py:24](../lib/aos_agent_tools.py)、`:48`、`:82`。  
    **現象／推理：** 已裝 `foo` 後，自製套件資料夾叫 `foo.json`，其程式目的地就是原本 `tools/foo.json` manifest。加 `--force` 會把該檔移開再放成目錄；即使兩包函式名稱不同，也會破壞原包。  
    **建議修法：** 限制套件名称，拒絕保留後綴及特殊名稱；`--force` 驗證目的地確實屬於同包。另可提供修復模式處理壞 manifest，目前 `load_llm_view` 會在替換前拒絕它。  
    **缺測：** `foo`／`foo.json`、目的地是檔案或連結、壞 manifest 後重裝。正常情況下，包內重複函式名及其他已啟用檔案中的同名均有檢查，未看到一般單次安裝漏驗。

15. **〔建議〕相較 pi，主要缺口是多處編輯、換行容錯及截斷後的取回能力。**  
    **位置：** [edit:11](../tools/base/edit)、`read:37`、`bash:44`。  
    **現象／比較：**
    - 目前 edit 一次一組替換；查得的 pi `main` 支援多組不重疊 edits、BOM／換行正規化。base 的 CRLF 測試只替換單字，沒有驗模型提供 LF 多行片段時的情況。[pi edit 原始碼](https://raw.githubusercontent.com/badlogic/pi-mono/main/packages/coding-agent/src/core/tools/edit.ts)
    - base 截掉 read 長行後，offset 無法取回同一行後半；bash 丟掉的輸出也無法事後取得。pi bash 會提供完整輸出暫存檔，但引入時需要容量與清理規則。[pi bash 原始碼](https://raw.githubusercontent.com/badlogic/pi-mono/main/packages/coding-agent/src/core/tools/bash.ts)
    - pi read 支援圖片附件；base 只有文字 stdout。這是協定能力差距，不能只在 read 加 base64 就達到同等效果。[pi read 原始碼](https://raw.githubusercontent.com/badlogic/pi-mono/main/packages/coding-agent/src/core/tools/read.ts)
    
    **建議修法：** 優先補長行後續讀取指引、多區段原子 edit、CRLF／BOM 行為；圖片與完整輸出保存另行評估。以上比較對象是本次取得的上游 `main`，不是鎖定版本的 pi。  
    **缺測：** CRLF 多行替換、BOM 開頭匹配、截斷後是否真有可操作的續讀方法。

16. **〔建議〕安裝驗證順序與規範不一致，來源 manifest 還會在驗證後重新讀取。**  
    **位置：** [aos_agent_tools.py:46](../lib/aos_agent_tools.py)、`:90`、`spec/aos-agent/tools.md:26`。  
    **現象／推理：** 規範先驗家、後驗包；實作先驗包、root、AlreadyExists，才驗家。因此多項同時錯誤時，錯誤優先序不同。第 90 行也不是寫已驗過的 `new_tools`，而是重讀來源：中途被改便可能安裝未驗內容，甚至在程式已替換後才拋 JSON 例外。  
    **建議修法：** 統一驗證順序，使用一次讀取並驗證過的 manifest 快照。  
    **缺測：** 家與包同時無效、AlreadyExists 與同名同時成立、驗證後來源變動。其餘 CLI 參數、成功輸出、補 tools 條目、保留舊 config、`--root` 寫絕對路徑的主流程吻合；JSON 語法錯誤回 `JsonSyntax` 則符合 §3.3 的較詳細規定。

測試方面，現有三份套件主要覆蓋正常功能、一般參數錯誤、簡單越界及成功往返。除上述逐條缺測，還應補：根內絕對路徑與 `~`、相似前綴目錄、斷裂／循環連結、write 經外部父連結、find／grep 遞迴外部連結，以及真 daemon／kernel／agent 的 **失敗結果往返**——至少含 `NotUnique`、`ExitCode`、工具自身 Timeout、kernel Timeout 與強制取消，確認 §6.2 包裝後模型仍看得到錯誤與部分輸出。現有四步成功劇本不足以證明模型能自行修正錯誤。

**我沒看的：** 未重跑完整單元／整合測試、真模型測試、CMake／ctest，也未實際製造越界寫入、崩潰或殘留行程；未全面審查 daemon／kernel，只追到本題需要的 CPU 終止路徑。未驗證所有平台、檔案系統與 pi 歷史版本。全程未修改檔案，報告僅輸出於此。