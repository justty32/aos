← [入口](../2026-10-28-aos-tools.md)｜涵蓋：11-03 exe 快取的開關（`add --no-cache`）｜上一份 [03-結論](03-結論.md)

## 11-03 exe 快取的開關（`add --no-cache`）

### 原文（逐字）

使用者問了 tools.json 裡 exe 工具的 cache 與 stamp 之後說：「這個功能有時候會變成阻礙。是否有開關能夠關閉這個功能」。

頂層給兩個選項：(a) 跟著工具走——`aos-tools add --no-cache XXX`，tools.json 那一項記成不用快取，之後每次都重跑 `XXX --tooldef`；(b) 跟著這次呼叫走——`ls --no-cache`、`aos-mcp --no-cache`。使用者回「a」。

### 決定

選 (a)：開關記在 tools.json 的那一項上，跟著工具走；ls／get（以及經 aos-mcp 的 tools/list）讀到這種項就每次跑 `--tooldef`、不讀不寫快取。call 本來就不看快取，照叫。

### 代定（照原則定、可翻案）

1. **key 用 `"cache": false`**：跟原本的 `cache` 物件同一個 key、不同值——物件＝快取，`false`＝不用快取。不另開 `no_cache`，免得同時有 `no_cache: true` 又有快取物件這種打架的寫法。`cache` 只收 `false` 或物件，別的（例如 `true`）＝RegistryBad（不符合要求一律報錯、不猜）。
2. **dir／json 給 `--no-cache`＝ArgumentsBad**（它們本來就沒有快取，給了是寫錯）；手寫的 tools.json 在 dir／json 項寫 `"cache": false`＝ls／get 報 RegistryBad（訊息帶工具名）。
3. **`add --override` 沒帶 `--no-cache`＝回到有快取**：override 是整項重寫，寫什麼就是什麼；要繼續不用快取就再帶 `--no-cache`。
4. **add 時照樣跑一次 `--tooldef`**：驗定義合不合（跟沒帶旗標一樣），只是不存。
5. **手寫也行**：`aos-json set tools.json#/tools/名/cache false`（有 `$ref` 拆檔就加 `--follow`）；改回有快取＝`add --override` 重登記（只 `aos-json del …#/tools/名/cache` 的話沒有快取物件，ls／get 照樣每次重跑，因為讀的時候不寫回）。
6. aos-mcp 零改動（它只轉叫 `aos-tools ls --json`／`call`）。

實作：[proto8/bin/aos-tools](../../bin/README.md)。
