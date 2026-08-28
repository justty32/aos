// 彙整的耐久性面：header sidecar 的五個欄位、批 id 去重與 swept 閘門，以及崩潰
// 窗口的兩種現場（提交點之後崩在刪投遞前＝不得二次發布；崩在兩個 rename 之間＝
// roll forward）。
// 崩潰不是真的殺行程，而是**佈置崩潰之後的檔案現場**：確定性、無 sleep、無 race。
// 注意：正常跑完一輪之後 header 會被標成 swept（§C-8），所以要重現「殘留」現場
// 必須手工把 header 改寫回 swept:false——已 swept 代表清理走完，那時同名同內容的
// 投遞是全新的一批，MUST 照常發布（#1）。

#include "handoff_test_support.hpp"

#include <aos/inst.hpp>

#include <string>
#include <string_view>
#include <vector>

#include <sys/stat.h>
#include <unistd.h>

using namespace aos::handoff_test;

namespace {

constexpr std::string_view kHeaderPrefix = R"({"version":1,"id":")";
constexpr std::string_view kHeaderInfix = R"(","origin":"aggregated","result":null,"swept":)";

// 五欄位齊：version／id／origin／result／swept 照字面驗，回傳中間那個 id。
std::string header_id(const std::string &document) {
    REQUIRE(document.compare(0, kHeaderPrefix.size(), kHeaderPrefix) == 0);
    const std::size_t infix = document.find(kHeaderInfix);
    REQUIRE(infix != std::string::npos);
    return document.substr(kHeaderPrefix.size(),
                           infix - kHeaderPrefix.size());
}

// header 的 swept 欄（§C-8 的去重閘門）。
bool header_swept(const std::string &document) {
    const std::size_t infix = document.find(kHeaderInfix);
    REQUIRE(infix != std::string::npos);
    const std::string tail = document.substr(infix + kHeaderInfix.size());
    if (tail.compare(0, 4, "true") == 0) return true;
    REQUIRE(tail.compare(0, 5, "false") == 0);
    return false;
}

// 手工組一份 header：佈置崩潰現場用。
std::string make_header(const std::string &id, bool swept) {
    return std::string(kHeaderPrefix) + id + std::string(kHeaderInfix) +
           (swept ? "true" : "false") + "}\n";
}

// 一個只有 inbox 的世界；回傳 instruction 路徑。
std::string make_world(const TempDir &dir) {
    REQUIRE(std::filesystem::create_directory(dir.path + "/inst.tempd"));
    return dir.path + "/inst.json";
}

// 跑完一輪正常的彙整，回合也取件釋放掉，回傳那一批的 id 與 canonical 位元組。
// 這是所有崩潰現場的共同起點。
struct FirstRound {
    std::string id;
    std::string canonical;
};

FirstRound run_first_round(const std::string &base, const std::string &head) {
    aos::HandoffResult result;
    REQUIRE(aos::aggregate_instructions(base, result) == aos::HandoffState::Ok);
    REQUIRE(result.published);
    FirstRound round;
    round.canonical = read_file(base);
    const std::string document = read_file(head);
    round.id = header_id(document);
    // 正常跑完一輪之後投遞已清乾淨，header MUST 是 swept（#1 的修法）。
    CHECK(header_swept(document));

    std::string claimed;
    REQUIRE(aos::claim_instruction(base, claimed, result) ==
            aos::HandoffState::Ok);
    REQUIRE(aos::release_instruction(base, result) == aos::HandoffState::Ok);
    return round;
}

std::size_t inode_of(const std::string &path) {
    struct stat status {};
    REQUIRE(stat(path.c_str(), &status) == 0);
    return static_cast<std::size_t>(status.st_ino);
}

}  // namespace

