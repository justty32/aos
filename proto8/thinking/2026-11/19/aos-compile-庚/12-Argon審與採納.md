# 庚的 Argon 事後審與採納表：設計稿、第一刀程式各審一次，共 29 點，核實後多半已處理或與事實不符；真的開著的是六個小洞（都還在第三刀 f4cebb9d4），加兩題要使用者拍板

← [README](README.md)｜上一份：[11-跟除錯那條線的接點](11-跟除錯那條線的接點.md)｜Argon 原文：[12b-Argon原文](12b-Argon原文.md)

線 `geng-argon-1119`，11-19 早補正統流程漏掉的「Argon 審」那一步（使用者：「argon額度雖然不多，但是只有正規調查流程會用到。不用省　去派吧」）。只寫文件，沒改程式、沒通知別線。

## 先講結論

- **審到了**：分兩次送，一次送設計稿（README、01～08、10、11），一次送第一刀的紀錄與程式（`agent_spec.py` 第一刀 `4fc030f47` 那版）。兩次都把「C 與 .o」和六題裁定寫成不能推翻的前提。兩次各跑一輪、沒叫工具。送法的坑寫在最後一節。
- **Argon 審查段標「一定要改」的有 15 點**（設計 8、程式 7），提案段另有 5 點也標「一定要改」。對照程式與實測核實後，**沒有一點是會讓現在這份用不了的 bug**：
  - 設計那 8 點，有 7 點第一刀已經處理，或者跟事實不符。例如它說只有 `$override` 的 `tools.json` 過不了 `defs check`，但第一刀驗收 1 實跑回的是 `{"problems": []}`；它說 `$path` 少了開頭的斜線會壞，但 `aos-directive` 拼路徑時本來就會補。
  - 剩下真的開著的是**六個小洞**（下面第 1 類），都在程式那半邊。**第三刀 `f4cebb9d4` 交出的版本裡這六個都還在。**
- **(1) 施工線下次動 `agent_spec` 就該順手修的**：① `META` 的鍵不是字串會冒 traceback；② `ag.by_hand("agent.py")` 擋不下來；③ 改名的順序是「索引檔先、被指的檔後」，應該倒過來；④ 收尾清暫存檔時，刪一份失敗後面就都不刪了；⑤ 讀 `_metainfo.json` 的 I/O 錯誤被報成 `DefBad`，跟註解寫的不一樣；⑥ `INTERFACES` 改 `entry` 時，訊息叫人用 `ag.by_hand`，可是 `entry` 根本用不了它。
- **(3) 要使用者拍板的兩題**：一、第二刀（「`agent_def check` 順手重生」）是繼續「先不排」，還是直接移到「明講不做」；二、除錯線說的「執行中插指令」，要不要在 [11](11-跟除錯那條線的接點.md) 的三種走向之外，多擺一種「落在那隻 agent 自己的 stack」。
- 核實的依據：HEAD 的程式、第一刀紀錄裡的實跑輸出、`cpp/aos-directive/src/resolve.cpp` 的 `join_path`、`py/aos/apps/agent/llm.py` 怎麼讀 `llm_keys`、`templates/eca-claude` 與 `eca-pi` 的 `interfaces.json`，再加一個本機小實驗（`dict({...}, **{1: "a"})` 會丟 `TypeError: keywords must be strings`）。

## 逐點採納表

代號：D＝第一次（設計稿），C＝第二次（程式）。A＝審查，B＝提案。「Argon 標」是它自己標的等級。

### 第一次：設計稿

