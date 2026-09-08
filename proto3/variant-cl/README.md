# variant-cl — 同一套骨幹的 Common Lisp 版（SBCL）

← [proto3/README](../README.md)

跟 [Janet 版](../src/) 一比一對照：同樣的世界／時鐘／LLM 世界／agent 四個模組、同樣的範例、
同樣的 36 條測試。只用 SBCL 標準庫加 `sb-thread`，不裝任何套件（這台是 SBCL 2.2.9）。

## 對照表

| 概念 | Janet 版 | CL 版 |
|------|----------|-------|
| 世界 | table `@{}`，`(w :key)` | `eq` hash table，`(w-get w :key)`／`(w-put w :key v)` |
| 信、回覆、請求 | struct／table | plist `(:from … :body …)`，用 `getf` |
| 檔案系統 | `world/all`、`world/at` | `*all*`、`world-at` |
| 鐘 | table | `defstruct clock` |
| 非同步 | 一鐘一 fiber（`ev/spawn`，協作式） | 一鐘一 thread（`sb-thread`，真並行，所以求值時拿 `*tick-lock*`） |
| 暫停後繼續 | `kernel/continue` | `resume`（CL 已有 `continue`） |
| 寄信 | `world/send` | `send-mail` |

其餘函式名一樣：`make-world`／`dotick`／`spawn`／`kill`／`take-mail`／`say`、
`register`／`unregister`／`pause`／`ls`／`step-all`／`run`／`start`／`stop-all`、
`make-llm`／`ask`／`echo-engine`／`script-engine`、`make-agent`／`wait-for`。

## 檔案

```
src/package.lisp   套件 :aos
src/load.lisp      照順序載入 src/*.lisp（main／test 都 load 這支）
src/world.lisp     世界、信箱、小孩
src/kernel.lisp    時鐘：同步 step-all／run、非同步 start（thread）
src/llm.lisp       LLM 世界＋兩個假 engine
src/agent.lisp     agent 輪廓＋ wait-for
src/main.lisp      範例（跟 Janet 版同一個劇情）
test/basic.lisp    36 條
```

## 怎麼跑

```sh
cd proto3/variant-cl
sbcl --script src/main.lisp 8          # 同步走 8 格
sbcl --script src/main.lisp async 5    # 非同步跑 5 秒
sbcl --script test/basic.lisp          # 測試
```

## 寫的時候踩到的

- `start` 用 `loop for c being the hash-values` 然後 `(lambda () (run-clock c))`：所有 thread 抓到同一個
  `c`，loop 結束後是 nil。要在 loop 裡 `let` 一份新的再給 lambda。
- `continue` 是 CL 內建符號，SBCL 有 package lock，不能拿來當函式名。
