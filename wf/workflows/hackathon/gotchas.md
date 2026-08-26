# hackathon 踩坑（主辦人專用）

← [hackathon README](README.md)｜跨工作流共通的坑在 [common/gotchas](../common/gotchas.md)

**這裡記的是「辦一場黑客松」本身會撞到的坑**，不是參賽者在題目裡撞到的坑
（那些歸各場的 `records/`）。全部是實測，2026-08-26 第一場開場時一次撞完。

## 從 Windows 驅動 WSL

- **MSYS 會偷改路徑。** 在 Git Bash 裡 `wsl.exe -d Ubuntu -- bash -lc '...'`，
  參數裡的 `/mnt/...`、`/tmp/...` 會被 MSYS 改寫成 `C:/Program Files/Git/mnt/...`，
  症狀非常難認——**腳本裡的變數會莫名其妙變成空字串**，然後 `mkdir -p "$ROOT/x"`
  跑去建 `/x` 並報 Permission denied。
  **每次呼叫 `wsl.exe` 之前都要**：

  ```bash
  export MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*'
  ```

- **長腳本不要塞進 `bash -c '...'`**，寫成 `.sh` 檔放 scratchpad，
  用 `wsl.exe -d Ubuntu -- bash /mnt/c/.../foo.sh` 跑。引號與換行的坑一次消掉。

- **`bash foo.sh` 不會載入 login profile。** `codex` 裝在 `~/.local/bin`，
  非登入 shell 的 PATH 沒有它 → `timeout: failed to run command ‘codex’`、**exit 127**。
  腳本第一行後面補：

  ```bash
  export PATH="$HOME/.local/bin:$PATH"
  ```

- **不要跨呼叫依賴 `/tmp` 的狀態。** 實際發生過一次：場地建好、冒煙測過，
  下一次呼叫時整個 `/tmp/aos-hack-*/` 不見了（WSL 沒重開，uptime 連續；原因未明）。
  **把「建場地 → 放任務書 → 冒煙 → 開跑」合併成同一支腳本、同一次呼叫**，
  就完全繞開這件事。

## 場地

- **只複製 `build/bin/aos` 會跑不起來。** 症狀：
  `error while loading shared libraries: libaos_inst.so.0`。
  執行檔的 RUNPATH 是 `$ORIGIN/../lib`，所以**要一起複製 `build/lib/*.so*`**：

  ```bash
  mkdir -p "$A/build/bin" "$A/build/lib"
  cp -a "$SRC/build/bin/aos" "$A/build/bin/"
  cp -a "$SRC"/build/lib/*.so* "$A/build/lib/"
  ```

- **不要複製整個 `build/`。** 302 MB ×4 是小事，真正的問題是 `CMakeCache.txt` 裡
  全是原 repo 的絕對路徑——參賽者一旦手癢跑 build，**會寫回 `/mnt/c` 上的真 repo**。
  只複製 `bin` 與 `lib`，順便讓「不准 build」變成物理事實。

- **arena 不是 git repo，codex 會拒跑。** 本 repo 的 `.git` 是一個**檔**（linked worktree），
  而且複製時本來就該排除它。所以參賽者那邊要加 `--skip-git-repo-check`。

- **場地 44 MB 一份**（原始碼 1.8 MB ＋ 執行檔與 .so 約 42 MB），四份 176 MB，
  `rsync` 全部建完約十幾秒。不必省。

## codex

- **codex 在 WSL 裡就有**（`~/.local/bin/codex`，`~/.codex/auth.json` 已登入），
  所以**整場在 WSL 內跑**。不要用 Windows 的 `codex.exe` 去搆 `\wsl$\...` 的 UNC 路徑
  ——`-C` 進不去，沙盒也不會照預期運作。
  > 連帶：workshop README 說「任務書放 Windows scratchpad」是 Windows codex 時代的寫法。
  > 黑客松的任務書要放進 WSL 側（或從 `/mnt/c` 讀進來後複製一份到場地旁）。

- **`-s workspace-write` 預設沒有網路。** 所以題目書要明講「模型那端自己寫假模型腳本」，
  否則參賽者會在連線失敗上浪費整輪。真的需要網路要另外開，並在紀錄裡標明。

- **四位平行 ＋ `timeout 1800`**：每位包一層 `timeout`，有人掛掉就在紀錄裡**明寫少了誰**，
  用剩下的繼續，不要靜默略過。

- **收 session id 用 `--json`**，stdout 變 JSONL 落到本機檔，
  `grep -o '"session_id":"[^"]*"' | head -1`。**第二輪起要靠它 resume**，
  沒抓到就等於那一位的 context 掉了。
