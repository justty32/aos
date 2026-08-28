#include "handoff_test_support.hpp"

#include <aos/inst.hpp>

#include <cerrno>
#include <string>
#include <vector>

#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

using namespace aos::handoff_test;

TEST_CASE("handoff aggregates deliveries in filename order and flattens batches") {
    TempDir dir;
    const std::string base = dir.path + "/insts/llm.json";
    const std::string inbox = dir.path + "/insts/llm.tempd";
    REQUIRE(std::filesystem::create_directories(inbox));
    write_file(inbox + "/20.json", R"([{"argv":["second"]},{"argv":["third"]}])");
    write_file(inbox + "/10.json", R"({"argv":["first"]})");
    write_file(inbox + "/30.json.temp", R"({"argv":["ignored-temp"]})");
    write_file(inbox + "/40.json.bad", R"({"argv":["ignored-bad"]})");
    write_file(inbox + "/name.part.json", R"({"argv":["ignored-status"]})");

    aos::HandoffResult result;
    REQUIRE(aos::aggregate_instructions(base, result) == aos::HandoffState::Ok);
    CHECK(result.published);
    // name.part.json 以 .json 結尾但形狀不合，不收——但也不再靜默（#10）。
    REQUIRE(result.issues.size() == 1);
    CHECK(result.issues[0].kind == aos::HandoffIssueKind::DeliveryNameIgnored);
    CHECK(result.issues[0].path == inbox + "/name.part.json");
    CHECK_FALSE(std::filesystem::exists(inbox + "/10.json"));
    CHECK_FALSE(std::filesystem::exists(inbox + "/20.json"));
    CHECK(std::filesystem::exists(inbox + "/30.json.temp"));
    CHECK(std::filesystem::exists(inbox + "/40.json.bad"));
    CHECK(std::filesystem::exists(inbox + "/name.part.json"));
    CHECK(std::filesystem::exists(dir.path + "/insts/llm-head.json"));

    std::string document;
    REQUIRE(aos::claim_instruction(base, document, result) ==
            aos::HandoffState::Ok);
    std::vector<aos::inst_t> instructions;
    REQUIRE(aos::read_all(document.data(), document.size(), instructions,
                          nullptr) == aos::InstState::Ok);
    REQUIRE(instructions.size() == 3);
    CHECK(instructions[0].argv[0] == "first");
    CHECK(instructions[1].argv[0] == "second");
    CHECK(instructions[2].argv[0] == "third");
    CHECK(std::filesystem::exists(base + ".runi"));
    CHECK(aos::release_instruction(base, result) == aos::HandoffState::Ok);
    CHECK_FALSE(std::filesystem::exists(base + ".runi"));
}

TEST_CASE("handoff isolates invalid deliveries and publishes the valid ones") {
    TempDir dir;
    const std::string base = dir.path + "/inst.json";
    const std::string inbox = dir.path + "/inst.tempd";
    REQUIRE(std::filesystem::create_directory(inbox));
    write_file(inbox + "/bad.json", "not json");
    write_file(inbox + "/good.json", R"({"argv":["good"]})");

    aos::HandoffResult result;
    REQUIRE(aos::aggregate_instructions(base, result) == aos::HandoffState::Ok);
    CHECK(result.published);
    REQUIRE(result.issues.size() == 1);
    CHECK(result.issues[0].kind == aos::HandoffIssueKind::InvalidDelivery);
    CHECK(result.issues[0].inst_state == aos::InstState::JsonSyntax);
    CHECK(std::filesystem::exists(inbox + "/bad.json.bad"));
    CHECK_FALSE(std::filesystem::exists(inbox + "/good.json"));
    CHECK(std::filesystem::exists(dir.path + "/inst-head.json"));

    std::string document;
    REQUIRE(aos::claim_instruction(base, document, result) ==
            aos::HandoffState::Ok);
    std::vector<aos::inst_t> instructions;
    REQUIRE(aos::read_all(document.data(), document.size(), instructions,
                          nullptr) == aos::InstState::Ok);
    REQUIRE(instructions.size() == 1);
    CHECK(instructions[0].argv[0] == "good");
    REQUIRE(aos::release_instruction(base, result) == aos::HandoffState::Ok);
}

