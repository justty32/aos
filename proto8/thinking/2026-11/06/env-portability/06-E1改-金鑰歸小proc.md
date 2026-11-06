← [入口](README.md)｜涵蓋：使用者 11-06 更正 E1——金鑰歸那個跑一次的 endpoint 函數 proc（「小 proc」）自己保管；照原則定的細節、代定、方向題｜上一份 [05-衝突與方向題](05-衝突與方向題.md)

# E1 改：金鑰歸小 proc

## 使用者原文（11-06，逐字）

> 不該是這樣的，金鑰應該由那個小proc自己保管，我們在定義那個小proc的時候就要跟他說讀哪個環境變數當金鑰了

前情：頂層先說明了 `request.json` 的由來——kernel 認領信、寫 `request.json`、請 daemon 掛一個跑一次的 endpoint 函數 proc，stdin 讀 `request.json`。這句取代 Q1 原本選的「endpoint 那步才解」：kernel 連 `{"$env": X}` 這個指示詞都不經手、不轉交。

## 一句話

**每個要金鑰的端點，在 llm kernel 的定義裡有一個自己的小定義資料夾**（`endpoints/<名>/`），它的 `_entry` 寫「跑 `llm_http`、`--key-env LITELLM_KEY`」；kernel.json 那包只寫 `"exec": "endpoints/<名>"`、不再有 `key`。小 proc 跑起來時從自己的環境讀那個變數。kernel 的程式一行不用改。

## 定下的（照原則）

1. **「小 proc 的定義」在哪：小 proc 自己的定義資料夾，不在 kernel.json 那包裡**
   - 例：`kernel/llm-kernel/endpoints/litellm/_entry`＝`{"argv": ["aos-exec", "../../../../lib/base/llm_http", "--key-env", "LITELLM_KEY"]}`；kernel.json 的 `smart-high`、`luna`、`sol` 三包都寫 `"exec": "endpoints/litellm"`（包本來就能各自指 `exec`，[aos-llm-kernel docs/01](../../../../impls/aos-llm-kernel/docs/01-用法.md)）。
   - 為什麼不是 kernel.json 那包加一個 `key_env`：那包是 kernel 的設定，kernel 會「整個原樣」把它寫進 `request.json`——就是使用者說的 kernel 經手。C-52「不碰子層」：kernel 只知道「這包交給哪個函數」，不知道函數要什麼。
   - 為什麼不是 `lib/base/llm_http` 自己的 `.env` 或 `_tooldef.json`：lib 是好幾包共用的（LiteLLM 要金鑰、LM Studio 不要），變數名是「這個端點」的事、不是 `llm_http` 的事；寫進 lib＝每個人都得用同一個名字。
   - 為什麼不用 `.env` 設一個旋鈕變數（例 `LLM_KEY_ENV=…`）：四種性質 ④「旋鈕原則上不走環境變數」；argv 就是定義，寫什麼做什麼（C-56）。
   - 可遷移性（C-83、N-67 ⑦⑧）：小定義資料夾在 llm kernel 的定義裡、跟樹走，**裡面只有變數名**；值永遠只在執行期的環境裡。image（定義＋stack）grep 不到金鑰。
2. **kernel.json 的 `key` 欄：拿掉**。範本、kernel docs/01、aos-llm-kernel README／docs/01 的 `"key": {"$env": …}` 例子改成上面的寫法。**kernel 程式不改**：它本來就不認得 `key`（只看 `exec`／`slots`／`budget`／`speed`，其他原樣交出），不為它加檢查（C-52：不替下層驗）。舊寫法不留相容（使用者 11-05「一律當成沒有舊版」）。
3. **`llm_http`（和以後的 endpoint 函數）怎麼讀**：
   - `_tooldef.json` 的參數加 `key_env`（字串、選填）；`tool_io` 照 P-45 把 `--key-env NAME` 映成它（tool_io 已會合併 argv 旗標與 stdin）。
   - 有 `key_env`：讀 `os.environ[NAME]`，帶 `Authorization: Bearer …`；沒 `key_env`：不帶（LM Studio 這種）。
   - **stdin 的 `endpoint` 裡有 `key`＝`ArgumentsBad`**（「endpoint.key is not accepted; give the endpoint function --key-env NAME」）：寫錯地方的金鑰第一封就報錯、被看見，不悄悄照用。
   - 以後的 endpoint 函數照同一個慣例：金鑰變數名是自己的 `--key-env`，不從 stdin 拿。寫進 lib/docs 一句。
