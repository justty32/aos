# 2026-11-06 「給人用的指令」慣例——json-argv 的另一半（human-cli，fable 規劃，沒改程式、沒改條文）

← [2026-11-06](../README.md)｜[thinking](../../../README.md)｜另一半：[json-argv](../../05/json-argv/README.md)（aos 函數的 JSON ↔ 旗標；J1 已做）｜依據：[stdio-unify](../../05/stdio-unify/README.md)（三扇門、`--help`）、[P-44](../../../../docs/CONVENTION/02-題目stack停錯腦/07-P-44.md)、[C-54](../../../../docs/CONCEPTS/01-設計理念/04-C-54.md)｜要落到：[arch-refactor 04](../../05/arch-refactor/04-實作步驟.md) S8／S9、[apply-ideas 02](../apply-ideas/02-排程.md)

## 使用者原文（11-05 晚，字句照原話；全文在 [json-argv README](../../05/json-argv/README.md)、[07](../../05/json-argv/07-使用者回覆-11-05晚.md)）

> 另一面則是這東西可以給人使用，畢竟你讓人去寫json，其實不太方面。
> 若是要給人操作的(或是agent使用shell工具操作的)，那就是用法要遵循unix/linux習慣，man/--help要有，設計要符合人體工學(以人爲主)。若是單純的aos函數，不需要給人操作的，那就是argv的旗標盡量不要濫用，大多東西都走要給stdin的json。
> 從一開始設計程式的時候就該想好這個程式是設計給誰用的了。不過就像先前說的，依據實際需要去做吧，比如方便與否。
> 子資料夾就是子動作，我覺得這個最好，但這個之後實作的時候我要看一眼，怕有些問題。
> 你要在argv塞一些不會在stdin裏面出現的東西的話，那代表這個程式就比較偏向於給人用的那種。

11-06 頂層與使用者同意：這份慣例在今晚家機 S8（拆大檔、aos-agent 拆套件、說明只留英文 `--help`）與 S9（命名）**之前**定下，S8／S9 照著做一次。

## 一句話結論

**給人用的指令現在缺的不是 `--help`（全有了），是 `--help` 沒分層、錯誤行的 usage 兩極、人看的輸出不齊**——慣例只要定三件事：① 每個子命令一份自己的英文 `--help`（頂層一屏、子命令一屏、長篇規則進 README）；② 錯誤行後面只接**那個子命令**的一行 usage 或 `see 程式 子命令 --help`；③ 會列資料的子命令都有 `--json`、人看的一列一筆 TAB 分欄。其餘（長旗標、位置參數、不互動、不顏色、env 只當人殼預設）現況已經合，寫成條文就好。子命令套件照「群組＝子資料夾、動作＝模組、顯式派發表」拆，S8 今晚做 aos-agent 時給使用者看一眼。

## 分檔目錄

| 分檔 | 涵蓋 |
|---|---|
| **[01-樣本-aos-agent](01-樣本-aos-agent.md)** | **使用者說「實作的時候我要看一眼」的那份**：照慣例後 `aos-agent --help`、`ctl --help`、`ctl add`／`say`／`listen --help` 全文，`cmd/aos-agent/` 子資料夾結構示意 |
| [01-樣本-aos-daemon-ctl](01-樣本-aos-daemon-ctl.md) | 同上的 aos-daemon-ctl：頂層、`add`、`ls` 的 `--help`；單檔不拆、只拆 help 的做法 |
| [02-盤點](02-盤點.md)（資料檔 [02-盤點.csv](02-盤點.csv)） | 97 列（20 支指令＋75 個子命令＋lib 一列）：給誰用、旗標、`--help` 形狀、輸出、錯誤行、結束碼、讀的 env、跟草案差哪幾條 |
| [03-慣例草案](03-慣例草案.md)、[03-續](03-慣例草案-續.md) | H1～H16（03：給誰用、子命令結構與檔案結構、旗標、位置參數、`--help`／man、人看 vs `--json`；續：stdin 與優先序、錯誤與結束碼、互動與 `--yes`、顏色／tty、環境變數、字彙、`--version`、條文落點）；每條一句話＋理由，有爭議的 2～3 選項＋推薦 |
| [04-落到S8S9](04-落到S8S9.md) | 哪些併進 S8、S9、哪些排大重構後；跟 J2～J8 的分工；估時 |
| [05-邊緣與衝突](05-邊緣與衝突.md) | 邊緣狀況 18 條；跟現行條文、json-argv 代定、artifact 說明頁的衝突 11 條 |

