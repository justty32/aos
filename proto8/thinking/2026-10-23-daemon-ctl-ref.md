# 2026-10-23 daemon 的 ctl 只寫變動、`$ref` 自動切檔、指示詞全面支援

← [thinking](README.md)｜月份表 [2026-10](months/2026-10.md)｜前一份：[daemon 壓測後的六個問題](2026-10-23-daemon-bench.md)

規矩見 [thinking/README](README.md)：只留使用者原文、決定、結論。落點：[N-45](../NORMS/06-基礎設施-命令列與指示詞.md)、[N-06、N-08、N-11](../NORMS/05-基礎設施-窗.md)、[N-28、N-54](../NORMS/04-基礎設施-loop與daemon.md)；程式在 `proto8/impls` 的 aos-directive、aos-loop、aos-fsm、aos-daemon（只改 C++ 版）。

## 使用者原文（整理版）

### 10-23 深夜，ctl 與大 JSON

> ctl這塊我會想要是"啓動XXX loop/刪除XXX loop"，而不是每次都讓他讀全部。除此之外，當loop太多的時候，json超大，我會希望他會自動用$ref切，每個檔案一百個

頂層提出跟 N-06（ctl 是宣告式：整份就是期望、寫幾次都一樣）、N-10（指令式控制資料夾，10-16 已刪）的衝突，給三個選項；使用者選「**維持宣告式，但可以只寫變動的**」：ctl 多兩個 key，一個寫「名單上要多這些」、一個寫「名單上要少這些」，讀幾次結果都一樣。

`$ref` 自動切檔用在哪裡，使用者三個都選：**daemon 的 state、daemon.json、ctl**。

### 指示詞

> 對了，各種json應該都支援指示詞吧

頂層說明目前只有 inst 單子和 aos-exec 的 argv 陣列會解；使用者選「**aos 讀的 JSON 全部支援**」：loop.json、daemon.json、fsm.json、ctl 讀的時候都解；state 是程式自己寫的，只在自動切檔時用 `$ref`，讀的人自己用同一個庫解。

對 10-15 那句「後續就是都默認沒有指示詞能用」：

> 其他地方預設不支援指示詞...這不應該是規範，這是在陳述事實，因爲其他人做的程式未必會想支援這個

### 10-23 晚，`$ref` 陣列與兩題確認

頂層問 `loops` 拆成好幾份檔的格式時：

