// 彙整的耐久性面：header sidecar 的四個欄位、批 id 去重，以及崩潰窗口的兩種現場
// （提交點之後崩在刪投遞前＝不得二次發布；崩在兩個 rename 之間＝roll forward）。
// 崩潰不是真的殺行程，而是**佈置崩潰之後的檔案現場**：確定性、無 sleep、無 race。

#include "handoff_test_support.hpp"

#include <aos/inst.hpp>

#include <string>
#include <string_view>
#include <vector>

using namespace aos::handoff_test;

namespace {

constexpr std::string_view kHeaderPrefix = R"({"version":1,"id":")";
constexpr std::string_view kHeaderSuffix = R"(","origin":"aggregated","result":null})"
                                           "\n";

// 四欄位齊：version／id／origin／result 照字面驗，回傳中間那個 id。
std::string header_id(const std::string &document) {
    REQUIRE(document.size() > kHeaderPrefix.size() + kHeaderSuffix.size());
    REQUIRE(document.compare(0, kHeaderPrefix.size(), kHeaderPrefix) == 0);
    REQUIRE(document.compare(document.size() - kHeaderSuffix.size(),
                             kHeaderSuffix.size(), kHeaderSuffix) == 0);
    return document.substr(kHeaderPrefix.size(), document.size() -
                                                     kHeaderPrefix.size() -
                                                     kHeaderSuffix.size());
}

// 一個只有 inbox 的世界；回傳 instruction 路徑。
std::string make_world(const TempDir &dir) {
    REQUIRE(std::filesystem::create_directory(dir.path + "/inst.tempd"));
    return dir.path + "/inst.json";
}

}  // namespace

TEST_CASE("handoff writes the four header fields beside the published batch") {
    TempDir dir;
    const std::string base = make_world(dir);
    write_file(dir.path + "/inst.tempd/10.json", R"({"argv":["work"]})");

    aos::HandoffResult result;
    REQUIRE(aos::aggregate_instructions(base, result) == aos::HandoffState::Ok);
    REQUIRE(result.published);
    CHECK(result.issues.empty());

    const std::string id = header_id(read_file(dir.path + "/inst-head.json"));
    CHECK(id.size() == 16);
    CHECK(id.find_first_not_of("0123456789abcdef") == std::string::npos);

    SECTION("the id is a deterministic digest of the delivery names and bytes") {
        TempDir same;
        const std::string same_base = make_world(same);
        write_file(same.path + "/inst.tempd/10.json", R"({"argv":["work"]})");
        REQUIRE(aos::aggregate_instructions(same_base, result) ==
                aos::HandoffState::Ok);
        CHECK(header_id(read_file(same.path + "/inst-head.json")) == id);
    }

    SECTION("different delivery bytes give a different id") {
        TempDir other;
        const std::string other_base = make_world(other);
        write_file(other.path + "/inst.tempd/10.json", R"({"argv":["other"]})");
        REQUIRE(aos::aggregate_instructions(other_base, result) ==
                aos::HandoffState::Ok);
        CHECK(header_id(read_file(other.path + "/inst-head.json")) != id);
    }
}

TEST_CASE("handoff refuses to publish a batch twice after a crash before cleanup") {
    TempDir dir;
    const std::string base = make_world(dir);
    const std::string delivery = dir.path + "/inst.tempd/10.json";
    const std::string document = R"({"argv":["work"]})";
    write_file(delivery, document);

    aos::HandoffResult result;
    REQUIRE(aos::aggregate_instructions(base, result) == aos::HandoffState::Ok);
    REQUIRE(result.published);

    // 這一回合跑完了（取件＋釋放），但崩潰讓投遞留在 inbox：同名同內容、恰好整組。
    std::string claimed;
    REQUIRE(aos::claim_instruction(base, claimed, result) ==
            aos::HandoffState::Ok);
    REQUIRE(aos::release_instruction(base, result) == aos::HandoffState::Ok);
    write_file(delivery, document);

    REQUIRE(aos::aggregate_instructions(base, result) == aos::HandoffState::Ok);
    CHECK_FALSE(result.published);
    CHECK(result.issues.empty());
    CHECK_FALSE(std::filesystem::exists(base));
    CHECK_FALSE(std::filesystem::exists(delivery));

    // 去重不會把世界卡住：下一組不同的投遞照樣發布。
    write_file(dir.path + "/inst.tempd/20.json", R"({"argv":["next"]})");
    REQUIRE(aos::aggregate_instructions(base, result) == aos::HandoffState::Ok);
    CHECK(result.published);
    CHECK(std::filesystem::exists(base));
}

