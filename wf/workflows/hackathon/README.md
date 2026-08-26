# hackathon — 黑客松（多 agent 動手做、只收坑）

← [WORKFLOWS](../../WORKFLOWS.md)｜[專案 INDEX](../../INDEX.md)｜**五份任務書模板在 [briefs.md](briefs.md)**

**做什麼**：使用者出題（或從研討會的待答問題裡挑），**我當主辦人**備一份資料包，派幾個
`codex exec` 實例**各自去真的做做看**——做法不指定、隨意發想、可以推翻現有設計。
做完收兩樣東西：**踩坑報告**（撞到什麼、哪裡舒服、哪裡難用、哪裡放棄），以及**評委對路線的判斷**。

**成功條件不是做出東西。做不完是正常的，卡住的地方就是最有價值的產出。**

**不追求可合併的程式碼**——參賽者寫的是拋棄式的，真有價值就轉交
[feature-dev](../feature-dev/README.md) 重做。

## 跟 workshop / experiments 的分界

| | [workshop](../workshop/README.md) | [experiments](../experiments/README.md) | **hackathon（本檔）** |
|---|---|---|---|
| 動手 | 唯讀，只講 | 動手，我自己跑 | 動手，多個 agent 平行跑 |
| 目標 | 想法的「多」 | 驗一個明確假設（是／否）| 同一題不同做法**各撞到什麼** |
| 產出 | 紀錄 | 實測證據 | **坑／好處／壞處** ＋ **評審意見** |
| 誰拍板 | 使用者 | 事實 | 評委給建議，**使用者拍板** |

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

| 角色 | 是誰 | 帶 persona？ | 職責 |
|------|------|---|------|
| **主辦人** | 我（Claude）| — | 出題、備場地、發任務書、**檢查改動範圍**、丟連結。**不下場做** |
| **參賽者 ×3–4** | `codex exec -s workspace-write` | **是（名人）** | 在自己的場地真的動手，回報坑／好處／壞處 |
| **評委 ×1** | 另一個 `codex exec` | **是（名人）** | 讀原始回報，判斷**哪條路值得走**、抓出不可信的回報 |
| **書記** | 另一個 `codex exec` | **否** | 把回報收攏成紀錄（發生了什麼）|
| **祕書** | 另一個 `codex exec` | **否** | 白話導讀（讓使用者讀得動）|
| **出題者** | 使用者 | — | 出題、隨時改題、決定要不要有第二段、**最後拍板** |

**書記與祕書刻意不帶 persona**：他們是**寫給使用者看的**，帶了風格就變成模仿秀，反而更難讀。

### 參賽者與評委用名人 persona（2026-08-26 使用者指定）

不用 workshop 那種抽象身份（「資深工程師」「架構師」），改用**具體的電腦領域名人**——
理由是抽象身份講出來的東西會趨同，**名人有明確的偏見，才會做出真的不一樣的東西**。

格式取自 [soul.md](https://github.com/aeonfun/soul.md) 的精簡版：任務書裡給一個四行
soul 區塊（**他是誰／他會先做什麼／他絕對不會做什麼／他的口吻**）。**同一位被用了好幾次、
需要更厚的設定時，才拆出 `souls/<name>.md`** 走完整那套（SOUL／STYLE／範例），現在不要預先建。

常用名單（每場挑 3–4 位，不必固定）：

| 名人 | 他會先做什麼 | 他絕對不會 |
|------|------|------|
| **Linus Torvalds** | 用最笨的 C／shell 直接打通，然後罵中間那層抽象 | 為了「將來可能需要」先做介面 |
| **Rob Pike** | 拆成幾支各做一件事的小工具，用管線接起來 | 加一個旗標來解決問題 |
| **Ken Thompson** | 砍到只剩最小的能動的東西 | 多寫一行 |
| **Joe Armstrong** | 假設它一定會死，先做「死掉之後怎麼回來」 | 相信 happy path |
| **Leslie Lamport** | 先問「你到底在保證什麼」，寫出狀態與不變式 | 沒定義正確性就開寫 |
| **John Carmack** | 半小時內做出能跑的最醜版本，然後量測 | 先開會討論設計 |
| **Rich Hickey** | 質疑資料模型本身，把狀態跟時間分開 | 用可變狀態繞過去 |
| **Bryan Cantrill** | 先讓出事時看得見——log、退出碼、現場留什麼 | 吞掉錯誤 |
| **Julia Evans** | 站在第一次用的人的位置，畫出實際發生了什麼 | 假設讀者已經懂 |

**挑人判準**跟 workshop 一樣：**他們會做出不一樣的東西**才是好指派。兩位會交出同一份東西，
就換掉一位。這題如果是可靠性，Armstrong 與 Cantrill 一起上很值得；如果是「這條路走不走得通」，
Carmack 一定要在。

> **這是風格 persona，不是那個人真的說過的話。** 紀錄與評審意見的檔頭要標明是風格模擬，
> 不要寫成「Linus 認為……」那種會被誤讀成引用的句子。

## 一場怎麼跑（兩段式，2026-08-26 使用者指定）

- **第一段：同題摸底。** 3–4 位拿**同一份**題目書、同一批資料，**互不見面**各做各的。
  同一題有人三十分鐘做完、有人卡死，那個落差就是資料。
- **收場（依序，不能平行——三個角色寫同一個檔）**：

  ```
  參賽者原始回報 → 書記寫紀錄（發生了什麼）
                 → 評委追加〈評審意見〉（哪條路值得走）
                 → 祕書追加〈白話導讀〉（讓使用者讀得動）
                 → 主辦人丟連結
  ```

- **第二段：分頭深挖。** 依第一段撞出來的坑拆成子題，一人一題再跑一次。
  **不一定要跑**——第一段就問完了就收。

**主辦人在收場只做三件事**：把原始回報餵給書記／評委／祕書、每一棒之後檢查 `git status`
只動了該動的檔、**丟檔案連結給使用者**。不自己把紀錄讀一遍再複述——那正是這三個角色要省掉的成本。

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

## 紀錄

- 落點 `records/<題目-kebab>.md`，**一題一檔、三層追加**（書記→評委→祕書；第二段再追加一輪）。
- 檔頭要標**參賽者是哪幾位名人**，以及**這是風格模擬**。
- **跨工作流通用的坑**往 [common/gotchas](../common/gotchas.md) 併一條；題目專屬的留紀錄裡。
- 驗出結論要改規格 → **轉交提案，我不自己改 `docs/`**，要使用者拍板。
- 值得做成真功能 → 轉 [feature-dev](../feature-dev/README.md) 重做，**不要合併黑客松的程式碼**。

## 指令形態

`codex exec` 的旗標、reasoning effort、`--json` 抓 session id、`-o`＋stdin、MCP
`AuthRequired` 噪音等**全部沿用 [workshop README 的〈指令形態〉](../workshop/README.md)**，
不複製一份。黑客松只有兩處不同：**參賽者沙盒是 `-s workspace-write`**（`-C` 指向他自己的
場地複製品），**逾時拉長到至少 1800 秒**（workshop 是 600）。
