# SESSION-LOG — 進度日誌（hub）

← [AGENTS.md](../AGENTS.md)｜[INDEX](INDEX.md)

**只放「還沒完成」的活狀態**（in-flight / open）。完成的不留這裡——過程細節交給 git log（若有「已落地功能目錄」則濃縮一句進去）。待**使用者**親自驗證／做的另見 [WAIT_USER.md](WAIT_USER.md)。

> **膨脹就拆**：本檔若過大，就在 repo 頂層新立 **`session_logs/`** 資料夾，按工作流／類別**拆檔 + 一個 index 導航**（照 [STRUCTURE「結構整理原則」](STRUCTURE.md)）。

本檔同時 ① 連到各工作流自己的 session-log（若該工作流已長出自己的），② 收**不屬任何工作流**的進度。

> **條目格式**：每條只留**一行 open 狀態 + 指向細節的連結**（設計決策/修了什麼落到該工作流的文件、待使用者驗的進 [WAIT_USER](WAIT_USER.md)）。完成即整條刪除。

## 最新進度

- **proto8（主線）**：10-11 使用者三輪口述已記進 [restart](../proto8/thinking/2026-10-11-restart.md)（§3c～§3h、§3g.1～3g.14），定下的進 [CONCEPTS](../proto8/CONCEPTS.md)；圖解：概念 https://claude.ai/artifact/QJjGNnKFhKeS7r1f5bHzu7 、實作 https://claude.ai/artifact/ATizWpsmAa2qutXWZ2owjm 。PLAN 擱置（[診斷](../proto8/thinking/2026-10-11-why-wrong.md)）。**下一步等使用者開口**：他說「先做 demo」但還沒說開始；restart §4 列了他停在半路的幾處。10-12 使用者說 AI 問的四題沒用，questions.md 已刪，不再追。10-12 照使用者選的「先看懂現有 code」做了一頁現況導覽（daemon／tick-tock／C++ loop，只描述不提改法）：https://claude.ai/artifact/LueXKAUcH7bAhYNjCKfwvz ，使用者看完說「就這樣」。10-12 使用者說 proto8 開工、用 Python：指示詞 lib 已從 proto7-2 拿進 [proto8/lib](../proto8/lib/README.md)，同日照使用者要求精簡成一檔：只留 $ref／$at／$env，入口 `resolve(doc, base_dir)` 解整份。接著 inst（[aos_inst.py](../proto8/lib/aos_inst.py)）：選項改平的 key、基準 `--base inst|cwd`、跑法最小；之後使用者改：拿掉 --base 一律呼叫者 cwd、cwd 沒寫就繼承、串流從 cwd 算；結束碼分工＝子程式的碼只進 exit 檔、命令列 0／1 只說 aos_inst 自己；exit 寫不進去不管；加 timeout_ms、timeout_grace_ms；被訊號停掉不代寫 exit；之後使用者要求 proto8 測試全刪（殘留過去的想法），目前沒有測試。之後使用者再改：run() 不回東西；exit 被訊號停掉改寫 128＋N。使用者講了理念——aos_inst 跑起來就「變成」JSON 指定的東西，JSON 只寫不一樣的，其他從 aos_inst 繼承，怎麼管它由啟動的人決定；所以子程式留在 aos_inst 的行程群組（不自成一群）、拿掉 kill_leftover 與 JSON 裡的 timeout_ms／timeout_grace_ms；Python 只留一個 run()，參數只放「非在 run() 裡做不可的事」：timeout_ms、grace_ms、forward_signals（命令列＝forward_signals=True，收到訊號轉給子程式、照樣寫 exit）。再改：exit 不 fsync；find() 回 realpath 當 daemon 的 id；run() 加 stop（停止鈕）。daemon 構想（使用者口述，還沒做）：拿 run() 當 lib，外包何時跑／幾次／間隔，以 inst.json 的 realpath 當 id 管每個實例；控制＝增刪查改實例（含執行方式）、暫停繼續、加減次數；刪／暫停時留選項「是否等這次跑完」（不等＝按 stop）。kill_leftover 之後可能回來。daemon 啟動時吃 config：控制要吃哪個資料夾、stop 幾秒檢查一次（→ run() 加了 stop_poll_ms）等。同日 daemon 做出來：aos_loop（實例表＋重複執行，lib；照 10-11「loop 變成 daemon 的 lib」）、aos_daemon（config＋控制資料夾 in/out）。丟檔規矩使用者定：控制資料夾不分 in/out，處理完 名字.json 改成 名字.json.done（內容換成回覆）；不規定寫的人怎麼寫（. 開頭的不讀）、不 fsync。多執行緒的四條規矩寫進 lib README。意外錯誤使用者定：控制資料夾看不了／讀不到不掛、stderr 印一次、不建回來；回覆寫不了就把指令改名 .done，改名也不行就 let it go；指令與實例沒料到的錯記成 Internal、照常繼續。控制格式統一（使用者五項都要）：指令一律 {op,id,...}、id 什麼寫法都收（find 轉 realpath，target 拿掉）、執行方式收進 how、times op 改名 add_times；回覆 {request, ok, result} 或 {request, ok, error:{code,msg}}。.done 放回覆、不合法也變 .done，使用者說這樣就好。其他預設（實例表只在記憶體、每次重讀 inst.json、被收掉也算一次、相對路徑從 daemon cwd、只有「馬上跑＋間隔」、結束全收、沒碰權限）使用者說「這樣就好」。使用者明說不做：_metainfo、AOS_DIR（原 AOS_DIRNAME）、非同步啟動。10-12 使用者再定：inst 不再加東西（直接跑普通檔不該做、-- 參數不碰、字串進出〔舊 run() 的 input_bytes〕不管）；daemon 加 save／load 指令（起來時表是空的，config `load` 當語法糖、失敗＝起不來；config `save`＝收到 SIGTERM 時先存，SIGINT 不存）；指定時間跑、Linux 權限之後再說；kill_leftover 照 agent 評估做了：run() 加 new_session（預設關，start_new_session，整群送訊號、結束後整群補 SIGKILL、收屍前先清所以群組號碼不會被拿走），loop 固定開，命令列與 JSON 不變；load 任何一點不對（含 inst.json 不在）就整個回 error。demo 在 proto8/demo。demo 回報的三個不順，使用者選：寫一半被讀到不改（寫的人負責，文件寫明）；pause／remove 等子程式真的停了才回（指令檔留原地、停了才寫 .done，remove 回 state＝removed）；set／resume／add_times／pause／remove 回狀態物件（id、state 排前面）。使用者再定：id 只收絕對路徑（inst.json 或它的資料夾，相對＝FieldType）；自動測試可以做（proto8/lib/tests，unittest）；aos_inst 自己出錯的那次下一次至少隔 error_wait_ms（預設 1000，防空轉）；多個 daemon 搶同一個 control_dir、daemon 被 SIGKILL 留下子程式、指示詞串字串——都不管。10-12 使用者口述 tasks：跟 daemon 的 save（語法糖）是兩碼事，像 lisp 的基礎函數；每支跟 aos_inst 一樣是獨立程式、寫在 inst.json 的 argv[0]（tasks 是統稱，會有 aos-seq 之類），指示詞跟它無關。做進 [proto8-1](../proto8-1/README.md)：aos-seq（像 &&）、aos-par（等全部、照參數順序第一個非 0），先全部驗過才跑、收到訊號全收掉回 128＋N、子程式不開 new_session；為了拿結束碼，proto8/lib 的 run() 改回傳結束碼（推翻先前「run() 不回東西」，使用者說這樣就好）。使用者再定只做最精簡的：加 aos-if（COND THEN [ELSE]，沒 ELSE 不成立＝0）、aos-not；retry／timeout（要數字參數）、while、race 等不做，daemon 不管。10-12 使用者定結束碼三項：aos_inst 命令列退出碼＝子程式的碼（變成它；舊的 0／1 分工作廢）；aos_inst 與 tasks 自己出錯照 Unix 包裝程式慣例 127＝找不到程式、126＝不能執行、125＝其他（`exit_code()`）；loop／daemon 狀態加 `last_code`（save／load 也帶）；daemon 自己的退出碼不動。子程式自己宜只用 1～123。daemon 退出碼不改（使用者定）。demo（proto8-1/demo，15 條發現）使用者說照建議：錯誤訊息帶 inst.json 路徑已修，其他維持或留到 tick-tock。**下一步：tick-tock**——過去作用與剝掉跑任務後剩什麼的調查記在 [thinking 10-12](../proto8/thinking/2026-10-12-tasks-ticktock.md)；使用者說「我想想」，等他開口。
- 10-12 清帳（使用者說）：proto7-2 頭腦風暴題（抽屜／選單／32 份文件）忽略、不再追；WAIT_USER 舊帳全清；proto6 不管。10-10 留下的待辦候選（astra-8 剩項、包間互相 import、轉址 stub 等）屬 proto7-2，一併不追，原文見 [10-12 封存](session_logs/2026-10/2026-10-12.md)。
- 10-09 留下的約定（全文 [→](session_logs/2026-10/2026-10-09.md#2026-10-09)）：合併用 `../aos-wt/merge.sh <分支>`；對使用者一律 ELI5、少用隊名代號；`proto7/user-advice.md` 不碰。

其餘（open 已解／無）與全文索引 → [session_logs/](session_logs/README.md)

## 各工作流 session-log

> 某工作流長出自己的 `session-log.md` 後，在這裡加一列。一開始是空表很正常。

| 工作流 | session-log | open 摘要 |
|--------|-------------|----------|

## 不屬任何工作流的進度

- （無）
