← [入口](../2026-10-21-ideas.md)｜涵蓋：9. 設定檔是唯一的位置參數、`$path` 改字串拼接（10-21 傍晚） › 9.1 原話、9. 設定檔是唯一的位置參數、`$path` 改字串拼接（10-21 傍晚） › 9.2 決定｜上一份 [05-7-審後的五個細縫與修正](05-7-審後的五個細縫與修正.md)｜下一份 [07-9-設定檔是唯一的位置參數-$path-改字串拼](07-9-設定檔是唯一的位置參數-$path-改字串拼.md)

### 9.1 原話

1. > 我回來了。windows不管，反正就是要WSL。
2. > 狀況都不錯。我這邊有想額外了解一些東西：做了的各程式的程式碼行數，他們是否都有用到aos-exec，還有--cfg是否可以簡化？比如aos-loop --cfg loop.json foo.json，簡化成aos-loop loop.json，然後loop.json內就包含各種東西？

   （頂層提議 `aos-loop [旗標] loop.json`：唯一的位置參數就是設定檔，要跑什麼寫在 run；參數放進 loop.json，(a) args key 或 (b) run 可以是陣列；命令列多給東西 (甲) 報錯 (乙) 接到參數後；傾向 (b)+(甲)。）
3. > Hmmm，關於--cfg這塊，我的想法是，我aos-exec loop.json，然後loop.json的內容是{"_exec":"aos-loop", "--interval_ms", "1000", "${AOS_CF}", "max":5, "run":["fsm.json", "--some-opt", "1"]}

   （頂層整理成 `{"_exec": ["aos-loop", "--interval-ms", "1000", {"$env": "AOS_CF"}], "max": 5, "run": ["fsm.json", "--some-opt", "1"]}`，並問：1. `${AOS_CF}` 在 argv 裡不認（N-45 不做字串內插），(a) 寫 `{"$env":"AOS_CF"}` (b) argv 開放 `${}`；2. loop 設定在大 JSON 裡面（`big.json#/loops/a`）時怎麼辦；3. 相對路徑：aos-exec cd 到 loop.json 的資料夾，run 裡 fsm.json 就是旁邊那個；4. 旗標＞設定檔不變；5. fsm、daemon 比照，daemon 起子 loop 也改經 aos-exec。）
4. > 1. a, 2. {"$env":"AOS_CF", "$at":  "loops/a"}, 我記得是$path和$prefix? 5.要。 大概就醬
5. > $path/$prefix和$at，能否想個好方法，將其統一整合？比如$path/$prefix就只是單純的字串拼接，頂多處理一下/，所以$path也可以透過$path:"#/loops/a"，來取代$at？

   （頂層給兩個選項：(a) 留 `$path`，開頭是 `#` 就直接接；其他情況中間補剛好一個 `/`；`$prefix` 照舊。(b) 改成 `$prefix`／`$suffix` 純拼接、不管 `/`。）使用者：
   > a
6. > 對了，$ref如果指向的是資料夾？

   （頂層：(a) 維持報錯 (b) 照 aos-exec 找入口的規則走進去 (c) 把整個資料夾組成一個 JSON 物件。）使用者：
   > 那還是維持報錯吧
7. 頂層說明 `$ref` 的 `#/` 和 `at` 是「把那段內容換進來」，`$env`＋`$path:"#/…"` 只是「拼出指標字串」，兩者不同。使用者：
   > 好，我覺得OK。只是哪天搞不好我又會覺得$path和$at的功能有所重疊，然後統一成一個名字。不過現在先這樣

   （這裡的 `$at` 指的是 `$ref` 的 `at`。）

### 9.2 決定

- **H1 設定檔是唯一的位置參數**（第 2、3 句；第 4 句之 4「旗標＞設定檔不變」沒被反對）：`aos-loop [旗標] 設定檔`、`aos-fsm [旗標] 設定檔`、`aos-daemon [旗標] 設定檔`。沒有 `--cfg`、命令列上沒有 XXX；設定檔必給、只能一個，多給位置參數＝usage 錯（(甲)）。旗標（loop、daemon 的 `--max`、`--interval-ms`、`--ctl`、`--state`）＞設定檔＞預設。
- **H2 設定檔可以寫 `檔#/指標`**＝讀那份檔裡那個位置的物件（第 4 句之 2 的用途；回答 [計畫](../2026-10-21-plan.md) § 1.2 第 4 題）。
- **H3 `run` 可以是陣列**（第 3 句的 `"run":["fsm.json", "--some-opt", "1"]`；(b)）：字串＝aos-exec 目標；陣列＝第一個是目標、其餘每拍傳給它（元素都要是字串）；物件＝錯。fsm 的 `val` 比照。
- **H4 argv 裡讀環境變數用 `{"$env": "AOS_CF"}`**（第 4 句之 1「a」），不開放 `${}`。loop.json 帶 `"_exec": ["aos-loop", {"$env": "AOS_CF"}]`，`aos-exec loop.json` 就把它跑起來。
- **H5 daemon 起子 loop 經 aos-exec**（第 4 句之 5「要」）。
- **H6 `$path` 是字串拼接**（第 5 句「a」）：換出來的值是字串時，`$path` 以 `#` 開頭＝直接接在後面（`{"$env":"AOS_CF","$path":"#/loops/a"}` → `/x/big.json#/loops/a`）；其他＝去掉基底結尾的 `/`、去掉 `$path` 開頭的 `/`，中間剛好一個 `/`（`a.txt` 和 `/a.txt` 都變成 `/ws/a.txt`）；寫絕對路徑也照這樣拼、不整個取代。`$prefix` 在 `$path` 之後套；不是字串或 null＝當沒寫、換出來不是字串＝靜默不作用。**不做 `$at`**（第 4 句之 2 的寫法由 `$path: "#/…"` 取代）。大 JSON 裡的寫法：`{"$env": "AOS_CF", "$path": "#/loops/a"}`。
- **H7 `$ref` 的 `at` 這裡不動**（第 5 句頂層提醒、使用者沒反對）；10-23 已刪、位置一律寫 `檔#/指標`（[daemon 的 ctl 與 `$ref`](../2026-10-23-daemon-ctl-ref.md)）。
- **H8 `$ref` 指到資料夾＝讀不到、算錯**（第 6 句「維持報錯」），測試釘住。
- **使用者留意**（第 7 句）：`$path` 與 `at` 日後可能統一成一個名字；現在先這樣。
