#pragma once

/* 錯誤分類與 HTTP／串流 transport 介面。 */

#include <aos/export.h>

#include <functional>
#include <string>
#include <string_view>
#include <vector>

namespace aos::llms {

enum class ErrorKind {
    None,
    InvalidArgument,
    Capability,
    Transport,
    Http,
    Json,
    Response,
    Io,
};

AOS_API const char *to_string(ErrorKind kind) noexcept;

struct ReplyError {
    ErrorKind kind = ErrorKind::None;
    std::string message;
};

struct HttpRequest {
    std::string method = "POST";
    std::string url;
    std::string body;
    std::vector<std::string> headers;
    long timeout_ms = 60000;
};

struct HttpResponse {
    long status = 0;
    std::string body;
    std::string error;
};

using Transport = std::function<HttpResponse(const HttpRequest &)>;
using StreamByteSink = std::function<void(std::string_view)>;
using StreamTransport =
    std::function<HttpResponse(const HttpRequest &, const StreamByteSink &)>;

}  // namespace aos::llms
