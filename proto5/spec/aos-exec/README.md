← [spec 總導航](../README.md)

# aos-exec：把一個目標跑一次（命令列說明）

← [proto5 README](../../README.md)｜實作：[lib/aos_exec.py](../../lib/aos_exec.py)（執行）＋
[lib/aos_inst.py](../../lib/aos_inst.py)（讀／驗 inst.json）＋ [cli/aos-exec](../../cli/aos-exec)（入口）；
inst.json 的格式與執行語意在 [inst-posix.md](../inst-posix/README.md)，指示詞在 [directives.md](../directives/README.md)

> **命令列走法照 proto4-3 現況整理，使用者還沒逐條拍板。** 旗標、三種目標的分法、退出碼都
> 是從 [proto4-3/docs/exec.md](../../../proto4-3/docs/exec.md) 搬過來的，沒有新發明；哪天拍板了
> 再回來改這份。

一句話：**aos-exec 把一個目標執行一次，然後把「這次是誰的碼」分清楚交回來。**
「照一份 inst.json 跑一次」到底做什麼（驗完才跑、mkdir／append／inherit／merge、環境清空或
疊加、逾時怎麼砍、exit 檔怎麼寫），全部照 [inst-posix.md 第 6 節](../inst-posix/exec.md#6-執行語意執行者要做到的)，
這裡不重講。

## 各節

原文裡「檔尾〈沿革〉」「檔尾〈實作補記〉」「見下」這類方位詞是拆檔前的位置，拆後照下表找對應檔（`history.md`、`impl-notes.md`、`rulings.md` 等）。

| 檔 | 內容 |
|---|---|
| [usage.md](usage.md) | 用法；三種目標：`xxx` 是什麼決定怎麼跑；旗標 |
| [exit.md](exit.md) | 退出碼：自己的失敗跟子程式的碼分開；125 與 2 時 stderr 印什麼 |
| [api.md](api.md) | 給程式用：`run_target()`；例子 |
| [aos-jail.md](aos-jail.md) | 另一支小指令 `aos-jail`：照參數把程式關進 bwrap 跑（09-24 access-impl，aos-agent 送件包牢用） |
