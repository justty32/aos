#include "handoff_test_support.hpp"

#include <aos/inst.hpp>

#include <string>
#include <vector>

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
    CHECK(result.issues.empty());
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
