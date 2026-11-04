# inst（libaos，C 版 aos_inst）

`libaos - 起一個程式、等它結束、告訴你結果`（NAME，C-54 R1）

**一句話：一個很小的純 C 函式庫，只做一件事——起一個程式、等它結束、告訴你結果。**
沒有命令列、不讀 JSON，給其他語言用 C FFI 呼叫（Python ctypes、Rust、Go、Zig…）；[aos-exec](../aos-exec/README.md) 遇到 inst 單子時在行程內呼叫它（單子 JSON 的解析在 aos-exec 的 C++ 庫，不在這裡）。
全家慣例見 [impls/README.md](../README.md)（這個專案是純 C，名字沿用 dcap 的 C 模板：資料夾 `inst`、標頭 `aos.h`、函數 `aos_inst_*`）。
inst 的語意以 [NORMS inst](../../docs/NORMS/03-基礎設施-inst.md)（N-04、N-25、N-27、N-30）為準；本頁只寫 C 介面與實作。

就像你請人幫忙跑腿：你填一張單子（`aos_inst_input_t`）寫清楚「做什麼（argv）、去哪（cwd）、帶什麼（envs、stdin）、
東西放哪（stdout／stderr）、最晚幾點回來（timeout_ms）」，他回來時在回條（`aos_inst_result_t`）上寫「辦完了，結果是幾號；
或是超時了，被叫回來」。盡量少做事：路徑一律絕對路徑、找程式交給 glibc 的 `execvp`、不幫忙建資料夾、不 malloc。

```c
aos_inst_input_t in = {
    .argv = (const char *const[]){"sh", "-c", "echo hi; exit 3", NULL},
    .cwd = "/tmp",
    .paths = {NULL, "/tmp/out.txt", NULL},   // 一律絕對路徑
    .timeout_ms = 5000,
    .grace_ms = 2000,
};
aos_inst_result_t r;
int rc = aos_inst_exec(&in, &r);
if (rc != AOS_INST_OK) printf("lib 出錯：%s\n", aos_inst_strerror(rc));
else printf("%d %d %llu\n", r.code, r.timed_out, r.ms);   // 3 0 11 左右
```

## 分檔目錄

> 超過 8 KB，依 [STRUCTURE](../../../wf/STRUCTURE.md) 按標題拆開；本檔留前言與表，各段逐字在下列分檔。

| 分檔 | 涵蓋的段 |
|---|---|
| [01-用法與元素](docs/01-用法與元素.md) | 用法（介面）；元素（檔案） |
| [02-行為細節等](docs/02-行為細節等.md) | 行為細節；Python ctypes 範例；建置與測試；寫法 |

<a id="用法介面"></a>
<a id="元素檔案"></a>
<a id="行為細節"></a>
<a id="python-ctypes-範例"></a>
<a id="建置與測試"></a>
<a id="寫法"></a>
