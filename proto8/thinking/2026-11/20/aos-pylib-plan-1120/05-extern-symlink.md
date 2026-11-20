設計之五：`defs.extern` 的 symlink 版——語意、連結寫相對還是絕對、目標不存在時、哪些欄位能用、`--dry-run` 顯示什麼、`defs.load` 的底有 extern 時、定義夾被抄／進 git／搬機器／放 Windows 檔案系統時會怎樣、`agent_def check` 查不查斷鏈、「別濫用」的說明文字草稿。

← [README](README.md)｜上一份：[04](04-函數-依賴與互動.md)｜下一份：[06-對照與衝突](06-對照與衝突.md)

依據是頂層對使用者第二段話的**解讀**（[00](00-使用者原話.md)）：extern 留著、換意思，編譯時只產生一個 symlink（連結檔：一個指到別的檔的小檔，讀它等於讀它指的那份）。

## 先講結論

```python
system=defs.extern("../shared/system.txt")     # 編譯時：定義夾的 system.txt 是一個連結 → ../shared/system.txt
```

- **一個參數：目標路徑。** 連結放在那一欄本來的檔名上（`system.txt`、`tools.json`、`llm.json`、`hooks.json`、`fsm.json`）。
- **你寫什麼，連結裡就存什麼**：寫相對路徑＝從定義夾算的相對連結；寫絕對路徑＝絕對連結。庫不替你轉。
- **目標不存在＝編譯報錯、什麼都不寫。**
- **四個欄位隨便指（system、tools、llm、hooks）；fsm 只能指同一夾裡的檔。**
- 手改那份目標檔，不用重新編譯就生效——這就是它跟「Python 讀檔進來」的差別，也是它危險的地方。

## 逐項

| 項 | 定法 | 理由／依據 |
|---|---|---|
| 參數 | `defs.extern(目標)`，目標是一個普通字串 | 使用者：「創建一個symlink，指向我們要的檔案路徑」 |
| 相對還是絕對 | 照你寫的字面存進連結 | 「寫什麼就做什麼」（KISS 條）；相對的跟著整棵樹搬不會斷，絕對的單搬定義夾不會斷，兩種都有人要 |
| 相對路徑從哪算 | 從**編譯進去的那一夾**（連結所在的夾）；`--compile 別的夾` 時也是從那個夾算 | 連結檔本來就這樣算；通常就是 `agent.py` 那一夾 |
| `defs.env(…)`／`defs.home(…)` 當目標 | 不收（`SpecBad`） | 連結裡存不了環境變數；編譯時展開會把這台機器的路徑寫死 |
| 目標不存在 | `SpecBad`：`extern("x") for SYSTEM: x does not exist (seen from 夾)`，不寫任何檔 | 斷掉的 `system.txt` 連結執行時是**靜靜地沒有 system 文字**（格程式看不到檔就當沒有），不能留到那時候 |
| 目標是資料夾、或繞回連結自己 | `SpecBad`；後者的訊息特別寫：`defs.extern now takes the file to link to; "system.txt" is the link itself` | 昨天的寫法 `defs.extern("system.txt")` 今天正好是「連到自己」。怎麼判：把目標解成真實路徑，跟「定義夾的真實路徑＋連結的檔名」比（連結那個檔名本身不解），這樣第二次編譯（那裡已經是連結）不會誤判，`./system.txt`、繞一圈指回來的也抓得到（Argon A7） |
| extern 包在串列裡（`tools=[defs.extern(…)]`） | `SpecBad`：`extern stands for the whole field: write tools=defs.extern(...)` | tools、hooks 平常收串列，容易寫錯 |
| 目標內容驗不驗 | 不驗 | 它是你自己的檔（昨天的 extern 也不驗） |
| `interfaces.json` | 一律寫預設檔名；不再出現手寫檔的名字 | 連結就坐在預設檔名上 |
| 不宣告 fsm（eca 版） | 連結坐在現有 `interfaces.json` 宣告的那個檔名上 | 同今天找檔名的規矩 |
| `--dry-run` | 那一格印 `{"$symlink": "../shared/system.txt"}` | 其他格是內容；`$` 開頭的鍵在 aos 的 json 裡本來就是「指示」，不會跟真的內容搞混 |
| 寫檔 | 先做一個暫存連結再改名換上去；原來那裡是普通檔或舊連結都直接換掉；**不碰目標** | 同「直接蓋」 |
| 之後那一欄不再寫 extern | 下次編譯把連結換成普通檔；目標不動 | 同上 |
| `defs.load` 的底有 extern，目標在底那一夾**外面** | 欄位照樣拿得到（`base.system` 是那個 extern），衍生那支用它＝也編成連結、指同一份目標；相對路徑等到知道編譯進哪一夾時才換算 | 產物指的是共用的那份檔，不是底那一夾，不違反 N-70 |
| `defs.load` 的底有 extern，目標在底那一夾**裡面**（同夾的手寫檔） | 用到那個欄位＝`SpecBad`（同昨天：「手寫檔，沒有可接的，自己寫」） | 不然衍生那夾的連結會指回底那一夾，執行時去別的定義拿東西，違反 N-70（Argon A8） |
| `agent_def check` | **加一項**：定義夾裡宣告的檔是斷掉的連結＝報一條問題 | check 是唯讀的，查得起；今天不查 |