TEST_CASE("handoff does not publish over an existing instruction") {
    TempDir dir;
    const std::string base = dir.path + "/inst.json";
    const std::string inbox = dir.path + "/inst.tempd";
    REQUIRE(std::filesystem::create_directory(inbox));
    write_file(base, R"({"argv":["waiting"]})");
    write_file(inbox + "/next.json", R"({"argv":["next"]})");

    aos::HandoffResult result;
    REQUIRE(aos::aggregate_instructions(base, result) == aos::HandoffState::Ok);
    CHECK_FALSE(result.published);
    CHECK(std::filesystem::exists(inbox + "/next.json"));
    CHECK(read_file(base) == R"({"argv":["waiting"]})");
    // 沒發布就不寫 header：header 描述的是現任的批。
    CHECK_FALSE(std::filesystem::exists(dir.path + "/inst-head.json"));
}

TEST_CASE("handoff treats missing and empty inboxes as no work") {
    TempDir dir;
    const std::string base = dir.path + "/inst.json";
    aos::HandoffResult result;

    REQUIRE(aos::aggregate_instructions(base, result) == aos::HandoffState::Ok);
    CHECK_FALSE(result.published);
    REQUIRE(std::filesystem::create_directory(dir.path + "/inst.tempd"));
    REQUIRE(aos::aggregate_instructions(base, result) == aos::HandoffState::Ok);
    CHECK_FALSE(result.published);
    CHECK_FALSE(std::filesystem::exists(base));
    CHECK_FALSE(std::filesystem::exists(dir.path + "/inst-head.json"));
}

TEST_CASE("handoff consumes empty deliveries with and without useful work") {
    SECTION("alongside a normal delivery") {
        TempDir dir;
        const std::string base = dir.path + "/inst.json";
        const std::string inbox = dir.path + "/inst.tempd";
        REQUIRE(std::filesystem::create_directory(inbox));
        write_file(inbox + "/10.json", "[]");
        write_file(inbox + "/20.json", R"({"argv":["work"]})");

        aos::HandoffResult result;
        REQUIRE(aos::aggregate_instructions(base, result) ==
                aos::HandoffState::Ok);
        CHECK(result.published);
        CHECK(result.issues.empty());
        CHECK_FALSE(std::filesystem::exists(inbox + "/10.json"));
        CHECK_FALSE(std::filesystem::exists(inbox + "/20.json"));
        CHECK(std::filesystem::exists(dir.path + "/inst-head.json"));

        std::vector<aos::inst_t> instructions;
        const std::string document = read_file(base);
        REQUIRE(aos::read_all(document.data(), document.size(), instructions,
                              nullptr) == aos::InstState::Ok);
        REQUIRE(instructions.size() == 1);
        CHECK(instructions[0].argv == std::vector<std::string>{"work"});
    }

    SECTION("as the only delivery") {
        TempDir dir;
        const std::string base = dir.path + "/inst.json";
        const std::string inbox = dir.path + "/inst.tempd";
        REQUIRE(std::filesystem::create_directory(inbox));
        write_file(inbox + "/empty.json", "[]");

        aos::HandoffResult result;
        REQUIRE(aos::aggregate_instructions(base, result) ==
                aos::HandoffState::Ok);
        CHECK_FALSE(result.published);
        CHECK(result.issues.empty());
        CHECK_FALSE(std::filesystem::exists(base));
        CHECK(std::filesystem::is_empty(inbox));
        // 空投遞只是被消化掉，沒有批可以描述，所以也不寫 header。
        CHECK_FALSE(std::filesystem::exists(dir.path + "/inst-head.json"));
    }
}

