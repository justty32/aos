# mail 意圖卡

← [intents](README.md)｜[包 README](../../modules/mail/README.md)

**①解決什麼**：資料夾當郵局；寄一句話給別人，對方辦完自動回「完成」，最後查有沒有沒辦完的。

**②必要的副作用**：建 `<郵局>/<名>/inbox/`、信檔（撞名加序號、不覆寫）、`done/`、`.handled/`、`.numbers.json` 等狀態檔與鎖；`done` 把原信連進 `done/` 再拿掉頂層那份；回信給寄件人。不連網、不花錢、不起背景程序。

**③不做**：不推播、不 watch；不接團隊 REQUEST；不碰 tasks.json／帳。

**④多出來的（現狀）**
- `send` REQUEST 會在**對方** node 建／寫 `events/` 必讀通道 → **改成可選**：對方已有 `events/` 才發（compact 已是這樣），沒有就只寄信。
- `read` 順便對**每個**信箱跑 audit、逐一拿 `.delivery.lock` → **移除**：read 只看自己的；audit 留給 `audit` 指令。
- `read`／`done` 每次起子程序 `aos7-events read --ack` → **保留**（有 events/ 才做），改成單次呼叫。
- `roster` 覆寫 wfnode 裝的 `ROSTER.md` → **保留**（進階，原子換）。
