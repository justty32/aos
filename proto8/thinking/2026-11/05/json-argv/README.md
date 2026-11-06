# 2026-11-05 晚 為何用 JSON、argv 的兩面（json-argv；使用者原文＋結論；細節規劃交 fable）

← [thinking README](../../../README.md)｜日 [2026-11-05](../README.md)｜相關：[no-pid 03](../no-pid/03-找daemon與脫鉤.md)（`--env-file`／`--envs`）、[stdio-unify](../stdio-unify/README.md)（三扇門、`--help`）、[agent-knowledge](../agent-knowledge/README.md)（「json本身與檔案系統也有同像性」）

## 使用者原文（11-05 晚，整理版；只分段加小標題，字句照原話）

**11-06 註**：原文逐字搬到[使用者原文續檔](README-parts/01-使用者原文.md)，實作與文件結果見 [10](10-J3到J7實作結果.md)。

<a id="為何要-json"></a>
<a id="aos-函數與-tool-呼叫"></a>
<a id="argv-的兩面"></a>
<a id="應對方式的兩面"></a>
<a id="兩題的回答"></a>

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
| [07-使用者回覆-11-05晚](07-使用者回覆-11-05晚.md) | 使用者對四點與三題的回覆原文、由此定下的 7 條 |
| [08-J1實作結果](08-J1實作結果.md) | 11-06 J1：tool_io 從 `_tooldef.json` 生旗標映射與 `--help` 旗標段；代定 9 條、實測、隊員分工、邊緣 5 條 |
| [09-J2實作結果](09-J2實作結果.md) | 11-06 J2：27 支 lib 工具刪手寫參數段、`_tooldef.json` 補 `default`／`errors`、claude／codex 改走 tool_io、`AOS_WS` 不再預設 `.`；代定 7 條、245 組新舊對照、邊緣 5 條 |
| [10-J3到J7實作結果](10-J3到J7實作結果.md) | 11-06 公司 D 隊 J3～J7：一步一節（做了什麼、代定、實測、新邊緣） |
| [11-J6實作結果](11-J6實作結果.md) | 11-06 註：J6 env 核對與 agents 相對路徑、代定、實測、新邊緣（從 10 逐字搬出） |
| [12-J5實作結果](12-J5實作結果.md) | 11-06 註：J5 tokenizer 去重與 SIGPIPE、代定、實測、新邊緣（從 10 逐字搬出） |
| [13-J4實作結果](13-J4實作結果.md) | 11-06 註：J4 四格共用解析、act 限時與 stderr 尾、代定、實測、新邊緣（從 10 逐字搬出） |

## fable 規劃一句話結論

**`_tooldef.json` 的 `parameters` 已經是腦看的 schema；再讓它同時生出旗標映射、英文 `--help` 與最小型別檢查（全放 `lib/tool_io.py` 一處），純 aos 函數就零成本多一個人能用的介面，手寫的三份參數說明收成一份；環境變數只留 aos-exec 六個與 hub，input 一律 stdin JSON，hub 脫鉤靠 no-pid 的 `--env-file`／`--envs` 補。**

## 要使用者裁的（白話；推薦放第一）

**11-06 註**：三題已於 11-05 裁定，原選項與回覆連結逐字搬到[方向題續檔](README-parts/02-方向題.md)；已實作項見 [10](10-J3到J7實作結果.md)，子資料夾＝子動作仍待使用者先看。

## fable 代定（可翻案）

- **11-06 註（J1 已實作，`9b97aeb3`，[08](08-J1實作結果.md)）**：映射取 argparse 子集：連字號↔底線；`integer`／`number` 轉型；`boolean`＝`--flag`／`--no-flag`；`array`＝重複旗標；`object`＝整段 JSON 字串，也可用 `--a.b` 只換一葉（使用者 [07](07-使用者回覆-11-05晚.md) 已裁）；純函數不做短旗標、nargs、子命令。
- **11-06 註（J1 已實作，[08](08-J1實作結果.md)）**：schema 沒的旗標＝`FlagUnknown`；型別轉不了、required 缺、開關帶值、位置參數不對＝`ArgumentsBad`；工具錯誤行兩邊各印一行、退 1，旗標錯誤另附 `(see NAME --help)`。
- **11-06 註（J1 已實作，[08](08-J1實作結果.md)）**：stdin 是 tty＝`{}`、不讀（解 P-39「會卡」）。
- **11-06 註（J1 已實作，[08](08-J1實作結果.md)）**：只查 `type`／`required`；`enum` 只供 help 顯示，未知 op 交工具報 `OpUnknown`（aos-schema 隨 S10 封存）。
- **11-06 註（J1／J2 已實作，J2 `85f22b2a`，[08](08-J1實作結果.md)、[09](09-J2實作結果.md)；J3 核對見 [10](10-J3到J7實作結果.md)）**：工具側選填 `positional`／`errors`／`env`，property 可帶 `default`；模型只取 `description`／`parameters`，所以 property 的 `default` 也看得到。
- C++ 現在不做 schema 映射；`aos::parse_cli` 不動；aos-exec 不參與映射（C-52）。
- **11-06 註（J3 已實作，`a6d8cd9a`，[10](10-J3到J7實作結果.md)）**：aos-tools `call` 三種工具都吃 stdin；add 用 `--envs`＋`--env-file`，當下讀檔存內容；`--envs` ＞檔案合成登記格 `env`，call 時登記值＞繼承；`AOS_STACK` 另由 call 一處算小格，登記值不得覆蓋。
- **11-06 註（J6 已核對，`1ab16a8a`，[10](10-J3到J7實作結果.md)）**：`AOS_KERNEL` 改信去向時已有 warning，沒加 `--kernel`；C++ 的兩處舊註解仍等 S7。
- **11-06 註（J5／J4 已實作，`92717ee3`／`2eb02ea4`，[10](10-J3到J7實作結果.md)）**：aos_flags 包 tool_io 的 tokenizer；stdout 被關安靜退 141；四格改共用解析，act 按工具 metainfo 限時、非 0／逾時附 stderr 尾。
- **11-06 註（J7 文件已同步，[10](10-J3到J7實作結果.md#j7-條文與文件)）**：P-44、P-41、C-52、N-43、lib 規則與英文知識書照實作；P-45 核對相符，N-57／N-63 不改。
