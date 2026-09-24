← [aos-agent](README.md)｜[spec 總導航](../README.md)

# 1.8 `tools add`：裝一個工具包，或原地引用工具（09-24 tools-base 補；access-impl 擴充）

```
aos-agent tools add NAME|DIR|FILE.json [--target DIR] [--as NEW | --as OLD=NEW[,OLD=NEW…]] [--only a,b] [--root DIR] [--force]
```

一句話：**把一個工具包複製進 agent 家的 `tools/`（或只在 `info.tools` 引用一個現成的工具檔／資料夾），下一批工具就能用，不用重 `start`。**
列、拿掉、改名在 [tools-manage.md](tools-manage.md)。
內建的只有 `base`（read／write／edit／bash／grep／find／ls，裝了就能當 coding agent 用）；每個工具怎麼用、錯誤長怎樣在 [proto5/tools/README.md](../../tools/README.md)。

## 工具包長什麼樣

一個資料夾 `<名>/`，裡面：

| 檔 | 必要 | 做什麼 |
|---|---|---|
| `<名>.json` | 要 | 工具陣列，格式照 [agent.md §3.3](../agent/info.md)；`_meta.argv[0]` 寫 `tools/<名>/<程式>`（相對 agent 家） |
| 工具程式 | — | stdin 收 arguments、stdout 回結果（agent.md §3.3），要有執行位 |
| `config.json` | 可省 | 工具包自己的設定；`base` 用它的 `root` 當工作根目錄 |

對象怎麼判斷（09-24 access-impl）：

| 給的 | 算 | 做什麼 |
|---|---|---|
| `NAME`（不含 `/`、也不是存在的 `.json` 檔） | 內建工具包 `proto5/tools/<NAME>/` | 裝（下面「裝＝做哪幾件事」） |
| 含 `/` 的資料夾，裡面有 `<資料夾名>.json` | 自己寫的工具包 | 裝 |
| 含 `/` 的資料夾，沒有 `<資料夾名>.json`（例 `../util-tools`） | 原地引用整個資料夾 | 不複製，`info.tools` 加一條；裡面一個 `*.json` 都沒有＝`NotFound` |
| 以 `.json` 結尾、存在的檔 | 原地引用單一工具檔 | 同上；檔不在就照工具包名字驗（＝`BadName`，訊息附「找不到 <路徑>」） |

路徑照殼的目前資料夾算。原地引用寫進 `info.tools` 的路徑：在家裡的寫相對家、家外的寫絕對路徑。
`--root`、`--force` 只給裝包；原地引用給了＝用法錯 2。原地引用的那個檔或資料夾已被某條讀到＝`AlreadyExists`（改名用 `tools alias`、拿掉用 `tools rm`）。

`--as`、`--only`（兩種都可用）：那條寫成 `tools` 元素的 `$opt`（[agent §3.4](../agent/tools-opt.md)）。
`--only a,b` 是原名、逗號分隔、不可空、不可重複；`--as OLD=NEW[,…]` 逐支改名；`--as NEW`（沒有 `=`）只在挑完恰好一支時可用，否則用法錯 2（訊息列出有哪幾支）。
寫法錯（空名字、重複、`a=`）＝用法錯 2；原名不在檔裡＝`ToolInvalid`。

## 裝＝做哪幾件事（照順序）

整段持著**管理鎖** `<家>/.admin.lock` 的 flock（astra 審查後改；access-impl #4 起不再鎖會被 rename 的 `info.json`），同一個家同時兩個會排隊。細節見 [tools-manage.md](tools-manage.md)。

1. 驗，照這個順序，第一個不過的就報：家要讀驗得過（`NotAnAgent` 等照 §1；家裡已有的工具檔也要驗得過）→ 工具包：名字只能英數、`_`、`-`（`BadName`）、
   資料夾要在（`NotFound`，訊息列出內建有哪些）、`<名>.json` 照 agent.md §3.3 驗（`ToolInvalid`）→ `--root` 給了就要是存在的資料夾（`NotFound`）→
   **裝過了**＝`tools/<名>.json` 在、`info.tools` 也涵蓋它＝`AlreadyExists`（加 `--force` 重裝；工具檔在但 info 沒登記＝上次沒裝完，照樣往下做、當修復）→
   新工具跟家裡其他工具檔同名＝`ToolInvalid`，列出撞到哪個檔（有 `--as`／`--only` 時改由下面的試算抓）→
   `info.tools` 要改、又不是「字面陣列、元素是路徑字串或字面 `$opt` 物件」（例如用 `$ref`）＝`FieldTypeMismatch`，請人自己加 →
   （09-24 access-impl）**整份試算**：用改好的 `info.tools`、把新工具檔當作已經在 `tools/<名>.json`，照 agent §3.3／§3.4 讀一次全部工具，撞名等就拒絕。
   任何一條不過：退 1、什麼都不寫。**寫進家的工具檔就是驗過的那份**（只讀一次）。
