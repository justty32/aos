# proto8 討論紀錄：2026-11-20

← [2026-11](../README.md)｜[thinking](../../README.md)

規矩見 [thinking/README](../../README.md)。這天的每份一列，一句：定了什麼、還有什麼未決。

| 份 | 一句話 |
|---|---|
| [T7 第 9 步回公司（14-真機驗證）](../10/two-machines/14-真機驗證.md#第-9-步回公司那一步-11-20-實跑) | two-machines T7 第 9 步回公司那一步公司機代跑、全過：pull 到 rv day 2、兩台起來不用換台指令、ann 答 back at office、error: 0 行、git status 只有 stack 狀態檔；T7 全部跑完（第 5 步 codex 先前已跳過），~/code/rv 沒 commit、沒 push |
| [初始 kernel＝llm＋權限沙箱（aos-init-kernel-1120）](aos-init-kernel-1120/README.md) | 調查＋發想：今天灌 kernel 實際只灌 llm kernel；權限那側沒有隨灌 kernel 裝上的東西（站與 kernel_gate 預設不裝，limits／sub:N 在 daemon 本體，guard／sandbox 在 agent 與工具）；四種切法與八題待裁，等使用者 |
| [編譯的通用底座與函數當工具／hook（aos-compile-base-1120）](aos-compile-base-1120/README.md) | 只查只寫：能編譯的只有 agent 與工具、兩支共用 0 行；底座攤五個形狀（甲～戊）；函數當工具／hook 分「抽出來」與「回頭跑」兩大類，小原型兩種都走通；八題待裁，等使用者 |
| [aos-gdb 問答（aos-gdb-問答-1120）](aos-gdb-問答-1120.md) | 使用者問 a.stop() 是不是阻塞、斷點 id 為什麼是 xxxx_1；只讀快查：把手沒有 a.stop，暫停是 a.bp.pause()、停掉是 a.ctl.stop()，正在跑的一格不被打斷、扣在斷點上停不了，id 是施工線順手定的「種類_N」且刪了會重用；選項框四題已答（pause 加 wait=、不等回可查的物件 is_done()、id 純數字搭配屬性待確認、add 回物件），還沒施工 |
| [hook 點的介面與耦合（aos-hook-iface-1120）](aos-hook-iface-1120/README.md) | 只查只寫：hook 是程式走到時機明叫、不是每圈觸發；引擎一份、事件表 agent 與 kernel 各一份同形狀，表裡沒有欄位與誰觸發，沒有提供點的條文；fsm 加一個點約 16 處、手抄清單約 19 處（5 處漏改不報錯）；五個形狀、十題待裁，等使用者 |
| [kernel 的資源基底與排程介面（aos-kres-1120）](aos-kres-1120/README.md) | 發想：資源基底＝請求帶的自由 json＋kernel 放話 schema＋粗化／細化＋記帳，今天用 llm kernel 的 hook 能做單人版，缺宣稱的約定位置、帳不收宣稱、schema 放哪與跨體系；排程介面「骨架本來就有」對一半：骨架有叫「誰先」的口，規則每包自寫、hook 碰不到；repo 外小原型；九題等使用者。使用者答了四題（08：「給位置和格式。當然，這都是可選的，kernel自己可以選擇不給。」、誰判與經驗存哪先不定、選「把原型接成 hook 試一次」）；試跑（09，線 aos-kres-try-1120）：跑起來了，換規則不用重起，hook 改的優先序這一輪不算數（實測），卡點是宣稱沒約定位置、帳不收宣稱、兩支 hook 的格對不起來、hook 壞了整站停；五題還沒問 |
| [aos-gdb 施工：wait=、純數字 id、斷點物件（aos-gdb-wait-1120）](aos-gdb-wait-1120.md) | 照使用者 11-20 裁定改 a.bp：resume／step／pause 加 wait=（False＝回 Pending，is_done() 問好了沒、wait() 拿同樣結果）；id 改純數字、刪了不重用（計數器在 agent 的 stack，觀察者從看的每一隻一起拿）；add 回斷點物件，屬性每次重查、刪了讀報錯；自己取名 id="mine" 照留（替使用者選的）；乾淨複本假腦全過，沒在 repo 跑 install.py，等使用者點頭後試 |
| [「提供 hook 點」的介面：設計與施工計劃（aos-hook-plan-1120）](aos-hook-plan-1120/README.md) | 只出稿：使用者選「宣告式＋小函式都做」「任何子程式，含非 Python」「在 loop 層加通用的點」；設計＝每個提供者一份 hook_points.json、小庫 aos.hook_point、指令 aos-hook fire（取代 hook_fire）、aos-loop 的 before_run／after_run（沒人掛每圈約 2 微秒、有人掛每點約 18 毫秒起跳）；加一個點從約 16 處變 2 處；六條衝突、十四題待裁、施工七刀（1、2、4 刀可先做），等使用者；使用者 11-20 已答七題、四個點都跟著停改掉設計預設、還有十題沒問（見 13） |
| [「編譯變成整套一個 Python 程式庫」設計稿與施工計劃（aos-pylib-plan-1120）](aos-pylib-plan-1120/README.md) | 只出稿：寫定義變成物件（defs.Agent、.dry_run() 只算、.compile(夾) 寫，defs.main 旗標不變）；Python 函數用新模組 fn（@fn.tool、@fn.hook、fn.block）標成工具與 hook，編譯時抽成定義夾的 fn/名.py；defs.extern(目標) 編成連結並附「別濫用」說明；跟已定的逐條對照、衝突六條、待裁十題、施工六刀（只有第 0 刀不依賴任何題）；Argon 審一次、採納表 |