| 點 | Argon 標 | 它說什麼（一句） | 建議 | 理由 |
|---|---|---|---|---|
| D-A1 | 一定要改 | 只有 `$override` 的 `tools.json` 會被 `defs check` 判壞；`ag.no` 沒搭包、包名不存在、同名都沒擋 | **不採納** | 第一刀驗收 1：只有三個包的骨架，`agent_def check` 回 `{"problems": []}`。`ag.no` 沒搭包、包不存在（有 `AOS_HOME` 時）、同名（「listed twice」）第一刀都擋了 |
| D-A2 | 一定要改 | 寫檔要兩階段（先寫完全部暫存檔再改名）；改名順序要從被指的檔往索引檔換 | **前半不用，後半採納（建議）** | 兩階段 `write_defs` 本來就是這樣做的（先寫完全部暫存檔，失敗就清掉，最後才連著改名）。改名順序今天照 `out` 排，`loop.json`、`interfaces.json` 排在它們指到的檔前面。只在第一次生成、或 `by_hand` 換檔名時才會有一瞬間指到不存在的檔，機率很低，但改一行排序就好 → 第 1 類 ③ |
| D-A3 | 一定要改 | 稿 03 說 `DESCRIPTION` 寫進各份 json 的 `description`，04 說是各檔的用途，兩邊矛盾 | **程式不用改；稿 03 那格改一句（文件）** | 第一刀紀錄「對不上的地方」第 3 條已照 04 定：只有 `interfaces.json` 用 `DESCRIPTION`。第三刀驗收也寫明「只差各份的 `description` 句子」。只剩稿 03 對照表的字面沒跟著改 |
| D-A4 | 一定要改 | `_metainfo.json` 要在動筆前讀；不是物件時沒有代號；META 不准設 `summary` | **不採納（已做）** | 程式在寫任何暫存檔前就讀好 `_metainfo.json`，不是物件報 `DefBad`；META 設 `summary`、`lineage` 都報 `SpecBad` |
| D-A5 | 一定要改 | `DESCRIPTION` 開頭有換行，README 第一行會是空的；空的 README 已經在就不補；夾名不查 | **不採納** | `DESCRIPTION` 先 `strip()` 才用，開頭換行沒了。README 是「種子」，不是生成檔：已經在了就是人的東西，空的由 `defs check` 報，照「C 與 .o」lib 不替人修。夾名第一刀紀錄已決定不查（`defs check` 會報） |
| D-A6 | 一定要改 | 格名重複、`True` 當成 1、`0` 與 `"0"` 撞鍵、argv 與 timeout 沒驗、`$path` 少了開頭斜線 | **不採納** | 前四樣都擋了（重複「declared twice」、排除 `bool`、結束碼只收整數或 `"*"`、argv 與 `timeout_ms` 都有驗）。`$path` 的開頭斜線：`aos-directive` 的 `join_path` 會「去掉 v 結尾的 /、去掉 sub 開頭的 /，中間剛好一個 /」，有沒有斜線結果一樣 |
| D-A7 | 一定要改 | `by_hand` 能用在哪幾個宣告，各份稿寫法不一；沒擋 `../` | **不採納（已做）** | 程式四個宣告都能用，`FSM` 用 `by_hand` 時 `loop.json` 的 `exec` 跟著指過去；`..`、絕對路徑都擋了。稿 03 對照表只在 SYSTEM 寫了 `by_hand`，屬於文件字面 |
| D-A8 | 一定要改 | `INTERFACES` 要兩層合併、保護必填鍵、對合併後的 `llm_keys` 驗 | **不採納（已做）** | 三樣都照做了，`llm_keys` 是合併完才拿來驗 |
| D-A9 | 建議 | 「寫錯先記著」如果用模組全域變數，在 REPL 裡會一直卡著上一次的錯 | **不採納（已做）** | 錯是裝在回傳的物件裡（`{"kind": "bad"}`），沒有全域狀態；`write_defs` 一定要給資料夾 |
| D-A10 | 建議 | 編碼與換行、新檔權限、從 META 拿掉的鍵會一直留在 `_metainfo.json` | **只採納最後一項（文件）** | 編碼已經是 utf-8；新檔用 `open()` 預設權限（0666 扣 umask），沒有問題；aos 只在 Linux 跑。「從 `META` 拿掉的鍵不會自動刪」是真的，而且是「只設自己的鍵」必然的後果，骨架 README 補一句 → 第 2 類 |
| D-B1 | 一定要改 | 第二刀「check 順手重生」直接砍掉，移到「明講不做」 | **要使用者拍板** | 這是方向題，不是設計者能定的。Argon 的理由比稿 10 多一層，見第 3 類第一題 |
| D-B2 | 建議 | `INTERFACES`、`META` 移到第三刀 | **不採納** | 第一刀已經交了，第三刀也交了，移不移已經沒有意義 |
| D-B3 | 一定要改 | 不宣告 FSM 時，不要從夾裡的 `interfaces.json` 找檔名；而且 eca 版沒有 `system` 鍵 | **不採納** | 第二點不對：`eca-claude`、`eca-pi` 的 `interfaces.json` 都有 `"system": "system.txt"`。第一點，第三刀照稿 03 決定一做了（跟 `agent_def tools` 找檔同一個方法），也補了 Argon 擔心的情況：夾裡沒有 `interfaces.json`、沒宣告那一種檔、`by_hand` 的名字對不上，都有清楚的 `DefBad`／`SpecBad` |
| D-B4 | 建議 | `ag.tool` 的相對路徑裡有 `..` 就報 `SpecBad`，教人改用 `ag.home`／`ag.env` | **採納（建議，之後的刀）** | 稿 06 第 7 條、07 第三節自己就點出這個坑：`agent_def new` 換算好的路徑會被重生蓋回錯的。今天只寫在說明裡；一行檢查就能擋。只擋 `ag.tool` 的路徑，不擋 `ag.state` 的 argv（argv 裡可能有一般參數） → 第 2 類 |
| D-B5 | 建議 | 除錯時在執行中插的東西，應該落在那隻 agent 的 stack，不要改大家共用的定義夾 | **攤給使用者** | 是真的盲點：定義夾是共用的，改它等於所有用這份定義的 agent 一起被插。但這是除錯線的方向題，見第 3 類第二題 |