## 哪些欄位能用

| 欄位 | 能不能 | 說明 |
|---|---|---|
| system、llm、hooks、tools 的內容 | 能 | 讀的程式都是普通開檔，會跟著連結走 |
| tools、hooks 裡面的相對路徑 | 能，但要先實測 | 目標那份 `tools.json`／`hooks.json` 裡寫的相對路徑（工具的 `path`、hook 的 `handler`）從哪一夾算：讀程式看是從**連結所在的定義夾**算（兩邊都沒把連結解成真實路徑），不是從目標那一夾；沒實跑，施工第一步一起測 |
| fsm | **只能指同一夾裡的檔**（路徑整理後沒有上一層、沒有子夾；`./fsm.hand.json` 算同一夾），其他＝`SpecBad` | `aos-loop`／`aos-fsm` 會先把連結解成真實路徑，再把「定義夾」當成真實路徑那一夾；指到夾外，格程式會去別的夾找 `tools.json`。這是讀程式推的、沒實跑，施工第一步先實測，沒事就放寬 |

**同夾連結＝「這份我手寫、編譯別蓋它」的做法**：`system=defs.extern("system.hand.txt")`。編譯只會重做那個連結，`system.hand.txt` 永遠不碰。昨天 `defs.extern("system.txt")` 的用途由它接手（五個欄位都行）；要不要另外再有「設定檔列出不產出的檔」是 [08](08-待裁題.md) 第 1 題。

## 定義夾被搬、被抄時

| 動作 | 連結會怎樣 | 驗過嗎 |
|---|---|---|
| `cp -r` 到同一層 | 連結照抄，相對的照樣通 | 實測 |
| `cp -r` 到不同深度 | 連結照抄、文字不變，相對的**斷** | 實測 |
| `cp -rL` | 變成普通檔（當下內容的拷貝） | 實測 |
| `agent_def new` 抄一份 | 同 `cp -r`（連結照抄、文字不改）；另外 `tools.json` 若是連結且有路徑要改寫，會被換成普通檔 | 讀程式 |
| git（Linux） | 存成連結（mode 120000），簽出來還是連結 | 實測 |
| `git archive`（測試用的乾淨複本） | 連結照樣在 | 實測 |
| git 在 Windows 簽出（公司 Windows 那份 clone） | 沒開 symlink 支援時變成一個內容是路徑的文字檔 | 沒實測，git 的已知行為 |
| 搬到另一台 | 相對的＋目標一起搬＝通；絕對的＝那台同路徑有檔才通 | — |
| 放在 `/mnt/c`（WSL 看 Windows 磁碟） | WSL 裡建得起來、讀得到 | 實測（公司 WSL）；從 Windows 那一側看是什麼沒驗 |

所以：**repo 裡的範本不放連結**（骨架不用 extern）；測試在暫存夾裡自己建。

## 連結在的時候，別的指令去寫那份檔會怎樣

| 誰寫 | 結果 |
|---|---|
| `agent_def system set` | 連結被換成普通檔，目標沒動；下次編譯又換回連結（跟「手改的產物下次被蓋」同一條） |
| `agent_def llm set`、`agent_def tools add`、`aos-tools add --file` | **寫穿**：改到的是目標那份，所有連到它的定義一起變 |
| `self_*`（改自己 stack 那一層） | 不碰定義，照舊 |
| guard 的「不准寫定義夾」 | 照目標的真實位置判；目標在定義夾外就保護不到 |

寫穿這件事跟「產出後的東西就跟他沒關係了」有出入，列在 [06 的衝突第 4 條](06-對照與衝突.md#要帶給使用者的衝突)。

## 「別濫用」的文字草稿（英文；程式輸出一律英文）

函式的說明（`defs.extern` 的 docstring）：

```
extern(target): compile this field as a symbolic link to a file you write yourself.

    system=defs.extern("../shared/system.txt")   # system.txt in the definition becomes a link to that file

The link holds the path exactly as you wrote it: a relative path is counted from the definition folder.
Compiling again only remakes the link; it never touches the target. Editing the target takes effect
without recompiling.

DO NOT OVERUSE THIS. A link makes the definition depend on a file outside it:
  - copy or move the definition without the target and it breaks (the agent then runs with no system text,
    silently); `agent_def check` reports a broken link, nothing else does;
  - some commands write through the link and change the shared file for every definition that links to it
    (agent_def llm / tools); others replace the link with a plain file (agent_def system);
  - git on Windows may check a link out as a text file.
If all you want is the text of a file at compile time, read it in Python instead: system=open("x.txt").read().
Use extern only when one hand-written file must stay the single live copy.
```

`--help` 加的一段：

```
defs.extern("PATH") compiles a field (system, tools, llm, hooks; fsm only for a file in the same folder)
as a symbolic link to PATH instead of writing a file. Use it sparingly: see "extern" in the README.
```

編譯時不另外印提醒：使用者要的是「註釋要說」，寫的那一行 `--compile` 的輸出照常是 `wrote 夾/system.txt -> ../shared/system.txt`，看得出它是連結。骨架 README 的「extern」一節用上面那段的中文版。
