# 2026-11-05 晚 為何用 JSON、argv 的兩面（json-argv；使用者原文＋結論；細節規劃交 fable）

← [thinking README](../../../README.md)｜日 [2026-11-05](../README.md)｜相關：[no-pid 03](../no-pid/03-找daemon與脫鉤.md)（`--env-file`／`--envs`）、[stdio-unify](../stdio-unify/README.md)（三扇門、`--help`）、[agent-knowledge](../agent-knowledge/README.md)（「json本身與檔案系統也有同像性」）

## 使用者原文（11-05 晚，整理版；只分段加小標題，字句照原話）

### 為何要 JSON

> json這塊，是這樣的，爲何要json？我看重他的好處在於幾個點：
> 1. 就算不憑藉任何工具，人類也能理解...大段文字這塊可能比較麻煩，畢竟他沒換行，但也沒關係。
> 2. 大語言模型生成起來幾乎不會出錯，就算是笨模型也是。
> 3. tool呼叫就是用json格式。
> 4. 與檔案系統的同像性。
> 5. 大部份程式語言都原生支援。

### aos 函數與 tool 呼叫

> 那，其中一個很重要的東西，就是tool呼叫，你知道的，我們aos函數他也是透過json去定義的，並且aos函數是aos體系的基石，和tool呼叫，兩者之間應該要是可以無痛轉換。除此之外，aos體系也大量使用json來做訊息傳遞，乃至於函數的input/output，config格式之類，甚至可以說，aos體系下，唯一與json無關的，就是環境變數。

> 總而言之，用了json，就是可以跟agent的工具呼叫，也就是agent的手腳輕鬆相連。也正是因爲如此，我才說不要濫用環境變數。

### argv 的兩面

> 至於argv，這東西我的看法是兩面的，一面是一連串argv[]組合起來，等同於一個method，至於這個method的實際input，在aos體系下通常都來自於stdin，output也是stdout/err。另一面則是這東西可以給人使用，畢竟你讓人去寫json，其實不太方面。

### 應對方式的兩面

> 所以其應對方式我覺得同樣也可以有兩面，一面是以其用途做區分，若是要給人操作的(或是agent使用shell工具操作的)，那就是用法要遵循unix/linux習慣，man/--help要有，設計要符合人體工學(以人爲主)。若是單純的aos函數，不需要給人操作的，那就是argv的旗標盡量不要濫用，大多東西都走要給stdin的json，要包成工具的也通常是這類(另一類就是走shell工具)。

> 另一面，就是在設計argv旗標時，其實可以用python的argparse爲參照，將其映射到json，比如--xxx yyy，就可以映射到stdin json中的"xxx":"yyy"這樣，至於具體型別那自然會有所限制，但就是提供一個方法，讓那些不是設計用來給人操作的函數，也有一個讓人勉強可用的界面。

### 兩題的回答

> （題 1：JSON 是不是 aos 的通用介質、要不要寫成規範）看起來是的，但我沒有定死，就只是把優點擺出來，之後實際工程上大家就依據需求斟酌使用。

> （題 2：JSON 手改設定很痛——不能註解、尾逗號）是的，但我們也有各種工具，不管是jq，或是寫一個小程式將其抽象化/自動轉換，或是把一些重要的東西抽出來成簡單json，讓人簡單改。

## 結論（11-05 晚，只寫上面能直接推出的）

1. **JSON 是預設介質，但不定死**：優點擺出來，工程上依需求斟酌；不寫成硬規範。
2. **aos 函數定義 ↔ tool 呼叫要能無痛互轉**：aos 函數是基石、用 JSON 定義；tool 呼叫也是 JSON，兩邊要能直接對上（agent 的手腳）。
3. **環境變數是 aos 體系裡唯一不走 JSON 的**，所以別濫用。
4. **argv＝method 名**：一串 argv 組起來指定「呼叫哪個方法」；方法的 input 走 stdin JSON，output 走 stdout／stderr。
5. **給人用（或 agent 走 shell 工具用）的指令**：照 unix／linux 習慣、要有 man／`--help`、以人為主設計。
6. **純 aos 函數（不給人操作）**：少用旗標，大多東西走 stdin JSON；要包成 tool 的通常是這類。
7. **旗標可照 argparse 映射到 stdin JSON 的鍵**（`--xxx yyy` → `"xxx": "yyy"`；型別有限制），讓純 aos 函數也有一個人勉強能用的介面。
8. **JSON 手改不便靠工具補**：jq、小程式抽象化／自動轉換、或把重要的抽成簡單 JSON 給人改。

## 分檔目錄（fable 細節規劃，11-05 晚）

