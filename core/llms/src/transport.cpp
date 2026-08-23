#include "llms_internal.hpp"

#include <curl/curl.h>

#include <array>
#include <exception>
#include <memory>
#include <new>
#include <string>

namespace aos::llms {
namespace {

struct CurlDeleter {
    void operator()(CURL *curl) const noexcept { curl_easy_cleanup(curl); }
};

struct HeaderDeleter {
    void operator()(curl_slist *headers) const noexcept {
        curl_slist_free_all(headers);
    }
};

struct WriteTarget {
    std::string *body = nullptr;
    const StreamByteSink *sink = nullptr;
    CURL *curl = nullptr;
    std::exception_ptr error;
};

std::size_t write_body(char *data, std::size_t width, std::size_t count,
                       void *opaque) noexcept {
    WriteTarget &target = *static_cast<WriteTarget *>(opaque);
    const std::size_t size = width * count;
    try {
        long status = 0;
        if (target.curl != nullptr) {
            curl_easy_getinfo(target.curl, CURLINFO_RESPONSE_CODE, &status);
        }
        if (target.sink != nullptr && status >= 200 && status < 300) {
            (*target.sink)(std::string_view(data, size));
        } else if (target.body != nullptr) {
            target.body->append(data, size);
        }
        return size;
    } catch (...) {
        target.error = std::current_exception();
        return 0;
    }
}

CURLcode global_curl_state() {
    static const CURLcode state = curl_global_init(CURL_GLOBAL_DEFAULT);
    return state;
}

HttpResponse perform(const HttpRequest &request, const StreamByteSink *sink) {
    HttpResponse response;
    if (global_curl_state() != CURLE_OK) {
        response.error = "libcurl 全域初始化失敗";
        return response;
    }
    std::unique_ptr<CURL, CurlDeleter> curl(curl_easy_init());
    if (!curl) {
        response.error = "libcurl 初始化失敗";
        return response;
    }

    curl_slist *header_list = nullptr;
    for (const std::string &header : request.headers) {
        curl_slist *next = curl_slist_append(header_list, header.c_str());
        if (next == nullptr) {
            curl_slist_free_all(header_list);
            throw std::bad_alloc();
        }
        header_list = next;
    }
    std::unique_ptr<curl_slist, HeaderDeleter> headers(header_list);
    std::array<char, CURL_ERROR_SIZE> error_buffer{};
    WriteTarget target{
        .body = &response.body, .sink = sink, .curl = curl.get()};

    curl_easy_setopt(curl.get(), CURLOPT_URL, request.url.c_str());
    curl_easy_setopt(curl.get(), CURLOPT_HTTPHEADER, headers.get());
    curl_easy_setopt(curl.get(), CURLOPT_WRITEFUNCTION, write_body);
    curl_easy_setopt(curl.get(), CURLOPT_WRITEDATA, &target);
    curl_easy_setopt(curl.get(), CURLOPT_ERRORBUFFER, error_buffer.data());
    curl_easy_setopt(curl.get(), CURLOPT_NOSIGNAL, 1L);
    curl_easy_setopt(curl.get(), CURLOPT_FOLLOWLOCATION, 1L);
    curl_easy_setopt(curl.get(), CURLOPT_TIMEOUT_MS, request.timeout_ms);

    if (request.method == "GET") {
        curl_easy_setopt(curl.get(), CURLOPT_HTTPGET, 1L);
    } else {
        curl_easy_setopt(curl.get(), CURLOPT_CUSTOMREQUEST,
                         request.method.c_str());
        curl_easy_setopt(curl.get(), CURLOPT_POSTFIELDS, request.body.data());
        curl_easy_setopt(curl.get(), CURLOPT_POSTFIELDSIZE_LARGE,
                         static_cast<curl_off_t>(request.body.size()));
    }

    const CURLcode state = curl_easy_perform(curl.get());
    if (target.error) std::rethrow_exception(target.error);
    if (state != CURLE_OK) {
        response.error = error_buffer[0] != '\0'
            ? error_buffer.data() : curl_easy_strerror(state);
        return response;
    }
    curl_easy_getinfo(curl.get(), CURLINFO_RESPONSE_CODE, &response.status);
    return response;
}

}  // namespace

HttpResponse curl_transport(const HttpRequest &request) {
    return perform(request, nullptr);
}

HttpResponse curl_stream_transport(const HttpRequest &request,
                                   const StreamByteSink &sink) {
    return perform(request, &sink);
}

}  // namespace aos::llms
