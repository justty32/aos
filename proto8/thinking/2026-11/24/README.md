# proto8 討論紀錄：2026-11-24

← [2026-11](../README.md)｜[thinking](../../README.md)

規矩見 [thinking/README](../../README.md)。這天的每份一列，一句：定了什麼、還有什麼未決。

| 份 | 一句話 |
|---|---|
| [eca自產工具與MCP-1124](eca自產工具與MCP-1124/README.md) | eca 自產工具要不要另弄一台 MCP 存放（發想）：aos-mcp 今天就在、self_tools add 當輪生效；缺的是工具夾放哪、多隻共用、防改壞；實測兩個洞（共用包同名蓋掉庫存工具、包檔壞了整台全掛）；五題等使用者 |
| [跨agent資源鎖-kernel-1124](跨agent資源鎖-kernel-1124/README.md) | 跨 agent 的資源鎖往 kernel 想（發想）：零件幾乎都在（kernel 骨架、runner.py、llm kernel 的格數排序、aos-lock）；四種意思，推薦「代跑式」資源 kernel（格＝一件在飛的工作，跟 proc 同生死）；arena 每逾時多叫一次腦是它們工具自寫 180 秒上限、不是 aos；五題等使用者 |
| [閒置輪詢C++重寫-1124](閒置輪詢C++重寫-1124/README.md) | 閒置輪詢用 C++ 重寫的施工規劃：每拍先由 C++ 閘判斷「確定沒事」才不起 Python（壞了放行、保底拍）；配 context_wrap 降頻；九個優化方向與搭配表；第 0～6 刀（第 0 刀補 .pyc）；估 4.3 核降到約 0.2～0.45 核；五題等使用者 |
