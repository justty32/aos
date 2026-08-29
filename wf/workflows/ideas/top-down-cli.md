# 從上到下：使用者要的指令面（`aos pu` 與 `aos agent`）

← [ideas](README.md)｜[WORKFLOWS](../../WORKFLOWS.md)

**記錄日期**：2026-08-30。**這篇的角度跟其他構想相反。** 其餘篇章都是由下往上推
（inst 是什麼 → loop 是什麼 → 資料夾是什麼），這篇是使用者某天改用**由上往下**思考的
產物：先把「我坐在終端機前想打什麼指令、看到什麼」定死，再回頭看底層缺什麼。

前提是一句話：**aos 最初就是為了 agent loop 而打造的**。所以先把想要的東西說好。

## 一、兩個視窗的劇本（要的成品）

```text
視窗 A                                   視窗 B（同一個資料夾）
─────────────────────────────────────    ─────────────────────────────────────
$ cd some/folder
$ aos pu init            ← 把這個資料夾變成「世界」
$ aos pu run --step 5 --interval 50
  （持續執行 inst）                       $ aos agent init
                                            ← 順便幫忙做 pu init
                                            ← 問：哪種思考引擎？哪種人格？
                                              初始對話是什麼？
                                            ← 在 .aos/ 擺好 agent 所需的東西
                                            ← 往 inst.tempd 投遞一份「會自我複製
                                              投遞」的 agent 指令
                                          $ aos agent talk
                                            （跟這個 agent 交流）
```

agent loop 就是這樣**安插進 `aos pu run` 的迴圈裡**的：不是另開一個常駐行程，而是往
投遞匣塞一份會把自己再投遞一次的指令。

## 二、指令面

**指令只要兩組。** `aos exec` 那些可以先放掉，或歸類進 `aos pu`。

### `aos pu` — processing unit

| 指令 | 做什麼 |
|---|---|
| `aos pu init` | 對目前資料夾做初始化設定，使其成為世界 |
| `aos pu run --step 5 --interval 50` | 連續執行五次 inst，每次間隔 50（毫秒） |

`pu` ＝ **processing unit**。這一組就是現在的 `aos init`／`aos exec`／`aos exec --loop`
換一個更誠實的名字與歸屬——它們是「這個世界的處理單元」。

### `aos agent`

| 指令 | 做什麼 |
|---|---|
| `aos agent init` | 互動式問答（思考引擎／人格／初始對話）→ 在 `.aos/` 擺好 agent 所需的東西 → 往 `inst.tempd` 投遞一份會自我複製投遞的 agent 指令。**預期會順便做 `pu init`** |
| `aos agent say` | 把「你要對這個 agent 說的話」寫進 `.aos/` 底下的某個檔 |
| `aos agent listen` | 把 agent 目前的思考與所說的貼到 stdout |
| `aos agent talk` | 上面兩者串起來，類似 REPL 迴圈 |
| `aos agent talk --interface claude` | 不自己做 REPL，直接把 stdin／stdout 轉接到指定程式——這樣更好用 |
| `aos agent state` | 看這個 agent 現在是**空閒**／**思考中**／**執行工具中** |

> `say` 與 `listen` 是**原語**，`talk` 是它們的合成。`--interface` 讓「好用的介面」這件
> 事外包給已經做得很好的程式，aos 自己不必長出一套終端機 UI。

## 三、思考怎麼發生：投遞到另一顆 PU

**agent 裡的 LLM 思考 ＝ 把指令投遞到指定 llm pu 資料夾的 tempd**，等它們處理；
本地這邊則在 `aos pu run` 的迴圈中**持續監控它好了沒**。

```text
folder/.aos/inst.tempd/          ← agent 自我複製投遞的下一回合
        ↓ 本回合執行時
llm-folder/.aos/inst.tempd/      ← 把「想一次」投遞給 LLM PU
        ↓
（llm pu 自己的 run 迴圈處理它）
        ↓
本地 pu loop 每回合檢查結果好了沒 → 好了就接下去
```

也就是說：**LLM 不是一個被呼叫的函式，是另一台跑同一套協定的機器。** 兩邊都只靠
投遞匣接觸，誰也不進誰的記憶體。

## 四、跟既有紀錄的關係

