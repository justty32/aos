#include <aos/llm.hpp>

#include <curl/curl.h>
#include <nlohmann/json.hpp>

#include <array>
#include <charconv>
#include <cstdlib>
#include <limits>
#include <memory>
#include <stdexcept>
#include <string>
#include <system_error>
#include <utility>

namespace aos::llm {
namespace {

using Json = nlohmann::json;

std::string env_or_default(const char *name, std::string fallback) {
    const char *value = std::getenv(name);
    return value != nullptr && value[0] != '\0' ? value : std::move(fallback);
}

long parse_timeout(const std::string &text) {
    long value = 0;
    const auto [end, error] =
        std::from_chars(text.data(), text.data() + text.size(), value);
    if (error != std::errc() || end != text.data() + text.size() || value <= 0) {
        throw std::invalid_argument("--timeout-ms 必須是正整數");
    }
    return value;
}

int parse_priority(const std::string &text) {
    int value = 0;
    const auto [end, error] =
        std::from_chars(text.data(), text.data() + text.size(), value);
    if (error != std::errc() || end != text.data() + text.size()) {
        throw std::invalid_argument("--priority 必須是整數");
    }
    return value;
}

std::string completion_url(std::string base) {
    while (!base.empty() && base.back() == '/') base.pop_back();
    if (base.empty()) throw std::runtime_error("LLM endpoint 不可為空");
    return base + "/chat/completions";
}

template <typename Value>
void set_option(CURL *curl, CURLoption option, Value value) {
    const CURLcode result = curl_easy_setopt(curl, option, value);
    if (result != CURLE_OK) {
        throw std::runtime_error(std::string("設定 HTTP 請求失敗: ") +
                                 curl_easy_strerror(result));
    }
}

struct ResponseBuffer {
    std::string text;
    bool write_failed = false;
};

std::size_t receive_body(char *data, std::size_t size, std::size_t count,
                         void *userdata) noexcept {
    ResponseBuffer &response = *static_cast<ResponseBuffer *>(userdata);
    const std::size_t bytes = size * count;
    try {
        response.text.append(data, bytes);
        return bytes;
    } catch (...) {
        response.write_failed = true;
        return 0;
    }
}

}  // namespace

Options options_from_env() {
    Options options;
    options.url = env_or_default("AOS_LLM_URL", options.url);
    options.model = env_or_default("AOS_LLM_MODEL", options.model);
    options.key = env_or_default("AOS_LLM_KEY", {});
    return options;
}

CommandOptions parse_arguments(const std::vector<std::string> &arguments) {
    CommandOptions command;
    command.completion = options_from_env();
    command.engine = env_or_default("AOS_LLM_ENGINE", command.engine);
    if (const char *priority = std::getenv("AOS_LLM_PRIORITY");
        priority != nullptr && priority[0] != '\0') {
        try {
            command.priority = parse_priority(priority);
        } catch (const std::invalid_argument &) {
            command.priority = 0;
        }
    }

    for (std::size_t index = 0; index < arguments.size(); ++index) {
        const std::string &argument = arguments[index];
        auto take_value = [&](const char *name) -> const std::string & {
            if (++index >= arguments.size()) {
                throw std::invalid_argument(std::string(name) + " 缺少值");
            }
            return arguments[index];
        };

        if (argument == "--system") {
            if (command.system) throw std::invalid_argument("--system 重複指定");
            command.system = take_value("--system");
        } else if (argument == "--messages") {
            if (command.messages_file) {
                throw std::invalid_argument("--messages 重複指定");
            }
            command.messages_file = take_value("--messages");
        } else if (argument == "--url") {
            command.completion.url = take_value("--url");
        } else if (argument == "--model") {
            command.completion.model = take_value("--model");
        } else if (argument == "--timeout-ms") {
            command.completion.timeout_ms =
                parse_timeout(take_value("--timeout-ms"));
        } else if (argument == "--engine") {
            command.engine = take_value("--engine");
            if (command.engine.empty()) {
                throw std::invalid_argument("--engine 不可為空");
            }
        } else if (argument == "--priority") {
            command.priority = parse_priority(take_value("--priority"));
        } else if (argument == "--slots") {
            command.slots = true;
        } else {
            throw std::invalid_argument("未知參數: " + argument);
        }
    }
    if (!command.slots && command.system && command.messages_file) {
        throw std::invalid_argument("--system 不可與 --messages 同時使用");
    }
    return command;
}

std::vector<Message> parse_messages_json(std::string_view text) {
    try {
        const Json root = Json::parse(text);
        if (!root.is_array()) {
            throw std::runtime_error("messages JSON 必須是陣列");
        }
        std::vector<Message> messages;
        messages.reserve(root.size());
        for (const Json &item : root) {
            if (!item.is_object() || !item.contains("role") ||
                !item["role"].is_string() || !item.contains("content") ||
                !item["content"].is_string()) {
                throw std::runtime_error(
                    "messages 每一項都必須包含字串 role 與 content");
            }
            messages.push_back(
                {item["role"].get<std::string>(),
                 item["content"].get<std::string>()});
        }
        return messages;
    } catch (const std::runtime_error &) {
        throw;
    } catch (const Json::exception &error) {
        throw std::runtime_error(std::string("messages JSON 無法解析: ") +
                                 error.what());
    }
}

std::string make_request_json(const std::vector<Message> &messages,
                              const Options &options) {
    Json request = {{"model", options.model},
                    {"stream", false},
                    {"messages", Json::array()}};
    for (const Message &message : messages) {
        request["messages"].push_back(
            {{"role", message.role}, {"content", message.content}});
    }
    return request.dump();
}

std::string parse_response_text(std::string_view text) {
    try {
        const Json root = Json::parse(text);
        if (!root.contains("choices") || !root["choices"].is_array() ||
            root["choices"].empty() || !root["choices"][0].is_object() ||
            !root["choices"][0].contains("message") ||
            !root["choices"][0]["message"].is_object() ||
            !root["choices"][0]["message"].contains("content") ||
            !root["choices"][0]["message"]["content"].is_string()) {
            throw std::runtime_error(
                "LLM 回應缺少 choices[0].message.content");
        }
        return root["choices"][0]["message"]["content"].get<std::string>();
    } catch (const std::runtime_error &) {
        throw;
    } catch (const Json::exception &error) {
        throw std::runtime_error(std::string("LLM 回應 JSON 無法解析: ") +
                                 error.what());
    }
}

std::string parse_response_model(std::string_view text) {
    try {
        const Json root = Json::parse(text);
        if (!root.contains("model") || !root["model"].is_string()) return {};
        return root["model"].get<std::string>();
    } catch (const Json::exception &error) {
        throw std::runtime_error(std::string("LLM 回應 JSON 無法解析: ") +
                                 error.what());
    }
}

std::string complete(const std::vector<Message> &messages,
                     const Options &options, std::string *served_model) {
    if (options.model.empty()) throw std::runtime_error("LLM model 不可為空");
    if (options.timeout_ms <= 0) throw std::runtime_error("timeout 必須大於零");

    static const bool curl_ready = [] {
        const CURLcode result = curl_global_init(CURL_GLOBAL_DEFAULT);
        if (result != CURLE_OK) {
            throw std::runtime_error(std::string("初始化 libcurl 失敗: ") +
                                     curl_easy_strerror(result));
        }
        return true;
    }();
    (void)curl_ready;

    using CurlHandle = std::unique_ptr<CURL, decltype(&curl_easy_cleanup)>;
    CurlHandle curl(curl_easy_init(), &curl_easy_cleanup);
    if (!curl) throw std::runtime_error("無法建立 HTTP 請求");

    using HeaderList =
        std::unique_ptr<curl_slist, decltype(&curl_slist_free_all)>;
    HeaderList headers(nullptr, &curl_slist_free_all);
    auto append_header = [&](const std::string &header) {
        curl_slist *next = curl_slist_append(headers.get(), header.c_str());
        if (next == nullptr) throw std::runtime_error("無法建立 HTTP headers");
        headers.release();
        headers.reset(next);
    };
    append_header("Content-Type: application/json");
    if (!options.key.empty()) append_header("Authorization: Bearer " + options.key);

    const std::string url = completion_url(options.url);
    const std::string request = make_request_json(messages, options);
    if (request.size() >
        static_cast<std::size_t>(std::numeric_limits<curl_off_t>::max())) {
        throw std::runtime_error("LLM 請求過大");
    }
    ResponseBuffer response;
    std::array<char, CURL_ERROR_SIZE> error_buffer{};

    set_option(curl.get(), CURLOPT_URL, url.c_str());
    set_option(curl.get(), CURLOPT_POST, 1L);
    set_option(curl.get(), CURLOPT_HTTPHEADER, headers.get());
    set_option(curl.get(), CURLOPT_POSTFIELDS, request.data());
    set_option(curl.get(), CURLOPT_POSTFIELDSIZE_LARGE,
               static_cast<curl_off_t>(request.size()));
    set_option(curl.get(), CURLOPT_TIMEOUT_MS, options.timeout_ms);
    set_option(curl.get(), CURLOPT_NOSIGNAL, 1L);
    set_option(curl.get(), CURLOPT_WRITEFUNCTION, &receive_body);
    set_option(curl.get(), CURLOPT_WRITEDATA, &response);
    set_option(curl.get(), CURLOPT_ERRORBUFFER, error_buffer.data());

    const CURLcode result = curl_easy_perform(curl.get());
    if (response.write_failed) throw std::runtime_error("無法儲存 HTTP 回應");
    if (result != CURLE_OK) {
        const char *reason = error_buffer[0] != '\0'
            ? error_buffer.data() : curl_easy_strerror(result);
        throw std::runtime_error(std::string("LLM 連線失敗: ") + reason);
    }

    long status = 0;
    if (curl_easy_getinfo(curl.get(), CURLINFO_RESPONSE_CODE, &status) !=
        CURLE_OK) {
        throw std::runtime_error("無法取得 HTTP status");
    }
    if (status < 200 || status >= 300) {
        throw std::runtime_error("LLM endpoint 回傳 HTTP " +
                                 std::to_string(status));
    }
    const std::string reply = parse_response_text(response.text);
    if (served_model != nullptr) {
        *served_model = parse_response_model(response.text);
    }
    return reply;
}

}  // namespace aos::llm
