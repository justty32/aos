# smoke — 以 math 的加法與乘法兩題驗證量測、門與自洽。

← [case 格式](../README.md)

兩題都是函數型腳本步：`addition` 算 `17+25`，固定答案 `42`；`multiplication` 算 `17*23`，固定答案 `391`。兩題的 `expect/stdout.json` 都包含結尾換行，要求逐 byte 相同。

```sh
aos-exec proto8/lib/aos/measure --case "$PWD/proto8/cases/smoke" --defs "$PWD/proto8" --repeat 3
```

呼叫前把 `AOS_WS` 指向測試工作區、`AOS_STACK` 指向本次量測小格；執行檔需已在 PATH。通過時 stdout 是一份 JSON，`check.pass` 與 `consistency.pass` 都為 `true`，`samples` 有三份。
