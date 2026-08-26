# hackathon — 黑客松（多 agent 動手做、只收坑）

← [WORKFLOWS](../../WORKFLOWS.md)｜[專案 INDEX](../../INDEX.md)

**做什麼**：使用者出題（或從研討會的待答問題裡挑），**我當主辦人**備一份資料包，派幾個
`codex exec` 實例**各自去真的做做看**——做法不指定、隨意發想、可以推翻現有設計。
做完只收一樣東西：**踩坑報告**（撞到什麼、哪裡舒服、哪裡難用、哪裡放棄）。

**成功條件不是做出東西。做不完是正常的，卡住的地方就是最有價值的產出。**

**這不是**：不評分、不排名、不選冠軍，也不追求可合併的程式碼——參賽者寫的是拋棄式的，
真有價值就轉交 [feature-dev](../feature-dev/README.md) 重做。

## 跟 workshop / experiments 的分界

| | [workshop](../workshop/README.md) | [experiments](../experiments/README.md) | **hackathon（本檔）** |
|---|---|---|---|
| 動手 | 唯讀，只講 | 動手，我自己跑 | 動手，多個 agent 平行跑 |
| 目標 | 想法的「多」 | 驗一個明確假設（是／否）| 同一題不同做法**各撞到什麼** |
| 產出 | 紀錄 | 實測證據 | **坑／好處／壞處**對照 |
| 誰拍板 | 使用者 | 事實 | 沒有拍板，只有材料 |

> workshop 的硬規則是 read-only、不准 build，所以它結構上**只能**產出「應該」。
> 2026-08-25 那次「你直接去試」的 [T5 實測](../experiments/t5-agent-loop.md)一次就抓到
> 規格與 roadmap 互相矛盾，比七場研討會的轉交提案都硬。**黑客松＝把那次的做法變成常設、
> 而且多人平行。**

## 題目哪裡來

**優先挑 [workshop/BACKGROUND.md](../workshop/BACKGROUND.md) 的「最小的驗證方式」**——
`background/` 那 17 檔裡每題結尾都有一條，共 20 條，**每條祕書都明寫「一小時內做得完」**，
是現成的題目卡。其次是 [OPEN-QUESTIONS](../workshop/OPEN-QUESTIONS.md) 的阻塞題
（使用者不想用想的拍板的，改成用做的），再來是使用者臨時起意。

資料包通常是：對應那場的 `records/*.md` ＋ 該題的 `background/*.md` ＋
[`docs/aos-folder.md`](../../../docs/aos-folder.md)（規格唯一真源）＋
[`docs/roadmap.md`](../../../docs/roadmap.md)。

## 角色

| 角色 | 是誰 | 職責 |
|------|------|------|
| **主辦人** | 我（Claude）| 出題目書、備場地、發任務書、**檢查改動範圍**、丟連結給使用者。**不下場做** |
| **參賽者 ×3–4** | `codex exec -s workspace-write` | 在自己的場地真的動手，回報坑／好處／壞處 |
| **書記** | 另一個 `codex exec` | 收攏成一份紀錄。**省主辦人 token**，同 [workshop 的書記](../workshop/README.md) |
| **出題者** | 使用者 | 出題、隨時改題、決定要不要有第二段 |

**不設裁判。** 要的是坑，不是名次。

## 一場怎麼跑（兩段式，2026-08-26 使用者指定）

- **第一段：同題摸底。** 3–4 位拿**同一份**題目書、同一批資料，**互不見面**各做各的。
  同一題有人三十分鐘做完、有人卡死，那個落差就是資料。
- **收攏。** 把原始回報餵給書記 → 一份紀錄。
- **第二段：分頭深挖。** 依第一段撞出來的坑拆成子題，一人一題再跑一次。
  **不一定要跑**——第一段就問完了就收。

收場三件事：**餵原始回報給書記、檢查 `git status` 只動了那一個檔、丟檔案連結給使用者。**
不自己把紀錄讀一遍再複述——那正是書記要省掉的成本。

## 場地（整包複製，不碰 repo 工作區）

**2026-08-26 使用者指定：整包複製。** 參賽者要真的寫檔，不能讓幾個人在 repo 工作區互相蓋。
**場地開在 WSL 的 `/tmp/aos-hack-<題目-kebab>/p<N>/`**，一人一份，做完丟掉、不進 repo。

```bash
# 從 WSL 跑。repo 在 /mnt/c/code/mine/simple_tools/aos
SRC=/mnt/c/code/mine/simple_tools/aos
ARENA=/tmp/aos-hack-<題目-kebab>/p1
mkdir -p "$ARENA"
rsync -a --exclude build/ --exclude .git/ "$SRC/" "$ARENA/"
mkdir -p "$ARENA/build/bin" && cp "$SRC/build/bin/aos" "$ARENA/build/bin/"
```

**為什麼是 WSL 的 `/tmp` 而不是 Windows 側的 scratchpad**：`build/bin/aos` 是 **Linux ELF**
（實測 `file`：`for GNU/Linux 3.2.0`），**Windows 這側執行不了，要把 aos 跑起來就只能從
WSL 跑**；而且 `/mnt/c` 是 9p 掛載，小檔 I/O 慢又會噴 clock skew。Windows 側的 session
scratchpad 照 workshop 慣例放**任務書與原始回報**（不進 repo）。

