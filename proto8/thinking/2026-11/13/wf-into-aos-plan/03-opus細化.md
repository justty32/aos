# 03 opus 細化：fable 的待驗逐條驗掉、跟 fable 不同的七處、目標形狀落到實際檔名、十四條邊緣狀況

← [回入口](../wf-into-aos-plan.md)｜上一份：[02-fable規劃](02-fable規劃.md)｜下一份：[04-施工分段與驗收](04-施工分段與驗收.md)

查法：隊長唯讀查檔與 git（11-13 晚 21:00 前後，家機，main `50fac6347`）；沒跑會寫檔的腳本、沒起 aos 行程、沒碰活樹。compact 那兩項要在 `repo-aos` 畫面上實際 compact 才驗得到，留給段 0。

## 一、fable 的待驗：結果

| # | 待驗 | 結果 | 出處 |
|---|---|---|---|
| 1 | 通用版節點有沒有「引用別的節點、只寫差異」的欄位 | **沒有**。`nodes.json#/workflow_form` 只定固定鍵（`_description`／`when`／`not_when`／`done_when`／`steps`／`handoff`），其餘鍵自取。`$ref` 是「整段換成別處那段」，不能疊加。docs/01 允許加任何額外鍵 | `proto8/knowledge/wf/nodes.json`、`proto8/knowledge/docs/01-樹長怎樣與多庫.md` 第 23、25 行 |
| 2 | `_index.json` 能不能指向 `wf/` 外的節點 | 一格的 `index` 只能指**另一份 index**（`_index.json` 或檔內 `_index`），不能直接指節點；絕對路徑照用，相對路徑從那份 index 所在的夾算 | 同上第 23 行 |
| 3 | 路徑怎麼寫才在 repo、活樹、兩台都解得開 | `repo-aos` 的工作區就是 repo，所以寫 repo 根相對路徑 `proto8/knowledge/wf/…` 就讀到 repo 那份（比活樹複本新）。活樹的 `~/aos-home/knowledge` 是抄本、會落後（家機的抄本現在就少了 `skeletons/`、`source/`）。repo 的 `wf/` 本來就只給在 repo 做事的讀，不必在活樹解得開 | `ls ~/aos-home/knowledge/wf` 對 `ls proto8/knowledge/wf` |
| 4 | CLAIMS 有沒有人用 | **有**：現役一列（併入線）、一個月 4 次 commit、11-13 16:38 剛改。**不進丟棄候選** | `wf/workflows/dispatch/CLAIMS.md` |
| 5 | inbox 的 arcagi、aos 是誰 | arcagi＝另一個專案 `~/repo/arcagi`（`reply-to: /home/lorkhan/repo/arcagi/wf/inbox/`），樹外；aos＝本 repo 的各線。**`wf/inbox` 還在服務樹外的專案**，不能整個丟 | `wf/inbox/done/*arcagi*` |
| 6 | `index_gen_desc.json`（168K）是什麼 | 取不到檔頭一句話的檔（圖、紀錄、沒 README 的夾）的手寫一句話；md 轉 json 後節點的 `_description` 標題就能當一句話，這份會慢慢縮 | 檔頭 `description` |
| 7 | `json_text*` 是不是人讀 json 的輔助 | **部分是**：它是 git textconv，把 json 展開成逐行文字，讓 `git diff`／`git log -p` 看得懂；不是「印成人讀的頁」 | sonnet 4；`wf/tools/json_text.py` 檔頭 |
| 8 | 還有沒有檔靠 `wf-table/1`（tabledb） | **有**，不在 archive 的至少 10 份：`proto8/docs/CONCEPTS/abbr.json`、`proto8/knowledge/wf/source.json`、各日 thinking 的 `decide_*.json`、`two-machines/*.json`… → tabledb 現在不能丟 | `git ls-files … | xargs grep -l wf-table/1` |
| 9 | `index_check.py` 是不是對 md 硬擋 8K | **不是**（檔裡沒有 8192／oversize）；「SESSION-LOG ≤ 4096」也不是它的規則，是模板 repo 檢查器的、沒帶進來（`proto8/knowledge/wf/source.json` 的 `not_carried`）。fable「現況就違規」那條**不成立** | `grep` index_check.py |
| 10 | AGENTS.md 有沒有已經寫使用者偏好 | 只有「不寫自動記憶」與鐵律 2 的授權；語言、只有 main、先結論大白話、調度者不親做**都不在** AGENTS.md | `AGENTS.md` |
| 11 | 久沒用的工作流最後一次真的用 | git 的最後 commit 全是 11-13 的鋪 index、整理 commit，不能當「用過」。看最後一次**新增內容**：digest 11-01（一週總結）、hackathon／workshop 11-03 整批封存（真的場次在 8～9 月）、experiments 09-25 | `git log --diff-filter=A` |
| 12 | 通用版 `code-map-rules.json` 期待 code map 在哪 | 專案自己的在工作區 `wf/knowledge/code-map.json`（骨架 `wf/skeletons/code-map.json`）；它講的是領域表，不是逐檔生成表 | `proto8/knowledge/wf/knowledge/code-map-rules.json` |
| 13 | 工具裡寫死 `wf/workflows/…` 的地方 | 只有兩支：`compact_reload.sh`（`common/user.md`）、`codemap_gen.py`（`common/code-map/proto8/`）。fable 說的「refactor 被引用 33 處」是 md 裡的文字提及，不是寫死 | `grep` wf/tools |
| 14 | 舊 md 被多少檔連進來（轉 json 會斷） | decisions 3、planning 2、investigation 3、feature-dev 6、team-model 6、dev-env 12、inbox/README 12、testing 26、common/user 26、common/conventions 34（不含 archive） | `git grep -l` |
| 15 | compact 後 `compact_reload.sh` 在 eca 身裡跑不跑、AGENTS.md 會不會重帶 | **沒驗**（要在畫面上真的 compact）→ 段 0 | — |

