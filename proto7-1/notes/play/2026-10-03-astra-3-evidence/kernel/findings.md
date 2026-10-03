# 第三輪 kernel 邊界證據

入口：先讀 `proto7-1/README.md`，沿入口讀核心／原型 spec、兩輪報告及 problems 系列。沒有執行 `demo/real.py`、沒有任何 LLM 呼叫、未改產品碼。四組整合實驗都開真正 daemon／tick／tock／kernel；成員 usage 是手寫的已結束任務用量，隔離規則本身。`repro.py` 可從任意 cwd 直接執行，按檔案位置找 proto7-1；實驗只用 `/tmp/astra3-kernel-*`，finally 終止 daemon、回收任務並清目錄。

## 新 bug 1：移出後到期 resume 漏清 acc，加回便對同一筆用量重複 pause

- 分類：〔bug〕；S-17、S-18。屬 astra-2 二-7「已修」的後半段不完整，不是重報原先永遠不 resume。
- 重現：`kernel.json={"members":["a"],"budget_tokens":10,"cool_rounds":5}`；先讓 a 的 tokens=0 成基準，寫成20，等 budget pause；members 改 `[]`，等5個 kernel 回合自動 resume；tokens 仍20，members 加回 `["a"]`。再移出、等待、加回一次。
- 實際：r3 pause、r8 resume、r9 pause、r14 resume、r15 pause。同一筆20 tokens、沒有任何新增呼叫，總共 pause 三次。每次移出分支 resume 後 `usage["team/a"]={"last":20,"acc":20}` 未歸零。一般成員 resume 分支會 `acc=0`，移出分支漏做。
- 證據：`removed-readd.json`（真 daemon）、`pure-rules.json`（純規則 r2/r4/r5/r7/r8 同一問題），`repro.py` 的 `readd_case/rules_case`。

## 新 bug 2：成員搬走形成斷鏈，新 roster 寫入使整個 kernel 退出

- 分類：〔bug〕；S-01、S-16、S-18、S-23。
- 重現：kernel 管 a、b，正常掛兩人的 `.aos`、各寫 roster；a 用量120、`cap_tokens=100`，等 a 被 pause；把整個 `team/a` 搬成 `team/moved-a`，kernel.json 暫時維持原樣。下一輪仍要更新 a 的名冊。
- 實際：r4 `write_rosters → fs.write_json → os.makedirs(mnt/a)` 丟 `FileExistsError`，`kernel-r1` code1 結束；因名冊寫入在 snapshot／run_rules 之前，a 的斷鏈連帶中止管理所有成員。r5 keep 起 `kernel-r5` 接手，舊路徑建出空 `.aos`，r5 對原 id 發 cap resume，理由竟為「總額上限改了（用量0，上限100）」；但 kernel.json 未改，120 tokens 在 moved-a。r6 roster 仍列原 team/a，而 daemon nodes 只有 team、team/b、team/moved-a。
- 新問題主體是**名冊寫失敗導致整個 kernel 崩潰**。M-2（重起掛載建空殼）、P-15（搬名等於新 id）、M-15（名冊為設定投影）是既有行為，只作影響鏈證據，不另報。cap 的 misleading why 同樣不另外拆條。
- 證據：`roster-broken-mount.json` 保存 traceback、exit code、前後 state／decisions／daemon status／roster，`repro.py:roster_case`。

## 通過與已知邊界覆核

- **astra-2 二-7 原重現通過**：移出 members 的限速 pause 確實到期 resume；不足處為上面的加回 bug。
- **cap 與限速交錯通過**：budget10/cool8/cap100；0→20 在r3限速 pause；pause 期間手寫120模擬在飛呼叫完成，r4升級cap pause；到r14仍停（原冷卻早過）；提高cap至200，r15 resume，acc歸零。見 `cap-budget.json`。
- **cap 移出／加回符合已知 R-4**：純規則r1 cap pause；r2移出，r3 cap提高但仍不在members，均不resume；r4加回才resume。見 `pure-cap-removed-known.json`。不當新問題。
- **名冊列到 mount_allow 拒絕成員，符合 M-15 的設定投影**：讓 kernel 只准 `.aosd` 與 `team/a/.aos`，members仍a,b。b的加掛回條 `ok:false`，birth只掛daemon與a；a名冊仍有b。見 `roster-denied-known.json`。不當新問題。
- 四次 daemon 均正常 stop（exit0）；`cleanup.json` 顯示記錄群組沒有活程序、沒有 `/tmp/astra3-kernel-*` 殘留、單檔都小於200KB。