**預設不 build，用複製過去的那顆 `aos`。** 理由是實測的：codex 沙盒下 `$HOME` 唯讀，
vcpkg 拿不到 `~/dev/vcpkg/buildtrees/` 的 write lock，configure 一定失敗
（[T5 現場](../experiments/t5-agent-loop.md)）。題目真的要改 C++ 才給
`--add-dir ~/dev/vcpkg`，並預期第一次 configure 很久。

**可以讀 `../` 的兄弟專案**（2026-08-26 使用者指定）：`agent-machine`、`freepy`、`dcap`、
`arc_agi_tweets` 等，在 WSL 是 `/mnt/c/code/mine/simple_tools/`。沙盒只擋寫不擋讀，但
**場地已被搬到 `/tmp`，所以要在任務書裡把這個絕對路徑明講**，否則他們的 `../` 是空的。

## 題目書

```markdown
## 題目
<一句話。要能動手——不是「討論 X」，是「做出一個 X 看看」>

## 為什麼問這題
<卡在哪、誰在等答案。哪一場研討會、哪一則待答問題>

## 我想知道的
<這條路走不走得通／要付什麼代價／哪一步會痛>

## 資料包
<repo 內路徑：研討會紀錄 / background / 規格 / roadmap>

## 場地
<複製品在哪、aos 執行檔在哪、可以讀哪些外部路徑>

## 明確不必做的
<不必寫測試／不必顧相容／不必收乾淨>
```

## 參賽者任務書

題目書 ＋ 下面幾塊，寫成一個檔丟 stdin：

```markdown
## 場地與環境
- 你的場地：`/tmp/aos-hack-<題>/p<N>/`。**一份拋棄式的完整 repo 複製品，隨便改。**
- **從 WSL（Ubuntu）跑。** `build/bin/aos` 是 Linux ELF，Windows 側執行不了。
- **預設不要 build**（沙盒下 vcpkg 拿不到 write lock，一定失敗）。用 `build/bin/aos`。
- 可以讀 `/mnt/c/code/mine/simple_tools/` 底下的兄弟專案（agent-machine、freepy、dcap…）。
- 需要 sub agent 做雜活：指名 **Terra** 或 **Luna**，一次最多一個。

## 本輪任務
<第一段：照題目書自己想辦法做出來；第二段：只挖 <某個坑>>

## 硬規則
- **做法完全不指定。** 現有實作與規格只是參考，**你可以主張它們是錯的、可以推翻**。
- **做不完是正常的，而且不扣分。** 卡住的地方就是我要的東西——
  **不要為了交差假裝做完，也不要把失敗寫得漂亮。**
- **貼真的指令與真的輸出。** 不要憑印象轉述，不要美化錯誤訊息。
- 只在自己的場地寫檔，不要碰 `/mnt/c` 上的 repo。
- 繁體中文，長度以講清楚為準。不要開場白與收尾客套。

## 輸出格式
**我做了什麼**：<一段話，你的路線是什麼>
**能跑到哪**：<實際指令 + 實際輸出，貼原文>
**坑**：<撞到什麼、怎麼繞、繞不過就寫繞不過。這一節越長越好>
**好處**：<這個做法哪裡真的舒服、比想像中好的地方>
**壞處**：<哪裡難用、哪裡會爆、哪裡讓你想罵人>
**我放棄的**：<試了但沒做完的，以及為什麼放棄>
**如果重來**：<你會改走哪條路>
```

## 書記

分工與任務書格式沿用 [workshop 的書記](../workshop/README.md)，只換三處：

- **寫的檔**是 `records/<題目-kebab>.md`，**只准動這一個**。
- **紀錄骨架**：檔頭表格（題目、日期、幾位、環境、狀態、**誰沒跑完**）→ **各人做了什麼**
  → **坑的總表**（多人獨立撞到的要**明寫「幾位獨立地都撞到」**，那是最強訊號）→
  **好處** → **壞處** → **這題的答案**（如果真的有）→ **仍然不知道的**。
- **失敗照實寫。** 有人整場沒跑起來，就寫他卡在哪一行。紀錄的價值在誠實，不在好看。

## 紀錄

- 落點 `records/<題目-kebab>.md`，一題一檔、追加式（第二段追加一節）。
- **跨工作流通用的坑**往 [common/gotchas](../common/gotchas.md) 併一條；題目專屬的留紀錄裡。
- 驗出結論要改規格 → **轉交提案，我不自己改 `docs/`**，要使用者拍板。
- 值得做成真功能 → 轉 [feature-dev](../feature-dev/README.md) 重做，**不要合併黑客松的程式碼**。

## 指令形態

`codex exec` 的旗標、reasoning effort、`--json` 抓 session id、`-o`＋stdin、MCP
`AuthRequired` 噪音等**全部沿用 [workshop README 的〈指令形態〉](../workshop/README.md)**，
不複製一份。黑客松只有兩處不同：**沙盒是 `-s workspace-write`**（`-C` 指向他自己的場地
複製品），**逾時拉長到至少 1800 秒**（workshop 是 600）。