### 第二次：第一刀程式（`agent_spec.py` 第一刀那版的行號）

| 點 | Argon 標 | 它說什麼（一句） | 建議 | 理由 |
|---|---|---|---|---|
| C-A1 | 一定要改 | 指示詞沒查 `$path` 必填、非空，也沒查 `$env` 的名字 | **不採納；`$env` 名字那半是可做可不做的建議** | `join_path` 遇到空的 `$path` 就不接，「沒有 `$path`」就是那個變數本身，兩種都合法。`$env` 名字不合法，到跑起來會報 `DirectiveBad`；加一行 `ENV_KEY_RE` 檢查可以提早報，但不是必要 |
| C-A2 | 一定要改 | `META = {1: "a"}` 會在 `try` 外面丟 `TypeError`，冒出 traceback | **採納** | 本機實驗確認 `dict({...}, **{1: "a"})` 會丟 `TypeError: keywords must be strings`。第三刀在 `agent_spec.py` 第 278 行還是同一句 → 第 1 類 ① |
| C-A3 | 一定要改 | `by_hand` 可以指到 `agent.py`；可以互搶別格的預設檔名；空白、換行、結尾斜線 | **只採納 `agent.py` 那一項** | `FSM = ag.by_hand("agent.py")` 時，`loop.json` 每拍都跑一次不帶參數的 `agent.py`；`SYSTEM = ag.by_hand("agent.py")` 時，原始碼變成 system。第三刀的 `FILES` 已經擋 `agent.py`（`RESERVED`），但 `by_hand` 那份清單（`_names` 的 `made`）沒有 → 第 1 類 ②。互搶檔名不算衝突：那份檔本來就不生，名字只是借用。結尾斜線會被 `normpath` 吃掉，結果正確 |
| C-A4 | 一定要改 | 讀 `_metainfo.json` 的 `OSError` 被轉成 `DefBad`；`NaN`；鍵的順序跟著舊檔 | **只採納第一項** | 註解寫「OSError 照丟（報 WriteFailed）」，程式卻一起轉成 `ValueError`，兩邊要對齊（第三刀第 305 行還是一樣） → 第 1 類 ⑤。舊檔裡有 `NaN` 要人手寫進去，不管。鍵的順序：同一份舊檔加同一份宣告，結果永遠一樣，決定性沒有破 |
| C-A5 | 一定要改 | 改名順序顛倒；暫存檔遇到 symlink；`finally` 刪一份失敗就停；權限遮罩用 `0o7777` | **採納第一項與第三項** | 改名順序同 D-A2 → ③。`finally` 裡 `os.unlink` 丟錯的話，後面的暫存檔都留下，下次 `agent_def new` 會一起抄走 → ④。symlink 那條要有人先在定義夾裡放一個 `.名.tmp-pid` 的 symlink，不管；`0o7777` 跟 `tool_spec` 一樣，不管 |
| C-A6 | 一定要改 | `INTERFACES` 能改掉 `description`；`llm_keys: None` 以後驗的跟寫出來的對不上；`entry` 的錯誤訊息叫人用 `by_hand` | **只採納訊息那一項** | `llm.py` 對 `llm_keys` 是「沒寫＝不知道、不提醒」；lib 改用預設清單來驗，只是比較嚴，不會出事。`description` 讓人用 `INTERFACES` 改，算逃生門的一部分。`entry` 的訊息確實不對：`entry` 沒有宣告可以接 `by_hand`（第三刀 parts 第 119 行還是同一句） → ⑥ |
| C-A7 | 一定要改 | `--write-defs --help` 會把 `--help` 當成資料夾；`--help foo` 會退 0；`agent.py 夾` 報成 `FlagUnknown` | **不採納（可順手）** | `write_defs` 遇到不是資料夾的會報 `WriteFailed`，不會寫錯地方，只是錯誤名稱不準。要改的話，`--write-defs` 後面接的是 `-` 開頭就報 `FlagUnknown`，一行 |
| C-A8 | 建議 | `realpath` 會把 symlink 解開，寫回共用的目標夾；`_getframe(1)` 遇到包一層的寫法會取錯；骨架的 `_e.name != "aos"` 遇到「有 aos 套件但沒有 agent_spec」會冒 traceback | **只在文件提醒 symlink** | `tool_spec` 也是用 `realpath`，兩邊一致比較好。但「`agent.py` 是指到共用檔的 symlink 時，生成檔寫回共用那一夾」值得在骨架 README 寫一句 → 第 2 類。最後一項：在還沒跑 `install.py` 的機器上，確實會印 `No module named 'aos.agent_spec'` 的 traceback。訊息本身看得懂，`tool.py` 也是同一個寫法，不改 |
| C-A9 | 建議 | 有沒有 `AOS_HOME`，`ag.pack` 的行為不同；`os.listdir` 沒接住 `OSError` | **不採納** | 前者是設計如此（沒有 `AOS_HOME` 就只查寫法）。後者要 `lib/packs` 沒有讀取權限才會碰到 |
| C-B1 | 建議 | 砍 45～55 行，壓到 300 行以內 | **不採納（已過時）** | 第三刀已經拆成 `agent_spec.py`（368 行）＋`agent_spec_parts.py`。其中「README 被跳過的判斷改成明寫」這一小項可以跟 ④ 一起做 |
| C-B2 | 一定要改 | 第三刀的 `FILES`：子目錄的暫存檔路徑、撞名、`+x` | **不採納（第三刀已避開）** | 第三刀的 `FILES` 只收單層檔名（不准 `/`、不准 `.` 開頭），也擋了保留名與宣告用的檔名。`+x`：格的程式本來就靠 `["python3", …]` 跑 |
| C-B3 | 一定要改 | 加 `HOOKS` 時，`interfaces` 禁改的鍵要加 `hooks` | **不採納（第三刀已做）** | parts 第 118 行已經加了 |
| C-B4 | 一定要改 | 不宣告 FSM 時 `fsm=None`；骨架與禁名隨模式變；殘留的 `fsm.json` | **不採納（第三刀已做／不是問題）** | `fsm=None` 已經是預設值。不宣告 FSM 時骨架不碰，殘留的 `fsm.json` 照「不宣告的檔不碰」留著；`defs check` 不看 `fsm.json`，不會因此報錯 |
| C-B5 | 建議 | 拆檔後維持 `agent_spec` 這一個對外入口；`install.py` 要裝到新檔 | **不採納（已做）** | 第三刀從 `agent_spec` 轉出對外的名字。`install.py` 的 `lib/` 是整份 `py/` 的複本，新檔會跟著裝 |

