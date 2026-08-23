#pragma once

#include <functional>
#include <string>
#include <string_view>

namespace aos::llms {

class SseParser {
  public:
    using EventSink = std::function<void(std::string_view)>;

    explicit SseParser(EventSink sink);
    void feed(std::string_view bytes);
    bool done() const noexcept;

  private:
    void line(std::string_view value);
    void dispatch();

    EventSink sink_;
    std::string pending_;
    std::string data_;
    bool done_ = false;
};

} // namespace aos::llms
