#include "test_run_support.hpp"

#include <aos/inst.hpp>

#include <algorithm>
#include <cerrno>
#include <cstdio>
#include <memory>
#include <string>
#include <vector>

using namespace aos::test;

namespace {

int call_deliver(std::vector<std::string> args) {
    std::vector<char *> argv;
    for (std::string &arg : args) argv.push_back(arg.data());
    return aos::run_deliver(static_cast<int>(argv.size()), argv.data());
}

// 跑一次 aos deliver：input_path 非空就接管 stdin，stdout 一律收進 output。
int deliver(const TempDir &dir, std::vector<std::string> args,
            const std::string &input_path, std::string &output) {
    const std::string output_path = dir.path + "/stdout.txt";
    int status = 0;
    {
        ScopedFd out(STDOUT_FILENO, output_path, O_WRONLY | O_CREAT | O_TRUNC);
        std::unique_ptr<ScopedFd> in;
        if (!input_path.empty()) {
            in = std::make_unique<ScopedFd>(STDIN_FILENO, input_path, O_RDONLY);
        }
        status = call_deliver(std::move(args));
    }
    output = read_file(output_path);
    return status;
}

// 把一份文件寫成檔案，回傳路徑（給 -f 或 stdin 當來源用）。
std::string make_input(const TempDir &dir, const std::string &name,
                       const std::string &document) {
    const std::string path = dir.path + "/" + name;
    write_file(path, document);
    return path;
}

std::string delivery_name(const std::string &output) {
    const std::string key = "\"delivery\":\"";
    const std::size_t start = output.find(key);
    if (start == std::string::npos) return {};
    const std::size_t from = start + key.size();
    const std::size_t end = output.find('"', from);
    if (end == std::string::npos) return {};
    return output.substr(from, end - from);
}

std::size_t count_suffix(const std::string &directory,
                         const std::string &suffix) {
    std::size_t total = 0;
    for (const auto &entry : std::filesystem::directory_iterator(directory)) {
        const std::string name = entry.path().filename().string();
        if (name.size() > suffix.size() &&
            name.compare(name.size() - suffix.size(), suffix.size(), suffix) ==
                0) {
            ++total;
        }
    }
    return total;
}

const char *const kTouch = R"({"argv":["/bin/sh","-c","printf ran > ran"]})";

}  // namespace

TEST_CASE("deliver publishes one delivery per call from one process") {
    TempDir dir;
    REQUIRE(init_world(dir.path) == 0);
    const std::string inbox = dir.path + "/.aos/inst.tempd";
    const std::string input = make_input(dir, "input.json", kTouch);

    constexpr int kDeliveries = 5;
    std::vector<std::string> names;
    for (int index = 0; index < kDeliveries; ++index) {
        std::string output;
        REQUIRE(deliver(dir, {"aos deliver", dir.path, "-f", input}, "",
                        output) == 0);
        names.push_back(delivery_name(output));
    }

    // 同一個 process 連續投遞 N 次得 N 份（spec 驗收 2）：每次都是新名字、
    // 檔案都在、沒有殘留的 .temp。
    std::sort(names.begin(), names.end());
    CHECK(std::unique(names.begin(), names.end()) == names.end());
    for (const std::string &name : names) {
        CHECK(std::filesystem::exists(inbox + "/" + name));
    }
    CHECK(count_suffix(inbox, ".json") == kDeliveries);
    CHECK(count_suffix(inbox, ".temp") == 0);
}

TEST_CASE("deliver reports the delivery, count and target as one JSON line") {
    TempDir dir;
    REQUIRE(init_world(dir.path) == 0);
    const std::string input =
        make_input(dir, "batch.json",
                   R"([{"argv":["/bin/true"]},{"argv":["/bin/false"]}])");

    std::string output;
    REQUIRE(deliver(dir, {"aos deliver", dir.path, "-f", input}, "", output) ==
            0);
    const std::string name = delivery_name(output);
    CHECK_FALSE(name.empty());
    CHECK(output == "{\"delivery\":\"" + name +
                        "\",\"count\":2,\"target\":\".aos/inst.tempd\"}\n");
    CHECK(std::filesystem::exists(dir.path + "/.aos/inst.tempd/" + name));
}

TEST_CASE("deliver reads standard input by default and on request") {
    TempDir dir;
    REQUIRE(init_world(dir.path) == 0);
    const std::string inbox = dir.path + "/.aos/inst.tempd";
    const std::string input = make_input(dir, "input.json", kTouch);

    std::string output;
    // 預設吃 stdin（folder 也預設 `.`，所以這一次連 folder 都不給、直接進世界跑）。
    {
        ScopedCwd cwd(dir.path);
        REQUIRE(deliver(dir, {"aos deliver"}, input, output) == 0);
    }
    CHECK_FALSE(delivery_name(output).empty());
    // 明示的 `-` 與 `-f -` 都是 stdin。
    REQUIRE(deliver(dir, {"aos deliver", dir.path, "-"}, input, output) == 0);
    CHECK_FALSE(delivery_name(output).empty());
    REQUIRE(deliver(dir, {"aos deliver", dir.path, "-f", "-"}, input, output) ==
            0);
    CHECK_FALSE(delivery_name(output).empty());
    CHECK(count_suffix(inbox, ".json") == 3);
}