TEST_CASE("handoff writes the five header fields beside the published batch") {
    TempDir dir;
    const std::string base = make_world(dir);
    write_file(dir.path + "/inst.tempd/10.json", R"({"argv":["work"]})");

    aos::HandoffResult result;
    REQUIRE(aos::aggregate_instructions(base, result) == aos::HandoffState::Ok);
    REQUIRE(result.published);
    CHECK(result.issues.empty());

    const std::string document = read_file(dir.path + "/inst-head.json");
    const std::string id = header_id(document);
    CHECK(id.size() == 16);
    CHECK(id.find_first_not_of("0123456789abcdef") == std::string::npos);
    // 投遞全數刪除且目錄落盤之後，header MUST 改寫成 swept:true（§C-8）。
    CHECK(header_swept(document));

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

// #1 的回歸測試：sweep 走完之後去重 MUST NOT 再擋任何投遞。修補之前這一批會被
// 靜默刪除、永不執行（退出碼 0、零 warning），因為內容導出的 id 分不出「崩潰
// 殘留」與「恰好長得一模一樣的全新投遞」。
TEST_CASE("handoff republishes an identical delivery once the header is swept") {
    TempDir dir;
    const std::string base = make_world(dir);
    const std::string head = dir.path + "/inst-head.json";
    const std::string delivery = dir.path + "/inst.tempd/10.json";
    const std::string document = R"({"argv":["work"]})";
    write_file(delivery, document);

    const FirstRound first = run_first_round(base, head);
    REQUIRE(header_swept(read_file(head)));

    // 同名同內容的**全新**投遞：id 會跟現任 header 一模一樣，但 header 已 swept。
    write_file(delivery, document);
    aos::HandoffResult result;
    REQUIRE(aos::aggregate_instructions(base, result) == aos::HandoffState::Ok);
    CHECK(result.published);
    CHECK(std::filesystem::exists(base));
    CHECK_FALSE(std::filesystem::exists(delivery));
    CHECK(header_id(read_file(head)) == first.id);
}

TEST_CASE("handoff refuses to publish a batch twice after a crash before cleanup") {
    TempDir dir;
    const std::string base = make_world(dir);
    const std::string head = dir.path + "/inst-head.json";
    const std::string delivery = dir.path + "/inst.tempd/10.json";
    const std::string document = R"({"argv":["work"]})";
    write_file(delivery, document);

    const FirstRound first = run_first_round(base, head);

    // 崩在「提交點之後、刪投遞之前」的現場：header 是這一批的 id 且**還沒 swept**
    // （sweep 沒走完，正是殘留的定義），投遞同名同內容留在 inbox。
    write_file(head, make_header(first.id, false));
    write_file(delivery, document);

    aos::HandoffResult result;
    REQUIRE(aos::aggregate_instructions(base, result) == aos::HandoffState::Ok);
    CHECK_FALSE(result.published);
    CHECK(result.issues.empty());
    CHECK_FALSE(std::filesystem::exists(base));
    CHECK_FALSE(std::filesystem::exists(delivery));
    // 清完投遞（且目錄落盤）之後 MUST 把 header 標成 swept（§D-6）：下一次同樣的
    // 投遞就不該再被擋。
    CHECK(header_swept(read_file(head)));

    // 去重不會把世界卡住：下一組不同的投遞照樣發布。
    write_file(dir.path + "/inst.tempd/20.json", R"({"argv":["next"]})");
    REQUIRE(aos::aggregate_instructions(base, result) == aos::HandoffState::Ok);
    CHECK(result.published);
    CHECK(std::filesystem::exists(base));
}

TEST_CASE("handoff rolls a committed batch forward after a crash between renames") {
    TempDir dir;
    const std::string base = make_world(dir);
    const std::string head = dir.path + "/inst-head.json";
    const std::string delivery = dir.path + "/inst.tempd/10.json";
    const std::string document = R"({"argv":["work"]})";
    write_file(delivery, document);

    const FirstRound first = run_first_round(base, head);

    // 崩在 header 的 rename（提交點）之後、批發布之前的現場：header 是新 id 且未
    // swept、批還躺在那一輪自己的**唯一暫存**裡、投遞還在 inbox。
    // 錨不是固定的 `<base>.temp`（那個共用槽位已經拿掉了），而是**兄弟唯一暫存**
    // `inst-<pid>-<seq>.json.temp`，靠位元組認身分。
    // #21 之後 roll-forward 要求「位元組 == 本輪重算的 canonical 位元組」，所以
    // 不能用「內容刻意不同的暫存」來分辨 roll forward 與二次發布。改用 **inode
    // 身分**分辨：先 link 一份硬連結指到那個兄弟檔，彙整之後 base 與硬連結同
    // inode ⟹ 它是被 rename 過去的（roll forward），不是重寫出來的。
    const std::string sibling = dir.path + "/inst-9999-0.json.temp";
    write_file(head, make_header(first.id, false));
    write_file(delivery, document);
    write_file(sibling, first.canonical);
    const std::string witness = dir.path + "/witness.link";
    REQUIRE(link(sibling.c_str(), witness.c_str()) == 0);
    const std::size_t committed_inode = inode_of(witness);

    aos::HandoffResult result;
    REQUIRE(aos::aggregate_instructions(base, result) == aos::HandoffState::Ok);
    CHECK(result.published);
    CHECK(result.issues.empty());
    CHECK(read_file(base) == first.canonical);
    CHECK(inode_of(base) == committed_inode);  // rename 過去的那一份，不是重寫的
    CHECK_FALSE(std::filesystem::exists(sibling));
    CHECK_FALSE(std::filesystem::exists(delivery));
}

// 這一條釘住的是「拿掉共用固定槽位」那個裁決：位元組對不上的兄弟暫存**絕不**
// 被扶正。共用槽位時代 A 可能發布 B 寫進槽位的批（兩人看到的投遞集合不同時），
// 只清掉 A 自己看到的那幾份投遞，剩下的下一輪重跑＝重複執行。現在身分完全由
// 內容決定，名字只是索引。
TEST_CASE("handoff does not roll forward a sibling temp that is not this batch") {
    const std::string document = R"({"argv":["work"]})";

    // 殘檔（解析不出批）與「解析得出、但位元組不是這一批」兩種都不得扶正。
    // 後者是 #21：修補之前只檢查「解析得出非空批次」，於是一份與這批毫無關係的
    // 殘骸會被當成「這一批」扶正並執行掉——等於執行了未經任何驗證來源的批次。
    const std::vector<std::string> sibling_contents = {
        R"([{"argv":[)",                       // 殘檔：解析不出批
        R"([{"argv":["UNRELATED_GARBAGE"]}])"  // #21：合法的批，但不是這一批
    };

    for (const std::string &sibling_content : sibling_contents) {
        INFO("sibling temp content: " << sibling_content);
        TempDir dir;
        const std::string base = make_world(dir);
        const std::string head = dir.path + "/inst-head.json";
        const std::string delivery = dir.path + "/inst.tempd/10.json";
        write_file(delivery, document);

        const FirstRound first = run_first_round(base, head);
        REQUIRE(sibling_content != first.canonical);

        const std::string sibling = dir.path + "/inst-9999-0.json.temp";
        write_file(head, make_header(first.id, false));
        write_file(delivery, document);
        write_file(sibling, sibling_content);

        aos::HandoffResult result;
        REQUIRE(aos::aggregate_instructions(base, result) ==
                aos::HandoffState::Ok);
        CHECK_FALSE(result.published);
        CHECK_FALSE(std::filesystem::exists(base));
        CHECK_FALSE(std::filesystem::exists(delivery));
        // 兄弟原封不動：沒有被扶正，也沒有被當成自己的殘骸刪掉（它可能是同儕的）。
        CHECK(read_file(sibling) == sibling_content);
    }
}

TEST_CASE("handoff republishes when the current header cannot be read") {
    TempDir dir;
    const std::string base = make_world(dir);
    const std::string head = dir.path + "/inst-head.json";
    const std::string delivery = dir.path + "/inst.tempd/10.json";
    const std::string document = R"({"argv":["work"]})";
    write_file(delivery, document);

    run_first_round(base, head);
    write_file(delivery, document);
    // 讀不懂的 header 一律視同沒有 header：寧可重發（回到本階段之前的行為），
    // 也不拿一個看不懂的檔當去重依據。
    write_file(head, "not json");

    aos::HandoffResult result;
    REQUIRE(aos::aggregate_instructions(base, result) == aos::HandoffState::Ok);
    CHECK(result.published);
    REQUIRE(result.issues.size() == 1);
    CHECK(result.issues[0].kind == aos::HandoffIssueKind::HeaderInvalid);
    CHECK(header_id(read_file(head)).size() == 16);
}

// #4：去重只認**頂層**的 id。§C-8 說 result 欄由 loop 於 M2 寫回，一旦它變成
// 含 id 的物件，掃描器就必須分得清楚——否則會拿巢狀的 id 去比對，把全新的批
// 靜默丟掉（或反過來，去重整個失效）。
TEST_CASE("handoff only reads the top-level id out of the current header") {
    TempDir dir;
    const std::string base = make_world(dir);
    const std::string head = dir.path + "/inst-head.json";
    const std::string delivery = dir.path + "/inst.tempd/10.json";
    const std::string document = R"({"argv":["work"]})";
    write_file(delivery, document);

    const FirstRound first = run_first_round(base, head);
    const std::string decoy = "0000000000000000";
    REQUIRE(first.id != decoy);

    // 每個版面都在描述「這一批的殘留」，差別只在真 id 擺在哪裡。頂層 id 是真的
    // ⟹ 去重命中（不發布）；頂層 id 是假的 ⟹ 不命中（照常發布）。
    struct Layout {
        const char *name;
        std::string header;
        bool expect_published;
    };
    const std::vector<Layout> layouts = {
        {"nested id in result is ignored",
         R"({"version":1,"result":{"id":")" + first.id + R"("},"id":")" + decoy +
             R"(","swept":false})" "\n",
         true},
        {"top-level id wins over a nested decoy",
         R"({"version":1,"result":{"id":")" + decoy + R"("},"id":")" + first.id +
             R"(","swept":false})" "\n",
         false},
        {"an escaped \"id\" inside a string value is not a key",
         R"({"version":1,"origin":"the \"id\" of a batch","id":")" + first.id +
             R"(","swept":false})" "\n",
         false},
        {"an \"id\" inside an array is not a key",
         R"({"version":1,"tags":["id",")" + first.id + R"("],"id":")" + decoy +
             R"(","swept":false})" "\n",
         true},
    };

    for (const Layout &layout : layouts) {
        INFO(layout.name);
        // 每一輪都回到同一個現場：批已被取走、投遞同名同內容留在 inbox。
        std::filesystem::remove(base);
        std::filesystem::remove(base + ".temp");
        write_file(delivery, document);
        write_file(head, layout.header);

        aos::HandoffResult result;
        REQUIRE(aos::aggregate_instructions(base, result) ==
                aos::HandoffState::Ok);
        CHECK(result.published == layout.expect_published);
        CHECK(result.issues.empty());
    }
}

