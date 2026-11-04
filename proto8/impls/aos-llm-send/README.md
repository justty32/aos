# aos-llm-send

`aos-llm-send - 把一張單子寄進 kernel 的信箱，等回信，結果原樣交回`（NAME，C-54 R1）

**一句話：`aos-llm-send [旗標] 單子.json`——不直接跑那張單子，而是寫成一封信丟進 `$AOS_KERNEL` 信箱的 `new/`，等 kernel（[aos-llm-kernel](../aos-llm-kernel/README.md)）輪到它、跑完照信封的 `reply_to` 寄一封回信，再把 stdout、stderr 原樣吐出來、以單子的碼結束。**
叫它的那一格看到的跟直接跑那張單子一樣，不知道有 kernel（C-20）。一個 lib（`lib/libaos-llm-send.a`，沒有公開標頭）加一支薄命令列（`bin/aos-llm-send`）。連 aos-llm-kernel 的公開標頭（信箱與信的格式）。全家慣例見 [impls/README.md](../README.md)。

像寄掛號信：你不自己跑一趟，把要辦的事寫好丟進郵筒、站在旁邊等回條；回條來了就照著上面的結果交差。等太久被叫走（收到訊號）就把信從郵筒抽回來；已經在辦的就讓他辦完，回條沒人拿、由郵局清掉。

```sh
cat fsm.json   # think 格不直接跑腦，跑閘門；腦那張單子放在同一格的 brain，加 priority
# "think": {"exec": {"argv": ["aos-llm-send", {"$env": "AOS_CF", "$path": "#/states/think/brain"}],
#                    "stdout": {"$env": "AOS_STACK", "$path": "plan.txt"}, "timeout_ms": 120000},
#           "brain": {"argv": ["python3", "brain.py"], "priority": "high"}, "next": "act"}
AOS_KERNEL=/path/to/mailbox aos-exec --ws ws agent    # 信箱位置由叫它的人綁（像 AOS_BRAIN_*，P-39）
```

設計與決定見 [thinking 2026-10-24 LLM kernel](../../thinking/2026-10/24/llm-kernel/README.md)。

## 分檔目錄

> 超過 8 KB，依 [STRUCTURE](../../../wf/STRUCTURE.md) 按標題拆開；本檔留前言與表，各段逐字在下列分檔。

| 分檔 | 涵蓋的段 |
|---|---|
| [01-用法等](docs/01-用法等.md) | 用法；元素；錯誤代號；建置與測試；已知限制 |

<a id="用法"></a>
<a id="元素"></a>
<a id="錯誤代號"></a>
<a id="建置與測試"></a>
<a id="已知限制"></a>
