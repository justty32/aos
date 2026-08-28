# 前作對照：`simple_tools/docs` 的 agent-world 設計 vs aos 模型

← [ideas](README.md)｜[WORKFLOWS](../../WORKFLOWS.md)

**這批來源不在本 repo 裡。** 它們在 aos 的上一層 `simple_tools/` 底下：

- `simple_tools/docs/design/agent-world/`（01-path-world、02-nine-axes、03-memory-context、
  04-time-agency、05-protocol-security、06-roadmap）
- `simple_tools/docs/explorations/live-agent-machine/`（01-world-function 起共八篇）

**時序很關鍵**：這兩批文件最早的 commit 是 **2026-08-12**，aos 的第一個 commit 是
**2026-08-14**。也就是使用者在動手寫 aos 的**兩天前**，已經對同一批問題做過一輪收斂。
本檔把兩邊逐條對照，標出 aos 哪裡是**回歸**（退回前作判定為較不精確的版本）、哪裡是
**前作已有現成答案**、哪裡**兩邊一致**。

> **使用者的總裁決**：「這些有些是可以參考的，但**很多機制都是可以在 loop、或更外層去
> 處理的**。」——也就是**不進呼叫格式、不進最核心那圈**。下面每條的「落點」是我按這句
> 話推的，**未經逐條裁決**，實際歸屬要落地時再定。

## 一、三個時間尺度塌成一個「回合」（回歸）

`04-time-agency.md` 定了 **Step／Round／tick** 三尺度，並警告：「**不要把 tick 直接改名
為 Round，它們的同步範圍不同**」。

對照 aos：一整批 inst 執行完＝**tick**（world state transition）；LLM CPU 那邊
`insts/llm.json` 的一次取出執行＝**Step**。**aos 已經同時有兩個尺度，而且都叫「回合」**
——正是那句警告針對的事。

而 **Round 在 aos 裡沒有對應物**。前作定義是「agent 啟動後到**主動停止**的一段活動」，
還規定要記 stop reason、要區分主動完成與 supervisor 強制停止。這正是
[handoff-and-world](call-format/handoff-and-world.md) 第六條「這顆 CPU 沒有停機」——
**答案兩天前就寫好了，名字叫 Round。**

*落點*：loop（Round 的生命週期與 stop reason 天然屬於取指單元）。

## 二、git 買不到 replay（前作已否定）

`01-world-function.md` 的對應表：「Git commit／object ＝ quote／frozen definition；
**branch 是新求值分支，不是 replay**。」

使用者在[第四輪](call-format/handoff-and-world.md)裁決「快照／回滾／複製都用 git」。按
前作的結論，git 給的是**凍結的定義**，不是**重播**——從一個 commit 重跑得到的是新的求值
分支。同一份文件還列了 closure 的完整組成：

```text
workspace root + private namespace + capability handles
+ goal/postconditions + policy + memory refs + resource leases
+ current Round continuation + source/event head
```

**git 只抓得到第一項。** 這與已接受的「daemon 讓世界外溢」是同一個洞的兩面。

*落點*：git 仍然是對的工具，但要知道它買到的是**快照與分支**，不是**可重播性**。

## 三、path 是 symbol、handle 才是 capability（這條「交給上層」救不了）

`01-path-world.md` 第三條：「**知道名字不能取代授權**；handle 應綁 actor、instance 與
grant generation。」

aos 的 inst 傳的是**字串路徑**，知道路徑＝有權限，結構性違反這條邊界。

**但這一條和其他條不同，它不能往外推**：fork/exec 傳遞的就是路徑本身，外層攔不到。唯一
能補的位置是 **spawn 時建 per-process namespace**（正是使用者選的 plan 9 方向），而
namespace 必須在 `fork` 之後、`execve` 之前建立——**那個位置只有 exec 層碰得到**。

*落點*：**這是 spawn 參數，不是外層的事。** 「安全交給其他人」對權限的其他面向成立，對
這一條在機制上不成立。這是本檔唯一一條與總裁決有出入的，留著待判。

