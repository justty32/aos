# daemon 帳號模組：主程式降權、root 端開別的帳號的程序

← [daemon 目錄](README.md)｜[核心 B-640](core.md)｜[控制 B-641](control.md)｜[重讀設定 B-642](reload.md)｜[記住狀態 B-643](state.md)｜[收屍／cgroup B-644](cgroup.md)｜[訊息 B-645](mq.md)｜格式：[P-126](../protocol/daemon/account.md)｜舊設計：[暫緩區 B-303](../deferred/helper.md)、[B-609](../deferred/daemon/helper-actions.md)

本篇只有 B-646，寫帳號模組**做什麼**。設定怎麼寫、root 端的封包、stderr 的行，寫在格式篇 [P-126](../protocol/daemon/account.md)。

依據：[verdicts 11 篇末「2026-10-01 第十三批：帳號模組」](../../../notes/verdicts/11-tick-as-unit/15-1001-第十三批.md#2026-10-01-第十三批帳號模組)、[第十二批](../../../notes/verdicts/11-tick-as-unit/14-1001-第十二批.md#2026-10-01-第十二批cgroup-與帳號)、[plan m3m 模組五](../../../plan/m3m-daemon-modules/06-模組五-帳號.md#模組五帳號modulesaccount)；現行程式 [帳號](../../../src/py/README.md#帳號m3m-模組五)（`lib/aos_daemon_account.py`、`lib/aos_daemon_root.py`，有出入以程式為準）。

## 分檔目錄

> 2026-10-02 整理：原檔約 8 KB 超過 8 KB 門檻，按標題逐字拆進 `account/`；本檔只留前言與目錄（原路徑保留當入口）。

<!-- wf-nav -->
| # | 檔 | 段落 |
|---|---|---|
| 1 | [01-B-646-兩支程序與名單.md](account/01-B-646-兩支程序與名單.md) | B-646：帳號模組〔使用者 2026-10-01 第十二、十三批〕 |
| 2 | [02-B-646-其他模組與先不做.md](account/02-B-646-其他模組與先不做.md) | 跟其他模組；先不做 |
