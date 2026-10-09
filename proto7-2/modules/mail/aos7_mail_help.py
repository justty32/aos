"""日常與各指令的 CLI 說明。"""
HELP = """aos7-mail：用檔案寄信的小郵局。
先指定郵局資料夾：export AOS_MAIL_ROOT=<資料夾>（或每個指令加 --root <資料夾>）。

日常三個指令：
  aos7-mail send  <我> <對象> '<一句話>'    寄一個請求（REQUEST）給對象
  aos7-mail read  <我>                      看我的信，每封前面有序號
  aos7-mail done  <我> <序號> ['<一句話>']  辦完這封：歸檔；若是請求，自動回 DONE 給寄件人

例：
  export AOS_MAIL_ROOT=$(mktemp -d)
  aos7-mail send alice bob '請 bob 檢查範例'
  aos7-mail read bob
  aos7-mail done bob 1 '檢查完了'
  aos7-mail read alice

各指令細節：aos7-mail <指令> --help。
進階指令 audit（查整個郵局未辦請求）、roster、team，及其他狀態，見 ADVANCED.md。
退出碼：見 ADVANCED.md〈退出碼〉。"""

SUB_HELP = {
    'send': """aos7-mail send <我> <對象> '<一句話>' [正文檔]
  寄一個請求給 <對象>；對方用 read 看、用 done 辦完後你會收到 DONE 回信。
  成功印一行 JSON：{"sent": 信檔路徑, "id": 信id}。
進階：aos7-mail send <我> <對象|--up|team:<隊>> <STATUS> '<一句話>' [正文檔] [--re <請求id>]
  STATUS 可為 REQUEST PROGRESS DONE BLOCKED NEEDS-USER FAILED，見 ADVANCED.md。""",
    'read': """aos7-mail read <我> [--quiet] [--json]
  列出我的未辦信：<序號>  <檔名>  <一句話>。序號給 done 用。
  沒有信印「（沒有新信）」。--quiet 只報新的、沒東西就不印；--json 印 JSON 陣列。""",
    'done': """aos7-mail done <我> <序號> ['<一句話>']
  辦完 read 列出的第 <序號> 封：搬進 done/ 歸檔。
  若那封是請求（REQUEST），必須給一句結論，會自動回 DONE 給寄件人。
  序號只認最近一次 read 的清單（避免辦到你沒看過、剛到的新信）；也可給信檔名或信 id。
進階：aos7-mail done <我> <序號> <DONE|BLOCKED|NEEDS-USER|FAILED> '<一句話>' [正文檔]""",
    'audit': """（進階）aos7-mail audit [<我>] [--json]
  查還有沒有寄出卻沒人辦完的請求。沒有就退出 0；有就列出並退出 1。
  給 <我> 只看跟我有關的。""",
    'roster': """aos7-mail roster <我> --who W --up U --territory T --can C --cannot X [--team 隊]
  （進階）在我的 ROSTER 加一格身份，之後 send <我> --up 會寄給 U。見 ADVANCED.md。""",
    'team': """aos7-mail team <隊名> <領導> [成員...]
  （進階）建立團隊；成員可用 send <我> team:<隊名> PROGRESS '...' 廣播。見 ADVANCED.md。""",
}

