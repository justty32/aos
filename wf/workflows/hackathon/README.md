# hackathon — 黑客松（多 agent 動手做、只收坑）

← [WORKFLOWS](../../WORKFLOWS.md)｜[專案 INDEX](../../INDEX.md)

> **本檔＝流程。** 題目書與參賽者任務書在 **[briefs.md](briefs.md)**；收場四棒（書記／評委／資料員／祕書）的任務書在 **[staff.md](staff.md)**；
> **辦一場會撞到的坑在 [gotchas.md](gotchas.md)——第一次辦之前先讀那份。**

**做什麼**：使用者出題（或從研討會的待答問題裡挑），**我當主辦人**備一份資料包，派幾個
`codex exec` 實例**各自去真的做做看**——做法不指定、隨意發想、可以推翻現有設計。
做完收兩樣東西：**踩坑報告**（撞到什麼、哪裡舒服、哪裡難用、哪裡放棄），以及**評委對路線的判斷**。

**成功條件不是做出東西。做不完是正常的，卡住的地方就是最有價值的產出。**

**不追求可合併的程式碼**——參賽者寫的是拋棄式的，真有價值就轉交
[feature-dev](../feature-dev/README.md) 重做。

## 跟 workshop / experiments 的分界

| | [workshop](../workshop/README.md) | [experiments](../experiments/README.md) | **hackathon（本檔）** |
|---|---|---|---|
| 動手 | 唯讀，只講 | 動手，我自己跑 | 動手，多個 agent 平行跑、**跨輪迭代** |
| 目標 | 想法的「多」 | 驗一個明確假設（是／否）| 同一題不同做法**各撞到什麼** |
| 產出 | 紀錄 | 實測證據 | **坑／好處／壞處** ＋ **每輪評分與意見** |
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
| **參賽者 ×3–4** | `codex exec -s workspace-write`，**跨輪 resume** | **是（名人）** | 動手做 → 拿評委意見回去**改或重作** |
| **評委 ×1** | 另一個 `codex exec` | **是（名人）** | **每輪打分＋給意見**，並抓出不可信的回報 |
| **書記團** | 兩個 `codex exec` | **否** | **書記**＝每輪紀錄發生了什麼；**資料員**＝依這輪卡住的地方，備**下一輪的資料包** |
| **祕書** | 另一個 `codex exec` | **否** | 每輪把總結翻成白話給使用者 |
| **出題者** | 使用者 | — | 出題、隨時改題、決定跑幾輪、**最後拍板** |

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

## 一場怎麼跑（**預設三輪迭代**，2026-08-26 使用者指定）

黑客松**不是跑一次就收**，是**實作 → 評分 → 回去改 → 再評**的循環。預設三輪。

**每一輪都是這五棒，依序**（書記／評委／資料員／祕書寫同一個紀錄檔，**不能平行**）：

```
① 參賽者 ×3–4 平行動手（R1 各自摸底；R2/R3 用 resume 接同一位，依評委意見改或重作）
       ↓ 原始回報
② 書記   → 寫／追加〈第 N 輪紀錄〉      發生了什麼
③ 評委   → 追加〈第 N 輪評分與意見〉    打分、指出下一輪該修什麼
④ 資料員 → 追加〈下一輪的資料包〉        針對他們卡住的地方，找出可參考的東西
⑤ 祕書   → 追加〈第 N 輪白話導讀〉      翻譯給使用者
       ↓
下一輪：④ 的資料包 ＋ ③ 的意見一起塞進參賽者的下一份任務書
```

**參賽者跨輪保留 context 與場地**：用 `codex exec resume <session-id>` 接同一位，
場地不清掉，他改的是自己上一輪的東西。**session id 一定要記進紀錄檔**
（`--json` 抓第一筆 `session_id`），**只在開場那台機器上有效**。
resume 不吃 `-s`／`-C`／`--add-dir`，沙盒與工作目錄從原 session 繼承。

**主辦人每一輪只做三件事**：把原始回報餵給下一棒、每一棒之後檢查 `git status` 只動了該動的檔、
**丟檔案連結給使用者**。不自己把紀錄讀一遍再複述——那正是這四個角色要省掉的成本。

### 評委要打分（2026-08-26 使用者指定），但評分表要保護誠實

打分會製造一個問題：**參賽者一旦知道被評分，就會粉飾失敗**——而失敗現場正是這工作流唯一要的東西。
解法不是不打分，是**把誠實寫進評分表、而且權重最高**：

| 項目 | 滿分 | 怎麼給 |
|---|---|---|
| **證據強度** | 5 | 貼了多少**真實**的指令與輸出 |
| **誠實度** | 5 | 卡住有沒有照實寫 |
| 走了多遠 | 5 | 推進到哪 |
| 回答了題目的數字 | 5 | 答了幾個、答得多硬 |
| 路線價值 | 5 | 對使用者要拍板的那個決定有沒有貢獻 |

