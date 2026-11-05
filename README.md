# aos

「資料夾＝程式」的 AI agent 體系。現役本體在 **[proto8/](proto8/README.md)**（第八版原型）：
C／C++ 的基礎層與標準庫（aos-exec、aos-loop、aos-fsm、aos-daemon、aos-llm 等）在 `proto8/impls/`，
給人打的指令、腦叫的工具、agent 範本是 Python／sh，概念／規範／慣例條文在 `proto8/docs/`。

## 建置與安裝

需要 CMake、支援 C++20 的編譯器，以及 [vcpkg](https://vcpkg.io)（裝在 `~/dev/vcpkg` 的話什麼都不用設）。
`proto8/impls/` 每個專案一夾、各自建；照依賴順序全建一次的指令在 [testing「proto8」](wf/workflows/testing.md#proto8)。
建好後 `proto8/install.sh` 把指令 symlink 進 `~/.local/bin`（`--dry-run` 只印、`--uninstall` 拿掉）。

repo 根沒有 CMake：08～09 月那一代單一執行檔 `aos`（根目錄 CMake、`core/`、`modules/`、`docs/`…）
11-05 整組封存在 [archive/](archive/README.md) 的 `aos-v1/`，不再建。

## repo 佈局

```
proto8/     現役本體（程式、條文、討論紀錄；一覽在 proto8/README）
wf/         分層工作流文件（開發流程用，給 agent 看）
archive/    封存：舊原型 proto～proto7-2、甲代 aos-v1
AGENTS.md   agent 的最頂層入口（CLAUDE.md 指向它）
```

## 文件

| | |
|---|---|
| [proto8/README.md](proto8/README.md) | 各夾一覽、入口（CONCEPTS／NORMS／CONVENTION）、現況 |
| [proto8/impls/README.md](proto8/impls/README.md) | C／C++ 各專案與建置 |
| [AGENTS.md](AGENTS.md) → [wf/](wf/INDEX.md) | 開發流程（不是給使用者看的）|
