← [續推計畫](plan-2026-10-09-next.md)｜[代定清單](decisions-2026-10-09.md)｜細項 [blueprint-wfnode-items.json](blueprint-wfnode-items.json)

# W0：讓 aos 上的 AI 用 wf 記事、照流程做事

## 1. 一句話＋ELI5 圖

AI 的工作簿放在 node；aos 叫它翻書、做事、記帳、寫回進度。

```text
                    [tick 心跳]
                         |
                         v
[node 上的 wf 樹] --> [組 prompt] --> [llmcall 呼叫]
       ^                                   |
       |                                   v
       +-- [events：必讀＝必達信] <-- [budget 帳／metrics 量測]
       |
       +-- 回寫 SESSION-LOG：更新未完項，完成就移除
```

共 6 框。wf 是工作簿，prompt 是這次帶給 AI 的幾頁。
呼叫前先留預算，回來再結帳；圖是資料流，量測只讀證據。
必達信要落盤、回終局才確認；滿了或結果不明，寄件者留證據再接續。

## 2. 在 aos 上實現 workflows 是什麼意思

`wf/` 是 workflows 在本 repo 的實例；aos 上的 AI 也用它當工作記憶與流程骨架，只讀需要的下一層。

workflows 沒引擎，aos 補引擎：tick＝heartbeat、events must＝必達信、學徒 job＝交接書；新能力進模組，不進核心。

記憶是 node 上的檔，不是模型視窗；R-13 曾被單一對象洗滿視窗，進度與成果要另存檔。

P1 按需組裝；C2 借 proto2 summarize_old／replace_old 整理，大輸出借 ref／bigmem 折疊。

## 3. 對照表摘要

落點、量法見 JSON。

| 概念 | aos 機制 | 隊 |
|---|---|---|
| AGENTS 路由 | prompt 組裝入口 | P1 |
| SESSION-LOG／WAIT_USER | node 活狀態檔、check | W1 |
| inbox「五狀態」 | mail＋events must；實為六 STATUS | X1 |
| heartbeat／routines／schedule | tick 驅動 routines | H1 |
| dispatch 交接書 | 學徒 job | A4／A5 |
| tidy | compact 任務 | C2 |
| skills/ | skills 模組 | S1 |
| wf-lint | 三關的第一關 | A4 |
| 記憶／bigmem | ref:// 折疊 | P1 |
| 效率四指標 | metrics 唯讀復算 | E1 |

## 4. 向 agentctl 借什麼

- B1 ROSTER：身份、上游、領地、能力邊界；W1 建，X1 聲明。
- B2 line-claims：一地一寫者、只加自己那格；W1 建，X1 管，A4 核。
- B3 BRIEF：唯一目標、排除範圍、固定驗收、REPORT 檔；A4 出單，A5 交件。
- B4 tool-index：任務→必用工具，抄入 BRIEF；S1 索引，A4 接單。
- B5 handoffs：STATE＋NEXT-SESSION 續行點；W1 建，A5 交接。
- B6 inbox：五通道、members 首行領導、每步 poll；X1 接模板路由。
- B7 compact：任務告一段落且下一段性質差很多，不只看 context 大小；C2 做。

不借 Skyrim 遊戲、部署、鍵鼠鎖與 tmux 編制；不搬歷史流水帳當 open 進度。

## 5. 凍結項

W0 親定、即日生效；各隊遵守，僅頂層可改（衝突回報頂層）。

