> 封存 2026-09-05，由 wf/workflows/ideas/README.md（新版構想集）取代

# 自我投遞能不能埋進 loop

> **已採用方案 A，2026-08-30**（使用者裁決）：loop 提供 `.aos/every/`，agent 不再自我投遞。

← [ideas](README.md)｜[top-down-cli](top-down-cli.md)｜[machine-shape/loop](machine-shape/loop.md)｜[PROTOCOL](../dispatch/proto/PROTOCOL.md)｜[隊 B 交接書](../dispatch/proto/done/proto-B-agent.md)

**記錄日期**：2026-08-30，隊 B 原型（`aos agent`）做完後的規劃。**這份只是規劃，還沒實作，
等使用者拍板。** 問題只有一個：agent 每回合把「下一回合的自己」投進 inbox 這件事，
能不能／該不該改由 loop 原生支援？

## 現況：純投遞式自我複製長什麼樣

`aos agent init` 投第一條 `{"id":"agent-bob-0","argv":["aos","agent","step",W,"bob"]}`；之後
每次 `step` 結束前（含丟例外時）都再投一條 `agent-bob-<turn>`。loop 對此一無所知——它只看
inbox 有東西就搬、就跑，bob 跟任何一條 `ls` 沒有差別。這正是協定 §1「loop 不理解內容」的
直接後果，也是 [core-layering](core-layering.md) 試跑的結論（agent 整套不進 core）。

```text
turn N                            turn N+1                          turn N+2
────────────────────────────────  ────────────────────────────────  ─────────────────────
loop 搬 inbox → batch/N/insts     loop 搬 inbox → batch/N+1/insts   loop 搬 inbox → …
  fork step(bob) ─┐                 fork step(bob) ─┐  fork sh -lc    fork step(bob) ─┐
                  │ 讀 say/                         │ 找 out/N+1/tool                 │ 讀 out/N+1/tool ✓
                  │ 叫 LLM，想用 sh                 │ ✗ 還沒寫（同批並行中）           │ 叫 LLM
                  │ 投 tool-N-0 → inbox             │ 什麼都不做                       │ 投 agent-bob-N+2
                  │ 投 agent-bob-N → inbox          │ 投 agent-bob-N+1 → inbox         │
  全部等完，寫 out/N ◄┘             全部等完，寫 out/N+1 ◄┘             全部等完 ◄┘
  turn ← N+1                        turn ← N+2                        turn ← N+3
```

規律：**回合 N 投的東西，N+1 才跑，N+2 才讀得到結果。** 自我投遞讓 bob 每回合都在，
但「在」的方式是靠上一回合的自己把它投進來。

## 做得到什麼

- **loop 零改動**、協定零改動。agent 是普通 inst，符合單向分層與「loop 只做鏡射」。
- **多 agent 同一個世界**只是多幾條 inst；跨世界也只是投到別的 inbox。
- **世界可凍結、可續跑**：關掉 `aos run`，inbox 裡那條 `agent-bob-N` 就是「下一步」，
  下次 `aos run` 原地接上；整個 `.aos/` 可以 tar、可以 git。
- **使用者能在回合間介入**：往 `say/` 丟話、手改 inbox 裡的指令、刪掉它。
- 不叫 LLM 的回合（第 4 步）幾乎免費，只是一支行程空跑一下。

## 做不到什麼

隊長在原型裡實際撞到的，全部源於同一件事：**「bob 應該每回合都在」這個事實沒有任何檔案
承載**，它只存在於「上一回合有沒有投成功」這個瞬時狀態裡。

1. **靜默死亡**：step 崩了、被 `timeout_ms` 殺了、`aos` 不在 PATH，就沒有下一回合。
   例外路徑「仍然自我投遞」擋得住 C++ 例外，擋不住 SIGKILL 與 fork 失敗。沒有人會發現，
   `state.json.agents.bob` 永遠停在最後一次的 `thinking`。
2. **停不下來**：沒有 `aos agent stop`。刪 inbox 那條，只要它已經被搬進 `batch/` 就晚了
   ——這回合跑完又投一次。唯一可靠的停法是關掉 `aos run`，那是停整個世界。
3. **工具往返固定三回合**：投工具（N）→ 工具跑（N+1）→ 讀結果（N+2）。這是 loop
   「先匯聚整批、並行跑完才寫 out」的節奏，自我投遞只是把它暴露出來；對話延遲固定 3 倍。
4. **狀態新舊**：`state.json.agents` 是 loop 在回合首尾鏡射 `status.json`，而 agent 在
   回合中途改它，鏡射到的可能是半路的 `thinking`。
5. **agent 互相看不見、沒有排程／優先權**：整批並行，誰先誰後不定；兩個 agent 同回合
   互投訊息也是下回合才收到。
6. **id 撞名與指數成長**：使用者手動再投一次 `agent-bob-0`（或 `init` 跑兩次），就有兩個
   bob 同回合跑、各投一條，下回合四個。id 帶回合號只擋同一回合撞檔名，擋不住這個。