2. 程式複製到 `tools/.<名>-<版>.tmp/`（不含 `<名>.json`、`__pycache__`；`<版>` 是奈秒時間）→ 放 `config.json`：給了 `--root` 就寫 `{"root": <絕對路徑>}`；
   沒給就沿用 `tools/<名>/config.json`（有的話）→ rename 成 `tools/.<名>-<版>/`。`config.json` 的 `root` 是相對路徑（相對 agent 家）就把那個資料夾建好。
3. `tools/<名>` 是**符號連結**、指到 `.<名>-<版>`：新連結先建好、再 `rename` 蓋過舊的——原子，tick 不會看到「工具檔在、程式不在」。
   舊式安裝（`tools/<名>` 是真資料夾）先挪開，只有這一次有短暫空窗。
4. **最後**寫 `tools/<名>.json`（`.tmp` 再 rename）。第 3、4 步之間工具檔還是舊的、程式已是新的；工具包改了參數時這一瞬間可能對不上，下一格就好。
5. `info.tools` 沒涵蓋 → 在陣列尾巴補 `"tools/<名>.json"`（有 `--as`／`--only` 就補 `$opt` 物件）、整份重寫 `info.json`（原始內容，不展開 `$ref`）。
   **涵蓋**＝有一條（`$opt` 物件看它的 `$val`）等於 `tools/<名>.json`，或等於 `tools` 整個資料夾且那條沒 `only`、或 `only` 挑到這包至少一支。`init` 的家是 `"tools"` 整個資料夾，不用補。
   已涵蓋又給了 `--as`／`--only`：那條就是 `tools/<名>.json` → 選項整個換成這次給的；那條是整個資料夾 → `as` 併進去，`only` 改成「這條原本挑到的其他檔的工具＋這次的 `--only`」。
6. 刪掉這個包的舊版本與之前崩潰留下的殘渣：`tools/` 下名字是 `.<名>-<數字>`（可帶 `.tmp`、`.old`、`.link-<pid>`）、又不是現在連結指的那個。別的包的不碰。

崩在半路：重跑一次同一行指令就好（第 1 步的「修復」＋第 6 步的清殘渣）。
7. （09-24 access-impl）家裡還沒有 access 檔（[agent/access.md](../agent/access.md)）就建一份預設：`{"mounts": {"ws": <工作根目錄>}, "cwd": "ws", "net": false}`，工作根目錄＝`--root` 的絕對路徑或 `workspace`；印出來。**已有就不動、也不印那兩行**（09-24 access round2：`init` 生的家一律已經有 access.json）。原地引用不建。

成功印：`installed <名> → <工具檔>（N 個工具：…；改名的寫 `原→新`）`；改了 info 再一行（補了什麼或第幾條改成什麼）；家裡還沒有 access 檔才建一份、多印兩行（上面第 7 點）；有工作根目錄再一行（沒 access 檔＝路徑與改哪個檔；有＝牢裡的 `/work/<cwd>` 對到哪、看 `access ls`，另一行說 `config.json` 的 root 只在不關牢時用；（09-24 access round2）access 檔早就在、又給了 `--root X`、但表的起點沒對到 X 時再多一行：`要讓工具在 X 工作：aos-agent access set <cwd名> X --target <家>`）；最後「下一批工具生效，不用重 start」。退 0。
原地引用印：`referenced <路徑>（原地引用、不複製；N 個工具：…）`、`info.json 的 tools 補了 …`、最後同一句。
工作根目錄包含 agent 家（例如 `--root` 給了家的上層；兩邊都解開符號連結再比）時 stderr 多一行注意：模型改得到自己的 `info.json`、記憶與 `state.json`。

## 工作根目錄（base 用）

- 工具的 cwd 照 agent.md §3.3 是 agent 家；`base` 的七支工具各自讀**自己資料夾**的 `config.json`，`root` 相對 agent 家；沒這個檔或沒這格＝`workspace`。
- 沒給 `--root`：工作根目錄＝`<家>/workspace/`（裝的時候建好）。要指到某個專案：`--root ~/proj`，或事後改 `tools/base/config.json`，下一次叫工具就生效。
- read／write／edit／grep／find／ls 的路徑解開符號連結後必須在工作根目錄裡（`OutsideRoot`）；read／edit／write 打開之後再用 `/proc/self/fd` 驗一次。
  這是**防模型手滑、不是沙盒**：檢查跟打開之間有別的行程在換路徑的話擋不完全；**bash 本來就不關**——它只是 cwd 在工作根目錄，指令想碰哪裡都碰得到；（09-24 access-impl）家裡有 access 檔時整支工具關在牢裡（[access.md](access.md)）。

## 這一節沒管的

見 [tools-manage.md](tools-manage.md#這兩節沒管的)。