## 分三類

### (1) 施工線下次動 `agent_spec` 就該順手修的

第三刀已經交了（`f4cebb9d4`），下面六條都對照過那一版，都還在。六條各只有幾行，可以併成一刀小補丁；要不要開線、誰做，由頂層決定。

| # | 在哪（第三刀版） | 改法 | 驗法 |
|---|---|---|---|
| ① | `agent_spec.py` 第 278 行 `dict({"summary": …}, **(meta or {}))`；META 的驗證在第 254 行附近 | 驗 META 的時候一起查鍵都是字串，不是就報 `SpecBad` | `META = {1: "a"}` 只印一行 `SpecBad`，沒有 traceback |
| ② | `agent_spec.py` `_names` 的 `made` | 把 `"agent.py"` 加進 `by_hand` 不能用的名字（`FILES` 用的 `RESERVED` 已經有它） | `SYSTEM = ag.by_hand("agent.py")`、`FSM = ag.by_hand("agent.py")` 各得一行 `SpecBad` |
| ③ | `write_defs` 的改名迴圈（第 321～322 行） | 改名排序：先換內容檔（`system.txt`、`tools.json`、`llm.json`、`hooks.json`、`fsm.json`、`FILES`），再換 `loop.json`、`body.json`，最後才換 `interfaces.json`、`_entry`、`_metainfo.json` | 檢查 plan 順序的小測試 |
| ④ | `write_defs` 的 `finally`（第 324～326 行） | 每一份暫存檔各自 `try: os.unlink … except OSError: pass`，不要先 `exists` 再刪 | 照讀；沒有好測的方法，可以不加測試 |
| ⑤ | `write_defs` 讀 `_metainfo.json`（第 305 行 `except (OSError, ValueError, UnicodeError)`） | 讓 `OSError` 照樣丟出去（報 `WriteFailed`），只有讀不懂才報 `DefBad`；或者改註解。兩邊對齊就好 | 拿一個資料夾頂替 `_metainfo.json`，看報哪個代號 |
| ⑥ | parts 第 119 行的訊息 | `entry` 分開講（「entry is body.json, the skeleton agent.py writes; it cannot be changed」）；`tools`／`llm`／`system`／`hooks` 照舊叫人用 `by_hand` | 訊息字串 |

