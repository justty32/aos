# fix-r5：r4 試玩清單 #1–#8（proto4-3、proto4-5、proto4-6 都會碰，一個人做）

清單在 `proto4/notes/play/README.md` 的 r4 表；兩份報告 `2026-09-13-r4-opus.md`、`2026-09-13-r4-gptsol.md` 可以看，其他 `proto4/notes/` 不用讀。

## 規矩

- 你在 repo `/home/lorkhan/repo/simple_tools/aos`。先讀 `AGENTS.md` 開頭三軸與 `wf/workflows/dev-env.md`，再讀要改的 README 與原始碼。
- 先跑 baseline 記數字：`proto4-3`（`cd proto4-3 && python -m unittest discover -s test`，236）、`proto4-5`（同法，56）、`proto4-6`（同法，77）、`proto4-4`（`cd proto4-4 && for t in aos step cpu; do janet test/$t.janet; done`，42／45／12；`janet` 在 `~/.local/bin`）。做完全部重跑，只能變多不能變少。
- **不要碰 `playground/`**（Fable 正在寫）。其他資料夾可以改。
- 程式碼與 README 單檔不超過 300 行（`aos_run.py` 300、`aos_inst.py` 296、`llm_cpu_home.py` 289、`aos_daemon.py` 281 都在邊上，能不碰就不碰；一定要碰就先把一塊完整功能搬到新檔）。
- 每個行為變更都要有測試；文件大白話、繁體中文。
- LLM 真打只准本機 LM Studio（`http://localhost:1234/v1`，`google/gemma-4-e4b`）；**不碰 DeepSeek、不讀任何 `*_API_KEY`**。
- **不 commit、不 push、不開 agent。** 最後 markdown 回報：改了哪些檔、每條怎麼做、四邊測試數字、沒做的說清楚。

## 要做的

1. **proto4-5 README quickstart**（#1、#5、#7）：module 那節的指令區塊補 `setsid -f aos-daemon`（或指到 proto4-3 README 的「五分鐘開機」）與 `aos-kernel-boot K` 兩行，照真實順序：開 daemon → init 帶 `--module` → boot → 等一回合 → 改 endpoints → 丟單。全篇指令改成跟 proto4-3 一樣的 PATH 慣例（開頭一句「以下假設 proto4-3 與 proto4-5 都在 PATH」，指令寫 `aos-llm`、`aos-kernel`，不寫 `./`）。補兩句：「kernel 沒活著時，不管有沒有 `--wait`，單子都會撤掉不排隊」、「`aos-kernel ls` 看的是上一回合的帳，最多落後一回合」。
2. **proto4-6 README Python 節**（#2）：放一份完整可抄的三格範例，開頭就有 `K = "/abs/K"`（註明它只是普通變數，你自己填 kernel 的家）；寫清楚 `aos.llm_submit(K, req, name) -> 結果檔的絕對路徑`、`aos.wait_for(path)` 要 `return` 出去；「`aos.llm` 同步、用自己的 endpoint 檔、不經 kernel；`aos.llm_submit` 丟給 kernel 排隊、結果在 `K/llm/results/<name>.json`」這句 Python 節也要有（現在只在 Lua 節）；明講 `<PROG 去掉副檔名>.state.json` 是公開介面、可以直接讀。
3. **endpoints.json 排版與提醒**（#3）：`llm_cpu_home` 生 `K/llm/endpoints.json` 時 `indent=2`；`aos-kernel-init … --module` 結束時畫面上直接印「第一回合會生 `K/llm/endpoints.json`，把 local 的 model 換成 `aos-llm models` 看到的 id」（init 不知道 module 是不是 llm，就對每個 module 檔名含 `llm` 的印，或更簡單：module 提供 `init_hint()` 字串、init 有就印，你選簡單穩的）；module 的 `status()` 在任一 endpoint 的 model 還是 `loaded-model-id` 時，`llm:` 那行尾巴加「⚠ local 的 model 還沒換」。
4. **撞名訊息＋查單／清單指令**（#4）：`id 已經存在於 results：X` 後面補「要重問就 `aos-kernel llm rm K X` 或換名字」。加兩個子命令：`aos-kernel llm ls K` 列 queued／running／done 三段，每筆一行：名字、endpoint、送出時間、（done 的）結果檔路徑與 ok／error.kind；`aos-kernel llm rm K NAME` 刪掉那個名字的 request／running／result（running 中的先砍 worker 再刪，砍不掉就說），刪了印一行，沒這個名字退 1。這兩個是直接讀 `K/llm/`，不走 syscall（daemon 沒活也能用）。README 補上。注意現在的 CLI 是 `aos-kernel llm [K] REQ.json …`，加子命令時第一個參數是 `ls`／`rm` 就走新路，別把叫 `ls.json` 的請求檔弄壞。
5. **`--reset` 一併刪 `<PROG>.error`**（#6）：三支 proto4-6 執行器與 proto4-4 的 `aos-step`（它的錯誤在 `.aos-step/error`，reset 現在會不會清？不會就一起清）。
6. **`LAST_EXIT` 換人時清掉**（#8）：kernel 把新行程換上 cpu 時，該 cpu 的 `last_exit`／`last_kind` 清成沒有，`ls` 在 RUNS=0 時印 `-`。測試：一個行程退 100 被收走、下一個排上來，`ls` 那格不是 100。

## 測試

proto4-5：indent、init 提示、status 的 placeholder 警告、`llm ls`／`llm rm`（含 rm 不存在退 1、rm running）。proto4-6／4-4：reset 後 error 檔不在、`--status` 乾淨。proto4-3：LAST_EXIT 換人清掉。
