# ops flavor 包 — 維運

← [repo README](../../README.md)

伺服器 / 服務維運的工作流包，搭配 [`template/`](../../template/) 這個共用 kernel 用。承接「**異常 → 轉對應深查工作流**」那一段：盤點看現況（inventory）、出事深查（incident）、上線走 deploy。

常與 [heartbeat 包](../heartbeat/workflows/routines.md) 搭配：routines 的「開工唯讀盤點」要叫的就是 [inventory](workflows/inventory.md)，盤到異常轉 [incident](workflows/incident.md)。

## 這個包有什麼

| 路徑 | 角色 |
|------|------|
| [WORKFLOWS.ops.md](WORKFLOWS.ops.md) | 派發表片段（貼進 kernel 的 `WORKFLOWS.md`）|
| [workflows/inventory.md](workflows/inventory.md) | 唯讀盤點 / 健康檢查：跑一輪指令、回一句總結 |
| [workflows/incident.md](workflows/incident.md) | 異常深查：現象原文照貼 → 定位 → 修 → 記坑 |
| [workflows/deploy.md](workflows/deploy.md) | 部署 / 上線 / 回滾，含 WAIT_USER 交接點 |

加購菜單（要了才建，照 `workflows/TEMPLATE.workflow.md` 從單檔長）：**backup**（備份 / 還原演練）、**monitoring**（告警規則）、**runbook**（例行操作手冊）。

## 怎麼合進 kernel

```
tools/wf-init.sh --target <專案> --flavor ops
```

通用步驟見 [IMPORT.md](../../IMPORT.md)。本包特有：只有一個片段檔 [WORKFLOWS.ops.md](WORKFLOWS.ops.md)（貼進專案 `WORKFLOWS.md` 的 `<!-- wf-insert:WORKFLOWS -->` 之前），`workflows/` 底下的檔直接併進專案 `workflows/`。

## 移除某工作流要動的地方

| 移除 | 要動的地方 |
|------|-----------|
| inventory | `workflows/inventory.md`；`WORKFLOWS.md` 該列；incident / deploy 交接段指向它的那行；heartbeat routines 的盤點項 |
| incident | `workflows/incident.md`；`WORKFLOWS.md` 該列；inventory / deploy 交接段指向它的那行 |
| deploy | `workflows/deploy.md`；`WORKFLOWS.md` 該列；`WAIT_USER.md` 殘留的 `[deploy]` 列 |

改完跑 `bash tools/wf-lint.sh <專案>`（Claude Code 可用 `/wf-lint`）確認沒有壞連結與孤兒列。
