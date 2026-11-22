# decisions-1118-night 改寫前的逐字（11-18 晚使用者的裁定），11-22 整理時條目改寫成只剩 litellm 那題

← [progress.json](../progress.json)｜[progress 整理-1122](../../proto8/thinking/2026-11/22/progress整理-1122/README.md)

## decisions-1118-night：11-18 晚使用者的裁定（逐字）

（等使用者，since 2026-11-18）

**what**：aos-llm 丁案（Python 函式庫＋同名薄指令）：「順延，這個不是大問題」；家機 pi：「我已經更新了」；家機 proxy master key：「先不加」；litellm 兩台版本：「先不統一，明天再看」；公司 litellm：「我確實想要讓那邊有litellm，那個等一下再說」；家機 `~/aos-home` 重建：「要等一下」；rm-treestart 的 AOS_* 檢查：「不補」（已記進 lines-1118-decide）；選項框四項——eca codex 身沒做的幾項：「先留著」（eca-rest）；guard 要不要做下去：「先擱著」（wrapup-1115）；cooldown 兩個小改：「前綴補回、清單只限 set-def (Recommended)」（lines-1118-decide）；家機 `~/.aos/scratch`（9.1 GB）與 `~/.claude/projects`（2.5 GB）要不要清：「先不清」（home-cleanup）；proto8/impls 舊編譯產物：「刪掉」（先不刪，見 impls-old-builds）。11-19 早使用者定公司用 ~/litellm-proxy 的 1.109.1、自己抄好 codex 登入；線 litellm-up-1119 起起來、三模型非串流與串流都通、aos 整條線真模型回字（公司 litellm 這項了結）。還等的：litellm 兩台版本要不要統一（1.87.5 的釘版理由在 1.109.1 已不成立）、家機重建。~/litellm-proxy 進 llm_proxy：使用者 11-19「好，併進llm_proxy當子夾」，已併進 ~/repo/llm_proxy/pinned_1.109.1/（llm_proxy commit bf9f5ec、432f9a8，沒 push）；同日「排吧」後公司機 proxy 已改從子夾起（pid 33494）。~/litellm-proxy 舊夾：11-19 上午使用者說「刪掉」，頂層已刪除（現行 proxy 照常跑）
