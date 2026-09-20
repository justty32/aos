# reference/ — 移植用的原始碼，**不是 aos 的一部分**

這層底下的東西**不建置、不安裝、不匯出**，沒有任何 `CMakeLists.txt` 引用它。
它存在的唯一理由是：C++ 重寫時要有一份對得起來的原文。

**重寫完成並驗證過之後，整個 `reference/` 會被刪掉。** 不要在這裡修東西，
不要讓 aos 的程式或文件指向這裡（`reference/PORTING.md` 例外，那是移植計畫本身）。

## 目前放了什麼

原文本身已經不在這裡了。**llmkit 在 2026-09-20 獨立成自己的 git repo：`~/repo/llmkit`**
（用 `git subtree split` 帶著在 aos 裡的五個 commit 拆出去，內容一字不差）。這一層現在只剩
本檔和 [`PORTING.md`](PORTING.md)。

| | 現在在哪 | 對應的 aos 小專案 |
|---|---|---|
| `tooljson/` | `~/repo/llmkit/tooljson/` | `core/tooljson`（S1 外殼已落地）|
| `llms/` | `~/repo/llmkit/llms/` | `core/llms`（已落地）|
| `proxy/` | `~/repo/llmkit/proxy/` | 原樣搬進 `core/llms/proxy/`，沒有程式碼要重寫 |

來歷：

```
2026-08-23  從 ~/repo/simple_tools/freepy/llmkit/ 原樣複製進 reference/llmkit/
            freepy commit 3631bd2  Move the instruction runner into the aos submodule
            只排除 __pycache__，其餘一個字都沒改
2026-09     在 reference/llmkit/proxy/ 接上 ChatGPT Pro／Claude Pro 訂閱（litellm.yaml、兩支 token 腳本）
2026-09-20  整個 reference/llmkit/ 帶歷史拆成獨立 repo ~/repo/llmkit，aos 這邊刪掉
```

「原文不改」的規矩仍然適用：要修正的想法寫進 `PORTING.md`，不要改 `~/repo/llmkit` 的
python 來遷就 C++。（proxy 那部分是活的設定，在那個 repo 裡照常改。）

## 讀哪幾份

移植的**契約**是這兩份，不是 `.py`：

- `~/repo/llmkit/tooljson/FORMAT.md` —— spec 的外殼，所有 `_type` 共通
- `~/repo/llmkit/tooljson/EXEC.md` —— `_type: "exec"` 的完整規則

它們本來就是寫給「別的語言的第二個實作」看的（FORMAT.md 最後一節「一份實作要做到
什麼」列了九條），C++ 版就是那個第二個實作。`.py` 只是同一份契約的第一個實作，
兩者衝突時**以 .md 為準**，並把落差記進 `PORTING.md`。

`~/repo/llmkit/tooljson/PYTHON.md` 是 python 專屬的 `_type`，C++ 這邊照規範就是讀不懂的壞檔，
留著只是為了讓 registry 的開放性有一個真實對照組。
