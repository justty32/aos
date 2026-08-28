# `.aos` 資料夾說明

> **本檔全部是說明性文件，normative 一律以 [SPEC](SPEC.md) 為準。** 回合語意與
> instruction 格式（A／C／F 區）早先已收編，命名與版面、交接協定、世界與 git
> （B／D／E 區）也在 M1 收編完畢。**本檔與 SPEC 不一致時以 SPEC 為準**，該修的是本檔。
> 留在這裡的是條文不寫的東西：為什麼長這樣、實作現況、還開著的問題。

← [文件索引](README.md)｜[roadmap](roadmap.md)｜指示詞 [inst-directives](inst-directives.md)

**這份不是規格，是說明。** `.aos` 長什麼樣、各個檔案什麼意思、交接怎麼做，條文在
[SPEC](SPEC.md)；下面每一節都標出對應的條款編號，照著過去看。

**核心實作已經落地。** `aos init`、`aos deliver [<folder>]`、`aos exec [<folder>]`、
`aos exec --loop <毫秒>` 讀得懂本檔描述的一切：命名標準、三步交接（含投遞）、彙整、
回合語意、回合計數器、批 header sidecar、退出碼、版本檢查。實作細節見
[`core/inst/docs/`](../core/inst/docs/)。**還沒實作的只有 `insts/` 底下的其他
CPU**——分層本身（`aggregate_instructions` 等以 instruction 檔路徑為參數的那幾支）已經
能對 `insts/llm.json` 運作，缺的是叫得動它的子命令。

模型的**為什麼**在 [`wf/workflows/ideas/turn-based-folder.md`](../wf/workflows/ideas/turn-based-folder.md)，
做的**順序**在 [roadmap](roadmap.md)。彼此衝突時：條文看 [SPEC](SPEC.md)、理由看 idea、
排程看 roadmap、現況與說明看本檔。

---

## 一、一句話

```text
<folder>            ＝ 世界（被演化的狀態）
<folder>/.aos       ＝ 這個世界的指令區
aos exec <folder>   ＝ 推進一回合
```

沒有常駐狀態。**世界在檔案系統上，不在任何行程的記憶體裡。**

## 二、命名標準

> 條文：[SPEC](SPEC.md) **§B-1**（狀況是**封閉清單**，加新狀況字＝修憲）。

```text
<名字>.<副檔名>.<狀況>
   │       │        └── 第二個 .xxx：這個檔案／資料夾目前的狀況
   │       └────────── 第一個 .xxx：副檔名
   └────────────────── 名字
```

**副檔名**

| | |
|---|---|
| `.json` | JSON 檔 |
| `.d` | 一般資料夾 |
| `.tempd` | 投遞匣資料夾 |

**狀況**（就這三個，不要再加新的字表達同一件事）

| | |
|---|---|
| `.temp` | 還在生成，別碰 |
| `.runi` | 已被取走、正在跑 |
| `.bad` | 內容無效，已被隔離 |

這條標準是為 `.aos` 訂的，但**不限於 `.aos`**。

## 三、版面

> 條文：[SPEC](SPEC.md) **§B-2**（版面樹）、**§B-3**（`turn`）、**§C-8**（header
> sidecar）、**§B-4**（`version`）。

```text
<folder>/                        ← 世界。這裡的一切就是狀態
    .aos/
        version                  ← 版面版本（見第九節）
        turn                     ← 回合計數器（這台機器的 PC，§B-3）
        .gitignore               ← §E-4 的 gitignore 政策，`aos init` 建（見第十節）
        inst.json                ← 核心 CPU 待執行的批次
        inst.json.temp           ← 彙整中的下一批
        inst.json.runi           ← 已取走、正在跑的那一批
        inst-head.json           ← 那一批的 header sidecar（§C-8）
        inst.tempd/              ← 投遞匣
            <pid>-<seq>.json     ← 投遞完成，等彙整（檔名見 §D-2）
            <pid>-<seq>.json.temp ← 還在寫，彙整者略過
        insts/                   ← 其他 CPU，一顆一份
            llm.json
            llm.json.temp
            llm.json.runi
            llm-head.json
            llm.tempd/
```

核心 CPU（`aos exec`，執行 POSIX 指令的那顆）的 instruction **直接放 `.aos/inst.json`**
——它是最核心的一顆，所以佔特權位置。其餘 CPU 一律收進 `.aos/insts/`，各自配同名的
`.temp`／`.runi`／`.tempd`。

**其他 CPU 最好也遵循同一套協定，但不強迫。**

## 四、路徑基準：一律是 `<folder>`

