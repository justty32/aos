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

- **場地絕對不要放 `/tmp`——會被清掉，而且原因不明。** 這是目前最貴的一條坑：
  **一整輪（四位、11 分鐘）的場地與報告全部蒸發**。現場是這樣的：

  | 時間 | 事實 |
  |---|---|
  | 15:00–15:10 | 四位跑完，腳本結尾 `wc -c` 印出四份報告 7.5K–10K，**檔案當時確實存在** |
  | 15:11 | 下一次呼叫，`/tmp/aos-hack-core-scope/` **整個不見**，連 14:56 建的無關 marker 也沒了 |
  | 同時 | `uptime` 連續 1:13（**WSL 沒有重開**）、`/tmp` 在 ext4 的 `/` 上（**不是 tmpfs**）、
  `~/.codex/sessions/` 的 rollout 檔**完好無損** |

  也就是說：不是 tmpfs、不是 VM 重啟、不是 systemd-tmpfiles 的年齡清理——
  **有東西在幾十秒內清掉了 `/tmp`，還沒查出是誰。**
  **修法不是查出兇手，是不要用 `/tmp`**：場地放 `$HOME/aos-hack/<題>/p<N>/`。
  `$HOME` 同樣在 WSL 原生 ext4 上（一樣快），而且實測活得下來。

  > **這條對黑客松是致命的**，因為多輪迭代要 `resume` 回同一個場地。
  > 場地沒了，session 的 context 還在也沒用——`resume` 的工作目錄是從原 session 繼承的。

- **還是把「建場地 → 放任務書 → 冒煙 → 開跑」合併成同一支腳本、同一次 `wsl.exe` 呼叫。**
  就算場地改放 `$HOME`，這樣做仍然少一整類跨呼叫的狀態問題。

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

- **session id 的 key 是 `thread_id`，不是 `session_id`。** codex 0.149.1 實測——
  workshop README 那句「grep 第一筆 `session_id`」是舊版的寫法，**在這裡抓不到任何東西**，
  而且失敗是無聲的（`grep` 沒中就是空字串，腳本照樣往下跑）。正確寫法：

  ```bash
  codex exec --json ... > out.jsonl
  tid=$(grep -o '"thread_id":"[0-9a-f-]*"' out.jsonl | head -1 | sed 's/.*:"//;s/"//')
  ```

  **第二輪起要靠它 resume**，沒抓到就等於那一位的 context 掉了。
  萬一真的漏抓，還可以從 `~/.codex/sessions/<年>/<月>/<日>/rollout-*.jsonl` 的**檔名**撈回來
  （UUID 就在檔名裡），但四位平行時無法分辨誰是誰。

- **`codex exec resume` 的旗標位置**：`--json` 與 `-o` 有支援，但**要放在 `resume` 前面**——
  `codex exec --json -o out.md resume <thread-id> - < brief.md`。
  `-s`／`-C`／`--add-dir` **不吃**（沙盒與工作目錄從原 session 繼承），
  所以**場地必須還活著**，這也是場地不能放 `/tmp` 的第二個理由。

## 主辦人自己會犯的錯

- **絕對不要在腳本執行中編輯它。** bash 是**邊讀邊執行、按位元組位移**的：
  你改了檔，正在跑的那個 bash 會從新內容的**舊位移**繼續讀，落在一行中間，
  於是**無聲地停掉、而且 exit 0**。
  2026-08-26 實測代價：R2 的收場四棒只跑完書記就結束，看起來像正常收工，
  白等三分鐘才發現紀錄裡少了三節。
  **要改就等它跑完，或另存一個新檔名。**

- **切紀錄檔的 regex 要綁死輪次。** 產生續輪任務書時要從紀錄裡撈「上一輪的資料包」，
  第一版寫成 `^## (第 2 輪之後的資料包|下一輪的資料包)` 想相容兩種標題——
  結果 R1 那節排在檔案前面，**先被抓走**，第三輪的參賽者拿到的是第一輪的舊資料。
  症狀很好認（切出來的字數跟上一輪一模一樣），但不看就發現不了。
  **一律用該輪專屬的標題，不要寫「或」。**

- **最後一輪不要跑資料員。** 他備的是「下一輪的資料包」，沒有下一輪就沒人讀。
  最後一輪跑書記 → 評委 → 祕書三棒就好，省一棒約三分鐘。

## 檢查改動範圍

- **不要用 WSL 的 `git status` 檢查收場四棒動了什麼——會全紅。** repo 在 `/mnt/c`，
  Windows 端 `core.autocrlf=true`，從 WSL 跑 `git -C /mnt/c/... status` 會把**幾十個
  完全沒被碰過的檔**全部報成 `M`（行尾差異）。實測 R1 收場時 WSL 報了滿螢幕 `M`，
  Windows 側查證只有一個未追蹤的 `records/` 目錄。
  **主辦人的「只動了那一個檔」這項檢查，一定要從 Windows 側做。**