7. 邊緣狀況（刻意跳過，只列不展開）：`say` 撞車、多視窗 `listen`、agent 刪掉自己的
   `agents/<name>/`、folder 被搬走後 argv 裡的絕對路徑失效。

第 3、4、5 條不是自我投遞造成的，換成任何方案都還在；本篇的方案只針對 1、2、6。

## 方案：讓 loop 原生支援

兩案共同前提：把「bob 每回合都要在」從瞬時狀態變成**一個常駐檔**，由 loop 每回合讀它。
差別在那個檔放哪、長什麼樣。

### 方案 A：常駐投遞匣（`agents/<name>/next.json`，或泛化成 `.aos/every/<id>.json`）

- **loop 要改**：匯聚階段搬完 `inbox/` 之後，再把每個常駐檔**複製**（不搬、不刪）成
  `batch/<turn>/insts/<id>-<turn>.json`。id 由 loop 補回合號。其餘不變。
- **agent 要改**：`init` 改寫常駐檔而不是投 inbox；`step` 刪掉第 6 步（不再自我投遞）；
  新增 `aos agent stop <folder> <name>` ＝ 刪掉常駐檔（或 rename 成 `.off`）。
- **解決**：1（崩了下回合照樣被叫，`out/` 留下 exit≠0）、2（刪檔即停，不會復活）、
  6（agent 自己不投，手動多投一條只多跑一次，不會指數成長；同回合最多一份）。
- **新問題**：(a) 若放 `agents/<name>/`，loop 開始讀 `agents/` 的內容——破了協定 §1
  「loop 只鏡射 status.json」；泛化成 `.aos/every/` 就不破，loop 甚至不知道 agent 存在，
  代價是多一個頂層目錄。(b) 常駐檔壞了（JSON 解不開）loop 怎麼辦——跳過並在 `state.json`
  記一筆，或整回合拒絕。(c) **idle 回合消失**：有常駐檔的世界每回合都有一批，`batch/` 每回合
  長一個目錄，step 每回合空跑一支行程（不叫 LLM，token 沒事）。要「每 N 回合」就得加欄位，
  協定開始長。

### 方案 B：`status.json` 反向驅動

- **loop 要改**：鏡射 `agents/*/status.json` 時（本來就讀），若 `"next": true`，替它投
  `{"id":"agent-<name>-<turn+1>","argv":["aos","agent","step",<folder>,<name>]}`。
- **agent 要改**：`status.json` 加 `next` 欄，每次寫都帶；`step` 刪掉第 6 步；`stop` ＝
  把 `next` 改成 `false`——但 step 下回合會整檔覆寫，所以 step 必須先讀舊值再寫。
- **解決**：1（status.json 還在就會被叫）、6（同上）；2 只算弱解（見下）。
- **新問題**：(a) `status.json` 從純觀測變成控制面，第 4 條的「半路狀態」現在會影響
  控制：鏡射到半路的檔就可能漏投一回合。(b) loop 得知道 `aos agent step` 的 argv 長什麼樣
  ——硬寫進 loop 就是「指令層知道 agent 層」，分層倒轉；改成 status.json 自帶 argv，
  就變回方案 A 只是塞進另一個檔。(c) 使用者寫 `stop` 與 agent 寫 status 撞同一個檔，
  正是 [top-down-cli §五 9](top-down-cli.md) 那個單檔撞車問題。

### 不建議走的第三條路

「supervisor 也做成一條自我投遞的 inst」符合 B12 判準（loop 只收無法成為 inst 的東西），
但靜默死亡只是往上推了一層——supervisor 自己死了一樣沒人知道。不展開。

## 建議與待使用者拍板的問題

**建議走 A，且放 `.aos/every/`。** 理由：一個檔一個職責，「刪檔即停」是資料夾世界最直覺
的控制面；loop 只是多一個「每回合重投而不搬走」的投遞匣，不需要理解裡面是誰——這比 B
乾淨，也比 A 放 `agents/` 少破一條協定。而且「每回合必須醒來的東西」正是 B12 判準說
該歸 loop 的那一類。第 3 條（三回合往返）與第 4、5 條另案處理，不混進這次。

要拍板的：

1. **自我投遞要不要進 loop？**（yes／no；no ＝ 維持純投遞式，接受第 1、2、6 條）
2. **進的話走 A 還是 B？**
3. **A 的常駐檔放 `.aos/every/<id>.json`（loop 不碰 `agents/`）還是
   `agents/<name>/next.json`（loop 破例讀 `agents/`）？**
4. **工具往返固定三回合，接受嗎？** 不接受的話 loop 得做「回合內二次匯聚」，那是另一篇。
5. **有 agent 的世界從此沒有 idle 回合，可接受嗎？** 不接受就得在常駐檔加「每 N 回合」欄位。

**這份只是規劃，還沒實作，等使用者拍板。**
