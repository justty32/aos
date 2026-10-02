← [daemon 協議：佈建、私有通道與 runner](../provision-and-runner.md)（分檔 3/3）｜[上一份](02-P-109-P-111-runner與錯誤.md)

## P-112．schema 與最小範例〔建議預設，未拍板〕

> **暫緩**（2026-10-01）：最核心 daemon 第一版不做（使用者 2026-10-01）。舊 schema（`daemon-rpc`、`daemon-registration`、`daemon-state`、`daemon-runner-report`、`daemon-provision`、`daemon-helper`、`daemon-launch-error`）與 `examples/daemon/` 裡對應的範例留作紀錄、不刪不改；現行的是 `daemon-core-config`（[P-120](../../../../protocol/daemon/core.md)）與 `daemon-ctl`（[P-121](../../../../protocol/daemon/control.md)）。條號保留、不重用。

| schema | 驗什麼 |
|---|---|
| [common](../../../../../protocol/schemas/common.schema.json) | 只放共用型別 |
| [daemon-rpc](../../../../../protocol/schemas/daemon-rpc.schema.json) | 公開 IPC，含 P-117～119 的通道 method |
| [daemon-registration](../../../../../protocol/schemas/daemon-registration.schema.json)、[daemon-provision](../../../../../protocol/schemas/daemon-provision.schema.json) | 上面兩類 method 的參數 |
| [daemon-helper](../../../../../protocol/schemas/daemon-helper.schema.json) | 私有通道 |

**範例**：[examples/daemon/](../../../../../protocol/examples/daemon) 的檔名首段對應 schema：`config`、`state`、`runner_report`、`launch-error` 驗同名 schema，`helper_*` 驗 helper，其餘驗 rpc。正反例涵蓋必填、未知欄位、版本、掛行程帶週期、通道憑證、查詢分頁與結果矛盾；解析、授權與 OS 事實仍要照正文驗收。

**嚴格或放寬**（照 [P-007](../../../../../protocol/README.md)，第十八批）：

- 持久檔 `daemon-config`、`daemon-state`、`daemon-launch-error`：放寬，不寫 `additionalProperties:false`；它們共用的 `$defs` 用開放版（`TopRegistrationOpen`、`RegistrationOpen`、`ProvisionGrantOpen`、`IdentityGrantOpen`、`GrantItemOpen`、`GroupItemOpen`）。
- 嚴格：`daemon-rpc`、`daemon-helper`、`daemon-provision`、`daemon-runner-report`，以及 `daemon-registration` 的 `RegisterParams`、`BoundRegistration`、`TopRegistration`、`MountRecord`。
