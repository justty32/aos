C 隊 json-argv J7 與 special-cases 兩批查過沒事的條文清單（no-pid、tick 的已核對在各自的「續」檔）。

← [入口](../03-條文-no-pid-tick-json-argv-special-cases.md)｜上一份 [05-四批之間打架](05-四批之間打架.md)

## 已核對沒問題的（json-argv）
- P-44:12「aos_flags 包 tool_io」改讀：使用者「P-44改吧」對的是 `05-衝突與方向題.md` 衝突 1，字面照它改；程式 `proto8/py/aos_flags.py:166` 真的呼叫 `tool_io.tokenize_flags`。
- P-45:7-8（lift-to-norms 寫的）逐字留著「旗標>stdin>環境變數」「只吃想吃的…不報錯」；lib 規則 1（`proto8/lib/docs/01-分層等/01-工具契約與規則1至5.md:17`）寫「旗標＞stdin、stdin 多的鍵忽略、不認得的旗標＝`FlagUnknown`」——把「JSON 多鍵忽略」和「旗標打錯要報」分清楚了，跟 `proto8/lib/tool_io.py:11-12` 一致；旗標打錯報錯不違反「只吃想吃的」（那句講的是 JSON）。
- P-44:15 array 旗標累加、覆蓋 stdin 同鍵：落在 P-44 原句「明說可重複收的例外」裡，跟「旗標＞stdin」一致。
- N-43 續最後一條「stdout 被關退 141」：沒有使用者原話，但它只是 N-43「訊號 128＋N」（SIGPIPE＝13）的套用，11-05 晚邊緣測試 tool_io 已這樣做、human-cli 05 第 7 條排 J5 一併；標「11-06 註（J5 已實作）」，可以。
- P-41:15「act 另按 `_metainfo.time_ms.max` 逾時」：是 fable 在 `06-實作步驟.md` J4 排的（A5），照 user/03「細節由 fable 規劃」；使用者 11-06 選項框只裁「act 附 stderr 尾保留」，逾時那半條文標為已實作註、沒寫成使用者裁，可以。
- C-52 主檔:13 例外 ④：J7 先標「要使用者看」，使用者選「保留 (Recommended)」後 `b7e86dcc6` 改成已定——流程對。
- lib 規則共通代號 `StackMissing`／`ModuleMissing`（`01-工具契約與規則1至5.md:20`）：J3 拿掉的是 exe 工具的 `StackMissing`（aos-tools 那側），lib 工具（`agent_tool.py`、templates 四格）仍會出，條文列它沒錯。
- 「`--target` 也可從 stdin 給」：使用者說「程式目前好像還沒支援」；程式確實只認 argv（`aos_agent/*.py` 全是 `parse(argv, {"--target": …})`），條文沒寫成已支援。
- knowledge 英文書的 J7 三段：F 隊 11-07 已核對並拆進 `cli/`，錯的那句已更正（同第 1 條）。

## 已核對沒問題的（special-cases）
- 題 1 讀法的例子「daemon 的 loop 型可以用 aos-loop 公開的 `ctl`／`state` 窗，但不准認錯誤行字句」與 K-2 已實作註（`:13`）：程式 `proto8/impls/aos-daemon/src/daemon/tend.cpp` 用 `CtlWindow` 常數、`failure.cpp` 拿掉 `is_wrap`；aos-daemon README 加了「透出：…給看表的人」一行，照 K1「README 寫一行」。後果（loop 型 proc 的 `reason` 變成 `aos-loop: error: RunFailed …` 包裝行）在 05 題 1 A 的後果裡寫了、使用者看過選的；N-43 續改讀「看到 `RunFailed` 就是下層的碼」補了讀法。
- K-2 docs/03「寫不了 ctl＝印 warning、改送 SIGTERM、daemon 繼續」：程式 `tend.cpp:98` 確實如此，文件照現況改。
- 題 3 K3 的三條退路：`AOS_DAEMON` 沒設找 `./.stack` 是使用者 11-05 portable-flow 題 3 自己選的（N-63 02:13）、程式 `proto8/py/daemon_ctl/table.py:11-19`；`AOS_KERNEL` 退 daemon ctl 信箱、`AOS_TICK` 退牆鐘——「沒設」那半都對。
- 題 4：docs 沒寫 `_` 保留；daemon 只在 `tick.name` 撞到既有 proc 時 `CfgBad`（`daemon.cpp:57-59`），跟「等撞名再說」一致。tick-time 03 邊緣 8 寫的「`_` 開頭留給 daemon」只在 thinking、沒進條文。
- 題 5 K7 跟 K-6 實作：tools／llm 覆蓋層照 `interfaces.json` 宣告（F 隊 P47 列核過）。
- 題 6 之外的 C-53:6、N-61:9「三處」「唯一例外」改讀：是 05 盤出的條文自相矛盾、「不用問，給條文隊」；改讀只加註、原句留，可以。
- thought `from`：K-6 先做「必填」，使用者同日選「定義裡配預設」後 Y 隊改成登記格 `env.AOS_THOUGHT_FROM` 預設、`from` 優先、都沒給＝`FromMissing`；`proto8/lib/agent/thought/_tooldef.json`（`required` 只有 `goal`、`from` 說明寫明三種情況）、`proto8/lib/docs/03-索引-agent等.md:13` 一致。
- special-cases README「已寫進條文」段自述（1、2、6 在 C-52 續；3 在四種性質表；5 在 C-81；4 不寫；05 矛盾修 1、2、4、6）跟實際落點相符；P-32 移除是使用者自填。
- apply-ideas 02:68-78 的 K-1～K-6、P7 狀態標記與 commit 對得上（F 隊另指出 K-6 的 agents 那半、csv 沒補）。