**權重最重的兩項是證據與誠實，不是走得多遠。** 老實寫「我卡在第一步」但貼了完整現場
→ 這兩項可以滿分；說做完了卻沒貼指令輸出 → **誠實度 0，總分墊底**。
**這張表要原文抄進參賽者任務書**，讓他們一開始就知道誘因在哪。

## 場地（整包複製，不碰 repo 工作區）

**2026-08-26 使用者指定：整包複製。** 參賽者要真的寫檔，不能讓幾個人在 repo 工作區互相蓋。
**場地開在 WSL 的 `$HOME/aos-hack/<題目-kebab>/p<N>/`**，一人一份，做完丟掉、不進 repo。
**不要用 `/tmp`**——實測會被清掉，賠掉過一整輪，理由見 [gotchas.md](gotchas.md)。

```bash
# 整場在 WSL 內跑（codex 在 WSL 就有：~/.local/bin/codex）
export PATH="$HOME/.local/bin:$PATH"          # bash foo.sh 不載 profile，沒這行 codex 會 127
SRC=/mnt/c/code/mine/simple_tools/aos
ARENA=$HOME/aos-hack/<題目-kebab>/p1        # 不要用 /tmp，會被清掉
mkdir -p "$ARENA/build/bin" "$ARENA/build/lib"
rsync -a --exclude build/ --exclude .git/ "$SRC/" "$ARENA/"
cp -a "$SRC/build/bin/aos" "$ARENA/build/bin/"
cp -a "$SRC"/build/lib/*.so*  "$ARENA/build/lib/"   # RUNPATH 是 $ORIGIN/../lib，少了跑不起來
```

**建場地、放任務書、冒煙、開跑要合併成同一支腳本、同一次 `wsl.exe` 呼叫**——理由與其他六個坑見 [gotchas.md](gotchas.md)。

**為什麼在 WSL 而不是 Windows 側的 scratchpad**：`build/bin/aos` 是 **Linux ELF**
（實測 `file`：`for GNU/Linux 3.2.0`），**Windows 這側執行不了，要把 aos 跑起來就只能從
WSL 跑**；而且 `/mnt/c` 是 9p 掛載，小檔 I/O 慢又會噴 clock skew。Windows 側的 session
scratchpad 照 workshop 慣例放**任務書與原始回報**（不進 repo）。

**預設不 build，用複製過去的那顆 `aos`。** 理由是實測的：codex 沙盒下 `$HOME` 唯讀，
vcpkg 拿不到 `~/dev/vcpkg/buildtrees/` 的 write lock，configure 一定失敗
（[T5 現場](../experiments/t5-agent-loop.md)）。題目真的要改 C++ 才給
`--add-dir ~/dev/vcpkg`，並預期第一次 configure 很久。

**可以讀 `../` 的兄弟專案**（2026-08-26 使用者指定）：`agent-machine`、`freepy`、`dcap`、
`arc_agi_tweets` 等，在 WSL 是 `/mnt/c/code/mine/simple_tools/`。沙盒只擋寫不擋讀，但
**場地不在 repo 旁邊，所以要在任務書裡把這個絕對路徑明講**，否則他們的 `../` 是空的。

## 紀錄

- 落點 `records/<題目-kebab>.md`，**一題一檔、每輪四層追加**（書記→評委→資料員→祕書）。
- 檔頭要標**參賽者是哪幾位名人**、**這是風格模擬**、以及**每位的 codex session id**
  （續輪要用；只在開場那台機器上有效）。
- **跨工作流通用的坑**往 [common/gotchas](../common/gotchas.md) 併一條；題目專屬的留紀錄裡。
- 驗出結論要改規格 → **轉交提案，我不自己改 `docs/`**，要使用者拍板。
- 值得做成真功能 → 轉 [feature-dev](../feature-dev/README.md) 重做，**不要合併黑客松的程式碼**。

## 指令形態

`codex exec` 的旗標、reasoning effort、`--json` 抓 session id、`-o`＋stdin、MCP
`AuthRequired` 噪音等**大致沿用 [workshop README 的〈指令形態〉](../workshop/README.md)**。
黑客松不同的地方：

- **參賽者沙盒是 `-s workspace-write`**（`-C` 指向他自己的場地複製品），加 `--skip-git-repo-check`。
- **逾時拉長到至少 1800 秒**（workshop 是 600）。
- **整場在 WSL 內跑**，不是 Windows 的 `codex.exe`——所以 workshop 那句
  「任務書放 Windows scratchpad」在這裡不適用。細節見 [gotchas.md](gotchas.md)。
