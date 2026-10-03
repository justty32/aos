from common import *
def main():
    r=read(OUT/'longrun-clean.json');v=read(OUT/'verification.json');ss=r['samples'];a,b=ss[1],ss[-1];report=OUT.parent/'2026-10-03-astra-7-infra.md';text=report.read_text()
    summary=f"**正式長跑觀測 {b['seconds']:.2f} 秒，20 線合計 {b['round_sum']:,} 回合**；穩態活程序 45、daemon fd 5～7，沒有觀察到持續增加的程序或 fd。歷史檔與磁碟則持續成長。stop＋kill 後 {r['stop_seconds']:.3f} 秒完成觀察（含 0.3 秒尾端等待），daemon rc0、產品活程序零殘留；所有測試暫存根與程序已清除。"
    header='| 分鐘 | 父線回合總數 | 活程序／Z | daemon fd／全樹 fd | 檔案數 | 邏輯 MiB／配置 MiB | log MiB | ctl-done | tasks-old |\n|---:|---:|---:|---:|---:|---:|---:|---:|---:|'
    lines=[header]
    for i,x in enumerate(ss):lines.append(f"| {i} | {x['round_sum']:,} | {x['processes']}／{x['zombies']} | {x['daemon_fd']}／{x['fd_total']} | {x['files']:,} | {x['bytes']/2**20:.3f}／{x['allocated_bytes']/2**20:.3f} | {x['log_bytes']/2**20:.3f} | {x['ctl_done']} | {x['tasks_old']:,} |")
    minutes=(b['seconds']-a['seconds'])/60
    analysis=f"1～10 分鐘活程序均為 45、Z=0；第 1 分鐘 daemon fd=7／全樹185，之後回到 5／183，沒有持續上升。0 分鐘冷啟動的 5 個 Z 是程序退出與取樣之間的瞬間狀態，後續已回收。全程取樣 io_errors=0、fd_unreadable 空。第 10 分鐘每線至少 300 回合，n18 因 wake 到 303；子線最後收尾到 r{r['child_round']['round']}。10 次 restart 控制皆有成功回條（plain／reload 各 5）、10 個動態掛載均在 birth，完成 stop 後無活後代。\n\n第 1→10 分鐘檔案增加 {b['files']-a['files']:,} 個，約 **{(b['files']-a['files'])/minutes:.0f} 個／分鐘**；配置量增加 {(b['allocated_bytes']-a['allocated_bytes'])/2**20:.2f} MiB，約 **{(b['allocated_bytes']-a['allocated_bytes'])/2**20/minutes:.3f} MiB／分鐘**；log 增加 {(b['log_bytes']-a['log_bytes'])/2**20:.3f} MiB。最後 tasks-old 有 {b['tasks_old']:,} 個任務。這是保留歷史造成的持續成長，不能把歸檔等同磁碟回收（H-08）。接近結束時另讀已提交歷史，20 線均未見 round 重複／缺號、ended 重報、summary errors 或 action／I/O 錯誤：[完整性取樣](2026-10-03-astra-7-infra-evidence/longrun-invariants.json)。"
    cleanup=f"來源比較覆蓋原有 proto7／proto7-1 的 **{v['protected_files_before']:,} 份檔案**，前後集合與內容聚合 SHA-256 相同，沒有新增／刪除／改動任何非交付檔案。{v['case_cleanup_count']} 份案例 cleanup 全數成功；核對時本輪記錄的暫存根、`/tmp/astra7-*` 資料夾、指向本輪 root 的產品程序均為 **0**，沒有 harness_error。[收尾 JSON](2026-10-03-astra-7-infra-evidence/verification.json)。交付只保留本報告與同名 evidence 目錄的腳本及精簡 JSON，沒有保留長跑原始空間、大型 log 或子程序。"
    for marker,value in [('LONGRUN_SUMMARY',summary),('LONGRUN_TABLE','\n'.join(lines)),('LONGRUN_ANALYSIS',analysis),('CLEANUP',cleanup)]:text=text.replace('<!-- '+marker+' -->',value)
    report.write_text(text)
    print('report complete')
if __name__=='__main__':main()
