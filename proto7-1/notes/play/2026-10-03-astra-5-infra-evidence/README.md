# astra-5 證據與重跑

主報告：[2026-10-03-astra-5-infra.md](../2026-10-03-astra-5-infra.md)。只用本機假任務與檔案探針，未跑 real.py／真 LLM；未改產品。實驗空間 `/tmp/astra5-*`，證據單檔嚴格小於200,000 bytes。

| 目錄 | 入口與結果 | 用途 |
|---|---|---|
| [tasks](tasks/fragment.md) | probe.py、stop_only.py、archive_probe.py；各案 JSON、cleanup.json | astra-4 任務全組回歸、stop-only 對照、Q3 讀取競態與撞號 |
| [crash](crash/fragment.md) | probe.py、sitecustomize.py、extended.py；各案 JSON | 七個舊崩潰案、九個相容／新窗口補驗 |
| [time](time/fragment.md) | probe.py、extra.py；各案 JSON、cleanup.json | 七個舊時間案、超大 interval 與 wake |
| [nested](nested/fragment.md) | reproduce.py、subroot.py、gone_mid_action.py；結果 JSON | 三層停機、路二成環、subroot 首掃、動作中途刪搬 |
| [controls](controls/fragment.md) | repro.py、results.json、cleanup.json | wake 洪水、resume/pause、max_live/batch、edit_json kill、wait-tock |
| [node](node/fragment.md) | repro.py、results.json | Q4 rename／I/O／原子替換／環境與採樣；原測試和 demo 異常清理 |
| [robustness](robustness/fragment.md) | probe.py、三份 JSON | 壞 name、ctl 回條目錄、加掛回條失敗 |
| [scale](scale/analysis.json) | scale_probe.py、analyze.py；summary、samples、timings 分片、daemon 原始輸出 | 10/50/100/200 三短任務與兩次200空任務，目標各15秒 |

## 命令

從 workspace 根執行。會覆寫本目錄同名證據，要保留本次結果請先複製。各小探針可獨立重跑；scale 必須等其他負載結束再序列跑。

```sh
python3 proto7-1/notes/play/2026-10-03-astra-5-infra-evidence/tasks/probe.py
python3 proto7-1/notes/play/2026-10-03-astra-5-infra-evidence/tasks/probe.py deletekeep tockdirpeer
python3 proto7-1/notes/play/2026-10-03-astra-5-infra-evidence/tasks/stop_only.py fork forksetsid
python3 proto7-1/notes/play/2026-10-03-astra-5-infra-evidence/tasks/archive_probe.py
python3 proto7-1/notes/play/2026-10-03-astra-5-infra-evidence/crash/probe.py
python3 proto7-1/notes/play/2026-10-03-astra-5-infra-evidence/crash/extended.py
python3 proto7-1/notes/play/2026-10-03-astra-5-infra-evidence/time/probe.py
python3 proto7-1/notes/play/2026-10-03-astra-5-infra-evidence/time/extra.py
python3 proto7-1/notes/play/2026-10-03-astra-5-infra-evidence/nested/reproduce.py
python3 proto7-1/notes/play/2026-10-03-astra-5-infra-evidence/nested/subroot.py
python3 proto7-1/notes/play/2026-10-03-astra-5-infra-evidence/nested/gone_mid_action.py
python3 proto7-1/notes/play/2026-10-03-astra-5-infra-evidence/controls/repro.py
python3 proto7-1/notes/play/2026-10-03-astra-5-infra-evidence/node/repro.py
python3 proto7-1/notes/play/2026-10-03-astra-5-infra-evidence/robustness/probe.py
python3 proto7-1/notes/play/2026-10-03-astra-5-infra-evidence/scale/scale_probe.py --repo "$PWD" --seconds 15 --counts 200 --tasks 0 --tag=-empty
python3 proto7-1/notes/play/2026-10-03-astra-5-infra-evidence/scale/scale_probe.py --repo "$PWD" --seconds 15 --counts 10 50 100 200
python3 proto7-1/notes/play/2026-10-03-astra-5-infra-evidence/scale/scale_probe.py --repo "$PWD" --seconds 15 --counts 200 --tasks 0 --tag=-empty-repeat
python3 proto7-1/notes/play/2026-10-03-astra-5-infra-evidence/scale/analyze.py
python3 proto7-1/notes/play/2026-10-03-astra-5-infra-evidence/verify.py
```

## 和 astra-4 腳本的必要差異

- tasks/probe.py、nested/reproduce.py、crash/probe.py 保留原實驗流程，換本輪 output 位置／tmp 前綴。stop_only 是去掉原先 task kill 的對照，避免把已知工作項修復混同 stop 自己能清。
- time/probe.py、scale/scale_probe.py 的 run_prog 計時 wrapper 改接受與轉交 `*args, **kwargs`，否則新版的 extra_env／gen／timeout／abort 會令舊 wrapper TypeError，量不到產品。time 的原 stall 注入分支直接 Popen，只能驗遲到，不能用來驗新世代／timeout。
- crash 舊流程期待 daemon 被 OSError 打死、或新動作能越過停住的舊動作；新版行為改變後原 harness 等不到條件，結果保留 `probe_error`，**不是未說明的產品失敗**。extended 分別驗恢復／鎖持有與等待。runner 改 fd-relative replace，原 `/exit.json` hook 不命中；補驗改匹配 `exit.json`。
- sitecustomize 新增 flock 與 aos7_fs.append_jsonl 的精準停點；只在明確設定 A4_FAULT 的自有測試程序載入。after-append 是完整行已落檔的中斷點，沒有聲稱測過斷電或所有 JSONL 半行寫入情況。
- scale 新增 start_mono／first_status_s 保存。本輪第一次 empty 已開始執行才加欄位，該案分析以首 OS sample 當起點，首 status 為略低估、視窗截點為近似；其餘是精確啟動前 monotonic。新 analyze 按 S-08 算 tick 完成間隔；原 actual_interval_ms 欄仍是起點差。
- N-24 補驗用 os.replace／append 寫前 barrier 固定合法交錯，並非觀察到自然頻率。Q3 讀競態同理，只停在讀檔前，真正搬移由獨立原版 tock 執行。

## 證據限制與清理

不是真實長期耐久／NFS／磁碟填滿／斷電測試。時間線規模是共用宿主的短窗，不能把本輪任何一個每秒回合數當固定容量。status 初次出現也不代表 node 全部發現；空任務結果有截尾，不能用較低回合間隔說它比有任務更健康。

各 harness 只清自己的程序。subreaper 是實驗控制器的清理工具，不是產品功能；先保存產品 stop 後仍活的結果，再補 kill／wait，不混淆兩者。node 的孤兒測試只重現原測試及 demo 的失敗路徑，沒有處理或追溯使用者事先找到的兩個程序。

來源檔版本：[source-manifest.json](source-manifest.json)。最終核對：[final-check.json](final-check.json)，涵蓋 `/tmp/astra5-*`、可讀 `/proc` 的 cmdline／AOS7_ROOT／AOS7_TASK、證據大小與 JSON、報告連結、產品雜湊不變；各組 cleanup 另驗自己持有的子程序已回收。重新執行 verify 只改 final-check.json。
