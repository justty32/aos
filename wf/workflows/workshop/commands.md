# workshop — codex exec 指令形態

← [workshop README](README.md)

本檔＝**真的要把參與者叫起來時打什麼**：兩台機器各自的命令、旗標的取捨（reasoning effort、
推理摘要、`--json` 抓 session id）、平行與依序、逾時與檔案落點。全部是實測。

## 指令形態（已實測）

```bash
# 家裡（WSL / Linux）
codex exec -s read-only -c model_reasoning_effort=medium \
  -C /home/lorkhan/repo/simple_tools/aos \
  -o <scratchpad>/r1-p1.md - < <scratchpad>/r1-p1.brief.md

# 公司（Windows codex.exe，從 Git Bash 跑；-C 與 -o 用 Windows 路徑，stdin 用 POSIX 路徑）
codex exec --json -s read-only \
  -c model_reasoning_effort=xhigh -c model_reasoning_summary=none \
  -C 'C:\code\mine\simple_tools\aos' \
  -o 'C:\...\r1-p1.md' - < <scratchpad>/r1-p1.brief.md
```

- **`model_reasoning_effort` 預設 `medium`**（使用者 2026-08-24 指定）。
  **難題用 `xhigh`**（2026-08-25 使用者對「核心行程」那場指定）。`gpt-5.6-sol` 支援
  `low`／`medium`／`high`／`xhigh`／`max`／`ultra`；`ultra` 會自動委派任務，研討會不需要。
  **一輪之內不要混等級**——混了紀錄就不誠實，要嘛全部重跑，要嘛在檔頭明寫誰是哪一級。
- **`-c model_reasoning_summary=none`**：不要回傳推理摘要。**這是唯一真的省流量的旗標**
  （使用者在公司網路時提的）。codex **沒有**關掉串流的開關，而且關了也省不到——串流與否
  傳的是同一批 token。真正能壓流量的只有三件事：**少讀檔**（每讀一個檔就整份塞進上行
  context）、**減人**、**關推理摘要**。
- **參與者可以自己開 sub agent** 做雜活（**2026-08-25 使用者指定**）：指名 **Terra**
  （`gpt-5.6-terra`）或 **Luna**（`gpt-5.6-luna`），**一次最多一個**。`codex features list`
  裡 `multi_agent` 是 stable/true。
- **抓 session id 要用 `--json`**：stdout 變成 JSONL（本機，不影響流量），從裡面 grep 第一筆
  `session_id`。`-o` 照樣只寫最後發言。**不要用 `--ephemeral`**，那會不存 session。
- **平行 vs 依序**：預設平行（同一個訊息裡一起發）。**網路吃緊時改依序**，一個 for
  迴圈跑完四五位，丟背景等通知——2026-08-25 使用者在公司網路下就是這樣跑的。
- **五位一起跑約要幾分鐘**，而且**沒有辦法用「關掉串流」加速**——等的是模型生成的時間，
  串流只是把同樣的時間切成一段段送。要縮短只有三條路：降 reasoning effort、叫他們少讀檔、
  或減人。
- **`-o` 只寫最後發言**，乾淨可直接讀；stdout 那些事件不用管。
- **`-`＋stdin**：任務書當檔案餵進去，比塞進 argv 可靠（長文、換行、引號都不會出事）。
- **逾時**：每位包一層 `timeout 600`。有人掛掉或吐空檔，就在輪紀錄裡**明寫少了誰**，
  用剩下的繼續——不要靜默略過。
- **拋棄式檔案**：任務書與原始發言全部放 session 的 scratchpad，**不進 repo**。
- 參與者**讀得到 `../` 的兄弟專案**（read-only sandbox 只擋寫，不擋跨目錄讀）。

