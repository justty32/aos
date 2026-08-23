#include "sse.hpp"

#include <utility>

namespace aos::llms {

SseParser::SseParser(EventSink sink) : sink_(std::move(sink)) {}

void SseParser::feed(std::string_view bytes) {
    if (done_ || bytes.empty()) return;
    pending_.append(bytes);
    std::size_t start = 0;
    while (true) {
        const std::size_t newline = pending_.find('\n', start);
        if (newline == std::string::npos) {
            if (start != 0) pending_.erase(0, start);
            return;
        }
        std::size_t end = newline;
        if (end > start && pending_[end - 1] == '\r') --end;
        line(std::string_view(pending_).substr(start, end - start));
        start = newline + 1;
        if (done_) {
            pending_.clear();
            return;
        }
    }
}

bool SseParser::done() const noexcept { return done_; }

void SseParser::line(std::string_view value) {
    if (value.empty()) {
        dispatch();
        return;
    }
    if (!value.starts_with("data:")) return;
    value.remove_prefix(5);
    if (!value.empty() && value.front() == ' ') value.remove_prefix(1);
    if (!data_.empty()) data_.push_back('\n');
    data_.append(value);
}

void SseParser::dispatch() {
    if (data_.empty()) return;
    if (data_ == "[DONE]") {
        done_ = true;
        data_.clear();
        return;
    }
    const std::string event = std::move(data_);
    data_.clear();
    sink_(event);
}

} // namespace aos::llms
