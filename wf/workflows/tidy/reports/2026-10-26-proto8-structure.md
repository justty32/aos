# 2026-10-26 整理：proto8 頂層結構

[tidy](../README.md)｜方法見 [STRUCTURE](../../../STRUCTURE.md)、搬檔見 [refactor/moving-things](../../refactor/moving-things.md)

使用者：「proto8底下太亂了，我希望你能幫我整理一下」。只做結構層：分類收納、入口 README、垃圾確認。檔案內容不改；歷史紀錄（thinking、session_logs、各隊 plan）裡的純文字舊路徑不改，只把 md 連結的目標改到新位置。不碰 `proto8/user-advice/`。

## 做了什麼

- proto8 頂層從 20 項降到 12 項：`README.md docs/ impls/ bin/ lib/ extras/ demo/ topdown/ tests/ thinking/ notes/ user-advice/`。
- `docs/`：CONCEPTS、NORMS、CONVENTION 三份條文（入口 `.md`＋同名分檔資料夾）整組搬進來，一個字都沒改。程式不讀這三份，只動了連結。
- `extras/`：10-24 一天開的周邊工具 human、ai_tools、grow、langs、editors、sandbox 搬進來。程式裡往上找 proto8 根的相對路徑多一層（`aos-ai` 的 `PROTO8`、`aos_human.py` 的 `sys.path`、nvim 外掛與 smoke 的 `PROTO8` 與 PATH 清單、Lua／Janet 例子的 `../../../../demo/`、sandbox 例子的兩條捷徑），`tests/` 六支測試的路徑、`lib/aos` 工具註解裡的路徑、WAIT_USER 給使用者跑的指令一起改。
- 新入口：`proto8/README.md` 加「頂層一覽」表、`docs/README.md`、`extras/README.md`、`topdown/README.md`。
- 試驗場（repo 外）`~/code/try/lua-aos/try.py`（WAIT_USER 要使用者跑的）與 `~/code/try/self-improve/README.txt` 的路徑一起改。
- 刪掉 5 個空資料夾（`proto8/.aos`、`proto8/.stack`、`tests/.stack`、`impls/.aos`、`impls/aos-exec/.aos`）：跑程式留下的，git 本來就不追蹤空資料夾。

## 沒動的

- `impls/` 的 181 MB 是各專案的 `build/`、`bin/`、`lib/`、`.cache/` 建置產物，根 `.gitignore` 早就排除了（git 只追蹤 182 個原始檔）。測試、demo、WAIT_USER 的指令都靠 `impls/*/bin/`，所以不刪。
- `lib/` 留在頂層：demo 與 topdown 有四十多條相對捷徑指向它，它是 agent 的工具庫，不算周邊。

## moves.tsv

```
舊路徑	新路徑
proto8/human	proto8/extras/human
proto8/ai_tools	proto8/extras/ai_tools
proto8/grow	proto8/extras/grow
proto8/langs	proto8/extras/langs
proto8/editors	proto8/extras/editors
proto8/sandbox	proto8/extras/sandbox
proto8/CONCEPTS.md	proto8/docs/CONCEPTS.md
proto8/CONCEPTS	proto8/docs/CONCEPTS
proto8/NORMS.md	proto8/docs/NORMS.md
proto8/NORMS	proto8/docs/NORMS
proto8/CONVENTION.md	proto8/docs/CONVENTION.md
proto8/CONVENTION	proto8/docs/CONVENTION
```

## 驗證

- `cmake --build --preset default && ctest --preset default`：8/8。
- `python3 -m unittest discover -s proto8/tests`：633 個 OK、skip 7（搬之前同一台機器也是 633 OK、skip 7）。
- `sh proto8/demo/run.sh`：結束碼 0。
- `wf-lint wf .claude/commands`：broken=0；`wf-lint proto8`：broken=0（搬前搬後都是 0）。