| 既有 | 這篇改了什麼 |
|---|---|
| [turn-based-folder/usage-and-agent-loop](turn-based-folder/usage-and-agent-loop.md) 的 `aos agent start` → `aos agent init ...` | 名字與分工換掉了：入口是 **`aos agent init`**（一個指令，含互動問答與 pu init），不再是 start／init 兩段。**以本篇為準** |
| [`docs/aos-folder.md`](../../../docs/aos-folder.md) 的 `aos init`／`aos exec [--loop]` | 規格沒變，**指令名字要搬到 `aos pu` 底下**。規格內容（版面、三步交接、回合語意）仍以那份為準 |
| [machine-shape/loop](machine-shape/loop.md)：「loop 沒有 status／暫停等控制介面」 | `aos agent state` 與 `--step N` 正是使用者自己給的部分答案——**有限步數**與**可觀測狀態** |
| [llm-cpu](llm-cpu.md)：LLM CPU 疊在 inst 之上、跨資料夾排程與 I/O 交換區 | 第三節就是它的使用者視角版本：跨資料夾投遞 + 本地輪詢取件 |

## 五、開放問題（我挖的邊緣狀況，**都還沒拍板**）

使用者定的是上面的方向；下面這些是照這個方向走會撞到、但這次沒講到的地方。

> **使用者已裁決（2026-08-30）：這些都是實作時順便解決的，現在不管。**
> 所以下面整節是**實作時的檢查清單**，不是動工前要先拍板的門檻——別拿它們擋住開工，
> 也別在動工前回頭再問一次。

**PU**
1. **`--step 5` 跑完之後 `.runi` 留在那裡怎麼辦**——現行規則是 `.runi` 存在就拒絕啟動
   （[D6](../../../docs/roadmap/decisions.md#d6)），有限步數會讓「正常結束」和「上次
   崩了」長得一模一樣。
2. **`--interval 50` 跟現行 `--loop <毫秒>` 是同一個東西還是兩個**（`--loop 0` 是忙碌
   輪詢，見 [machine-shape/loop](machine-shape/loop.md)）。
3. 現行子命令 dispatch 是**單層平面表**（`app/src/main.cpp` + CMake 產生的
   `aos_subcommands.inc`）。`pu`／`agent` 是第一組需要**兩層**的子命令。
4. 改名會讓 `docs/` 裡既有的 `aos init`／`aos exec` 敘述全部過期——machine-shape 已經
   記過「規範有三份真相且在漂」，這次改名是第四份的來源。

**Agent 的生死**
5. **自我複製投遞失敗 = agent 靜默死亡**：某回合那條指令沒跑成功，下一份就沒投出去，
   迴圈安靜地停掉，沒有任何人會知道。誰當 supervisor？
6. **怎麼讓 agent 停？** 目前這組指令裡沒有 `aos agent stop`——只能不再 `pu run`，但
   投遞匣裡那份還在，下次 run 就復活。這是特性還是缺陷要拍板。
7. `aos agent init` 對**已經 init 過**的資料夾再跑一次會怎樣（覆蓋人格？多一隻 agent？
   拒絕？）。

**狀態與對話**
8. **`aos agent state` 的狀態住在哪個檔、誰寫、什麼時候寫**：如果回合結束才寫，那看到
   的永遠是上一回合；崩潰後會永遠卡在「思考中」，跟第 1 點是同一類問題。
9. **`aos agent say` 寫「某個檔」會撞車**：使用者連說兩句、或 agent 正在讀的同時寫入。
   投遞匣（`say.tempd/`）已經是這個 repo 對這問題的標準答案，單一檔案不是。
10. **`aos agent listen` 怎麼知道哪些是「新的」**：游標／位移存哪？兩個視窗同時 listen
    算不算合法？
11. **`--interface claude` 的生命週期對不上**：被轉接的程式是常駐的，世界是回合制的。
    它在兩回合之間要不要活著、agent 死了它怎麼知道。

**跨資料夾**
12. **「指定 llm pu 資料夾」由誰指定、記在哪**（`.aos/` 裡的設定檔？）。
13. **跨資料夾投遞破壞了「路徑基準一律是 `<folder>`」這條鐵律**
    （[aos-folder 第四節](../../../docs/aos-folder.md)）——往別人的世界寫，用的是誰的基準？
14. **等 LLM 好了沒 vs 硬回合邊界**：一次思考是佔住一整個回合等它（回合要等所有 thread
    跑完），還是拆成「投遞回合」與「取件回合」兩回合？