TEST_CASE("handoff preserves unresolved directives through aggregation") {
    TempDir dir;
    const std::string base = dir.path + "/inst.json";
    const std::string inbox = dir.path + "/inst.tempd";
    REQUIRE(std::filesystem::create_directory(inbox));
    write_file(inbox + "/directives.json",
               R"({"argv":["command",{"$env":"ARG"}],"stdout":{"$ref":"values.json#/output"},"stderr":{"$opt":"merge"}})");

    aos::HandoffResult result;
    REQUIRE(aos::aggregate_instructions(base, result) == aos::HandoffState::Ok);
    const std::string document = read_file(base);
    std::vector<aos::inst_t> instructions;
    REQUIRE(aos::read_all(document.data(), document.size(), instructions,
                          nullptr) == aos::InstState::Ok);
    REQUIRE(instructions.size() == 1);
    const aos::inst_t &instruction = instructions[0];
    CHECK(instruction.stderr_merge);
    REQUIRE(instruction.pending_directives.size() == 2);

    const aos::PendingDirective &environment = instruction.pending_directives[0];
    CHECK(environment.kind == aos::DirectiveKind::Environment);
    CHECK(environment.field == aos::DirectiveField::Argv);
    CHECK(environment.argv_index == 1);
    CHECK(environment.argument == "ARG");

    const aos::PendingDirective &reference = instruction.pending_directives[1];
    CHECK(reference.kind == aos::DirectiveKind::Reference);
    CHECK(reference.field == aos::DirectiveField::Stdout);
    CHECK(reference.argv_index == 0);
    CHECK(reference.argument == "values.json#/output");
}

// ── 審查修補的回歸測試 ───────────────────────────────────────────────────────
// 每個 TEST_CASE 對應審查報告的一條，名字裡標了編號方便對照。

// #3：收件匣是 §D-3 明定的公開介面，任何生產者的 bug 或人手誤建都能塞進一個
// FIFO。修補之前 read_file 的 open 會對沒有寫端的 FIFO 永久阻塞——而那發生在
// 取件之前，世界既沒被鎖、也沒有任何診斷輸出，整台機器就這樣無聲停擺。
TEST_CASE("#3 handoff skips non-regular deliveries instead of blocking on them") {
    TempDir dir;
    const std::string base = dir.path + "/inst.json";
    const std::string inbox = dir.path + "/inst.tempd";
    REQUIRE(std::filesystem::create_directory(inbox));
    const std::string fifo = inbox + "/pipe.json";
    REQUIRE(mkfifo(fifo.c_str(), 0666) == 0);
    write_file(inbox + "/zz-ok.json", R"({"argv":["good"]})");

    // 這一行在修補之前會永遠回不來（測試逾時），現在應該立刻返回。
    aos::HandoffResult result;
    REQUIRE(aos::aggregate_instructions(base, result) == aos::HandoffState::Ok);

    // 正常投遞照發，FIFO 原地不動——它不是「內容無效」，不該被隔離成 .bad。
    CHECK(result.published);
    CHECK(std::filesystem::exists(fifo));
    CHECK_FALSE(std::filesystem::exists(fifo + ".bad"));
    CHECK_FALSE(std::filesystem::exists(inbox + "/zz-ok.json"));
    REQUIRE(result.issues.size() == 1);
    CHECK(result.issues[0].kind == aos::HandoffIssueKind::DeliveryNotRegular);
    CHECK(result.issues[0].path == fifo);
}

// #7：§D-8 說彙整者 MUST NOT 自動刪 .bad，而覆寫等同刪除。修補之前隔離用的是
// 覆蓋語意的 rename，第二份同名壞投遞會把第一份的鑑識證據無聲銷毀。
// 這一條同時是排他發布原語（publish_exclusive）「絕不覆蓋既有目的檔」的端到端
// 佐證——那個 helper 是內部符號，測試連不到，只能從公開 API 這樣觀察。
TEST_CASE("#7 handoff never overwrites an existing .bad when isolating") {
    TempDir dir;
    const std::string base = dir.path + "/inst.json";
    const std::string inbox = dir.path + "/inst.tempd";
    REQUIRE(std::filesystem::create_directory(inbox));
    const std::string delivery = inbox + "/x.json";

    aos::HandoffResult result;
    write_file(delivery, "FIRST-BAD-EVIDENCE");
    REQUIRE(aos::aggregate_instructions(base, result) == aos::HandoffState::Ok);
    REQUIRE(std::filesystem::exists(delivery + ".bad"));
    REQUIRE(read_file(delivery + ".bad") == "FIRST-BAD-EVIDENCE");

    // 同一個名字第二次被隔離（pid 重用之後撞名）。
    write_file(delivery, "SECOND-BAD-EVIDENCE");
    REQUIRE(aos::aggregate_instructions(base, result) == aos::HandoffState::Ok);

    // 第一份原封不動，第二份另外落在一個符合 §B-1 的唯一名底下。
    CHECK(read_file(delivery + ".bad") == "FIRST-BAD-EVIDENCE");
    CHECK_FALSE(std::filesystem::exists(delivery));
    std::vector<std::string> rescued;
    for (const auto &entry : std::filesystem::directory_iterator(inbox)) {
        const std::string name = entry.path().filename().string();
        if (name != "x.json.bad" && name.ends_with(".bad")) {
            rescued.push_back(name);
        }
    }
    REQUIRE(rescued.size() == 1);
    CHECK(read_file(inbox + "/" + rescued[0]) == "SECOND-BAD-EVIDENCE");
    // 形狀是 x-<pid>-<seq>.json.bad：權杖插在 .json 之前，仍然是
    // <名字>.<副檔名>.<狀況>（§B-1）。
    CHECK(rescued[0].starts_with("x-"));
    CHECK(rescued[0].ends_with(".json.bad"));
}

// #8：.bad 的定義是「內容無效」（§B-1），讀不到不是無效。修補之前一次暫時性的
// EACCES／EIO 就把一份完全合法的工作永久踢出佇列（.bad 不進彙整、又 MUST NOT
// 自動清）。
TEST_CASE("#8 handoff leaves an unreadable delivery in place instead of isolating it") {
    TempDir dir;
    const std::string base = dir.path + "/inst.json";
    const std::string inbox = dir.path + "/inst.tempd";
    REQUIRE(std::filesystem::create_directory(inbox));
    const std::string unreadable = inbox + "/y.json";
    write_file(unreadable, R"({"argv":["/bin/true"]})");
    write_file(inbox + "/zz-ok.json", R"({"argv":["good"]})");
    REQUIRE(chmod(unreadable.c_str(), 0) == 0);

    // root 無視檔案權限位元，chmod 000 仍然讀得到——那時這個場景根本不成立。
    if (access(unreadable.c_str(), R_OK) == 0) {
        SUCCEED("running as root: chmod 000 is not enforced, nothing to assert");
        return;
    }

    aos::HandoffResult result;
    REQUIRE(aos::aggregate_instructions(base, result) == aos::HandoffState::Ok);

    // 讀不到的那份留在原地、沒有 .bad；同一輪其他投遞照發。
    CHECK(std::filesystem::exists(unreadable));
    CHECK_FALSE(std::filesystem::exists(unreadable + ".bad"));
    CHECK(result.published);
    CHECK_FALSE(std::filesystem::exists(inbox + "/zz-ok.json"));
    REQUIRE(result.issues.size() == 1);
    CHECK(result.issues[0].kind == aos::HandoffIssueKind::DeliveryReadFailed);
    CHECK(result.issues[0].path == unreadable);
}

// #10：修補之前，檔名含第二個點的投遞被永久靜默忽略——不收、不隔離、不警告。
// 收的集合刻意維持原樣（改判定會改變行為），但不能再靜默。
TEST_CASE("#10 handoff warns about .json names it does not accept") {
    TempDir dir;
    const std::string base = dir.path + "/inst.json";
    const std::string inbox = dir.path + "/inst.tempd";
    REQUIRE(std::filesystem::create_directory(inbox));
    write_file(inbox + "/a.b.json", R"({"argv":["ignored"]})");
    write_file(inbox + "/.hidden.json", R"({"argv":["ignored"]})");
    write_file(inbox + "/zz-ok.json", R"({"argv":["good"]})");
    // 狀況檔不以 .json 結尾，不該被抱怨。
    write_file(inbox + "/quiet.json.temp", R"({"argv":["ignored"]})");
    write_file(inbox + "/quiet.json.bad", R"({"argv":["ignored"]})");

    aos::HandoffResult result;
    REQUIRE(aos::aggregate_instructions(base, result) == aos::HandoffState::Ok);
    CHECK(result.published);

    REQUIRE(result.issues.size() == 2);
    for (const aos::HandoffIssue &issue : result.issues) {
        CHECK(issue.kind == aos::HandoffIssueKind::DeliveryNameIgnored);
    }
    CHECK(result.issues[0].path == inbox + "/.hidden.json");
    CHECK(result.issues[1].path == inbox + "/a.b.json");

    // 不收＝不動：留在原地等人處理，不是被吃掉。
    CHECK(std::filesystem::exists(inbox + "/a.b.json"));
    CHECK(std::filesystem::exists(inbox + "/.hidden.json"));
    CHECK_FALSE(std::filesystem::exists(inbox + "/zz-ok.json"));
}

// #25：aggregate 的第 ⓪ 步用 lstat（不跟隨 symlink）、claim 用 open（跟隨）。
// 修補之前一個斷掉的 symlink 會讓 aggregate 判定「已有一批等著取」而不發布、
// claim 卻回 NoInstruction，CLI rc=0 且零輸出——世界無聲卡死。
TEST_CASE("#25 claim reports a base that exists but cannot be read") {
    TempDir dir;
    const std::string base = dir.path + "/inst.json";
    REQUIRE(std::filesystem::create_directory(dir.path + "/inst.tempd"));
    std::filesystem::create_symlink(dir.path + "/nowhere.json", base);
    REQUIRE(std::filesystem::is_symlink(base));

    std::string document;
    aos::HandoffResult result;
    // 存在但取不走：MUST 是 InstructionReadFailed（CLI 回 1、噴訊息），
    // 不是 NoInstruction（CLI 回 0、以為自己閒著）。
    CHECK(aos::claim_instruction(base, document, result) ==
          aos::HandoffState::InstructionReadFailed);
    CHECK(result.path == base);
    CHECK(result.error == ENOENT);

    // 對照組：base 真的不存在時仍然是 NoInstruction。
    REQUIRE(std::filesystem::remove(base));
    CHECK(aos::claim_instruction(base, document, result) ==
          aos::HandoffState::NoInstruction);
}

// #26：兩個各自可容忍的降級疊在一起就不可容忍了——header 沒寫成代表下一輪沒有
// 去重保證，投遞沒刪掉代表下一輪一定會再看到同一組，合起來是無上限的副作用重播
// （審查實測三回合各重跑一次，沒有任何機制會讓它停）。
TEST_CASE("#26 handoff fails the round when the header and the sweep both fail") {
    TempDir dir;
    const std::string base = dir.path + "/inst.json";
    const std::string inbox = dir.path + "/inst.tempd";
    REQUIRE(std::filesystem::create_directory(inbox));
    write_file(inbox + "/10.json", R"({"argv":["work"]})");
    // header base 佔成目錄 → rename 過去必失敗（HeaderWriteFailed）。
    REQUIRE(std::filesystem::create_directory(dir.path + "/inst-head.json"));
    // inbox 唯讀可執行 → 投遞 unlink 不掉（DeliveryRemoveFailed）。
    REQUIRE(chmod(inbox.c_str(), 0500) == 0);

    if (access(inbox.c_str(), W_OK) == 0) {
        REQUIRE(chmod(inbox.c_str(), 0700) == 0);  // 讓 TempDir 清得掉
        SUCCEED("running as root: chmod 500 is not enforced, nothing to assert");
        return;
    }

    aos::HandoffResult result;
    const aos::HandoffState state = aos::aggregate_instructions(base, result);
    REQUIRE(chmod(inbox.c_str(), 0700) == 0);  // 先還原，TempDir 才清得掉

    // 借用 PublishWriteFailed（不新增列舉值，見 inst.hpp 的註解），位置指向 header。
    CHECK(state == aos::HandoffState::PublishWriteFailed);
    CHECK(result.path == dir.path + "/inst-head.json");
    CHECK(result.error != 0);

    bool header_failed = false;
    bool remove_failed = false;
    for (const aos::HandoffIssue &issue : result.issues) {
        if (issue.kind == aos::HandoffIssueKind::HeaderWriteFailed) {
            header_failed = true;
        }
        if (issue.kind == aos::HandoffIssueKind::DeliveryRemoveFailed) {
            remove_failed = true;
        }
    }
    CHECK(header_failed);
    CHECK(remove_failed);
    // 批本身確實發布了（那一步沒失敗），致命的是「這一輪會被無限重播」。
    CHECK(result.published);
}

// 唯一暫存名（§D-5）：批的 `.temp` 用每行程唯一的名字寫，寫完才 rename 進固定
// 槽位。世界目錄不可寫時第一步就失敗，result.path 正好把那個唯一名露出來，
// 可以驗它的形狀確實是 §B-1 的 <名字>.<副檔名>.<狀況>。
TEST_CASE("aggregate writes the batch through a per-process unique temp name") {
    TempDir dir;
    const std::string base = dir.path + "/inst.json";
    const std::string inbox = dir.path + "/inst.tempd";
    REQUIRE(std::filesystem::create_directory(inbox));
    write_file(inbox + "/10.json", R"({"argv":["work"]})");
    REQUIRE(chmod(dir.path.c_str(), 0500) == 0);

    if (access(dir.path.c_str(), W_OK) == 0) {
        REQUIRE(chmod(dir.path.c_str(), 0700) == 0);
        SUCCEED("running as root: chmod 500 is not enforced, nothing to assert");
        return;
    }

    aos::HandoffResult result;
    const aos::HandoffState state = aos::aggregate_instructions(base, result);
    REQUIRE(chmod(dir.path.c_str(), 0700) == 0);

    REQUIRE(state == aos::HandoffState::PublishWriteFailed);
    const std::string name =
        std::filesystem::path(result.path).filename().string();
    // inst-<pid>-<seq>.json.temp：權杖插在最後一個 .json 之前，不是接在 .temp 後。
    CHECK(name.starts_with("inst-"));
    CHECK(name.ends_with(".json.temp"));
    CHECK(name != "inst.json.temp");  // 固定槽位是另一個檔
    CHECK(result.path == dir.path + "/" + name);
}
