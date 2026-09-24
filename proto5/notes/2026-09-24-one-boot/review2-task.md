← [本輪報告](README.md)

# astra 唯讀審查任務書（第二輪）：試玩 one-boot 七件的修正

你是唯讀審查者，repo 在目前目錄（git worktree）。不要改檔、不要跑會用到模型的東西（不准碰 LM Studio、localhost:1234、ollama）。

背景：`proto5/notes/play/2026-09-24-one-boot-opus.md` 新手試玩挖到七件。這次的改動是工作區裡**未提交**的差異：`git diff HEAD`（加上新檔 `proto5/lib/test/test_play_one_boot.py`、本任務書）。

改了什麼：
1. `aos-kernel ack` 印一行 `acked NAME（…下一格 tick 刪掉回音）`（`lib/aos_kernel_cli.py`）。
2. `aos-kernel check` 多一項 `pools/<池>`：那池的 `dpool` 在 daemon 家已有 `pool.json` 而 owner 不是這個 K＝bad（`lib/aos_kernel_check.py`、`lib/aos_daemon.py` 新 `pool_owner`）。
3. daemon 沒在跑時 `aos-kernel ls` 文字版：kernel 行、tick 行、池行不再印得像還活著（`lib/aos_kernel_ls.py`、`lib/aos_kernel_rows.py`）。
4. daemon 被 kill -9 時舊 cpu 不跟著死、新 daemon 開機先收它們死透才拉新的：判定為刻意，只寫規範（`spec/daemon/lifecycle.md`）與教程 01。
5. `aos down` 自己印摘要：kernel 剛停／本來就停了／沒 boot 過／沒在跑（帳本還寫 running）；每個 daemon 剛停／本來就沒在跑／留著／沒停（`lib/aos_up.py`、`lib/aos_kernel_boot.py` 新 `halt_status`）。
6. daemon 開機、正常停機各在 stderr 留一行（`lib/aos_daemon.py`），上一任沒正常停會註明。
7. 教程 01 的清場改看 `aos-daemon ls`、pgrep 要篩 `$W`。

請看：各項行為對不對、有沒有新的崩潰窗口或誤判（例如 `pool_owner` 在搬池、owner 路徑寫法不同、symlink 的 K；`halt_status` 跟 `stop` 之間狀態變了；`down` 在 `--keep-daemon`、多 daemon 時的輸出；Boot 行的「沒正常停」判斷在 `state.json` 壞掉時）；測試夠不夠；規範與教程與程式一致嗎。

回報用中文，分**必修**與**建議**，每條：檔:行、問題、為什麼、怎麼改；沒問題的面向各一句。