### (2) 之後的刀再說的

- **D-B4**：`ag.tool` 的相對路徑裡有 `..` 段就報 `SpecBad`，訊息教人改用 `ag.home(…)`／`ag.env("AOS_WS", …)`。
- **骨架 README 補兩句（文件）**：一、從 `META` 拿掉的鍵不會自動從 `_metainfo.json` 刪掉，要刪自己刪（D-A10）；二、`agent.py` 如果是指到共用檔的 symlink，生成檔會寫進共用檔所在的那一夾（C-A8）。
- **稿 03 對照表改兩格字面**：`DESCRIPTION` 那列改成「只有 `interfaces.json` 用它，其他 json 的 `description` 是固定的用途說明」（D-A3）；`by_hand` 四個宣告都能用（D-A7）。照「稿是當時的紀錄」，改不改由頂層定。
- 可順手、不急：C-A1 的 `$env` 名字檢查、C-A7 的 `--write-defs -x` 報 `FlagUnknown`。

### (3) 要使用者拍板的

**第一題：第二刀「`agent_def check` 順手重生」要不要直接劃掉**（**已裁：b，劃掉**，使用者 11-19「第二刀劃掉吧」，見 [10](10-使用者裁定.md) 末節）

今天稿 08 排成「先不排，等第一刀用過再決定」。Argon 主張直接移到「明講不做」，理由比稿 10 多一層：工具版能讓 `tools_def check` 順手重生，是因為 `tools_def add_tooldef` 碰到已經有的檔會拒絕（`PathExists`），`tool.py` 是唯一會寫那兩份 json 的人。agent 這格不一樣：第 2 題你裁了 `agent_def tools`／`llm`／`system` 照改 json，所以 check 一順手重生，就會把正規指令剛做的改動蓋掉。而且 `defs` 系列的檢查本來是唯讀的。

