#include "aos/session.hpp"

namespace aos {

// text 是 by value 的參數，會被搬進這個 coroutine 的 frame，
// 所以底下的 view 在整個 co_await 期間都有效。
asio::awaitable<void> say(Session& session, std::string text) {
    co_await session.write_output(text);
}

asio::awaitable<void> complain(Session& session, std::string text) {
    co_await session.write_error(text);
}

}  // namespace aos
