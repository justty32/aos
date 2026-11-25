# aos

「資料夾＝程式」的 AI agent 體系。現役本體在 **[proto8/](proto8/README.md)**（第八版原型）：
C／C++ 的基礎層與標準庫（aos-exec、aos-loop、aos-fsm、aos-daemon、aos-llm 等）在 `proto8/cpp/`，
給人打的指令、腦叫的工具、agent 範本是 Python／sh，概念／規範／慣例條文在 `proto8/docs/`。

## 建置與安裝

需要 Python 3.11 以上、支援 C++20 的 g++（10 以上）與 make；不用 CMake、不用 vcpkg（nlohmann json 已收進 `proto8/cpp/third_party/`）。
在 `proto8/` 跑 `python3 install.py`：查相依、編 `proto8/cpp/`、把指令放進 `proto8/bin/`、標頭放進 `proto8/include/`（兩夾不進 git）；重跑＝重新安裝。
裝好後先 `export AOS_HOME=<repo>/proto8`（每台一次，例如寫進 `~/.bashrc`），每個視窗再 `source "$AOS_HOME/env.sh"`（清掉 `AOS_HOME` 以外的 `AOS_*`、把 `$AOS_HOME/bin` 放到 PATH 最前；`AOS_HOME` 沒設就報 `EnvBad`、什麼都不改）。

repo 根沒有 CMake：08～09 月那一代單一執行檔 `aos`（根目錄 CMake、`core/`、`modules/`、`docs/`…）
11-05 整組封存在 `archive/`（11-17 已刪，見 git 歷史 c97d6ade8）的 `aos-v1/`，不再建。

## repo 佈局

```
proto8/     現役本體（程式、條文、討論紀錄；一覽在 proto8/README）
wf/         分層工作流文件（開發流程用，給 agent 看）
archive/    封存：舊原型 proto～proto7-2、甲代 aos-v1（11-17 已刪，見 git 歷史 c97d6ade8）
AGENTS.md   agent 的最頂層入口（CLAUDE.md 指向它）
```

## 文件

| | |
|---|---|
| [proto8/README.md](proto8/README.md) | 各夾一覽、入口（CONCEPTS／NORMS／CONVENTION）、現況 |
| [proto8/cpp/README.md](proto8/cpp/README.md) | C／C++ 各專案與建置 |
| [AGENTS.md](AGENTS.md) → [wf/](wf/INDEX.md) | 開發流程（不是給使用者看的）|

## 授權

程式與 repo 裡其他內容用 MIT（[LICENSE](LICENSE)）；`docs/` 的網站（GitHub Pages）另用 CC BY 4.0（[LICENSE-docs](LICENSE-docs)）。