// 找錨時必須跳過 header 自己的唯一暫存：它也長得像 `inst-...json.temp`
// （實際是 `inst-head-<pid>-<seq>.json.temp`），但那是 header 不是批。位元組比對
// 本來就會擋掉，這一條把「明著跳過 <stem>-head- 前綴」的行為釘住。
TEST_CASE("handoff never mistakes a header temp for a batch roll-forward anchor") {
    TempDir dir;
    const std::string base = make_world(dir);
    const std::string head = dir.path + "/inst-head.json";
    const std::string delivery = dir.path + "/inst.tempd/10.json";
    const std::string document = R"({"argv":["work"]})";
    write_file(delivery, document);

    const FirstRound first = run_first_round(base, head);

    // 佈置去重命中的現場，外加一份**內容剛好等於本輪 canonical 批**的 header
    // 唯一暫存殘骸。跳過前綴之後它不該被當成錨，所以這一輪只清投遞、不發布。
    write_file(head, make_header(first.id, false));
    write_file(delivery, document);
    const std::string header_temp = dir.path + "/inst-head-9999-0.json.temp";
    write_file(header_temp, first.canonical);

    aos::HandoffResult result;
    REQUIRE(aos::aggregate_instructions(base, result) == aos::HandoffState::Ok);
    CHECK_FALSE(result.published);
    CHECK_FALSE(std::filesystem::exists(base));
    CHECK_FALSE(std::filesystem::exists(delivery));
    CHECK(std::filesystem::exists(header_temp));
    CHECK(header_swept(read_file(head)));
}
