## 前綴是aos-user

say "hello"
    如果所在資料夾不是agent，則跟你說不是agent資料夾。
say --to ~/bob "hello bob"
    如果~/bob不是agent，同上。
say --to "hello bob"
    跟你說hello bob不是一個agent資料夾
say "hello bob" --to ~/bob
    可以
say "hello bob" --to
    默認為指定./

listen
    持續監看(每秒poll一次)本地agent資料夾的回覆檔，那個檔案有新東西，就顯示到畫面上。
listen --once
    只看一次有無新東西。
listen --from ~/bob
listen --from
    默認./

talk
    本地
talk --to ~/bob
talk --to
    默認./