4. **沒設那個變數報什麼：`EndpointFailed`**（現有代號；原因句寫「environment variable LITELLM_KEY (--key-env) is not set」）。照 C-54 `…Failed`＝這次叫不成、可以再試：人 export 之後重起 llm daemon 就好。從問腦的那一方看，就是「這個端點叫不成」，跟連不上同一類；不用 `ArgumentsBad`，那會讓寄信的人以為自己的信寫錯。
5. **daemon 給子項的環境有沒有那個變數：有，只要起 llm daemon 的殼有**。aos-daemon 起子項是繼承自己的環境、再 `setenv` 蓋 `AOS_STACK`／`AOS_DAEMON`／`AOS_WS`（[child.cpp](../../../../impls/aos-daemon/src/child/child.cpp)），照 N-63 ③「子 process 預設繼承」——小 proc 是 llm daemon 掛的子項，所以 `LITELLM_KEY` 要在**起 llm daemon 的那個殼** export（root 層，N-67 ⑨）。
   - kernel 行程本身的環境裡也有這個值（同樣繼承），但它不讀——「不經手」指的是不讀、不寫、不轉交。
   - llm daemon 若掛在別的 daemon 底下（P6 子 daemon＝普通 exec 型 proc），一路繼承，所以 export 在最上面那個殼。
   - 小 proc 若包在 aos-sandbox 裡，sandbox 的 `env` 陣列要列 `LITELLM_KEY`（明列＝整份取代預設）。
   - 小定義資料夾不放 `.env` 寫值（N-67 ⑧）。
6. **搬家**：`request.json` 裡沒金鑰；凍住時在飛的那封醒在新機器上，小 proc 重跑時讀新機器的 `LITELLM_KEY`；沒 export＝那封 `EndpointFailed`，別封照常。食譜第 5 步改成「export 各 `endpoints/*/_entry` 的 `--key-env` 列的名字」（grep `key-env` 就是清單）。

## 邊緣（記著，實作時自然可解）

- 有人仍在 kernel.json 那包寫 `"key": {"$env": X}`：kernel 照舊解開寫進 `request.json`（程式不改），`llm_http` 第一封就 `ArgumentsBad`——這一封的信資料夾裡短暫有明文，答完（錯誤回信）即刪。不為此讓 kernel 認得 `key`（C-52）。
- 不同包要不同金鑰（例兩個 LiteLLM 帳號）：各開一個小定義資料夾，`--key-env` 各寫各的。
- `fake`、`fake-demo-*` 這幾包用 `llm_fake`，不要金鑰，不動。

## 方向題（給頂層問；推薦放第一）

**Q1-2 `url`、`model` 要不要也跟著搬進小 proc 的定義？**（**11-06 使用者選「不搬，只搬金鑰 (Recommended)」**：`url`、`model` 留在 kernel.json）
- **A（推薦）不搬，只搬金鑰**：`url`、`model` 不是密鑰；kernel.json 是人一眼看全部包（代號、模型、價錢、速度）的地方，`aos-llm ls` 也從那裡算；換機器改 `url`（localhost 埠不同）是外接，食譜改 kernel.json 一處。代價：kernel 仍把 `url`／`model` 原樣轉交，「kernel 不經手端點設定」只做到金鑰這一樣。
- B 連 `url` 一起進小定義（`--url`）：kernel.json 只剩代號與排程屬性。代價：改模型要動兩處（`model` 留不留在 kernel.json 也要再分）、`aos-llm ls` 看不到端點在哪。

## 工時

E1 新做法約 **1 h**（原估 1.5 h）：`llm_http` 加 `key_env`、拒 `endpoint.key`（0.3 h）；範本 `kernel/llm-kernel/endpoints/litellm/` 與 kernel.json 三包改 `exec`、拿掉 `key` 例子（0.2 h）；kernel docs/01、aos-llm-kernel README／docs/01、lib/docs 一句（0.3 h）；假腦驗「image grep 不到金鑰、沒 export＝EndpointFailed」（0.2 h）。**不碰 C++**，所以不用等 T 線收 llm-kernel，P8 前做就好。
