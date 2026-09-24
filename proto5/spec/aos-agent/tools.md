← [aos-agent](README.md)｜[spec 總導航](../README.md)

# 1.8 `tools add`：裝一個工具包（09-24 tools-base 補）

```
aos-agent tools add NAME|DIR [--target DIR] [--root DIR] [--force]
```

一句話：**把一個工具包複製進 agent 家的 `tools/`，下一格就能用，不用重 `start`。**
內建的只有 `base`（read／write／edit／bash／grep／find／ls，裝了就能當 coding agent 用）；每個工具怎麼用、錯誤長怎樣在 [proto5/tools/README.md](../../tools/README.md)。

## 工具包長什麼樣

一個資料夾 `<名>/`，裡面：

| 檔 | 必要 | 做什麼 |
|---|---|---|
| `<名>.json` | 要 | 工具陣列，格式照 [agent.md §3.3](../agent/info.md)；`_meta.argv[0]` 寫 `tools/<名>/<程式>`（相對 agent 家） |
| 工具程式 | — | stdin 收 arguments、stdout 回結果（agent.md §3.3），要有執行位 |
| `config.json` | 可省 | 工具包自己的設定；`base` 用它的 `root` 當工作根目錄 |

`NAME`（不含 `/`）＝`proto5/tools/<NAME>/`；含 `/` 的＝那個資料夾（自己寫的工具包）。

## 裝＝做哪幾件事（照順序）

整段持著 `<家>/info.json` 的 flock（只讀不寫），同一個家同時兩個 `tools add` 會排隊、不會互相蓋掉 `info.tools`。（09-24 astra 審查後改）

1. 驗，照這個順序，第一個不過的就報：家要讀驗得過（`NotAnAgent` 等照 §1；家裡已有的工具檔也要驗得過）→ 工具包：名字只能英數、`_`、`-`（`BadName`）、
   資料夾要在（`NotFound`，訊息列出內建有哪些）、`<名>.json` 照 agent.md §3.3 驗（`ToolInvalid`）→ `--root` 給了就要是存在的資料夾（`NotFound`）→
   **裝過了**＝`tools/<名>.json` 在、`info.tools` 也涵蓋它＝`AlreadyExists`（加 `--force` 重裝；工具檔在但 info 沒登記＝上次沒裝完，照樣往下做、當修復）→
   新工具跟家裡其他工具檔同名＝`ToolInvalid`，列出撞到哪個檔 → `info.tools` 要補、又不是字面字串陣列（例如用 `$ref`）＝`FieldTypeMismatch`，請人自己加。
   任何一條不過：退 1、什麼都不寫。**寫進家的工具檔就是驗過的那份**（只讀一次）。
2. 程式複製到 `tools/.<名>-<版>.tmp/`（不含 `<名>.json`、`__pycache__`；`<版>` 是奈秒時間）→ 放 `config.json`：給了 `--root` 就寫 `{"root": <絕對路徑>}`；
   沒給就沿用 `tools/<名>/config.json`（有的話）→ rename 成 `tools/.<名>-<版>/`。`config.json` 的 `root` 是相對路徑（相對 agent 家）就把那個資料夾建好。
3. `tools/<名>` 是**符號連結**、指到 `.<名>-<版>`：新連結先建好、再 `rename` 蓋過舊的——原子，tick 不會看到「工具檔在、程式不在」。
   舊式安裝（`tools/<名>` 是真資料夾）先挪開，只有這一次有短暫空窗。
4. **最後**寫 `tools/<名>.json`（`.tmp` 再 rename）。第 3、4 步之間工具檔還是舊的、程式已是新的；工具包改了參數時這一瞬間可能對不上，下一格就好。
5. `info.tools` 沒涵蓋（沒有一條等於 `tools/<名>.json` 或 `tools`）→ 在陣列尾巴補 `"tools/<名>.json"`、整份重寫 `info.json`（原始內容，不展開 `$ref`）。`init` 的家是 `"tools"` 整個資料夾，不用補。
6. 刪掉這個包的舊版本與之前崩潰留下的殘渣：`tools/` 下名字是 `.<名>-<數字>`（可帶 `.tmp`、`.old`、`.link-<pid>`）、又不是現在連結指的那個。別的包的不碰。

崩在半路：重跑一次同一行指令就好（第 1 步的「修復」＋第 6 步的清殘渣）。
成功印：`installed <名> → <工具檔>（N 個工具：…）`；補了 info 再一行；有工作根目錄再一行（絕對路徑、改哪個檔）；最後「下一格就生效，不用重 start」。退 0。
工作根目錄包含 agent 家（例如 `--root` 給了家的上層；兩邊都解開符號連結再比）時 stderr 多一行注意：模型改得到自己的 `info.json`、記憶與 `state.json`。

## 工作根目錄（base 用）

- 工具的 cwd 照 agent.md §3.3 是 agent 家；`base` 的七支工具各自讀**自己資料夾**的 `config.json`，`root` 相對 agent 家；沒這個檔或沒這格＝`workspace`。
- 沒給 `--root`：工作根目錄＝`<家>/workspace/`（裝的時候建好）。要指到某個專案：`--root ~/proj`，或事後改 `tools/base/config.json`，下一次叫工具就生效。
- read／write／edit／grep／find／ls 的路徑解開符號連結後必須在工作根目錄裡（`OutsideRoot`）；read／edit／write 打開之後再用 `/proc/self/fd` 驗一次。
  這是**防模型手滑、不是沙盒**：檢查跟打開之間有別的行程在換路徑的話擋不完全；**bash 本來就不關**——它只是 cwd 在工作根目錄，指令想碰哪裡都碰得到。

## 這一節沒管的

- 家裡已有的工具檔壞了（`ToolInvalid`）時 `tools add` 不動它：先手動修好或刪掉那個檔再裝。
- `tools`／`tools ls`（列工具）、`tools remove`、`enable`／`disable`：使用者的構想在 [thinking/aos-agent.md](../../../thinking/aos-agent.md)，這輪不做。要拿掉就刪 `tools/<名>.json`（和 `tools/<名>/`）。
- `init --tools base`（生家時順便裝）：未來可加，等同 `init` 之後 `tools add`。
- bash 的白名單／沙盒、工作根目錄以外的讀權限：沒有，等使用者拍（見 [tools-base 報告](../../notes/2026-09-24-tools-base.md)）。