TEST_CASE("handoff rolls a committed batch forward after a crash between renames") {
    TempDir dir;
    const std::string base = make_world(dir);
    const std::string delivery = dir.path + "/inst.tempd/10.json";
    const std::string document = R"({"argv":["work"]})";
    write_file(delivery, document);

    aos::HandoffResult result;
    REQUIRE(aos::aggregate_instructions(base, result) == aos::HandoffState::Ok);
    REQUIRE(result.published);

    // 崩在 header 的 rename（提交點）之後、批的 rename 之前的現場：
    // header 已是新 id、批還在 .temp、投遞還在 inbox。
    // .temp 的內容刻意跟「重新彙整這組投遞」的結果不同——不然這一輪到底是
    // roll forward（用 .temp）還是把投遞重新彙整發布一次（那就是二次發布），
    // 從外面分不出來。
    const std::string committed = R"([{"argv":["committed"]}])";
    REQUIRE(std::filesystem::remove(base));
    write_file(base + ".temp", committed);
    write_file(delivery, document);

    REQUIRE(aos::aggregate_instructions(base, result) == aos::HandoffState::Ok);
    CHECK(result.published);
    CHECK(result.issues.empty());
    CHECK(read_file(base) == committed);
    CHECK_FALSE(std::filesystem::exists(base + ".temp"));
    CHECK_FALSE(std::filesystem::exists(delivery));
}

TEST_CASE("handoff does not roll forward a .temp that is not a complete batch") {
    TempDir dir;
    const std::string base = make_world(dir);
    const std::string delivery = dir.path + "/inst.tempd/10.json";
    const std::string document = R"({"argv":["work"]})";
    write_file(delivery, document);

    aos::HandoffResult result;
    REQUIRE(aos::aggregate_instructions(base, result) == aos::HandoffState::Ok);
    REQUIRE(result.published);

    // 同樣是 header 對得上，但 .temp 是殘檔：這一批早就發布也跑完了，殘檔跟它無關。
    REQUIRE(std::filesystem::remove(base));
    write_file(base + ".temp", R"([{"argv":[)");
    write_file(delivery, document);

    REQUIRE(aos::aggregate_instructions(base, result) == aos::HandoffState::Ok);
    CHECK_FALSE(result.published);
    CHECK_FALSE(std::filesystem::exists(base));
    CHECK_FALSE(std::filesystem::exists(delivery));
}

TEST_CASE("handoff republishes when the current header cannot be read") {
    TempDir dir;
    const std::string base = make_world(dir);
    const std::string delivery = dir.path + "/inst.tempd/10.json";
    const std::string document = R"({"argv":["work"]})";
    write_file(delivery, document);

    aos::HandoffResult result;
    REQUIRE(aos::aggregate_instructions(base, result) == aos::HandoffState::Ok);
    REQUIRE(result.published);
    std::string claimed;
    REQUIRE(aos::claim_instruction(base, claimed, result) ==
            aos::HandoffState::Ok);
    REQUIRE(aos::release_instruction(base, result) == aos::HandoffState::Ok);
    write_file(delivery, document);
    // 讀不懂的 header 一律視同沒有 header：寧可重發（回到本階段之前的行為），
    // 也不拿一個看不懂的檔當去重依據。
    write_file(dir.path + "/inst-head.json", "not json");

    REQUIRE(aos::aggregate_instructions(base, result) == aos::HandoffState::Ok);
    CHECK(result.published);
    REQUIRE(result.issues.size() == 1);
    CHECK(result.issues[0].kind == aos::HandoffIssueKind::HeaderInvalid);
    CHECK(header_id(read_file(dir.path + "/inst-head.json")).size() == 16);
}