## 四、「資料夾不天然是 AST」（回歸）

`01-world-function.md`：「資料夾不天然是 AST：它沒有可靠順序，也混有 source、cache、
secret、artifact 與 untrusted data。」當時的結論是在普通 workspace 上編一層
**Workspace Form IR**（declared inputs／exports／reads／writes／mounts／postconditions），
而不是發明新的虛擬檔案格式。結尾直接寫：

> 「更準確的說法**不是**『一個實體目錄就是全部 agent program』，而是『受版本與權限約束
> 的 world view 是程式；資料夾是它最重要、最通用、可由 Linux 編輯的表示』。」

而 [model](turn-based-folder/model.md) 第一句是「指定資料夾是被演化的世界／狀態容器」
——**正是前作標為較不精確的那個版本**：「表示」被讀成了「本體」。

*落點*：這是**措辭與模型定位**問題，不是機制，外推不掉。改一句話的成本近乎零。

## 五、declared／effective／observed 三分，aos 一個都沒有（前作已有現成答案）

`02-nine-axes.md` 的三分法，並警告「避免『文件寫可寫』被誤認成實際有權寫」。

inst 沒有 declared reads/writes、沒有 postconditions、沒有 mounts 宣告；執行完也沒有
observed reads/writes/cost/evidence。**一個回合結束，系統唯一的產出是一個 8-bit exit。**

*落點*：declared 要進格式（外推不掉），observed 可以完全在 loop 做。observed 是三者裡
最容易做、也最有用的那個。

## 六、事件與狀態的 projection，設計稿已經在了（前作已有現成答案）

`04-time-agency.md` 給了版面與規則：

```text
/self/state   /self/round   /self/step   /self/stop-reason   /self/events
```

> 「`events` 是 append-only cursor stream；`status` 是當前 projection。需要『當時發生
> 什麼』讀 event log，需要『現在怎樣』讀 status。」

[第四輪](call-format/handoff-and-world.md)裁決歷史「應該會在 loop 加」——**方向對，而且
不用重想**：兩檔式（append-only 事件流 ＋ 當下投影）已經寫好，連「不要用同一個檔兼差」
的理由都給了。

*落點*：loop。與總裁決一致。

## 七、巢狀 tick 的五個必填欄位，aos 有半個

前作規定巢狀時**必須顯式定義**：scope、barrier、propagation、cancellation、
resource accounting。

aos 目前：scope 隱含（就是那個資料夾）、barrier 只有一種（等所有 thread；前作列了
all／quorum／deadline／first-success 四種）、其餘三個空白。而巢狀**不是意外**——model.md
明說 inst 可以承載 aos 自己，一筆 inst 跑 `aos exec <另一個資料夾>` 巢狀就發生了。

*落點*：loop 或更外層。與總裁決一致。

## 八、`WorkspaceDelta`：人改檔案怎麼進系統

前作規矩：人存檔後由 supervisor 正規化成 delta，附來源、before/after hash、generation，
下一 Step 才明確決定是否載入；「**不讓半次寫入冒充新函數定義**」。

aos 的 `.temp` 狀況只保護 `.aos/` 裡的**投遞**，**不保護世界本體**。使用者用編輯器存到
一半、或外部程式正在寫，下一回合就讀到半個檔——而「使用者可以在回合之間介入」是 aos 的
核心賣點。**保護做在了信箱上，沒做在世界上。**

*落點*：loop 或更外層（取件前的一致性檢查）。與總裁決一致。

## 兩邊一致的一條（有前作背書）

`agent-world/README` 第 8 條：「**慢世界與快世界共用契約**——agentfs/9P 適合粗粒度組合；
可信且熱的邊可走 in-process，exec/container 仍是隔離地板。」

這跟[呼叫粒度的裁決](call-format/universality.md)（細粒度在程式內、這裡是更高層次的 CPU
指令）與「匯聚是注入式 lib」完全一致。**那兩個裁決有前作背書，不是臨時決定。**
