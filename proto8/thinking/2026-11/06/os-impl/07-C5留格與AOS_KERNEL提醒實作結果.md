# C5 留一格給高優先＋E2 的 llm kernel 半（AOS_KERNEL 指不到印 warning）實作結果（11-06 晚家機）

← [入口](README.md)｜上一份 [06-判官排隊第二步實作結果](06-判官排隊第二步實作結果.md)｜裁定來源 [no-pid 19 § 使用者裁定 1](../../05/no-pid/19-P9邊緣實測.md#使用者裁定11-06-晚家機)、[env-portability Q5](../env-portability/README.md#使用者裁定11-06選項框)｜原規劃 [01-續 C5](01-逐項分類-續.md)

## 一句話結論（白話）

llm kernel 現在可以「留位子給急件」：`kernel.json` 寫 `reserved: {"high": 1}`，普通和低優先的問腦信最多只能佔 `slots − 1` 格，最後一格只給 high。P9 那種「兩封慢的 low 把格子佔滿、high 乾等 3 秒」的情況，同樣的壓力下 high 現在 **17.5 ms** 就掛上（沒留格的對照組 **3065 ms**）。另外 `AOS_KERNEL` 設了但那裡沒有信箱時，llm kernel 會印一行提醒（以前默默寄失敗）。

## 做了什麼

| 項 | 改了什麼 | 檔 |
|---|---|---|
| `reserved` | `kernel.json` 頂層選填物件，只認 `high`（非負整數且小於 `slots`；其他 key、負數、≥ slots＝`CfgBad`；沒寫＝現況）；補位時信的**宣告級數**低於 high＝只能補到 `slots − N`，被擋的留 new/ 下一次，**繼續往後找 high**（不停整列）；aging 升上來的不算 high | `impls/aos-llm-kernel/src/serve/config.cpp`、`serve.cpp`、`serve.hpp` |
| AOS_KERNEL 提醒 | `find_host`：`AOS_KERNEL` 非空但 `<它>/new` 不是資料夾＝`aos-llm-kernel: warning: AOS_KERNEL points to a missing mailbox: PATH; letters to it fail until it exists`，每行程每路徑一次；照舊用它（不改退路、不報錯），掛 proc 失敗照舊 `LaunchFailed` | `src/daemon/daemon.cpp`、`daemon.hpp` |
| 文件 | impls/aos-llm-kernel README、docs/01／03／04（非搶占：保留格只防「低優先占滿」；slots 1 時沒辦法保留）、kernel/docs/01；os-impl 01-續 C5、env-portability Q5 加已實作註 | — |

## 代定（可翻案）

1. **只做 kernel 頂層 slots**；01-續 C5 原句寫「包加」，P9 量到的是頂層 slots 被占滿，包（endpoint）層等量到再說。
2. **只認宣告級數、不含 aging**：不然等久了的 low 會升級搶走保留格，留格就沒意義。
3. 窗 `endpoints.json` 只列包的 slots，沒列頂層 slots，所以沒加 `reserved` 窗。
4. E2 的 Python 半維持報錯，見 [06 代定 5](06-判官排隊第二步實作結果.md)。

## 驗收（codex 實跑；假腦 `fake_slow` 3 秒／`llm_fake`；證據 `/tmp/b1b-verify-anvqz8ez/`）

| 案 | 結果 |
|---|---|
| ① `slots: 2, reserved: {"high": 1}`：兩封 low、再一封 high | 第一封 low 30 ms 掛上；第二封 low 留 new；high **17.52 ms** 掛上（< 自己 800 ms）；第二封 low 在第一封跑完後掛上 |
| ② 同上不寫 `reserved`（對照） | high 等 **3065.46 ms**（重現 P9 B3-02） |
| ③ 設定檢查 17 組（`{"high": 2}`／`{"low": 1}`／`{"high": -1}`、null、陣列、bool、小數、超大數、slots 1 時 0 合法 1 不合法…） | 全對（壞的退 1 `CfgBad`） |
| ④ aging：low 的 effective 升到 19、高於新 high 的 1 | low 仍留 new，後面的 high 照掛 |
| ⑤ `AOS_KERNEL=/tmp/b1b-nowhere` 起三個行程 | 每個 stderr 正好一行 warning、退 0；問腦信照舊回 `LaunchFailed`；同行程重複／換路徑／fork 子行程另驗 |

收尾只收自己起的 daemon pid，`pgrep -af aos-` 無殘留；wf-lint 退 0。建置在 scratchpad 的 clone（`nice -n 15`、`-j4`）。**主 repo 的 `impls/*/bin` 這次沒重建**——使用者今晚在 `~/code/playground` 用的就是這些執行檔，等他玩完再 `(cd proto8/impls && nice -n 15 cmake --build build -j4)`；新設定沒寫時行為跟舊版一樣。
