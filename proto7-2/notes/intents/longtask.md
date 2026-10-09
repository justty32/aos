# 長任務實跑 意圖卡（r4，L 隊）

← [intents](README.md)｜[brain 多回合卡](brain-multiround.md)｜計畫 [plan-2026-10-09-r4](../plan-2026-10-09-r4.md)

**①解決什麼**：目標 1 與 2 的燈號都還是「各模組單獨過」，沒有一次「aos 上的 AI 真的用 wf 管自己跑一段長任務」的實證：多回合、會 compact、會用 skill、會收發信、被殺能接回。這一隊只做實跑與量測，不寫新功能。

**②必要的副作用**：一個 `aos7-up` 起的 node（真 AI，`--model chatgpt-gpt-6-sol-high`）、12 封需求信、約 20～40 回合；中途對 brain 程序 SIGKILL 一次；真 AI 呼叫 gate ≤100；產出 `notes/play/2026-10-09-real-ai/longtask.md` 與 evidence（node 的 wf/、brain/、events/ 快照）。

**③不做**：不改任何模組（發現 bug 回報頂層）；不用假 AI 充數；不手動幫 AI 整理記憶或挑技能。

**④對照現狀多出來的**：
- 場景與 12 封信的樣本 → **保留**在 `modules/up/examples/longtask/`（R 隊回歸可重跑）。
- 快照會有幾百 KB → **改成可選**：只留工具讀的檔，大的打包 tar.gz。
