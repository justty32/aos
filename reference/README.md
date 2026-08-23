# reference/ — 移植用的原始碼，**不是 aos 的一部分**

這層底下的東西**不建置、不安裝、不匯出**，沒有任何 `CMakeLists.txt` 引用它。
它存在的唯一理由是：C++ 重寫時要有一份對得起來的原文。

**重寫完成並驗證過之後，整個 `reference/` 會被刪掉。** 不要在這裡修東西，
不要讓 aos 的程式或文件指向這裡（`reference/PORTING.md` 例外，那是移植計畫本身）。

## 目前放了什麼

| | 來源 | 對應的 aos 小專案 |
|---|---|---|
| [`llmkit/tooljson/`](llmkit/tooljson/README.md) | freepy | `core/tooljson`（規劃中）|
| [`llmkit/llms/`](llmkit/llms/README.md) | freepy | `core/llms`（規劃中）|
| [`llmkit/proxy/`](llmkit/proxy/README.md) | freepy | 原樣搬進 `core/llms/proxy/`，沒有程式碼要重寫 |

搬過來的時間與出處：

```
2026-08-23  從 ~/repo/simple_tools/freepy/llmkit/ 原樣複製
            freepy commit 3631bd2  Move the instruction runner into the aos submodule
            只排除 __pycache__，其餘一個字都沒改
```

一個字都沒改是刻意的 —— 移植過程要能隨時回頭問「原本到底怎麼寫」，改過的原文
會讓這個問題答不出來。要修正的想法寫進 `PORTING.md`，不要寫進這裡。

## 讀哪幾份

移植的**契約**是這兩份，不是 `.py`：

- [`llmkit/tooljson/FORMAT.md`](llmkit/tooljson/FORMAT.md) —— spec 的外殼，所有 `_type` 共通
- [`llmkit/tooljson/EXEC.md`](llmkit/tooljson/EXEC.md) —— `_type: "exec"` 的完整規則

它們本來就是寫給「別的語言的第二個實作」看的（FORMAT.md 最後一節「一份實作要做到
什麼」列了九條），C++ 版就是那個第二個實作。`.py` 只是同一份契約的第一個實作，
兩者衝突時**以 .md 為準**，並把落差記進 `PORTING.md`。

`llmkit/tooljson/PYTHON.md` 是 python 專屬的 `_type`，C++ 這邊照規範就是讀不懂的壞檔，
留著只是為了讓 registry 的開放性有一個真實對照組。
