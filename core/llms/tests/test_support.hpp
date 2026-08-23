#pragma once

#include <aos/llms.hpp>

#include <catch2/catch_test_macros.hpp>
#include <nlohmann/json.hpp>

#include <cstdio>
#include <fstream>
#include <string>
#include <utility>
#include <vector>

#include <unistd.h>

using LlmsJson = nlohmann::ordered_json;

inline aos::llms::HttpResponse ok_reply(
    const std::string &content = "答案",
    const std::string &finish_reason = "stop") {
    LlmsJson body = {
        {"choices",
         {{{"finish_reason", finish_reason},
           {"message", {{"content", content}, {"tool_calls", nullptr}}}}}},
    };
    return {.status = 200, .body = body.dump()};
}

inline aos::llms::HttpResponse unknown_caps() {
    return {.status = 200,
            .body = R"({"data":[{"model_name":"m","model_info":{}}]})"};
}

/* 標準的 `/v1/models`：每個 OpenAI 相容端點都有，只給名字不給能力。 */
inline aos::llms::HttpResponse model_list() {
    return {.status = 200, .body = R"({"data":[{"id":"m"}]})"};
}

struct FakeEndpoint {
    std::vector<aos::llms::HttpRequest> requests;
    std::vector<aos::llms::HttpResponse> chats;
    aos::llms::HttpResponse caps = unknown_caps();
    aos::llms::HttpResponse models = model_list();
    std::size_t next_chat = 0;
    int cap_calls = 0;
    int model_calls = 0;

    aos::llms::HttpResponse operator()(const aos::llms::HttpRequest &request) {
        requests.push_back(request);
        if (request.url.ends_with("/model/info")) {
            ++cap_calls;
            return caps;
        }
        if (request.url.ends_with("/models")) {
            ++model_calls;
            return models;
        }
        REQUIRE(next_chat < chats.size());
        return chats[next_chat++];
    }
};

inline std::string llms_temp_file(const std::string &suffix,
                                  const std::string &content) {
    std::string pattern = "/tmp/aos_llms_test_XXXXXX";
    std::vector<char> buffer(pattern.begin(), pattern.end());
    buffer.push_back('\0');
    const int fd = mkstemp(buffer.data());
    REQUIRE(fd >= 0);
    close(fd);
    const std::string original = buffer.data();
    const std::string path = original + suffix;
    REQUIRE(std::rename(original.c_str(), path.c_str()) == 0);
    std::ofstream output(path, std::ios::binary | std::ios::trunc);
    REQUIRE(static_cast<bool>(output));
    output.write(content.data(), static_cast<std::streamsize>(content.size()));
    REQUIRE(static_cast<bool>(output));
    return path;
}

struct TempFile {
    TempFile(std::string suffix, std::string content)
        : path(llms_temp_file(suffix, content)) {}
    ~TempFile() { std::remove(path.c_str()); }
    std::string path;
};