## 二、跟 fable 不同的地方（七處）

1. **SESSION-LOG 沒有 4096 硬線**（見待驗 9）。段 2 改成只做 HANDOFF；SESSION-LOG 長條目要不要瘦，改成要使用者裁的題（Q5），不寫數字。
2. **「base＋local」用一個額外鍵實作，不改通用版格式**。本地節點寫 `"base": "proto8/knowledge/wf/workflows/decisions.json"`（字串，repo 根相對）＋ `"local": [...]`（只寫不一樣的幾條），`_description` 第一句講「先讀 base，再照 local 改」。docs/01 允許額外鍵，不用動 `nodes.json`。
3. **`wf/_index.json` 不在段 3 建，留到段 9**。理由：`wf/` 直接的東西不到 15 個，index_gen 不會生成；手寫要加進 `index_gen.json` 的 `hand_indexes`。過渡期 `WORKFLOWS.md` 是唯一的派發表（換過的那列指向 json），一個入口就夠，不必兩個入口並存。`wf/workflows/_index.json` 現在是 index_gen 生成的，json 節點的一句話它會自己從 `_description` 標題取，不用手寫。
4. **always-on 推薦改走 CLI 的 SessionStart hook，不搬偏好進 AGENTS.md**（Q3 給兩案）。AGENTS.md 自己寫「durable 細節一律不寫這裡」、user.md 開頭寫「always-on 鐵律在 AGENTS.md，這裡是這位使用者的偏好」——把偏好搬進 AGENTS.md 是改分層原則。把 `.claude/settings.json` 的 matcher 從 `compact` 改成 `startup|resume|compact`、腳本開場只印 `user.md` 入口（5.9K 那張表，不印分檔），一樣「每個 session 都有」，規矩還是只有一份。缺點：只有 claude 身吃得到（codex 身不讀 `.claude/`；這個 repo 現在沒有 codex 身的常駐 agent）；要先過段 0 確認 hook 在 eca 身裡真的跑。跑不了就退回 fable 的做法。
5. **tabledb 不丟、鐵律 6 先不改**（待驗 8：還有 10 份以上活檔是 `wf-table/1`）。段 9 再看。
6. **`fix_moved_links*` 不是一次性的，搬遷期間要留著**：每轉一個工作流，舊 md 被別處連進來（待驗 14），要用它把連結改指新的 json。搬完再進丟棄候選。
7. **aos-teams 不進知識庫 `aos/`（Q9 推薦留 repo）**：01～07 大半是使用者這個人的派工偏好（模型分級、gpt 走 agent-fsm、家機端點、原話），屬「這個 repo／這位使用者」那層；main-session-in-aos 定的是「不把 wf 規矩寫進共用知識庫」。真正「怎麼用 aos 開隊」的通用條目（subagent、agent-fsm 怎麼派）有就該寫進 `aos/` 的對應節點，那是另一條線的事。

## 三、目標形狀落到檔名（搬完那天）

```
AGENTS.md                         薄路由＋鐵律（輪廓照 02 第 5 節；偏好看 Q3）
CLAUDE.md                         不變
.claude/settings.json             SessionStart（看 Q3：startup|resume|compact 或只 compact）
wf/
  _index.json                     手寫（段 9 才建；進 index_gen.json 的 hand_indexes）
  workflows/
    _index.json                   index_gen 生成（派發表；description 取各節點 _description 標題）
    decisions.json planning.json investigation.json feature-dev.json testing.json tidy.json refactor.json
                                  base＋local 薄節點
    digest.json experiments.json hackathon.json workshop.json decide-page.json inbox.json dispatch.json
                                  通用版沒有的，全文（用到才轉；久沒用的段 9 問去留）
    <名>/archive/ <名>/reports/   原地凍結的 md
  knowledge/
    user.json conventions.json gotchas.json dev-env.json data-files.json team-model.json claims.json
    code-map/                     看 Q：搬或留在 workflows/common/code-map（鐵律 3 與 codemap_gen 同 commit 改）
  SESSION-LOG.md HANDOFF.md WAIT_USER.md wait-user/   活狀態，md（W11）
  inbox/                          樹外專案（arcagi 等）來信
  session_logs/                   照舊
  tools/                          codemap_gen、index_gen(+json)、index_check、check_anchors、json_text、tabledb、compact_reload；
                                  fix_moved_links 搬完再議；progress_board、decide_page 凍結
```

