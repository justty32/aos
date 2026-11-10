← [入口](README.md)｜涵蓋：11-10 傍晚兩支 ctl（aos-daemon-ctl、aos-agent ctl）已裁項的施工結果與續行｜依據 [08 改法與施工順序](08-改法與施工順序.md)

# 兩支 ctl 的施工結果（11-10 傍晚，two-machines 隊長）

| 項 | 結果 | commit | 怎麼驗 |
|---|---|---|---|
| Q4＝A 已停再停算成功 | 做了：`stop` 對 stopped、`sleep` 對 sleeping、`start`／`wake` 對 running＝stdout `名字: already 狀態`、退 0、不寄信；兩支同一套（`daemon_ctl.Already`） | `1d3ece5e5` | `cmd/aos-daemon-ctl/tests/test_already.py`；`impls/aos-daemon/tests/test_ctl.py`、`test_lifecycle.py` 原本斷言「已停再停＝PhaseBad」的兩處照新裁定改 |
| 甲5 撞名／rm 不存在＝報錯不寄 | 做了：add 撞名＝`InstanceExists`、rm 不在表上＝`ProcMissing`，都不寄 | `624355ee5` | `cmd/aos-daemon-ctl/tests/test_add_rm_checks.py` |
| 甲4 shutdown 成功說一句話 | 做了：`daemon at D stopped (ctl seq N); M procs asleep, …` | 同上 | /tmp 實跑 daemon-root 起停 |
| 甲3 ls 說 daemon 活著沒 | 做了：表後先一行 `# daemon: running (pid N)`／`# daemon: not running (…)`；`--json` 加 `running` | 見 git log「甲3」 | /tmp 實跑起停後 ls |
| Q5 | 已裁不修（使用者「喔沒關係，root這東西本來使用者就要多注意一點。」）：文件提醒起根前 `unset AOS_DAEMON` | 見 git log「Q5」 | — |
| 甲6、Q3、Q1、Q6 | 沒做（今天時間不夠） | — | — |

`templates/daemon-root/README.md` 的 copy-out 用法改成 `copy-out --template …`、`AOS_PROTO8` 改 `AOS_HOME`（跟另一隊的 Q7、改名對齊）。

另：施工途中跑 `impls/aos-daemon/tests/test_lifecycle.py` 抓到 two-machines B01 那次（`7c1791e6e`）把 `aos-daemon-ctl add` 打壞（`written=` 塞進 `o.get(...)` 的括號、每次 TypeError），`c2a6aa976` 修好、已 push。

## 續行（明天）

2. 甲6（`aos-agent ctl add` 對停掉的 daemon 先查、不乾等 30 秒）。
3. （Q5 已裁不修，移出待辦）
4. Q3（`aos-agent ctl rm` 預設留 stack、`--purge` 才刪）：lv6 `lib/agent/agents/_entry` 收回子 agent 時若要刪 stack，那一行要加 `--purge`（另一隊的檔，交頂層轉）。
5. Q1（旗標子命令前後都收、位置名字也收）、Q6（help 第一屏三對停與起對照表）。
