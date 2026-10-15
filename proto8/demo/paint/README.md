# 畫家 demo — 一個 agent 透過工具叫另一個 agent

← [proto8/demo](../README.md)｜機制說明：[lib agent.md「agent 當函數／當工具」](../../lib/agent.md#agent-當函數當工具)｜依據：[restart §3g.8～3g.12](../../thinking/2026-10-11-restart/05-第三輪口述後段.md#3g8-agent最普通的很簡單先做一個-demo真正的目標是怎麼讓這個函式方便人寫)

使用者 10-11 說「先實作一個 demo，看實作出來的協議符不符合概念」，舉的例子是：「我要使用這個**畫家 agent**，引數就是『幫我畫這一幅畫』」，畫家裡面還有一個「**畫筆 agent**」幫它準備東西（巢狀）；「agent 也可以變成 agent 的工具」。這個 demo 就照這個例子做。

> **已拍板（10-15 使用者「都按照推薦」）**：使用者原本說的是「先對元素求值，畫家才開始」（畫筆先跑完）；維持**畫家想到了才把畫筆當工具叫**（現在 lib 有的機制）。換腦**只換那一層**：畫筆不跟著畫家換，要換就在畫筆的 frame 放 `brain.json`（見下面「換腦」、[frame.md](../../lib/frame.md)）。

## 怎麼跑

```
python3 proto8/demo/paint/run.py                      # 假腦，約 7 秒，不連任何網路
python3 proto8/demo/paint/run.py 腦設定.json          # 換成真腦：畫家、畫筆都用它
python3 proto8/demo/paint/run.py ... --keep           # 跑完不刪 frame，印出路徑讓你自己翻
```

從哪裡跑都行。腦設定的路徑先照目前資料夾找，找不到再照本資料夾、`demo/fsm/` 找，所以 `brains/lmstudio.json`、`brains/litellm.json`（放在 `demo/fsm/brains/` 的）直接寫名字就行。腦設定就是一張 inst（例 `{"argv": ["aos", "brain", "openai", "--base-url", "http://localhost:4000/v1", "--model", "…"], "timeout_ms": 180000}`）。真腦要會用工具（OpenAI 的 `tool_calls`）。

## 裡面有什麼

```
paint/
  painter/            ← 畫家的定義資料夾（跑的時候一個字都不寫）
    fsm.json          intake → thinking → route →（tool → thinking → route）* → done
    loop.json         一拍敲一次 `aos agent fsm`，走到 done 就停（stop_on_end）
    cells/*.json      每一格就是一張 inst（aos agent intake／think／route／tool／done）
    brain.json        腦＝一張 inst（預設假腦）
    system.md         系統提示：先叫 brush 備顏料，再畫
    tools/brush.json  工具「畫筆」＝sh 三步：寫 frame.json 指 brush/ → 跑 brush 的 loop → 印 ret.json
  brush/              ← 畫筆的定義資料夾（同樣的表與格）
    tools/palette.*   工具「調色盤」：要畫貓 → 橘白黑（寫死的表）
  brains/fake.py       假腦：請求帶 brush 工具就當畫家、帶 palette 就當畫筆
  brains/fake_alt.json 同一支假腦加 `--name 換過的假腦`（回覆前面多「〔換過的假腦〕」，看得出換了）
  run.py              三段展示
```

## 會看到什麼（假腦）

1. **叫畫家**：暫存資料夾開 frame A，放 `frame.json`（`{"parent": painter/}`）和 `args.json`（「幫我畫一隻貓」），在 A 裡跑 `aos loop painter/loop.json`。畫家想 → 叫 brush → 畫筆在 A 的 `work/1/` 裡跑（那裡就是畫筆的 frame，`frame.json` 指 `brush/`）→ 畫筆叫 palette（在 `work/1/work/1/` 跑）→ 回「備好了：橘、白、黑。」→ 畫家畫一隻 ASCII 貓，寫進 A 的 `ret.json`。會印出 frame 的資料夾樹，看得到三層巢狀。
2. **同一個 frame 續聊**：在 A 再寫一份 `args.json`（「再畫一隻狗」）、再跑一次 loop。畫家接著原本的 history（回「第 2 幅」，history 8 則）；畫筆在新的 `work/2/`，是全新的對話。
3. **換腦（綁定）**：frame B 放一份同名 `brain.json`（`brains/fake_alt.json`），蓋過畫家定義裡的。回覆變成「〔換過的假腦〕…」。

最後檢查 `painter/`、`brush/` 的雜湊，跑前跑後一樣＝定義資料夾沒被動到。

```
[ 2.4s] ← ret.json：這是這個 frame 的第 1 幅：一隻貓
          /\_/\
         ( o.o )
          > ^ <
        畫筆說：備好了：橘、白、黑。
[ 2.4s]   work/1/frame.json {"parent": "brush"}｜args.taken.json {"question": "我要畫一隻貓，請備顏料"}
[ 4.8s] ← ret.json：這是這個 frame 的第 2 幅：一隻狗 …
[ 7.1s] ← ret.json：〔換過的假腦〕這是這個 frame 的第 1 幅：一片海 … 畫筆說：〔換過的假腦〕備好了：藍、白。
[ 7.1s] == 定義資料夾 painter/、brush/ 有沒有被動到：沒有（雜湊一樣）
```

## 換腦：為什麼畫筆也要另外綁

frame 裡放 `brain.json` 只蓋到**這個 frame 的 agent**。畫筆的 frame 是 `work/<n>/`，它的 `frame.json` 指回 `brush/`，往上找不會經過畫家的 frame，所以只放 `brain.json` 的話畫筆還是用自己定義的腦（測試 `test_brain_binding_only_reaches_own_frame` 驗這件事）。

要兩個都換，`run.py` 的 `bind_brain()` 多做一件事：在 frame 放一份同名的 `tools/brush.json`（蓋過定義的工具），內容是原本的三步前面多一步 `cp <腦設定> brain.json`——叫畫筆時順手把腦放進畫筆的 frame。這也是一種綁定（工具同名蓋過）。

## 展示到的機制

- fsm 只管「狀態 → 哪一張 inst」，`end` 寫 done／halted（halted 不在 states：think 連錯自己寫好 ret.json 的錯）；走到 end 那拍 loop 看 `stop_on_end` 就停。
- agent＝定義資料夾（fsm.json＋cells 各格 inst＋brain.json＋tools）；呼叫＝frame 資料夾當 cwd（frame.json／args.json／ret.json）。
- 工具＝inst；agent 當工具＝工具 inst 用 sh 三步叫另一個 agent，frame 是 tool 格開的 `work/<n>/`。
- 腦＝OpenAI chat completions 形狀的 inst；frame 放同名檔＝綁定。
- 沒展示到：`AOS_DIRNAME`（資料夾當 inst 的 TARGET 才用得到，這裡的 inst 都是 .json 檔）。

測試：`proto8/lib/tests/test_paint_demo.py`（3 個，假腦）。