**同一個基準，沒有例外。**

| 誰 | 基準 |
|---|---|
| 子行程的預設 cwd（instruction 的 `cwd` 留空時） | `<folder>` |
| `stdin`／`stdout`／`stderr`／`exit` 的相對路徑 | `<folder>` |
| `$ref` 的相對路徑 | `<folder>` |

絕對路徑照字面用。

> **實作提示**：最省事的作法是 `aos exec` 自己一開始就 `chdir` 到 `<folder>`，後面
> 三項就自然成立，不必各自帶基準參數。

**這改變了 `inst` 現有的行為**。現在那四個路徑欄位是從**呼叫者的目錄**起算的（見
[`exec.md`](../core/inst/docs/exec.md)），因為重導向在子行程套用 `cwd` 之前就開好了。
改成 `<folder>` 基準之後，**同一份 instruction 從哪裡呼叫都是同一個意思**，資料夾才
真的可以整包搬走。舊的 `aos inst <file>` 模式反正要砍（[roadmap D8](roadmap.md#d8)），
不會有兩套基準並存的問題。

## 五、回合語意

- **一回合＝一整批。** `inst.json` 可以是單一 instruction 物件或一個陣列；整批驗證
  通過才會開始執行任何一筆。
- **回合內可以並行。** 每筆 instruction 自帶一個欄位，決定要不要開 thread 用
  non-blocking 的方式跑。遇到 non-blocking 那筆之後，**下一筆立刻啟動**。
- **回合邊界仍然是硬的。** `aos exec` 等**所有** thread 跑完才算本回合結束。並行只發生
  在回合**之內**。
- **沒有 `inst.json` ＝ 停留在目前回合**，不是錯誤，退出碼 0。
- 多個子行程同時繼承同一個終端時 stdout／stderr 會交錯——**這不修**，要乾淨輸出就各自
  重導向到不同檔案。

## 六、交接協定：三步，每步一次 `rename`

> 條文：[SPEC](SPEC.md) **§D-1**（三步）、**§D-2**（投遞與檔名）、**§D-3**
> （`deliver`）、**§D-4**（彙整規則）、**§D-5**（fsync 與發布順序）、**§D-6**
> （批 id 與去重）、**§D-7**（`.runi` 語意）、**§D-8**（`.bad` 誰清）。庫層的實際
> 行為見 [`core/inst/docs/handoff.md`](../core/inst/docs/handoff.md)。

```text
投遞  inst.tempd/<名>.json.temp ─rename─▶ inst.tempd/<名>.json
彙整  併成 inst.json.temp       ─rename─▶ inst.json
取件  inst.json                 ─rename─▶ inst.json.runi
```

| 步驟 | 誰做 | 規則 |
|---|---|---|
| **投遞** | 任何生產者（用 `aos deliver`） | 先寫 `<名>.json.temp`，寫完才 `rename` 成 `<名>.json`。檔名必須唯一，因為 `rename` 原子但**寫入不是**，共用檔名會互相蓋寫；`aos deliver` 用的是 `<pid>-<seq>`（§D-2），發布時排他、絕不覆蓋既有名 |
| **彙整** | 彙整者 | 把 `inst.tempd/` 底下所有**沒有狀況後綴**的投遞併成 `inst.json.temp`，完成後 `rename` 成 `inst.json` |
| **取件** | `aos exec` | 完整讀進記憶體後**立刻** `rename` 成 `inst.json.runi`，然後才執行；回合結束再刪掉 `.runi` |

**`.runi` 的意思是「正在跑」，不是「跑過」。**

- **回合正常返回就刪掉 `.runi`**——不論退出碼是 0 還是 1。行程還活著、回合確實結束
  了，就算裡面有指令失敗也一樣。並行的那些 thread 全部 join 完之後才刪。
- **行程死掉（crash、被 kill、斷電）`.runi` 就會留著**，因為沒有人走到刪除那一步。

**整批 JSON 解析失敗也算「回合正常返回」**，`.runi` 一樣刪掉。那批壞內容就此消失，
只在 stderr 留下一行診斷——這是刻意的取捨：讓資料夾在任何情況下都能繼續跑，比保留一份
沒人寫得對的 JSON 更重要。

所以這個不變式成立：

> **`.runi` 存在 ⟺ 有一回合沒跑完。**

**`.runi` 已存在時拒絕啟動**（退出碼 3）。它是固定名稱，所以天生就是一把鎖：上一回合
crash 留下的現場不會被靜靜蓋掉，也不會有兩支 `aos exec` 同時跑同一個資料夾。代價是
crash 之後要人來處理——**這是刻意的**。

回合裡**個別指令**的成敗不靠 `.runi` 表達，走每筆自己的 `exit` 欄位（第八節）。如果
回合回 1 也留著 `.runi`，一次 `fork` 失敗就會永久卡死整個資料夾，那不是我們要的。

每顆 CPU 各鎖各的：`inst.json.runi` 只鎖核心 CPU，`insts/llm.json.runi` 只鎖 LLM 那顆。

### 彙整的規則

- **只收沒有狀況後綴的投遞**。`<名>.json` 會被收，`<名>.json.temp`（還在寫）與
  `<名>.json.bad`（已隔離）不會。這條規則自動涵蓋未來新增的任何狀況。
- **順序不保證**。實作用檔名字典序即可——確定性有意義，但**投遞者不得假設任何順序**。
  需要先後關係就自己排進同一份投遞裡，不要靠彙整順序。
- **`inst.json` 已經有一份沒被讀走的批次時，這一輪不發布**，等下一輪再試。不覆蓋、
  不合併——「一回合＝一整批」的直接推論。
- **無效的投遞：噴 warning、把那一份隔離、繼續處理其餘的**。隔離就是就地改名加上
  `.bad` 狀況（`<名>.json` → `<名>.json.bad`），這樣它自然不會再被收，也留在原地供人
  檢查。一份壞投遞不會擋住整批。
- 彙整完的投遞在發布成功之後才刪除。

彙整還有兩件本節原本沒寫、M1 才收編進 SPEC 的事：**發布順序與 fsync**（§D-5——批
`.temp` → header `.temp` → rename header〔提交點〕→ rename 批 → 刪投遞，每步都
fsync），以及**批 id 去重**（§D-6——同一組投遞在崩潰後殘留時不會被發布第二次；只保證
「整組殘留」這個情況）。同時彙整會在批旁邊寫一份 header sidecar（§C-8）。三件事的實作
說明都在 [`handoff.md`](../core/inst/docs/handoff.md)。

### 彙整跑在哪裡

彙整**併進 `aos exec`**：迴圈體就是「彙整 → 取件 → 執行」，拆成兩條命令只會多一個要
協調的東西。

但**實作上要與 `aos exec` 解耦**。「彙整＋取件」這組動作之後會被別的東西用到——每顆
抽象 CPU 都要對自己那份 instruction 檔做同樣的事（`insts/llm.json` 配 `llm.tempd/`）。
所以它應該是一個**以 instruction 檔路徑為參數的獨立單元**，`aos exec` 只是它的第一個
呼叫者，不是它的擁有者。

## 七、instruction 的格式

以 [`core/inst/docs/format.md`](../core/inst/docs/format.md) 為準——那份寫的是現況。

本節原本列為「要加的」兩樣東西**都已經落地**：

- **並行欄位**（第五節）就是 `"parallel": true`。
- **`$ref`／`$env`／`$opt` 指示詞**。設計理由見 [inst-directives](inst-directives.md)，
  解析分層見 [`core/inst/docs/resolve.md`](../core/inst/docs/resolve.md)。

有一條分層之間的約束值得寫在這裡，因為它是**協定的一部分，不只是實作細節**：彙整
是把每份投遞 `read_all` 成結構、再 `write_all` 回去，所以**每份投遞都會被格式層完整
往返一次**。因此「還沒解析的指示詞必須能原樣寫回 JSON」。任何新增的指示詞都得滿足
這條，否則它會在彙整那一步被無聲吃掉。

## 八、退出碼

> 條文：[SPEC](SPEC.md) **§D-9**（M1 逐失敗模式實測後收編，涵蓋 `aos exec`／`init`／
> `deliver` 三支）。**下面這張表是舊版、只涵蓋 `aos exec` 的粗略分類，以 §D-9 為準。**

`aos exec` 的退出碼只回答「**這個回合有沒有正常跑完**」，**不回答**「回合裡的指令做得
好不好」。

| 碼 | 意思 |
|---|---|
| 0 | 回合正常跑完（**包含**「沒有 `inst.json`，無事可做」） |
| 1 | 函式庫層失敗（fork 失敗、wait 失敗、寫 `exit` 檔失敗…） |
| 2 | 用法錯誤 |
| 3 | 拒絕啟動：`.runi` 已存在 |

§D-9 把 `1` 的界線改寫成「**aos 自己跑不動，或收不了尾**」——本表的「函式庫層失敗」
這個講法蓋不住實測到的兩種情況（世界不合法、`turn` 遞增失敗），後者甚至發生在回合
已經推進之後。另外 `2` **只在碰檔案系統之前**判定，所以「世界路徑打錯」是 `1` 不是 `2`。

子行程回非零、被訊號殺掉、逾時——那些都算「一次**完成**的執行」，回合照樣 0。要知道
某筆指令的結果，用它自己的 `exit` 欄位把狀態寫進檔案；**回合之間靠檔案傳結果**，退出碼
只給跑 `aos exec` 的那個人看。

## 九、版本

> 條文：[SPEC](SPEC.md) **§B-4**（版面版本，現行＝1）與 **§F-2**（版面版本與**格式
> 版本**是兩件事：格式版本住在批 header 的 `version` 欄，見 §F-1／§C-8）。`turn` 與
> `inst-head.json` 都是純新增，不會因此 bump 版面版本。

`.aos/version` 記錄這份標準的版本。

- **讀不到 `version` ＝ 不是一個合法的 `.aos`**，拒絕。
- **版本不認得（比自己新）＝ 拒絕**，不要猜、不要盡力而為。
- 內容格式（單一整數／語意化版本）等實作時定，但**「有這個檔、不認得就停」這條現在
  就定下來**。

沒有版本標記的話，未來遇到舊格式的 `.aos/` 會分不出「舊版」和「壞掉」，而那時候要補
就得讓所有既有資料夾去猜。現在加的成本是零。

## 十、`.aos` 與 git

> 條文：[SPEC](SPEC.md) **§E-4**（`.gitignore` 政策）、**§E-3**（快照與回滾）。
> **本節原本寫的「整個 `.aos/` 都不進 git」已經被 §E-4 取代**，下面是取代後的版本。

> **可攜的語意，和「這台機器上正在跑什麼」，必須分開。**

原本 `.aos` 裝的全部都是**指令佇列與它們的執行狀況**——沒有一樣是可攜的，所以整包不進
git。M1 之後 `.aos` 裡長出了可攜的東西（`turn` 是這個世界的回合座標），所以政策改成
逐項切：

```gitignore
# 機器暫態：MUST NOT 進 git
*.temp
*.runi
*.tempd/
*.bad
```

**這條政策的執行者是 `aos init`**：它會在新世界裡建一個 `.aos/.gitignore`，內容就是
上面那四條加註解（pattern 住在 `.aos/` 裡，所以相對 `.aos/` 生效）。實跑：

```console
$ aos init w1
$ cat w1/.aos/.gitignore
# aos 版面暫態（SPEC §E-4）：機器暫態不進 git。
# version 與 turn 是可攜的回合座標，MUST 納入，所以這裡不排除。
# inst.json 與 inst-head.json 是 MAY——要不要讓回滾重演舊回合由你決定。
*.temp
*.runi
*.bad
*.tempd/
```

**舊世界缺這個檔不算錯**：`aos exec` 與 `aos deliver` 都不檢查它，也不補建。要補就自己
複製一份過去。

- **一定不進**：`*.temp`（還在生成）、`*.runi`（正在跑）、`*.tempd/`（投遞匣）、
  `*.bad`（隔離的壞投遞）。理由跟原本一樣：clone 一份帶著 `inst.json.runi` 的世界，
  新機器會以為有個回合正在跑——那是一個永久拒絕啟動的死鎖世界（§E-3）。
- **一定要進**：`.aos/version` 與 `.aos/turn`。這兩個是可攜的座標：版面認不認得、
  這個世界走到第幾回合。
- **看你要不要**（MAY）：`inst.json` 與 `inst-head.json`。納入的話，回滾到某個 commit
  會連那批待執行的工作一起復原、下一次 `aos exec` 會重演那個回合——**那要是你選的，
  不是副作用**。

可攜的東西放在 `<folder>` 本體（那才是世界，本來就會 commit）。

> 本原始碼 repo 不是世界：它根目錄的 `.gitignore` 整包排除 `.aos/`，那是測試殘留的
> 處理，跟本節的世界政策無關（§E-4 末句）。

## 十一、怎麼變成一個 aos 世界

- `aos exec <folder>` 遇到**沒有 `.aos/`** 的資料夾 → **報錯**，不自動建立。
- 要讓一個資料夾變成 aos 的世界，用 **`aos init <folder>`**。
- **`<folder>` 都可以省略，省略就是目前目錄 `.`**——`aos init`、`aos exec`、
  `aos exec --loop <毫秒>` 三種形式都一樣。跟 `git init` 的習慣一致。

自動建立會讓「打錯路徑」靜悄悄變成「在錯的地方建了一個空世界」。多一條命令換一次明確
的失敗，划算。

省略 `<folder>` 對 `aos exec` 沒有風險——跑錯目錄就是沒有 `.aos/`，直接報錯。對
`aos init` 則要小心一點：在錯的目錄下光打 `aos init` 就會在那裡建一個世界。這是跟
`git init` 一樣的取捨，接受。

## 十二、留給實作決定的

這些不寫進標準，實作時再定。**實作已經替其中一部分做了決定**——那些搬到下面第二段，
留在這裡不是為了拘束實作，是為了讓下一個人知道現況是有理由的，不是隨手長出來的。

### 已經被實作決定的

- **`--loop` 的間隔單位是毫秒。**
- **`--loop 0` 會印一行警告，然後當成 `--loop 1`。** 零間隔的字面意思是「沒事做的時候
  也全速重跑」，實測會吃掉約一整顆核心。而 `0` 偏偏是最直覺會打的數字（這個旗標本來
  就是從「一直跑」的想法來的），所以不能讓它變成陷阱。降到 1 毫秒對人沒有差別，對
  CPU 差三個數量級。
- **信號收尾**：`--loop` 期間攔 `SIGINT`／`SIGTERM`，處理函式只設一個旗標，當前回合
  跑完才退出，退出碼 0。設了 `SA_RESETHAND`，所以**第二次信號直接殺掉行程**——那時
  `.runi` 會留著，正確表達「有一回合沒跑完」。子行程各自 `setpgid` 自成一個 process
  group，所以終端機的 Ctrl-C 打不到它們；回合不會被腰斬成一半。
- **回合失敗時 `--loop` 不停**，繼續下一回合。**只有退出碼 3（`.runi` 已存在）會讓
  迴圈退出**——那是「需要人來處理」的狀態，繼續轉沒有意義。
- **一支 `aos exec` 一次只推進一個世界。** 實作是用 `chdir` 到 `<folder>` 來達成第四
  節那個「一律以 `<folder>` 為基準」，而 cwd 是整個行程共用的。要同時看多個資料夾就
  得改成到處傳基準路徑，或是一個世界一支行程——**後者才是這個模型的作法**。
- **刪除 `.runi` 失敗**：印錯誤、回 1，資料夾就此卡在拒絕啟動。那正是「有一回合沒跑
  完」的誠實表述，不特別處理。

### 仍然開著的

- **`--loop` 要不要改用 inotify** 取代輪詢。
- **殘存檔案的清理**（`.bad` 會一直累積、crash 留下的 `.runi` 要人手動清）。
  **原本「彙整順手自動清掉」的雛形已經被否決**：[SPEC](SPEC.md) §D-8 裁定彙整者
  **MUST NOT** 自動刪 `.bad`，清理歸人、或歸之後的 `aos recover`（M3）。
  當初就看得出來的那個理由現在成了條文：`.bad` 是會累積很多份的，但 `.runi` 永遠
  只有一份——對 `.runi` 用「大小上限」等於「批次夠大就自動清掉 crash 現場」，那會跟
  「`.runi` 已存在就拒絕啟動、crash 之後要人來處理」這條刻意的規則打架。
- `.runi` 的檢查與 `rename` 之間有 TOCTOU。兩支 `aos exec` 撞在一起時第二支的 `rename`
  會因為 `inst.json` 已被搬走而失敗，所以**不會重複執行**，只是退出碼與訊息不精確。
  要真的原子化得用 `renameat2(RENAME_NOREPLACE)` 或 `link`＋`unlink`。
- `insts/` 底下的名字誰配、撞名怎麼辦。
- ~~**投遞那一步沒有實作。**~~ **M1 補上了**：投遞現在是 `aos deliver [folder]`
  （子命令）＋ `aos::deliver_instructions`（庫層）＋ `aos_deliver_buffer`／
  `aos_deliver_file`（C ABI），唯一檔名、先寫 `.temp` 再排他 `rename`、canonical
  位元組全部內建，生產者不必也不該自己手刻（[SPEC](SPEC.md) §D-3）。用法見
  [`docs/usage.md`](usage.md) 的 `aos deliver` 一節，庫層行為見
  [`handoff.md`](../core/inst/docs/handoff.md)。
- **「世界」本身沒有抽象。** 彙整那三支是以 instruction 檔路徑為參數的（所以已經能
  對 `insts/llm.json` 用），但「`.aos` 在不在」「`version` 認不認得」「`chdir` 到哪」
  三件事寫死在 `aos exec` 的實作裡。等 `aos llm exec` 出現時，要嘛複製一份，要嘛那時
  再把它抽出來。
