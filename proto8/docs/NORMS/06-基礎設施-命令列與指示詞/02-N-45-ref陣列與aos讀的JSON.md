← [回入口 06-基礎設施-命令列與指示詞.md](../06-基礎設施-命令列與指示詞.md)｜段落：N-45 `$ref` 陣列、argv 陣列、aos 讀的 JSON 都解｜上一份：[01-N-45-path-env-ref](01-N-45-path-env-ref.md)｜下一份：—

# N-45（續）：`$ref` 陣列、argv 陣列、aos 讀的 JSON 都解

- **`$ref` 可以寫成陣列＝幾份照順序合成一份**（10-23 使用者：「等一下，我記得可以這樣啊："$ref":["a.json", "b.json#/c/d]"」；使用者選「**`$ref` 可以寫成陣列＝把幾份照順序合成一份：都是物件就合 key，都是陣列就接起來，種類混在一起＝解不開**」與「**合物件時同名 key：後面的蓋前面的**」，淺層合併，不往下層合）。細則（頂層照兩類錯的規則推）：
  - **每個元素**就是一個 `$ref` 字串（`檔`、`檔#/位置`、`#/位置`，`#` 右邊的寫法同 `$ref`），相對路徑照原規則從寫著它的那份檔所在的資料夾算；每一份各自取原文、各自接著解（裡面的相對 `$ref` 從那份檔自己的資料夾算），解完再合。合物件時同名 key 的位置留在第一次出現的地方、值換成後面的。
  - **只有一份**＝就是它本身（不限種類，跟寫成字串一樣）；**兩份以上**卻不是全物件或全陣列（混在一起，或都是字串、數字、布林、`null`）＝合不起來＝`DirectiveBad`（頂層推的，10-23 使用者確認：「好。」）。
  - **位置**：每個元素各自寫 `檔#/位置`。
  - **`$path`、`$prefix`** 作用在合好的那一份：是字串才接（只會發生在只有一份時），不是字串靜默不作用。
  - **寫法寬容**：空陣列（同空字串）、有任何一個元素不是合格的字串（不是字串、空字串、只有 `#/…` 卻不知道是哪份檔）＝換不了，**整個物件原封不動留著**，不會只合其中幾份。
  - **真的解不開**：有一份讀不到、指不到＝`DirectiveBad`，整個都不換；**繞圈**看的是往上那幾層（某一份指回正在解的鏈上同一個位置）；同一個陣列裡寫兩次同一份不算繞圈（物件合起來一樣、陣列接兩次）。
  - 只換一格的讀法（`resolve_shallow`，見下「aos 讀的 JSON 都解」）：合出來的每個 key／元素記著它來自哪份檔，讀的人往下解那一格時從那份檔的資料夾算。
- **argv 陣列裡也能放**（10-20 使用者，[ideas](../../../thinking/2026-10/20/ideas.md) D2、D8）：入口的 argv 陣列（C-73、N-61）元素可以寫 `$env` 或 `$ref`（`$path`、`$prefix` 同樣適用）；aos-exec 在六個環境變數設好之後解，相對檔名從陣列所在的檔的資料夾（＝`AOS_CD`）算、`#/…` 取陣列所在的那份檔；解完每個元素都要是字串，不是（或解不開；寫法不合而原封不動留下的物件也不是字串）＝入口壞（代號 `EntryBad`）、aos-exec 退 1，不會把解出來的陣列攤開。
- **aos 讀的 JSON 都解**（10-23 晚；使用者「對了，各種json應該都支援指示詞吧」，使用者選「aos 讀的 JSON 全部支援」，[thinking 10-23 ctl 與 $ref](../../../thinking/2026-10/23/daemon-ctl-ref/README.md)）。分兩層：**規範**＝aos 自己的程式讀的 JSON 一律支援指示詞；**事實**＝別人做的程式不一定支援（使用者：「其他地方預設不支援指示詞...這不應該是規範，這是在陳述事實，因爲其他人做的程式未必會想支援這個」）。細則（頂層照原則定）：
  - **每支程式只解自己讀的那幾格**（C-52）：整份、以及它一層層讀進去的那幾層先換掉（只換那一格，不往裡面走）；它讀的 key 的值整個解；**它不讀的 key（`body`、`_entry`…）原封不動**，留給讀它的人——`loop.json#/body` 由跑那次的 aos-exec 自己解，所以 body 裡的 `$env` 沒設是那次 aos-exec 的錯、不擋 loop 起來。`exec` 直接放單子物件時（[thinking 10-24](../../../thinking/2026-10/24/exec-relative/01-使用者原文.md#10-24-exec-直接放單子)），loop／fsm／daemon 讀設定只把 `exec` 換一層、單子裡面不解，留到每次跑的時候（`AOS_CF`／`AOS_CO` 設好）由 `run_inst` 解；解不開＝那支程式自己的錯（`DirectiveBad`）。各程式解的格：aos-loop：loop.json 整份、`exec`、`max`、`interval_ms`、`ctl`、`state`；ctl 整份、`cmd`、`max`、`interval_ms`、`seq`（[ctl-commands](../../../thinking/2026-11/03/ctl-commands/README.md)）。aos-daemon 再加 daemon.json 的 `procs`、`adopt`，`procs_ctl.json` 的 `procs`／`procs_added`／`procs_removed`／`procs_stopped`／`procs_started`／`procs_slept`／`procs_woken`（使用者 11-14 專區答「fixok:ok」，reply cee70afc742361ba；子項怎麼解見 [N-28](../04-基礎設施-loop與daemon/02-N-28.md)「指示詞與切檔」②；[procs](../../../thinking/2026-11/03/procs/README.md)）。aos-fsm：fsm.json 整份、`start`、`states`、每一格、格的 `exec`、`next`（key 名：使用者「fsm.json，現在是用val，幫我改成exec」「exec，loop／daemon 的 run 也一起改 exec」，[thinking](../../../thinking/2026-10/23/naming.md)）。
  - **相對 `$ref` 從寫著它的那份檔所在的資料夾算**：設定檔＝設定檔的資料夾（`檔#/指標` 取的是那份檔）、ctl＝ctl 的資料夾、換進來的檔＝它解開捷徑後的資料夾。
  - **解不開**：設定檔＝程式自己的錯，退 1、一行 `程式名: error: DirectiveBad 原因`（N-43）；ctl＝整份不採用、維持上一份好的、原因進 state_flux 的 `ctl_warning`（N-08；回音欄在 state_flux，N-09）。寫法不合的照原封不動，再照那一格自己的規則判（例 `max` 留成物件＝`CfgBad`）。
  - **state 窗是程式自己寫的**：只有 daemon 的 `procs` 表太長時用 `$ref` 陣列切檔（N-28「指示詞與切檔」③）；讀 state 的人自己用同一個庫（aos-directive）解，拿回完整的 `procs` 表。
- **寫什麼就做什麼**（C-56）：值寫的就是「讀這個環境變數」「換成那份檔」，不做字串內插（`"$AOS_STACK/plan.txt"` 那種是把規則埋進字串的暗規則）。單子本來就能內嵌，**JSON 大不是問題**，慣例範本不用 `$ref` 拆檔（P-27、P-31）；`$ref` 是給要拆的人用的（使用者 10-15 深夜：「我記得有說過吧，在概念或規範那邊，有說過指示詞的用法」「……但是不用擔心json太大」，[thinking inst-exec 第四版](../../../thinking/2026-10/15/inst-exec-v4/README.md)）。`$ref` 是拆檔便利、`$env` 讀執行當下的環境可當正式機制（10-16 夜使用者：「可以用$env啊」，再選「A」，[稿 § 四](../../../thinking/2026-10/16/agent-inherit/02-四-使用者決定.md#四使用者決定10-16)）。

## 例子

- `$ref` 陣列：`{"$ref": ["a.json", "b.json#/c/d"]}`。
- argv 陣列裡放指示詞：`["echo", {"$env": "AOS_WS"}]`、`[{"$ref": "cmd.json#/0"}, "x"]`。
