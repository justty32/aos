# 02b 版面補充規則
← [入口](README.md)

這份是 [02 版面](02-layout.md) 的下半：設定檔有哪些欄，以及「記憶就是地」那一段。條款編號跟 02 是同一串。

## 設定檔

- **S-02-24** 使用者層 `$AOS_HOME/.aos/config.json` 必須只有這些欄：`format_version`、`units`、`max_parallel`、`max_wait_ms`、`llm_world`、`reap_after_ms`、`path`、`inst_timeout_ms`、`inbox_max`。〔主編補〕
- **S-02-25** 世界層 `<地>/.aos/config.json` 必須只准出現 `format_version`、`path`、`max_parallel`、`inst_timeout_ms`、`inbox_max`，其餘欄一律拒絕。〔主編補〕
- **S-02-26** 世界層的 `max_parallel` 必須只能往下限，比使用者層大的值必須拒絕。〔主編補〕
- **S-02-27** `llm_world` 必須是 LLM 世界那塊地的路徑，預設 `$AOS_HOME/.aos/llm`。〔主編補〕
- **S-02-28** `reap_after_ms` 必須是 daemon 清孤地的期限：脫節子地跑完、父超過這段時間沒來讀，daemon 連結果一起清並留紀錄。〔預設 2026-09-05，C-02〕
- **S-02-29** `inbox_max` 必須是收件匣背壓上限，預設 `1000`；滿了就拒收，見 [07](07-call-and-delivery.md)。〔預設 2026-09-05，I-07〕
- **S-02-47** `units` 每筆可以多一個 `timeout_ms`：LLM 世界跑那筆 `aos llm` 指令的逾時，沒填必須當 `300000`，見 [09](09-llm-world.md)。〔主編補〕

## 子地怎麼開

- **S-02-30** 子地預設必須躺著不動，父點名才開；禁止自動求值、禁止預設順序。〔裁決 2026-09-03〕
- **S-02-31** 「先跑完所有子地再做我的事」禁止內建；要就自己在原稿裡寫出來。〔預設 2026-09-05，B-04〕
- **S-02-32** 一個資料夾的入口必須是一批（可以同時有好幾條串），不是一條。〔預設 2026-09-05，B-05〕
- **S-02-33** 父開過誰、下一個開誰必須記在 `.aos/series.json`；那是資料夾層借住機器層那根接力棒，禁止另立第二根。〔預設 2026-09-05，B-02〕
- **S-02-34** 一塊地跑起來之後必須不理頂層原稿被改；下次被點名開才重讀。要立刻生效必須停掉重開。〔預設 2026-09-05，B-03〕

## 記憶就是地

- **S-02-35** 停掉、隔天再來，地還在就必須記得；禁止另做一個記憶容器。〔裁決 2026-09-04〕
- **S-02-36** OS 這一層必須只保證三件事：地還在、能列舉、能用 git 存檔回滾。〔預設 2026-09-05，C-03〕
- **S-02-37** 地上放什麼、怎麼摘要、多大要砍，必須交給應用（通常是 agent 自己的圈）。〔預設 2026-09-05，C-03〕

## 版本不合、地 id、誕生、tmpfs

