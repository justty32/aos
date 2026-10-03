# 第三輪：示範、測試、已修項目回歸

2026-10-03。從 `proto7-1/README.md` 進入，沿 README 的 spec／play／problems 連結讀取。沒有執行 `demo/real.py`，所有 agent 均用 `fake`。沒有改產品程式。以下是主報告可引用的實跑證據。

## 基線

- `python3 proto7-1/demo/play.py --root /tmp/astra3-reg-demo`：exit 0，14／14 項 OK，4456 筆 audit 無越界，示範自查無殘留程序。[demo.txt](demo.txt)
- `TMPDIR=/tmp/astra3-reg-tests python3 -m unittest discover -s proto7-1/tests -v`：exit 0，60 項，10.888 秒，OK。[tests.txt](tests.txt)
- 前一輪示範 14 項、測試 46 項／10.361 秒；第一輪示範 10 項、測試 34 項／9.862 秒。不同輪負載不同，秒數只記錄、不推論效能退化。

## 舊腳本適配範圍

以下腳本均複製自舊證據，再改根目錄探索方式與暫存前綴為 `/tmp/astra3-reg-*`。輸出指向本資料夾，未覆寫舊證據。

- 第一輪 `controls/reproduce.py`、`controls/additional.py`：增加刪除實驗根；保留控制案例及原始快照。
- 第二輪 `requests/probe.py`、`requests/additional.py`、`delivery/reproduce.py`、`space.py`：只改路徑／前綴（space 放本輪 `space/` 子目錄）。
- 第二輪 `audit/reproduce.py`：除路徑／前綴，證據收集時遇到已被修法阻止建立的檔案，從直接 `read_text()` 改成記錄 `null`。原先故意不理回條、仍直接寫未核准 mnt 的 worker 保留，因此該 worker exit 1 是預期的探針結果，不是產品 tick 失敗。

## 回歸結果

| 舊項目 | 本輪結果 | 實跑差異與證據 |
|---|---|---|
| astra 第一輪二-1：task ctl 為 `[]` 使 tick 持續失敗，status 停舊回合 | **已修** | 回條 `ok:false / not a JSON object`，原控制檔已消費；0.6 秒後 n 已 round 5，status 也是 round 5／idle。雙 node 腳本在「before-repair」已是 n／healthy 都 round 6、rounds 1～6 齊全；不必修理便持續前進。[controls/events.json](controls/events.json)、[controls/additional-events.json](controls/additional-events.json)。60 項測試含 `TestTickFailure`，也驗證 tick 失敗時 status 的 `last_error`。 |
| astra 第二輪二-1：mount name 非空 list 遺失回條、拖垮 tick | **已修** | `name-list` 回 `ok:false / name 與 path 要是字串（name 可省）`，矩陣全部 tick exit 0；daemon 的 01-good／02-bad／03-later 同次審核，pulse-r1～r4 都有，healthy 也前進。[requests/results.json](requests/results.json)、[requests/additional-results.json](requests/additional-results.json) |
| astra 第二輪二-2：a/b 與 a_b 自動掛載名碰撞 | **已修** | 分別為 `a_b_inbox`、`a_b_inbox-a21f9e84`；兩個 inbox 各有對應信件，sender outbox 與 failed 均空。[requests/additional-results.json](requests/additional-results.json) 的 first／second-auto-name |
| astra 第二輪二-3：mount_allow 沿 symlink 批准越界 | **已修** | `allowed/inside → c` 與 `allowed/outside → 根外` 都拒絕；根外 `new-created-by-tick` 未建立、c 也沒有 via-approved-link。符合現行 M-13 的 realpath 政策。[audit/results.json](audit/results.json)、[audit/raw-files.json](audit/raw-files.json) 的兩份 mount-done |
| astra 第二輪二-4：audit dir_fd／掛載改指錯判 | **宣稱修的部分已修；已知 M-12 仍在** | mkdir、rename 的來源／目的、unlink 全記真實 b 路徑且 `ok:false`；mnt/box 改指 c 後 open 記 c/retarget.txt、`ok:false`。`os.open('dirfd.txt',dir_fd=b)` 仍誤記 a/dirfd.txt、`ok:true`，但已明列 M-12（hook 不提供 fd），不列新的未修 bug。[audit/raw-files.json](audit/raw-files.json) |
| astra 第二輪二-5：收件夾刪除／搬走使 sender 崩潰 | **已修** | deleted／moved 均保持同一 agent-r1，到 round 13 idle，沒有 exit.json 或 traceback；第二封在 `outbox/failed`，含 `failed.why` 與 `at`。符合 M-14「不自動重掛／重寄」。[delivery/deleted-after-change.json](delivery/deleted-after-change.json)、[delivery/moved-after-change.json](delivery/moved-after-change.json) |
| astra 第二輪二-7：移出已被 kernel 限速 pause 的成員不 resume | **已修** | ben 在 kernel round 26 被 pause 後即移出 members；kernel round 38（cool_rounds=12）寫 resume，理由明寫「已不在 members，自己下的 pause 自己收」。kernel round 51 時 ben 已 round 41，並非加回才恢復；加回後繼續到 round 55。[space/space-events.json](space/space-events.json)、[space/space-lab-files.json](space/space-lab-files.json) |

沒有發現上述已修 bug 的新反例；M-12 仍存在但不可重複當新問題。第二輪二-6 空殼收件地址與二-8 restart 未審請求是已知技術選型，舊 delivery／requests 腳本亦有覆蓋，沒有重新列為新發現。

## 清理

各腳本已停止自己的 daemon／task 並刪除實驗根。最終檢查 `/proc/*/environ` 無任何 `AOS7_ROOT=/tmp/astra3-reg-*` 或測試 TMPDIR 程序；demo／tests 暫存根刪除後 `/tmp/astra3-reg-*` 為空。當時 321 個證據檔，最大 64689 bytes，未超 200 KB。[cleanup.json](cleanup.json)
