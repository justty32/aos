// aos/signals.hpp：【aos-util】收 SIGINT／SIGTERM／SIGHUP——收到了不死，記下來，由呼叫者（loop、daemon 的拍引擎）每拍去看。
//
// Python 版是裝一個訊號處理函數，收到就往 got 清單裡塞一個號碼。C++ 這裡換成更好懂的做法：
//   1. start()：用 sigprocmask「擋住」這三個訊號。擋住的訊號不會打死我們，而是在 kernel 裡排隊。
//   2. 開一個 signalfd：把「排隊中的訊號」變成一個可以 poll、可以 read 的 fd。
//   3. sleep(ms)：拍引擎每拍本來就要睡一下；這裡改成「poll 這個 fd 最多 ms 毫秒」，
//      有訊號就馬上醒、讀出來記下（first()＝第一個收到的）。
//   4. stop()：把還在排隊的讀掉，關 fd、恢復原本的遮罩（跟 Python 跑完把處理函數換回去一樣）。
// 沒有訊號處理函數，就沒有「處理函數裡能做什麼、不能做什麼」的麻煩；也沒有執行緒。
// 子程序不會繼承「擋住」：spawn 時把子程序的遮罩清空（aos/proc.hpp 的 spawn）。
// 對應 Python aos_loop.py 的 Loop.run 裡 signal.signal(...) 那段、got 清單。
#pragma once

#include <optional>

#include <signal.h>

namespace aos {

class SignalCatcher {
public:
    void start();
    void stop();

    // 睡 ms 毫秒；這段時間收到的訊號記下來（一收到就醒）。還沒 start＝單純睡。ms＝0＝只看一眼。
    void sleep(int ms);

    // 第一個收到的訊號；沒有＝nullopt。
    std::optional<int> first() const { return first_; }

private:
    int fd_ = -1;
    sigset_t old_{};
    std::optional<int> first_;

    void drain();   // 把排隊中的讀光、記下
};

}  // namespace aos