退場：`wf/WORKFLOWS.md`＋`WORKFLOWS-parts/`、`wf/INDEX.md`＋`INDEX/`、`wf/STRUCTURE.md`（組織原則改由通用版 `layers.json`／`nodes.json`／`tidying.json` 當唯一出處）、`TEMPLATE.workflow.md`、`resources.md`、`salvage/`、inbox 腳本整組——每一個都要使用者看過清單點頭才刪（鐵律 2）。

## 四、邊緣狀況（十四條）

1. **兩條線同時動 hub 檔**：CLAIMS 把 `AGENTS.md`、`WORKFLOWS`、`INDEX`、`SESSION-LOG`、`WAIT_USER` 保留給調度者。施工段碰到這些時由頂層自己做，或頂層在任務書裡明說放行，並在 CLAIMS 登一列。
2. **兩台機器同時開工**：公司 WSL 與家機都有 `repo-aos`。搬遷 commit 沒 push 到另一台前，另一台照舊讀 md；只要每段「舊 md 同 commit 刪」，pull 下來就是一致的，不會一台 md 一台 json 各改一份——前提是**另一台在那段期間不改同一個工作流的檔**。
3. **連進來的錨點斷掉**：md 錨點（`user.md#push-授權` 這種）轉 json 後變 `user.json#/push`。`check_anchors.py` 只查 md 錨點，**不查 json 的 `#/鍵`**（index_check 也不查內容引用，使用者 11-13 裁「都按照推薦」）。每段要多一步 `git grep` 舊路徑＝0。
4. **thinking 舊檔裡的連結**：歷史討論紀錄連到舊 md 的，改不改？`fix_moved_links` 會一起改；歷史紀錄被改連結算不算「改原文」——連結不是原話，改；文字不動。
5. **compact 後 hook 在 eca 身裡不跑**（段 0 驗）：那 HANDOFF 讀回這條路本來就是壞的，現在就壞著；Q3 的 B 案也跑不了，退 A 案。
6. **hook 開場印 5.9K 吃 context**：每個新 session 多 5.9K；子 agent 不吃 SessionStart（只有開 session 的那隻吃），影響只在頂層。
7. **base 節點變了**：通用版 `decisions.json` 改了步驟，本地 `local` 那幾條可能對不上。辦法：本地節點寫明 base 的來源 commit 不做（太重）；改通用版的人順手 `git grep '"base": "proto8/knowledge/wf/workflows/decisions.json"'` 看誰在用。
8. **活樹抄本落後**：樹裡別的 agent（`eca_main`）讀的是 `~/aos-home/knowledge/wf`，可能比 repo 舊。repo 的 `wf/` 節點寫的 base 指 repo 那份，`repo-aos` 讀得到新的；別的 agent 不讀 repo 的 `wf/`，不受影響。
9. **index_gen 對 json 節點取一句話**：取 `_description` 的標題；`_description` 寫成字串陣列也認。節點沒寫 `_description` → `DescMissing` 退 1，commit 前就會被抓到。
10. **新紀錄寫進凍結的 archive 夾**：reports、session_logs 照舊寫 md；跟 json 節點同夾並存是預期，不是違規（Q1）。
11. **WAIT_USER 切換期看兩處**：照 user-zone-plan；切之前 wf 這邊不動，不做雙寫。
12. **派出去的 agent 讀規矩的清單寫死 md 檔名**：user.md「子 agent 模型」那格寫「AGENTS.md、WORKFLOWS.md、common/user.md、common/conventions.md 等」——每轉一個就要改這句（段 5 轉 user.md 時一起改）。
13. **刪 inbox 腳本後樹外專案還在寄**：arcagi 用的是它自己 repo 的腳本寄到我們的 `wf/inbox/`，我們這邊只要 `ls wf/inbox/*.md` 收；但我們回信給 arcagi 要寫進它的 inbox，`inbox_send.sh` 的原子投遞（暫存檔再 mv）手寫容易漏。刪前要使用者裁。
14. **使用者自己讀 json**：第一個節點（decisions）轉完就請他看一次；說不好讀才做輔助（D1）。
