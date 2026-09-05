# 給 codex 的任務書（第 5 輪：給人玩的互動台，2026-09-05 晚上）

你在 /home/lorkhan/repo/simple_tools/aos 工作。能跑的 Python 純標準庫原型在 proto/（先讀 proto/README.md、proto/play-agent.sh、proto/examples/agent-real/ 的 brain.py 與 agent.json、proto/examples/team/README.md 與 run.sh）。規定在 wf/workflows/spec/（需要時才讀 09-llm-world、10-agent）。

硬規則：
- 只准碰 proto/play-chat.sh（新）、proto/play/（新資料夾）、proto/README.md（加一節）。不准改 proto/aosp/、proto/examples/、proto/tests/。不 commit、不 push、不 git add。
- Python 只用標準庫。
- **絕對不碰 LM Studio**（不打 localhost:1234、不叫 lms）。真模型一律 DeepSeek：端點 `https://api.deepseek.com/v1`、模型 `deepseek-v4-flash`、金鑰只用環境變數名 `DEEPSEEK_API_KEY` 寫進 config 的 `api_key_env`（照 play-agent.sh 的做法）。金鑰的值不准印、不准寫進任何檔、不准進 log。
- 給人看的字全部大白話中文。
- 使用者 21:15 回來要玩，做小做穩，不要做大。

## 要做什麼

一支 `bash proto/play-chat.sh` 起來就能玩的互動台：使用者打一句任務，一個 agent 在 aos 的一塊地上用 DeepSeek 跑，畫面即時看到它每一圈在幹嘛，中途可以插話。

流程（照 play-agent.sh 的骨架，改成互動）：
1. 起暫存家（`AOS_HOME`）、起 daemon、起 LLM 世界（`aos llm serve`，單元 deepseek）。**不要**用 mktemp 亂丟：家放 `proto/play/home-<時間戳>/`，玩完留著給人翻（proto/play/ 要進 .gitignore 除了腳本；.gitignore 只准加 `proto/play/home-*` 一行）。
2. 提示「你要它做什麼？」讀一行 → 建一塊 agent 地（複製 examples/agent-real 那套 brain.py／agent.json／main.aos.json，task.md 換成使用者打的那句），agent 自己登記時鐘（`daemon add`）。
3. 主迴圈每 2 秒：印新的一圈（圈數、模型說了什麼摘要一行、叫了什麼工具、tokens 用量、累計花費估算用 deepseek-v4-flash 的價目：自己在腳本頂端寫死一個估價常數並註明是估的），不要重印舊的。
4. 同時接鍵盤（用 `select` 讀 stdin，非阻塞）：
   - 打一行字 → 投一封信進 agent 地的收件匣（照 spec 投遞協定，kind `mail`），agent 下一圈的 prompt 會帶到（brain.py 已經會讀等待期間到的信；確認一下，若沒有就在 proto/play/ 放一份自己的 brain 副本改）。
   - `/status` → 印 `aos status` 與登記表那筆。
   - `/log` → 印最後一圈完整的 prompt 與回話。
   - `/stop` → `aos stop` 讓它在格尾停。
   - `/quit` → 收尾（停 daemon、殺 serve）並印結算：幾圈、幾次工具、tokens、估算花費、家在哪。
   - `/new 任務` → 收掉現在的 agent、開新一塊地重來（家不換）。
5. agent 自己收工（不再叫工具／連敗三次／到上限）時印「它收工了：原因」，回到提示等下一句（打字＝再給它一個新任務，等於 `/new`）。
6. agent 的工具：照 examples/agent-real 現有的（讀寫 work/ 裡的檔、跑 shell）。work/ 放在那塊地底下，畫面要印出路徑讓人可以去看它產出什麼。

驗證（一定要做）：
- `AOS_PLAY_BACKEND=echo: bash proto/play-chat.sh` 假後端整套能跑（腳本空轉：自動餵一句任務、跑幾圈、/quit），不打網路。做成 `proto/play/selftest.sh` 讓我能一鍵重跑。
- 真的用 DeepSeek 跑一次 smoke：任務「在 work/ 建一個 hello.txt，內容寫今天日期，然後收工」，看到它建檔並收工。把這次的畫面輸出存 `proto/play/smoke-<時間戳>.txt`（裡面不可有金鑰）。花費要小（≤ 5 圈）。
- proto/README.md 加一節「給人玩的互動台」：一行怎麼起、指令表、家在哪、花費估算是估的。

回報格式：做了什麼（檔案）、假後端自測結果、真模型 smoke 結果（幾圈、tokens、估算花費）、撞到的事。
