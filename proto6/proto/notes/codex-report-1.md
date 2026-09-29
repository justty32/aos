## 做了什麼

- `bin/aos`、`bin/aos-runner`、`bin/aos-tick`：三支可執行入口及指定 alias。
- `aosproto/`：設定驗證、自檢、真假 cgroup、IPC 授權、登記與排程、runner、tick group／needs、git 提交與還原。
- `tests/`：單元測試及真假 cgroup 端到端驗收。
- [README.md](../README.md)：繁體中文操作說明、實作範圍、檔案導航。
- 變更限於 `proto6/proto/`；未對外層 repo 執行 add、commit、push。

## 測試

```sh
cd proto6/proto && python3 -m unittest discover -s tests -v
```

- **62 個，62 通過，0 skip**，約 14.5 秒。
- 兩個真 cgroup 案例均實跑：root 完成一格、runner 被殺後清空後代並回報 unknown。

## spec-gaps

[spec-gaps.md](spec-gaps.md) 共 **14 條**，每條均有指定三行說明：

1. create-cgroup 缺少 root 的結束碼
2. cgroup 命名及樹形
3. 省略 root 時父框仍有其他程序
4. runner 診斷位置與 git ignore
5. 自動停格事項的最小格式
6. 不同內容重新登記的簡化
7. cgroup limits 暫回空物件
8. 原來源 bytes 改變的錯誤代號
9. 取值指示詞本輪未做
10. node resume 暫只送 IPC
11. once 不存在帳號與指定驗收矛盾
12. 假 cgroup 不是核心隔離
13. 尚不存在帳號的額度預授
14. CLI 跨 boot 分頁

## 留下一輪

- 按任務排除：指示詞、helper／切 UID、資源上限、state.json、正式 ops、收投件與摘要。
- 補 P-210 resume 驗證／提交、完整重登更新、未存在帳號預授。
- CLI 跨 boot 目前回 1 要求重列；假 cgroup 的取樣空窗與 PID 重用限制已記錄。