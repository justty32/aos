---
description: 檢查 aos run 的回合狀態與 heartbeat 排隊項目；未啟動時提供開啟方式
---

← [WORKFLOWS](../../wf/WORKFLOWS.md)｜[INDEX](../../wf/INDEX.md)

本指令是 [tick 工作流](../../wf/workflows/tick.md)的薄殼：只檢查本 repo 的 `aos run`
是否持續推進，不自行啟動常駐程序，也不代替 `aos tick` 判定清單。

## 檢查

1. 在 repo 根目錄確認 `.aos/state.json` 存在、含 `turn`，而且最近仍有更新：

   ```sh
   test -f .aos/state.json && grep -q '"turn"' .aos/state.json && find .aos/state.json -mmin -2 -print
   ```

2. 只有三項都成立才視為正在跑。可用下列指令讀目前回合：

   ```sh
   sed -n 's/.*"turn":[[:space:]]*\([0-9][0-9]*\).*/\1/p' .aos/state.json | head -n 1
   ```

## 回應

### 正在跑

回報「目前第 N 回合，心跳正常」，再執行：

```sh
aos routine ls
```

把目前常規事務與下次到期一併給使用者看；不另跑 `aos tick`。

### 沒在跑

不要自行開常駐。告訴使用者可在 repo 根目錄先執行：

```sh
aos heartbeat init --interval 30m
aos run --step 0
```

第二行會持續佔用目前視窗，通常放在另一個視窗；要停就中止它。最後問使用者要不要自己開啟。