| 選項 | 後果 |
|---|---|
| a. 維持「先不排」（今天的樣子） | 什麼都不用做，第二刀留在表上。以後覺得每次多打一行很煩，再回來想「在什麼條件下才順手重生」 |
| b. 移到「明講不做」 | 重生永遠只有 `python3 agent.py --write-defs` 這一個明講的動作，檢查工具保持唯讀；表上少一刀。以後真的嫌煩，要重開一題 |

推薦 a 或 b 都可以：兩個今天都不用動程式，差別只在要不要把這扇門關上。

**第二題：除錯時「執行中插指令」，要不要多擺一個走向**（還沒裁）

[11](11-跟除錯那條線的接點.md) 列了三種走向（長在 json 上、長在 `agent.py` 上、兩邊各長再併），三種都是去改**定義夾**。Argon 指出一個盲點：定義夾是所有掛同一份定義的 agent 共用的，為了除錯某一隻去改 `fsm.json`、`hooks.json`，其他 agent 下一拍也會一起踩到。aos 今天已經有「自己那份」（kit、`self_*` 寫在那隻 agent 的 stack，不改定義）。

| 選項 | 後果 |
|---|---|
| a. 加第四種走向「插的東西落在那隻 agent 自己的 stack」 | 跟 `agent.py` 重生完全不打架（重生只動定義夾）；只影響被除錯的那一隻。要定稿時，才由人寫回 `agent.py` 再重生。要看 stack 那一層能不能放 fsm 的格（今天 kit 與 `self_*` 只管工具、腦、system、hook） |
| b. 不加，照 11 的三種 | 由除錯線照原本的範圍走 |

這題是除錯線（`aos-gdb-1119`）的方向，我只把它記在這裡，沒有轉給那條線。

## 送法與坑（給下一個送 Argon 的人）

- **Windows 命令列上限約 32K 字元**：提示 6.3 萬、4.9 萬字，用 `-p "<prompt>"` 塞不進去。改用 stdin：`agy "--print=" --input-format stream-json --output-format stream-json --model "Gemini 4 Argon (High)" --mode plan --print-timeout 840s`，stdin 送一行 `{"event": "user", "message": {"role": "user", "content": "<全文>"}}`。三個細節：
  - 鍵叫 `event`，不是 `type`（寫成 `type` 會回 `stream input message is missing the "event" field`）。
  - `--print` 一定要帶值，寫 `--print=`。不帶值會被當成沒有 prompt，只印出用法。
  - 回答在最後一行 `{"event":"result","result":{"status":"SUCCESS","response":…}}`。
- **用量**：設計那次輸入 2.9 萬、輸出 3.2 萬 token；程式那次輸入 2.6 萬、輸出 3.9 萬（都含思考）。各 5～9 分鐘。
- **這次的命中率**跟 [model-notes](../../../../../wf/public/model-notes.md) 寫的一樣：它沒看過程式的部分，就照摘要去推，「一定要改」大多數已經處理過。看得到程式那一次，挑出來的真洞明顯比較多（第 1 類六條全出自程式那次，③ 兩次都有提）。
- 暫存夾在 Windows 的 session scratchpad，沒有放進 repo。提示裡的家目錄路徑換成了 `/home/USER`，沒有放姓名、信箱或憑證。