| 分檔 | 涵蓋 |
|---|---|
| [01-盤點-函數與tool](01-盤點-函數與tool.md) | 現況鏈圖、定義→schema、tool 呼叫→執行、13 處「不是無痛」（A1～A13，附檔:行）、無痛互轉判準 |
| [02-盤點-指令與旗標](02-盤點-指令與旗標.md) | impls／bin／extras／lib 每支指令：人用／函數／兩者、旗標數、input 來源、不合 unix 處；三個總結 |
| [03-旗標映射設計](03-旗標映射設計.md) | `--xxx yyy`→`"xxx":"yyy"` 規則表、型別、合併、`--help` 版面、`tool_io` 介面、C++ 側、同一份定義生 tool schema |
| [04-環境變數](04-環境變數.md) | AOS_* 與其他 env 盤點表、合理／該改（E1～E5）、跟 `--env-file`／`--envs` 的分工與判準 |
| [05-衝突與方向題](05-衝突與方向題.md) | 8 條衝突（P-44、P-41、lib 規則 1、P-39、C-56、N-63、no-pid、S5／S10）、方向題 Q1～Q3、fable 代定 |
| [06-實作步驟](06-實作步驟.md) | J1～J8、驗收、派誰、跟 S5～S11／P3～P4 的先後 |

## fable 規劃一句話結論

**`_tooldef.json` 的 `parameters` 已經是腦看的 schema；再讓它同時生出旗標映射、英文 `--help` 與最小型別檢查（全放 `lib/tool_io.py` 一處），純 aos 函數就零成本多一個人能用的介面，手寫的三份參數說明收成一份；環境變數只留 aos-exec 六個與 hub，input 一律 stdin JSON，hub 脫鉤靠 no-pid 的 `--env-file`／`--envs` 補。**

## 要使用者裁的（白話；推薦放第一）

1. **給人用的程式（aos-post、aos-daemon-ctl、aos-agent…）要不要也改成「一份 JSON 定義生旗標表＋`--help`」？**
   - **不做，旗標表留程式碼裡 (Recommended)**：給人的介面要子命令、位置參數、散文 help，JSON Schema 表達不了；它們也不需要 tool schema（agent 走 `bash` 叫）。
   - 做：`cmd/<名>/_cli.json` 生 C++／Python 表——多一個 codegen 步驟，只換到「一致感」。
2. **一個工具資料夾要不要有多個 method（memory 的 add／get／ls）？**
   - **子資料夾＝子 method (Recommended)**：`memory/add/_entry` 各有自己的 `_tooldef.json`，`aos-exec memory/add`，登記名 `memory_add`——每個 method 一份乾淨 schema；資料夾變多。
   - 維持 stdin 鍵 `op` 分支（現況）：schema 鬆、`--help` 一長串，但檔少。
   - 工具內解子命令 `aos-exec memory add`：工具要自己做子命令解析，跟「純函數少用旗標」背道。
3. **旗標跟 stdin 同一個鍵：蓋掉還是報錯？**
   - **旗標蓋 stdin、不報錯 (Recommended)**：同 N-58「旗標 ＞ 環境 ＞ `.env`」、同 argparse；可以 `cat base.json | aos-exec tool --limit 5`。
   - 報 `ArgumentsBad`：安全但失去管線覆蓋用法。

## fable 代定（可翻案）

- 映射只取 argparse 子集：連字號↔底線；`integer`／`number` 轉型；`boolean`＝`--flag`／`--no-flag`；`array`＝重複旗標；`object`＝整段 JSON 字串；不做短旗標、nargs、點路徑、子命令。
- 錯誤代號沿用：schema 沒的旗標＝`FlagUnknown`；型別轉不了、required 缺、開關帶值、位置參數不對＝`ArgumentsBad`；一行 `工具名: error: 代號 原因 (usage: …)` 退 1。
- stdin 是 tty＝`{}`、不讀（解 P-39「會卡」）。
- 型別檢查只做 `type`／`required`／`enum`（aos-schema 隨 S10 封存）。
- `_tooldef.json` 選填 key：`positional`（預設不宣告）、`errors`、`env`（no-pid P4）；aos-tools／aos-mcp 給模型只取 `description`、`parameters`（現況已如此）。
- C++ 現在不做 schema 映射；`aos::parse_cli` 不動；aos-exec 不參與映射（C-52）。
- aos-tools `call` 砍 exe 的 `--tool-call FILE` 路，三種工具都吃 stdin；`--env` 改名 `--envs`＋加 `--env-file`。
- `AOS_KERNEL` 改信去向時印 warning 行（或 `--kernel` 明給）；小格 `AOS_STACK=…/tools/<名>/` 只在 `aos-tools call` 算。
- 條文改動（P-44 末句、P-41 加註、lib 規則 1／5a）排在 J7、照實作寫。
