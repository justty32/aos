Argon（Gemini 4 Argon High，plan 模式）審本線報告初稿的 18 點，逐點對過程式與文件後的採納表：採納 16、只留底 1、核過不採納 1。Argon 的話不是使用者的話。

← [README](README.md)｜上一份：[03-不適用與刻意不同](03-不適用與刻意不同.md)｜原文：[04b-Argon原文](04b-Argon原文.md)

送審方式：提示寫成一個檔（初稿 README、00～03 全文＋骨架 README、`agent.py`、工具骨架 README、`agent_spec_parts.py` 全文、`agent_spec.py` 280–420 行、`agent_spec_load.py` 120–200 行、`agent_spec_lib.py` 20–80 行、N-70），放在只裝這一個檔的新空夾 `%TEMP%\argon-aos-vs-c-1119-r1`，`--add-dir` 給它、`-p` 只叫它讀那一檔。一次就過。

| 點 | Argon 說 | 頂層怎麼核 | 結論 | 改了哪 |
|---|---|---|---|---|
| A1 | 骨架 README 開頭第三點已寫工具程式與格「read when the agent runs」；那句也寫「next start」，初稿只抓到下半篇 | 讀骨架 README 開頭三點：屬實 | 採納 | 01 靜態連結、動態連結兩列；02 G2、G6；README 文件錯那節 |
| A2 | `defs.load` 只在收字串路徑時改寫成本機絕對路徑，收指示詞時寫成指示詞；「底夾不必在」講的是 N-70，不是工具實體 | 讀 `_moved`（`agent_spec_load.py` 129–136 行）：`root` 是 dict 就回指示詞。屬實 | 採納 | 01 可重現列；02 G3；README 第 3 條加「`("../底")`」 |
| A3 | `--compile` 不是全部直接蓋：`_metainfo.json` 合併、已有 README 不寫、拿掉宣告的舊檔不刪 | 讀 `write()`：屬實；骨架 README「What it does not touch」本來就寫明 | 採納 | 01 加 `make clean` 列；03 刻意不同那列 |
| A4 | 庫的 `lib.tool()` 是公開寫法；`agent.py` 對應 `static` 的是 `defs.load` 只交九欄 | 讀 README「Build on another agent.py」與 `Base`：屬實 | 採納 | 01 可見性列 |
| A5 | `interfaces.json` 頂層本來就開放，編譯器不該知道誰讀哪個鍵；真正的缺是 `interval_ms` 寫死 | 讀 `interfaces_json()`：只管 `aos-agent` 那格，其餘原樣寫出。屬實 | 採納 | 01 常數列、warning 列；02 G8 拿掉「沒人讀的 INTERFACES 鍵」警告 |
| A6 | 漏列：孤兒檔、`META` 鍵只加不刪、改 `DESCRIPTION` 後 README 不跟 | 讀 `write()` 與 `catalog.py` 166–174 行：check 只查兩者非空、不比對。屬實；README 已寫明，痛感低 | 採納（列小條） | 01 `make clean` 列；02 G13 |
| A7 | 底的格 `argv` 只在檔存在時才改寫，會漏改或誤改 | 讀 `agent_spec_load.py` 179 行 `os.path.exists`：屬實；沒實跑 | 採納 | 01 可重現列；02 G3 |
| A8 | 菱形 `defs.load` 底跑兩次；載完從 `sys.modules` 拿掉新 import 的非 aos 模組，可能變兩份模組 | 讀 99–123 行：屬實，卸載是設計（檔頭「07 A4」，為了 `import helper` 不撞）；今天看不出會痛的情境 | 只留底 | 02 G13 一條、03 header guard 列一句 |
| A9 | 漏列：跑著重新編譯時改狀態名會 `StateUnknown`、多檔之間會讀到一半新一半舊 | 兩件都在已裁「跑著讀到新定義＝特性」範圍內；改名那件骨架 README 第 3 點已寫，基底體檢（aos-base-audit-1119 P6、P7、P13）已記；跨檔一致性在那份「特性」一節也有 | 核過不採納 | — |
| A10 | 交叉編譯要本機讀得到庫，跟 C 的 `--sysroot` 一樣，不是缺 | 對：C 交叉編譯同樣要讀得到目標的標頭與庫 | 採納 | 01 交叉編譯列改「有（跟 C 同）」；03 不適用那列；拍板第 1 題拿掉這個代價 |
| A11 | G4 不是「標頭和 .c 分家」：`PARAMS` 與 `run` 在同一支 `tool.py`；是執行原始碼、腦看產物，屬 G7 的特例 | 讀工具骨架 README：`_entry` 跑 `python3 tool.py`、腦讀 `_tooldef.json`。對 | 採納 | 02 G4 標題與「跟 C 比」；README 第 4 題併進 G4 |
| A12 | 第 2 題 c（版本戳寫進 `_metainfo.json`）碰已裁；選項綁成累加；少了「真的靜態連結」選項 | 「不記帳」裁的是不記編譯紀錄，版本戳鄰近同一精神且破壞一字不差；三點都成立 | 採納 | 02 G2 補法；README 第 2 題改成可複選、加 c 真的靜態連結、寫明不列戳記進產物 |
| A13 | 直接拿 `--dry-run` 跟夾比，正常的夾永遠「不同」（README、`_metainfo.json` 保留規則） | 對照 `compile()` 與 `write()`：屬實 | 採納 | 02 G7 補法；README 第 4 題 a、d |
| A14 | 第 3 題 a：錯誤行是回給腦的、且沒報錯的情形抓不到；b：mtime 在 git 後不可靠；少了「aos-tools 比內容、印 stderr」 | 錯誤行回給腦：屬實（工具錯誤行原樣進 history）；mtime：同意 | 採納 | 02 G4 補法；README 第 4 題工具那半 |
| A15 | 第 1 題把三種代價不同的檢查綁一起；LLM 型別零代價；argv 分不出檔名；少了「拆開」選項 | 對 | 採納 | 02 G1 補法；README 第 1 題 a 改成拆開 |
| A16 | 第 5 題混了執行期撞名（G6）與工具描述長度（`tools_def` 的事），`agent.py --werror` 管不到 | 對：編譯時撞名已 SpecBad，G6 只在執行期 | 採納 | 02 G6、G8；README 第 5 題 |
| A17 | 拍板題漏了 G11（自己說要使用者判斷）、G3 的庫清單、G9／G10／G12；G11 補法有洞（死前剛重新編譯就抄到新版） | 對 | 採納 | README 加第 3、6、7 題；02 G11 寫明那個洞 |
| A18 | 照「無聲先」原則，G7 比 G4、G5 痛，應進前五 | 對：G4 照標準流程不發生、發生時有錯誤行；G5 只在兩個 home 並存 | 採納（把握中，照原則判） | 02 開頭加痛感順序；README 前五換成 G7、G6，G4、G5 下移 |

## 沒照 Argon 的地方

- 編號沒有重排：G1～G13 是初稿的代號，三位隊員的回報與重現腳本都對著它；痛感順序另寫一行。
- A9 不採納的理由見上表：使用者裁成特性，本線不再提成缺口。