## 方向題（原則推不出的；推薦放第一）

1. **子命令套件長什麼樣（S8 拆 aos-agent 就照這個；你說要看一眼）**
   - **群組＝子資料夾、動作＝模組檔、派發用一張顯式表 (Recommended)**：`aos_agent/ctl/add.py`、`aos_agent/say.py`…，每個模組頂端一個 `HELP` 字串就是那個子命令的 `--help`（第一行＝NAME 一句話），群組的 help 從各模組第一行拼；`SUBS = {"add": add, …}` 十行表、grep 得到、沒有 import 魔法。小動作同主題合一檔（start／stop／sleep／wake 一個 `phase.py`），不會長出一堆 <1 KB 小檔。後果：aos-agent 從 1,267 行一檔變約 15 個檔；lib 那邊「子資料夾＝子 method」是 aos-exec 照路徑找入口，cmd 這邊是 Python import，兩套字面不同、精神相同（一個動作一個地方、各自一份 help）。
   - 子資料夾＝子動作逐檔照抄 lib（`ctl/start.py`、`ctl/stop.py` 各一檔）：最整齊，但六個 20 行的小檔違反 STRUCTURE「小檔太多合併」。
   - 不拆套件、只把 HELP 拆成 per-sub 的 dict：最省，但 1,267 行留著，S8「沒有 >300 行」做不到。
2. **短旗標要不要**（P-44 說「沒有短旗標」；unix 習慣是 `-h`）
   - **只開 `-h`＝`--help`，其他一律長旗標 (Recommended)**：人反射性打 `-h`；`parse_cli`／`aos_flags` 各加一行。長旗標 agent 走 shell 時自解釋；人省字靠 `AOS_AGENT`／`AOS_DAEMON` 預設與 `using-aos-agent.sh`。
   - 完全不開：P-44 一字不改；`-h` 回 FlagUnknown（現況）。
   - 常用的開幾個（`-t` target、`-n` name、`-d` daemon、`-j` json）：最像 unix 工具，但每支要維護一張短名表、撞名要記。
3. **man 怎麼有**（你說「man/--help 要有」）
   - **`--help` 就是 man 的一屏版、README 是長版，不另寫 man 檔 (Recommended)**：`~/.local/bin` 沒有 man 目錄；寫 man 等於第三份說明。真要 `man aos-agent`，大重構後用 help2man 式小腳本從 `--help` 生 `cmd/<名>/man/`，零手寫。
   - 手寫 man page 進 `cmd/<名>/man/<名>.1`、install.sh 連進 `~/.local/share/man`：最正統，三份說明要同步。
4. **不可逆動作（`ctl rm` 刪 stack、`tools reset`、`llm reset`）要不要互動確認＋`--yes`**
   - **不問、不加 `--yes` (Recommended)**：unix `rm` 不問；agent 走 bash 會被問句卡死；防呆靠「名字必須位置參數明講、不吃 `AOS_AGENT`」（11-04 你已定 rm 這樣）＋ stack 的保護清單。`reset` 兩個現在靠 `--target`／`$AOS_AGENT` 定對象，建議 S9 改成也要明講（05 衝突 9）。
   - tty 才問、非 tty 不問、`--yes` 跳過：多一條「tty 改行為」的暗規則（H10 不要）。

## fable 代定（可翻案；細節在 03）

- 頂層 `--help` ≤ 40 行、子命令 ≤ 25 行、每行 ≤ 100 字；固定段序 NAME／usage／subcommands／flags／（一段散文）／exit codes／more。
- 錯誤行：頂層缺子命令＝列子命令名單＋`see X --help`；子命令層＝`(usage: 那個子命令那一行)`；子命令前 FlagUnknown 不附 usage（stdio-unify D9 照舊）。
- 人看的表無表頭、TAB 分欄（R15 照舊）；`#` 開頭＝註解行，`--json` 不印；清單空＝stdout 空、退 0（退 10 只給「查單件沒有」）。
- 全域旗標只放「選哪個容器」；`aos-grow --dry-run` 這種全域開關算例外、不改。
- 不做 `--version`、不做 `--quiet`／`--verbose`、不做顏色、不做進度條。
- 條文落點：P-44 擴一段「給人用的那類」（J7 同日照實作寫），cmd/README 加「慣例」一節指過去；impls/docs/04 加一句。
