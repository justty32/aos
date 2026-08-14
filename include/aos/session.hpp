#pragma once

#include <asio/awaitable.hpp>

#include <string>
#include <string_view>

namespace aos {

// 命令跟外界互動的唯一管道：stdin 用拉的，stdout／stderr 用推的。
// 兩個方向都不會把整份資料留在記憶體裡，所以命令可以邊讀邊寫。
// 介面是虛擬的，測試才能塞一個假的 Session 進去。
class Session {
public:
    Session() = default;
    virtual ~Session() = default;

    Session(const Session&) = delete;
    Session& operator=(const Session&) = delete;

    // 回傳空字串代表 stdin 已經結束；之後再呼叫仍然回傳空字串。
    [[nodiscard]] virtual asio::awaitable<std::string> read_input() = 0;

    // text 只是 view，呼叫端要保證它活過 co_await。現組的字串請用下面的
    // say()／complain()，它們接 by value，不會踩到懸空。
    virtual asio::awaitable<void> write_output(std::string_view text) = 0;
    virtual asio::awaitable<void> write_error(std::string_view text) = 0;
};

// 給 std::format 現組出來的字串用：參數 by value，會被搬進 coroutine frame，
// 所以不會有「view 指向已經死掉的暫時字串」這種問題。
asio::awaitable<void> say(Session& session, std::string text);
asio::awaitable<void> complain(Session& session, std::string text);

}  // namespace aos