- **S-02-38** `.aos/layout.json` 的 `layout_version` 跟本版不合時必須拒跑，結束碼 `3`，並寫停止原因檔；禁止自動升級或忽略。〔主編補〕
- **S-02-39** 版面要升級必須由人跑 `aos migrate`；第一版的 `aos migrate` 只印訊息，不動檔。〔主編補〕
- **S-02-40** `.aos/layout.json` 必須有 `land_id`：`aos init` 產的 32 個小寫 hex 隨機 id，之後禁止改；登記表每筆帶著它，用來認出「路徑變了但還是同一塊地」。〔主編補〕
- **S-02-41** 身分仍然是路徑，`land_id` 只是認人用的；禁止拿 `land_id` 當主鍵，daemon 也禁止自動改登記的路徑。〔主編補〕
- **S-02-42** 一塊地的誕生必須以 `.aos/layout.json` 用原子改名就位那一刻為準；`aos init` 必須先建好 `.aos/` 裡的東西，最後才把 `layout.json` 改名就位。〔主編補〕
- **S-02-43** `aos mv` 必須連 `.aos/` 一起搬、游標保留，並把前身路徑寫進 `layout.json` 的 `ext.moved_from`；這是「搬家＝死＋生」唯一的例外，直接用 shell `mv` 沒有這個保證。細節見 [08](08-daemon.md)。〔主編補〕
- **S-02-44** LLM 世界必須讀自己的 `.aos/units.json`（daemon 起它時寫進去），禁止去讀家的設定檔；agent 必須把每筆 `<結果落點>.usage.json` 累加進自己的 `.aos/usage.json`，上限對這個檔判，不讀家的帳簿。〔主編補〕
- **S-02-45** `.aos/` 放 tmpfs 時，重開機後從原稿重建必須當成從頭跑；禁止承諾副作用只做一次（寄過的信可能再寄一次）。〔主編補〕
- **S-02-46** 要跨重開機的地，`series.json`、`calls/`、`ticks/`、`frames/` 禁止放 tmpfs。〔主編補〕

## 範例

世界層 `<地>/.aos/config.json`：

```json
{
  "format_version": 1,
  "path": ["/usr/bin", "/bin"],
  "max_parallel": 2,
  "inst_timeout_ms": 30000,
  "inbox_max": 1000
}
```

使用者層 `$AOS_HOME/.aos/config.json`：

```json
{
  "format_version": 1,
  "units": [
    {
      "name": "local",
      "endpoint": "http://localhost:1234/v1",
      "model": "qwen3-8b",
      "tier": "fast",
      "max_parallel": 2,
      "api_key_env": "AOS_LLM_KEY",
      "timeout_ms": 300000
    }
  ],
  "max_parallel": 4,
  "max_wait_ms": 120000,
  "llm_world": "~/.aos/llm",
  "reap_after_ms": 3600000,
  "path": ["/usr/bin", "/bin"],
  "inst_timeout_ms": 60000,
  "inbox_max": 1000
}
```

## 待使用者拍板

- S-02-24 使用者層 config 的九個欄。〔主編補〕
- S-02-25 世界層 config 只准五個欄。〔主編補〕
- S-02-26 世界層 `max_parallel` 只能往下限。〔主編補〕
- S-02-27 `llm_world` 預設 `$AOS_HOME/.aos/llm`。〔主編補〕
- S-02-28 `reap_after_ms` 是清孤地的期限。〔預設，C-02〕
- S-02-29 `inbox_max` 預設 1000。〔預設，I-07〕
- S-02-47 處理單元可填 `timeout_ms`，沒填當 300000。〔主編補〕
- S-02-31 「先跑完所有子地」不內建。〔預設，B-04〕
- S-02-32 入口是一批。〔預設，B-05〕
- S-02-33 父開過誰記在接力棒裡。〔預設，B-02〕
- S-02-34 跑中不理原稿被改。〔預設，B-03〕
- S-02-36／37 OS 只保證地還在、能列舉、能回滾；其餘歸應用。〔預設，C-03〕
- S-02-38／39 版面版本不合就拒跑退出 3，只准人工 `aos migrate`。〔主編補〕
- S-02-40／41 `layout.json` 記 `land_id`，但身分仍是路徑。〔主編補〕
- S-02-42 地的誕生以 `layout.json` 改名就位為準。〔主編補〕
- S-02-43 `aos mv` 連 `.aos/` 一起搬、記 `ext.moved_from`，是唯一例外。〔主編補〕
- S-02-44 LLM 世界讀 `.aos/units.json`，agent 累計 `.aos/usage.json`。〔主編補〕
- S-02-45／46 tmpfs 重建＝從頭跑；接力棒等四樣不准放 tmpfs。〔主編補〕

## 現況對照

今天沒有世界層 `.aos/config.json`，也沒有使用者層 `$AOS_HOME/.aos/config.json`：LLM 並行上限住在 `<AOS_HOME>/cpus.json` 與 `<地>/.aos/llm.json`，PATH 白名單與指令逾時沒有設定檔可調。記憶這一段今天沒有主人，沒人保證地能列舉、也沒有用量上限。
