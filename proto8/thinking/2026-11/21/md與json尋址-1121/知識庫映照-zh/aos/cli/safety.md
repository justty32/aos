# `knowledge/aos/cli/safety.json` 的中文映照版，給人審用；正本是 json

> 來源：`proto8/knowledge/aos/cli/safety.json`，commit `fad6bef74`。這份是照 json 一對一轉出來的：每一塊前面的粗體 `#/…` 是它在 json 裡的位置（JSON 指標）；英文說明譯成中文，鍵名、指令、路徑、程式碼、錯誤代號照原樣。原文本來是中文的照抄。要改請改 json，這份會重新轉。

---

**`#/_description`**

# 移除與確認

下破壞性的指令之前，先確認選到的 daemon、agent 和 stack；腳本不會有確認提示。

---

**`#/rm`**

# 移除一個 agent

`aos-agent ctl rm bob` 必須明確寫出名字。它絕不從 `$AOS_AGENT` 拿名字。它會關掉畫面、把 bob 卸下；stack 留著（對話歷史、佇列、覆蓋層），用同一個名字和 `--stack` 下 `ctl add` 就能再接回來。`aos-agent ctl rm --purge bob` 還會刪掉 stack，這會毀掉對話歷史和覆蓋層：

```sh
aos-agent ctl rm --purge -y ann
# removed ann (deleted stack /.../stacks/root/procs/ann)
```

就算有 `--purge`，涵蓋了工作區、定義、daemon、cwd、home 或另一個列出的 stack 的 stack 也會保留。`aos-daemon-ctl rm bob` 和單純的 `aos-agent ctl rm bob` 只卸下、保留 stack；它們不會問。設了 `$AOS_KERNEL` 又沒有 `--daemon` 時，沒有 `--purge` 的 `rm` 會經過 kernel，而且不關畫面（見 `aos/cli/agent.json#/phases`）。沒有 `--purge` 卻給 `-y` 是 `ArgumentsBad`；`aos-daemon-ctl rm` 完全不收 `-y`。

---

**`#/reset`**

# 重置覆蓋層

`aos-agent tools -t bob reset` 刪掉這個 agent 的工具覆蓋層。`llm reset` 刪掉它改過的腦設定，`system reset` 刪掉它自己的系統文字，`hook reset` 刪掉它自己的 hook 清單。全部都回到定義；自訂的改動沒有別的副本，除非你自己存過一份。`aos-tools rm NAME` 移除註冊，保留工具檔案，而且不會問。`--replace` 會取代一筆註冊；先確認它的名字。

---

**`#/confirm`**

# [y/N] 問題

`ctl rm --purge`、`goal clear`、`history rm/summarize/set --no-keep` 和那些 reset，只有在 stdin 是終端機時才會在 stderr 問 `[y/N]`。只有 `y` 或 `yes` 會繼續。其他輸入、空行或 EOF 會得到 `aos-agent: warning: nothing done`，結束碼 0。在問題這裡按 Ctrl-C 以 130 結束。沒有覆蓋層的 reset 不會問。

在破壞性動作加上 `-y`/`--yes` 就跳過問題：

```sh
aos-agent ctl rm --purge --yes bob
aos-agent tools --target bob reset --yes
aos-agent system --target bob reset -y
```

管線、agent 的呼叫、stdin 不是終端機的腳本，或 `</dev/null`，都不會問，直接執行。結束碼 0 可能代表使用者拒絕了；去讀那條警告。