> 等一下，我記得可以這樣啊："$ref":["a.json", "b.json#/c/d]"

頂層查過，條文、thinking、程式原本都沒有這種寫法。使用者接著選：

- **`$ref` 可以寫成陣列＝把幾份照順序合成一份：都是物件就合 key，都是陣列就接起來，種類混在一起＝解不開（`DirectiveBad`）**；
- **合物件時同名 key：後面的蓋前面的**（淺層合併，不往下層合）。

另外兩題照推薦、使用者確認：ctl 的 key 名用 `loops_added`／`loops_removed`（C-54 R4）；ctl 沒寫 `loops_added` 就把加進來的收掉（維持宣告式，N-06）。

### 10-23 晚，`$ref` 陣列的兩個細節

頂層問「`$at` 遇到陣列時，是接在每一份的指標後面，還是對合好的結果再取位置」：

> 把$at刪掉，就都只認#/。

所以修飾詞 `$at` 整個刪掉：指位置一律寫 `檔#/指標`；寫了 `$at` 是不認得的 `$xxx`、不管（N-45）；空檔名的 `#/指標` 照現行規則（換不了、原封不動）。

頂層問「兩份以上都是字串或數字時當成解不開（`DirectiveBad`）」：

> 好。

## 結論（照原則推，細節頂層定）

### 零、`$ref` 陣列的細則（照 N-45 的兩類錯推）

1. 每個元素就是原本的 `$ref` 字串（`檔`、`檔#/位置`），相對路徑照原規則；每一份各自取原文、各自接著解，解完再合。合物件時同名 key 位置留在第一次出現的地方。
2. 只有一份＝它本身（不限種類）；兩份以上卻都是字串、數字之類＝合不起來＝`DirectiveBad`（使用者 10-23「好。」）。
3. 位置只認 `#/`：每個元素各自寫 `檔#/指標`；`$at` 刪了，寫了不管（使用者 10-23「把$at刪掉，就都只認#/。」）。
4. `$path`、`$prefix` 作用在合好的那一份，是字串才接。
5. 空陣列、有任何一個元素寫法不合＝整個物件原封不動（寫法寬容）；有一份讀不到、指不到、繞圈＝`DirectiveBad`。繞圈看往上那幾層，同一個陣列寫兩次同一份不算。
6. 只換一格的 `resolve_shallow`：合出來的值每個 key／元素記著來源檔的資料夾（`Resolved::dir_of`），往下解時用它。

### 一、指示詞：aos 讀的 JSON 都解

1. **兩層**：規範＝aos 自己的程式讀的 JSON 一律支援指示詞；事實＝別人做的程式不一定支援（10-15 原話照留、旁註這點）。
2. **每支程式只解自己讀的那幾格**（C-52「每一層只管自己」）：整份、以及它一層層讀進去的那幾層先換掉；它讀的 key 的值整個解；它不讀的 key（`body`、`_entry`…）原封不動，留給讀它的人（`loop.json#/body` 由跑那次的 aos-exec 自己解）。所以 body 裡的 `$env` 沒設，照舊是那次 aos-exec 的錯，不擋 loop 起來。
   - aos-loop：loop.json 整份、`run`、`max`、`interval_ms`、`ctl`、`state`；ctl 整份、`paused`、`stopped`、`max`、`interval_ms`、`seq`。
   - aos-daemon：再加 `loops`（一層層：`loops` 本身、每個子項本身；子項是目標＝整個解，是 loop 設定＝只解 `run`、`max`、`interval_ms`、`ctl`、`state`，其他 key 原樣寫進小格）、`adopt`；ctl 再加 `loops`、`loops_added`、`loops_removed`。
   - aos-fsm：fsm.json 整份、`start`、`states`、每一格、格的 `val`、`next`。
3. **相對 `$ref` 從寫著它的那份檔所在的資料夾算**（N-45 原則）：設定檔＝設定檔的資料夾、ctl＝ctl 的資料夾（`$AOS_STACK` 底下那份）、換進來的檔＝那份檔解開捷徑後的資料夾。daemon 把子項設定搬進小格前先解它的 loop key，因為搬進小格之後相對路徑會從小格算。
4. **解不開**（變數沒設、讀不到、指不到、繞圈）：設定檔＝自己的錯，退 1、一行 `程式名: DirectiveBad 原因`；ctl＝整份不採用、維持上一份好的、原因進 `ctl_warning`（N-08）。寫法不合（寬容的那幾種）＝原封不動留著，照那一格自己的規則判（例 `max` 留成物件＝`CfgBad`）。
5. **`#/` 指標走的是原文、不穿過 `$ref`**（N-45 原本就這樣）：`loops` 拆到別的檔之後，子項 `run` 要指進那份檔（`loops-1.json#/bob/body`），不是 `daemon.json#/loops/bob/body`。
6. 程式：aos-directive 多一個 `resolve_shallow`（只換這一格、不往裡面走，回換好的值與裡面的起點）；aos-loop 開出 `resolve_keys` 給 daemon、fsm 共用。

### 二、ctl 只寫變動：`loops_added`、`loops_removed`

（第 1 點的名字、第 4 點「拿掉 `loops_added`＝收掉」使用者 10-23 確認。）

1. **key 名照 C-54 R4「ctl 的 key 用狀態詞」**（`stop` → `stopped` 同一條）：`loops_added`＝名單上要多這些（寫法同 `loops`）、`loops_removed`＝名單上要少這些（名字的陣列）。主題 `loops` 在前（R7），跟 `loops` 排在一起。
2. **期望表＝（ctl 的 `loops`，沒寫＝daemon.json 的 `loops`）＋`loops_added`－`loops_removed`**，先加後減：同一個名字兩邊都寫＝不要；`loops_removed` 寫了名單上沒有的名字＝不管。只看這一份 ctl 與 daemon.json，讀幾次都一樣（N-06）。
3. **相對於哪一份名單**：同一份 ctl 有 `loops` 就相對它，沒有就相對 daemon.json 的 `loops`（N-06「沒寫＝回初始值」）。
4. **ctl 拿掉 `loops_added`＝加進來的那些收掉**（N-06：沒寫的欄位回初始值，`loops_added` 的初始值是「什麼都不加」）；同理拿掉 `loops_removed`，被減掉的照 daemon.json 重新起。這跟寫一份只有 `{"paused": true}` 的 ctl 會讓 `max` 回 daemon.json 的值是同一條規則。
5. 名單上已有的名字寫進 `loops_added`：設定換成這份，但已在跑的不重起（同 N-54「名字已在表上的不看設定變了沒」）。
6. 寫壞（`loops_removed` 不是字串陣列、`loops_added` 名字不合或跟 daemon 自己的 ctl／state 撞名、指示詞解不開）＝整份不採用、記 `ctl_warning`（N-08）。
7. daemon.json 不認這兩個 key：起來那份名單就是 `loops`（N-11：只有 ctl 能蓋，`loops` 系列是 ctl 的例外）。

### 三、`$ref` 切檔，每份 100 個

1. **拆檔用 `$ref` 陣列**（使用者決定，見上）：`loops` 一律是物件，要拆就寫 `"loops": {"$ref": ["loops-1.json", "loops-2.json"]}`，aos-directive 合成一份物件；daemon.json、ctl 的 `loops`／`loops_added` 都這樣。合出來的每個子項記著它來自哪份檔，子項裡的相對 `$ref` 從那份檔的資料夾算。
2. **daemon 寫 state 時，`loops` 超過 100 列才切**，每份最多 100 列、照表上的順序；100 以內維持原本的物件。主檔 `loops` 寫成 `{"$ref": ["state_loops/<雜湊>.json", …]}`，讀的人用 aos-directive 解開就是完整的 `loops` 物件。
3. **分檔放哪、叫什麼**：跟 state 同一層的資料夾，名字＝state 檔名去副檔名＋`_loops`（`state.json` → `state_loops/`；C-54 主題在前、裝同類用一個資料夾）；這個名字也算子項撞名（同 10-22 的 ctl／state）。分檔檔名＝內容的雜湊（FNV-1a 64 位元、16 個十六進位字）＋`.json`。
4. **怎麼寫、怎麼保持一致**：每份分檔照 N-05 先寫 `.` 開頭的暫存檔再改名；同名＝同內容，所以內容沒變的頁直接沿用、不重寫；分檔都寫好才寫主檔（同樣暫存再改名）——**主檔改名是唯一的提交點**。寫完清掉「這次與上一次的主檔都沒用到」的分檔；行程起來第一次寫時不清（磁碟上的主檔可能還指著上一個行程的分檔）；縮回 100 以內、分檔清空後拿掉資料夾。
5. **讀的人會看到什麼**（照實寫）：先讀主檔、再照 `$ref` 讀分檔，拿到的一定是同一次寫的表（分檔寫好就不再改）；只有讀得比 daemon 寫兩次 state 還慢時，那份主檔的分檔可能已被清掉、`$ref` 讀不到——重讀主檔就好。daemon 寫到一半當掉：主檔還是上一份、它的分檔都還在，`adopt` 讀到的是完整的上一份表。
6. **100 不開 key**（C-56 KISS：使用者給了數字，沒有要調的需求，就照字面做；要調再加）。
7. daemon.json 與 ctl 是人寫的，靠第一部分的指示詞就能拆，程式不替人切。

### 驗證

- impls 各專案 ctest 全綠；新加的測試在改之前的程式上會紅（loop 6 個、fsm 3 個、daemon 6 個）。
- 壓測 3000 個子 loop：state 切成 30 份、每份 100 列、合起來 3000 列名字全對；分檔資料夾平常只有 30 份（內容沒變不重寫）；收工後沒有殘留行程。