TEST_CASE("delivered instructions run in the next exec round") {
    TempDir dir;
    REQUIRE(init_world(dir.path) == 0);
    const std::string inbox = dir.path + "/.aos/inst.tempd";
    const std::string input = make_input(dir, "input.json", kTouch);

    std::string output;
    REQUIRE(deliver(dir, {"aos deliver", dir.path, "-f", input}, "", output) ==
            0);
    CHECK(exec_world(dir.path) == 0);
    CHECK(read_file(dir.path + "/ran") == "ran");
    CHECK(count_suffix(inbox, ".json") == 0);
    CHECK(std::filesystem::exists(dir.path + "/.aos/inst-head.json"));
}

TEST_CASE("deliver refuses an invalid batch and leaves nothing behind") {
    TempDir dir;
    REQUIRE(init_world(dir.path) == 0);
    const std::string inbox = dir.path + "/.aos/inst.tempd";
    const std::string broken = make_input(dir, "broken.json", "not json");
    const std::string unknown =
        make_input(dir, "unknown.json", R"({"argv":["x"],"nope":1})");
    const std::string second =
        make_input(dir, "second.json", R"([{"argv":["x"]},{"argv":[]}])");

    std::string output;
    CHECK(deliver(dir, {"aos deliver", dir.path, "-f", broken}, "", output) == 1);
    CHECK(deliver(dir, {"aos deliver", dir.path, "-f", unknown}, "", output) == 1);
    CHECK(deliver(dir, {"aos deliver", dir.path, "-f", second}, "", output) == 1);
    CHECK(output.empty());
    // 驗證不過就一個檔都不寫——收件匣裡連 .temp 都不該出現。
    CHECK(std::filesystem::is_empty(inbox));
}

TEST_CASE("deliver refuses a folder that is not a recognized world") {
    TempDir dir;
    const std::string input = make_input(dir, "input.json", kTouch);
    std::string output;
    CHECK(deliver(dir, {"aos deliver", dir.path, "-f", input}, "", output) == 1);

    std::string missing = dir.path + "/nowhere";
    CHECK(deliver(dir, {"aos deliver", missing, "-f", input}, "", output) == 1);

    REQUIRE(std::filesystem::create_directory(dir.path + "/.aos"));
    write_file(dir.path + "/.aos/version", "2\n");
    CHECK(deliver(dir, {"aos deliver", dir.path, "-f", input}, "", output) == 1);
    CHECK(output.empty());
}

TEST_CASE("deliver rejects bad argv with status two") {
    TempDir dir;
    REQUIRE(init_world(dir.path) == 0);
    const std::string input = make_input(dir, "input.json", kTouch);

    CHECK(call_deliver({"aos deliver", dir.path, dir.path}) == 2);
    CHECK(call_deliver({"aos deliver", "-f"}) == 2);
    CHECK(call_deliver({"aos deliver", "--loop", "5"}) == 2);
    CHECK(call_deliver({"aos deliver", "-f", input, "-"}) == 2);
    CHECK(std::filesystem::is_empty(dir.path + "/.aos/inst.tempd"));
}

TEST_CASE("deliver writes canonical bytes and accepts an empty batch") {
    TempDir dir;
    REQUIRE(init_world(dir.path) == 0);
    const std::string inbox = dir.path + "/.aos/inst.tempd";
    const std::string base = dir.path + "/.aos/inst.json";

    // 庫層直接呼叫：發布的位元組是 read_all→write_all 往返後的 canonical 形式
    // （§D-3 裁-7），單筆也會變成批陣列。
    aos::DeliverResult result;
    REQUIRE(aos::deliver_instructions(base, R"({"argv":["/bin/true"]})",
                                      result) == aos::HandoffState::Ok);
    CHECK(result.count == 1);
    CHECK(result.inbox == inbox);
    CHECK(read_file(inbox + "/" + result.name) ==
          "[{\"argv\":[\"/bin/true\"]}]\n");

    // 空批次合法（§C-2）：投得進去，彙整照樣把它消化掉、不發布。
    REQUIRE(aos::deliver_instructions(base, "[]", result) ==
            aos::HandoffState::Ok);
    CHECK(result.count == 0);
    CHECK(read_file(inbox + "/" + result.name) == "[]\n");
}

TEST_CASE("deliver requires an existing inbox and a .json instruction path") {
    TempDir dir;
    aos::DeliverResult result;

    // 收件匣不存在就報錯，不自動建世界（§D-3）。
    const std::string base = dir.path + "/.aos/inst.json";
    CHECK(aos::deliver_instructions(base, R"({"argv":["/bin/true"]})",
                                    result) == aos::HandoffState::InboxReadFailed);
    CHECK(result.error == ENOENT);
    CHECK_FALSE(std::filesystem::exists(dir.path + "/.aos"));

    CHECK(aos::deliver_instructions(dir.path + "/inst", "[]", result) ==
          aos::HandoffState::InvalidArgument);

    // 驗證失敗的原因照實回報（§C-6 的狀態表）。
    REQUIRE(std::filesystem::create_directory(dir.path + "/inst.tempd"));
    CHECK(aos::deliver_instructions(dir.path + "/inst.json",
                                    R"([{"argv":["x"]},{"argv":[]}])", result) ==
          aos::HandoffState::DeliveryInvalid);
    CHECK(result.inst_state == aos::InstState::EmptyArgv);
    CHECK(result.error_record == 2);
    CHECK(std::filesystem::is_empty(dir.path + "/inst.tempd"));
}
