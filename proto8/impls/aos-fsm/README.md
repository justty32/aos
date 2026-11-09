# aos-fsm

`aos-fsm - 照一張狀態表，每叫一次跑「現在狀態」那一格，成功就換到下一個`（NAME，C-54 R1）

**一句話：`aos-fsm [FLAGS] CONFIG.json`——一次只跑一格：看 `$AOS_STACK/stage.txt` 記的現在狀態，跑那一格，照表上的 `next` 換狀態（字串＝格退 0 才換；物件＝照格的結束碼查），換了以 0 結束、沒換以格的碼結束。**
一個 lib（`lib/libaos-fsm.a`，沒有公開標頭）加一支薄薄的命令列（`bin/aos-fsm`）。連 [aos-loop](../aos-loop/README.md) 的公開 API（跑一格＝`run_once`；它又帶進 aos-exec、aos-inst、aos-util、aos-directive）。全家慣例見 [impls/README.md](../README.md)。

像大富翁只擲一次骰子：桌上一張地圖（`fsm.json`：每格寫著「走到這裡做什麼、做完去哪格」），棋子停在哪格記在一張小紙條上（`$AOS_STACK/stage.txt`）。
叫它一次，它就看紙條、做那格的事、做成了（0）才把棋子移到下一格，然後下班；做不成就留在原地、帶著那個碼回去。
要一直玩下去，就讓 aos-loop 一次次叫它。

```sh
cat fsm.json
# {"start": "idle", "states": {"idle": {"exec": "idle", "next": "think"},
#   "think": {"exec": {"argv": ["python3", "brain.py"], "stdout": {"$env": "AOS_STACK", "$path": "plan.txt"}, "timeout_ms": 120000},
#             "next": "act"},
#   "act": {"exec": ["act", "--fast"], "next": "idle"}}}
AOS_STACK=st/ aos-fsm fsm.json; echo $?   # 跑 idle 那格（aos-exec -- idle）；退 0 → st/stage.txt 變 think
```

語意以 [NORMS 組合子 § fsm](../../docs/NORMS/07-基礎設施-組合子.md)（N-36、N-38、N-39、N-41）為準，另照 N-05、N-43、N-60 與 CONVENTION P-07～P-10、P-20、P-21、P-36、P-38；本頁只寫用法與實作。本支是唯一實作（使用者「python版本可以刪掉了。aos-exec/loop/daemon都用C++」）。
**不寫 `trace.jsonl`**（使用者「整個拿掉」，[thinking 11-03 trace](../../thinking/2026-11/03/trace.md)）：每次只動 `stage.txt`，而且狀態有變才寫（11-09；閒著停在同一格時不碰檔）。

**11-04 起狀態檔叫 `stage.txt`**（原 `state.txt`；使用者題 10「fsm改名，嘗試用同義詞」——`state` 跟 aos-loop 的 `state.json` 窗同在 stack 根、一詞二義，[four-elements 07](../../thinking/2026-11/04/four-elements/07-實作步驟.md) 步 3）；格式、讀寫規則不變，fsm.json 的 `start`／`states` 不改。
格的 `exec` 可以直接放單子（使用者「不過exec本來就應該要可以直接放內嵌單子吧」「好，就這樣做」，[thinking 10-24](../../thinking/2026-10/24/exec-relative/README.md#10-24-exec-直接放單子)）：物件＝aos-fsm 行程內 `run_inst`（aos-loop 的 `run_once`）。

**轉交的碼**（11-05 stdio-unify R8）：退非 0 時 stderr 有 `aos-fsm: error:` 這行＝我錯（退 1）；沒有＝格的碼（表沒接住，原樣往上）。格的分岔碼是給 fsm 表看的，被表接住不算錯（退 0）。`aos-fsm --help`＝英文說明印 stdout、退 0。

## 分檔目錄

> 超過 8 KB，依 [STRUCTURE](../../../wf/STRUCTURE.md) 按標題拆開；本檔留前言與表，各段逐字在下列分檔。

| 分檔 | 涵蓋的段 |
|---|---|
| [01-用法](docs/01-用法.md) | 用法 |
| [02-元素等](docs/02-元素等.md) | 元素；錯誤代號；建置與測試 |

<a id="用法"></a>
<a id="一次"></a>
<a id="訊號"></a>
<a id="元素"></a>
<a id="錯誤代號"></a>
<a id="建置與測試"></a>
