# 名詞表：回合、執行與喚醒
← [BACKGROUND](../../BACKGROUND.md)｜[workshop](../../README.md)｜[待答問題](../../OPEN-QUESTIONS.md)

「一回合怎麼開始、怎麼推進、怎麼被喚醒」相關的名詞。原本是一份檔案，詞條增長後按職責拆成三份；每個詞仍是固定四行（白話／嚴格／在 aos 裡具體是什麼／為什麼會冒出這個詞）。**要查某一個詞，直接看下面的〈逐詞索引〉。**

## 分檔導航

| 檔案 | 裡面有什麼 | 什麼時候會想看 |
|---|---|---|
| [回合邊界與崩潰現場](turn-boundary.md) | world、`.runi`、彙整／取件／釋放、孤兒行程／`setpgid`、running marker 與租約 | 想確認一回合從哪裡開始算、到哪裡算結束，或崩潰後留下的現場能不能相信時。 |
| [回合開頭的固定步驟與版本](boot-and-versioning.md) | `kernel.json`、init(1) 與 reset vector、角色表與 `boot.json`、busybox 式單一執行檔與 `/proc/self/exe` | 想知道每回合開頭的序言／尾聲與扮演者從哪裡來、又怎麼一起版本化時。 |
| [喚醒、進度與短路](wake-and-progress.md) | tick、cursor、短路與 `"needs"` | 想知道回合被什麼觸發、進度書籤記在哪、批次裡哪幾筆會被跳過時。 |

## 逐詞索引

（順序同拆檔前，共 12 個詞。）

- world／world folder → [回合邊界與崩潰現場](turn-boundary.md)
- `kernel.json` → [回合開頭的固定步驟與版本](boot-and-versioning.md)
- init(1)／reset vector → [回合開頭的固定步驟與版本](boot-and-versioning.md)
- `.runi` → [回合邊界與崩潰現場](turn-boundary.md)
- tick／wake → [喚醒、進度與短路](wake-and-progress.md)
- cursor → [喚醒、進度與短路](wake-and-progress.md)
- 彙整（aggregate）／取件（claim）／釋放（release） → [回合邊界與崩潰現場](turn-boundary.md)
- 角色表（role table）／`boot.json` → [回合開頭的固定步驟與版本](boot-and-versioning.md)
- 單一執行檔多子命令（busybox applet）／`/proc/self/exe` → [回合開頭的固定步驟與版本](boot-and-versioning.md)
- 孤兒行程（orphan）／process group／`setpgid` → [回合邊界與崩潰現場](turn-boundary.md)
- running marker（起跑標記）／租約（lease） → [回合邊界與崩潰現場](turn-boundary.md)
- 短路（short-circuit）／`"needs"` → [喚醒、進度與短路](wake-and-progress.md)