- F1 node 骨架用 `wf-init.sh --target <node> --flavor dev,heartbeat,multi-agent --non-invasive wf` 產，沿模板檔名，不自創入口。
- F2 根只留 AGENTS.md／CLAUDE.md／.claude/；其餘照模板收進 wf/。
- F3 prompt.json 格式只由 P1 定；沿 `$opt > $ref > $fmt > $env`，不改 lib。
- F4 信名 `<YYYYmmddTHHMM>-<寄件者>-<STATUS>.md`，STATUS 照 PROTOCOL 六種，同名拒覆蓋。
- F5 終局＝DONE／BLOCKED／NEEDS-USER／FAILED；讀信不算 ack，終局落盤才算。
- F6 routines／schedule 機器表走 wf-table/1（H1 定欄）；模板 md 留導航。
- F7 SESSION-LOG／WAIT_USER 只留 open，完成即刪。
- F8 大輸出只用 ref:// 折疊，先存原文再換，展開可逆。
- F9 skill 索引只有 name＋description。
- F10 學徒只發布 apprentice/<job>，人／頂層 merge；真 AI 一律走 llmcall。

正本：`~/repo/workflows/flavors/multi-agent/workflows/inbox/PROTOCOL.md`；agentctl 的五 STATUS 沒有 REQUEST。

## 6. 驗收燈號細則

尚未實跑。綠＝證據齊且達標；紅＝已跑且違反；黃＝未跑、缺證據或待代定。各隊量、R2 核；U 量人類面、E1 量效率。細則見 JSON。

repo 根跑 `systemd-run --user --scope python3 proto7-2/tests/run_all.py <包>/tests`；新測試各隊建，I4 全套 ×3，同時 ≤3 份。

| 目標 | 系統面 | 人類面 | 誰量 |
|---|---|---|---|
| 1 wf 當腦 | L1-1 init lint 0、L1-2 只留 open、L1-3 routines 29～31 次、L1-4 未終局 REQUEST audit、L1-5 prompt 曲線平 | L1-6 ELI5 ≤9 框、L1-7 ≤10 分鐘上手 | W1／H1／X1／P1；U |
| 2 compact／記憶／skill | L2-1 $ref 組裝、L2-2 折疊可逆、L2-3 open 20 仍 20＋降 ≥60%、L2-4 被殺 ×3 不丟、L2-5 skill 10 對 8、L2-6 SIGKILL 接回 | L2-7 三包 ≤3 指令、≤5 概念、分數 ≥7 | P1／C2／S1／R2；U |
| 3 學徒寫包 | L3-1 工具包、L3-2 模組包過三關並 merge、L3-3 7 壞全擋、L3-4 題 2 重問或 token 降、L3-6 復跑 | L3-5 BRIEF 新人 4／4、L3-7 學徒首跑 ≤10 分 | A4／A5／R2；U |
| 效率 | LE-1 token、LE-2 並行、LE-3 時間、LE-4 重試、LE-5 可重跑、LE-7 優化只排序 | LE-6 一指令一行 | E1／P；U |

## 7. 不做

不改 `~/repo/workflows/` 或 `proto7-2/lib/`；不碰 R1 的 `aos7_author*.py`、`aos7_llmcall*.py`、`play/real-ai`。W0 只寫本檔與 json，不寫程式。

## 8. 待頂層確認／代定

| 題 | 預設建議 |
|---|---|
| D1 模板與計畫落點 | 模板 wf/workflows/inbox/ROSTER.md 為正本，新 wf/ROSTER.md 只導航；skill 照模板 wf/skills/，根 skills/ 只作入口；handoffs／line-claims 是新擴充。 |
| D2 mail／author 搶 must | 先分 node，各自獨佔 must，以既有 send 轉交留回條；不改 R1，接法未核不算整圈綠。 |
| D3 Markdown 接 $ref | P1 宿主先讀成 JSON 字串；lib 只讀 JSON，append／clear 也交 P1，不改核心。 |
| D4 7 壞與 6 壞衝突 | A4 補「模組缺 spec／契約卡」壞例，成為 7 壞＋1 合法，共 8 份。 |
| D5 曲線與易用性口徑 | 固定負載，首末各 30 回合均值差 ≤5%；指令算公開操作，概念算需背名詞，mail 也不豁免。 |
| D6 compact 段落判準 | 保留大小或段落切換；後者須有結段＋下一段性質改變證據，SESSION-LOG 空了不夠。 |

