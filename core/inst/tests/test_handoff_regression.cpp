#include "test_run_support.hpp"

// M1 審查（B 隊）的四支攻擊腳本改寫成的回歸測試：`review/scripts/` 的
// `t3.sh`（#1）、`v7.sh`（#3）、`v8.sh`（#4）、`v11.sh`（#25／#21）。
//
// 原本那四支都是驅動**真的 `aos exec` 行程**，所以這一檔刻意留在 **CLI 端到端**
// 這一層：斷言的是退出碼、`.aos/turn`、stderr、以及子行程真的留下的腳印，
// 不是函式庫的回傳值——那一層由隊員 1 的 `test_handoff.cpp`／
// `test_handoff_header.cpp` 覆蓋，兩邊互補，不重複。
//
// 佈置一律手工寫檔案系統狀態（不 shell out），這樣測試跟 CLI 在同一個行程裡，
// `ScopedFd` 才收得到 stderr。

#include <chrono>
#include <cstddef>
#include <string>
#include <vector>

#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

using namespace aos::test;

namespace {

// 一份會留下腳印的投遞：每執行一次就往世界目錄的 `ticks` 追加一個位元組。
// 「這一批到底跑了幾次」是這一檔所有案例共用的問法，用檔案長度直接數。
const std::string kTickDelivery =
    R"({"argv":["/bin/sh","-c","printf t >> ticks"]})";

std::size_t ticks(const TempDir &dir) {
    return read_file(dir.path + "/ticks").size();
}

std::string head_path(const TempDir &dir) {
    return dir.path + "/.aos/inst-head.json";
}

std::string inbox_path(const TempDir &dir) {
    return dir.path + "/.aos/inst.tempd";
}

// 從 header 位元組裡抓頂層 `"id":"…"`。這裡的 header 都是彙整層剛寫出來的正常
// 版面，不需要跟 `decode_header_id` 一樣防巢狀。
std::string header_id(const std::string &header) {
    const std::string key = "\"id\":\"";
    const std::size_t start = header.find(key);
    REQUIRE(start != std::string::npos);
    const std::size_t from = start + key.size();
    const std::size_t end = header.find('"', from);
    REQUIRE(end != std::string::npos);
    return header.substr(from, end - from);
}

// 彙整層寫出來的版面（`handoff_header.cpp` 的 `encode_header`）。
std::string make_header(const std::string &id, bool swept) {
    return R"({"version":1,"id":")" + id +
           R"(","origin":"aggregated","result":null,"swept":)" +
           (swept ? "true" : "false") + "}\n";
}

// 跑一輪 exec 並把 stderr 收進檔案。
int exec_capturing(TempDir &dir, std::string &captured_text) {
    const std::string captured = dir.path + "/stderr.txt";
    int status = 0;
    {
        ScopedFd err(STDERR_FILENO, captured, O_WRONLY | O_CREAT | O_TRUNC);
        status = exec_world(dir.path);
    }
    captured_text = read_file(captured);
    return status;
}

// #3 修補之前是**永久阻塞**（`open` 在沒有寫端的 FIFO 上不回來）。ctest 沒有
// per-case timeout，所以自己架看門狗：真的退回阻塞行為時讓行程被 SIGALRM 砍掉
// （測試明確失敗），而不是把 CI 掛住。
class Watchdog {
public:
    explicit Watchdog(unsigned seconds) { alarm(seconds); }
    ~Watchdog() { alarm(0); }
};

}  // namespace

// ── #1：批被消化之後，同名同內容的**全新**投遞 MUST 照常執行 ────────────────
//
// 原始證據 `scripts/t3.sh`：固定檔名的生產者連投三回合同一份內容，實測
// `ticks=1 turn=1` 卡在第一輪——第 2、3 輪的投遞被 unlink、批不發布、
// **退出碼 0、stderr 一個字都沒有**。整份審查裡最貴的一條就是這個無聲丟批。

TEST_CASE("#1 固定檔名的生產者連投三回合，三回合都真的執行", "[run][handoff]") {
    TempDir dir;
    REQUIRE(init_world(dir.path) == 0);
    const std::string delivery = inbox_path(dir) + "/1000-0.json";

    for (int round = 1; round <= 3; ++round) {
        INFO("round " << round);
        write_file(delivery, kTickDelivery);

        std::string captured;
        CHECK(exec_capturing(dir, captured) == 0);
        CHECK(captured.empty());
        // 三回合都真的跑了：ticks 與 turn 一起往前，不是只有第一輪。
        CHECK(ticks(dir) == static_cast<std::size_t>(round));
        CHECK(read_file(dir.path + "/.aos/turn") ==
              std::to_string(round) + "\n");
        CHECK_FALSE(std::filesystem::exists(delivery));
        // 每一輪收尾都把 header 標成 swept（§C-8）——那正是下一輪能再發布的閘門。
        CHECK(read_file(head_path(dir)).find("\"swept\":true") !=
              std::string::npos);
    }
}

// 反向（同一條的另一半）：header 還沒 swept ＝ 上一輪的清理沒走完，那一組殘留
// 投遞 MUST NOT 二次發布。修補只把「已 swept」這個閘門打開，沒有把 §D-6 的保護
// 拆掉——這一條就是釘住「沒拆掉」。
TEST_CASE("#1 反向：header 未 swept 時同一組殘留投遞不重跑", "[run][handoff]") {
    TempDir dir;
    REQUIRE(init_world(dir.path) == 0);
    const std::string delivery = inbox_path(dir) + "/1000-0.json";
    write_file(delivery, kTickDelivery);
    REQUIRE(exec_world(dir.path) == 0);
    REQUIRE(ticks(dir) == 1);

    // 手工佈置「發布成功、投遞還沒清完」那個崩潰現場：header 退回 swept=false，
    // 同一組投遞（同名同內容、恰好整組）原封不動躺回 inbox。
    const std::string id = header_id(read_file(head_path(dir)));
    write_file(head_path(dir), make_header(id, false));
    write_file(delivery, kTickDelivery);

    std::string captured;
    CHECK(exec_capturing(dir, captured) == 0);
    CHECK(ticks(dir) == 1);  // 沒有第二次副作用
    CHECK(read_file(dir.path + "/.aos/turn") == "1\n");
    // 去重命中是 §D-4 三個「本輪處理完成」例外之一：殘留照清，只是不發布。
    CHECK_FALSE(std::filesystem::exists(delivery));
    CHECK_FALSE(std::filesystem::exists(dir.path + "/.aos/inst.json"));
    CHECK(header_id(read_file(head_path(dir))) == id);
}

// ── #3：收件匣裡的 FIFO 不得讓一整輪停擺 ────────────────────────────────────
//
// 原始證據 `scripts/v7.sh`：`exec 退出碼=124 耗時=10s`（被 timeout 砍掉），連同
// 一份完全正常的投遞都沒被處理，而且鎖都還沒拿到、stderr 全空——後續 exec 一個個
// 疊上去一起卡（實測 6 個行程）。收件匣是 §D-3 明定的公開介面，任何生產者的 bug
// 都能這樣癱瘓整台機器。

TEST_CASE("#3 收件匣裡的 FIFO 不會讓 exec 卡死", "[run][handoff]") {
    TempDir dir;
    REQUIRE(init_world(dir.path) == 0);
    const std::string fifo = inbox_path(dir) + "/pipe.json";
    REQUIRE(mkfifo(fifo.c_str(), 0666) == 0);
    write_file(inbox_path(dir) + "/zz-ok.json", kTickDelivery);

    Watchdog dog(60);
    const auto started = std::chrono::steady_clock::now();
    std::string captured;
    const int status = exec_capturing(dir, captured);
    const auto elapsed = std::chrono::steady_clock::now() - started;

    CHECK(status == 0);
    // 修補前這一輪要花掉整個 timeout；現在應該是「一輪 exec 該有的時間」。
    CHECK(elapsed < std::chrono::seconds(20));
    // 正常投遞照跑、照清。
    CHECK(ticks(dir) == 1);
    CHECK_FALSE(std::filesystem::exists(inbox_path(dir) + "/zz-ok.json"));
    // FIFO 原地不動：它不是「內容無效」，§D-8 的 `.bad` 不該貼到它身上。
    CHECK(std::filesystem::exists(fifo));
    CHECK_FALSE(std::filesystem::exists(fifo + ".bad"));
    // 而且不再是靜默的：§D-4 要求噴 warning、繼續處理其餘。
    CHECK(captured.find("pipe.json: DeliveryNotRegular") != std::string::npos);
}

// ── #4：去重比對只認**頂層** id ─────────────────────────────────────────────
//
// 原始證據 `scripts/v8.sh`：手造巢狀 `"result":{"id":…}` 的 header，A 向（巢狀是
// 真 id）把全新的批靜默丟掉，B 向（頂層是真 id、巢狀是假的）去重整個失效而重跑。
// §C-8 明寫 `result` 由 loop 於 M2 寫回，那時這個版面就是常態。

TEST_CASE("#4 巢狀的 id 不參與去重（CLI 端到端）", "[run][handoff]") {
    TempDir dir;
    REQUIRE(init_world(dir.path) == 0);
    const std::string delivery = inbox_path(dir) + "/1000-0.json";
    write_file(delivery, kTickDelivery);
    REQUIRE(exec_world(dir.path) == 0);
    REQUIRE(ticks(dir) == 1);

    const std::string id = header_id(read_file(head_path(dir)));
    const std::string decoy = "0000000000000000";
    REQUIRE(id != decoy);

    struct Layout {
        const char *name;
        std::string header;
        bool expect_rerun;
    };
    const std::vector<Layout> layouts = {
        // A 向：真 id 藏在巢狀物件裡、頂層是假的 → 這不是「這一批的殘留」，
        // 全新的批 MUST 照常發布並執行。
        {"nested id before the real one",
         R"({"version":1,"result":{"id":")" + id + R"("},"origin":"aggregated","id":")" +
             decoy + R"(","swept":false})" "\n",
         true},
        // B 向：頂層才是真 id → 去重 MUST 命中，不得重跑。
        {"nested decoy after the real one",
         R"({"version":1,"result":{"id":")" + decoy + R"("},"origin":"aggregated","id":")" +
             id + R"(","swept":false})" "\n",
         false},
        // C：M1 自己寫出來的版面，行為必須跟 B 一致。
        {"the layout M1 writes itself", make_header(id, false), false},
    };

    std::size_t expected = ticks(dir);
    for (const Layout &layout : layouts) {
        INFO(layout.name);
        // 每一輪都回到同一個現場：批已被取走、同名同內容的投遞躺在 inbox。
        std::filesystem::remove(dir.path + "/.aos/inst.json");
        write_file(delivery, kTickDelivery);
        write_file(head_path(dir), layout.header);

        std::string captured;
        CHECK(exec_capturing(dir, captured) == 0);
        if (layout.expect_rerun) ++expected;
        CHECK(ticks(dir) == expected);
    }
}

// ── #25：`.aos/inst.json` 是斷掉的 symlink ──────────────────────────────────
//
// 原始證據 `scripts/v11.sh`：三回合 `rc=0 stderr=[]`，三份合法投遞一筆都沒跑、
// 全部堆在 inbox、`turn=0`——世界永久卡死而且完全無聲。機制是 aggregate 用
// `lstat`（斷連結也算存在 → 不發布）、claim 用 `open`（跟隨 → ENOENT →
// NoInstruction → rc=0），兩層對「存在」的定義不一致。

TEST_CASE("#25 inst.json 是斷掉的 symlink 時 exec 大聲回 1", "[run][handoff]") {
    TempDir dir;
    REQUIRE(init_world(dir.path) == 0);
    const std::string base = dir.path + "/.aos/inst.json";
    std::filesystem::create_symlink(dir.path + "/nowhere.json", base);
    REQUIRE(std::filesystem::is_symlink(base));
    for (int i = 1; i <= 3; ++i) {
        write_file(inbox_path(dir) + "/d" + std::to_string(i) + ".json",
                   kTickDelivery);
    }

    for (int round = 1; round <= 3; ++round) {
        INFO("round " << round);
        std::string captured;
        // rc=1（不是 0）：「存在但取不走」是錯誤，不是「沒事可做」。
        CHECK(exec_capturing(dir, captured) == 1);
        CHECK(captured.find(".aos/inst.json") != std::string::npos);
        CHECK(captured.find("cannot read") != std::string::npos);
    }
    // 一筆都沒跑、PC 沒動——但投遞也一份都沒被吃掉（堆積 ≠ 遺失）。
    CHECK_FALSE(std::filesystem::exists(dir.path + "/ticks"));
    CHECK(read_file(dir.path + "/.aos/turn") == "0\n");
    for (int i = 1; i <= 3; ++i) {
        CHECK(std::filesystem::exists(inbox_path(dir) + "/d" +
                                      std::to_string(i) + ".json"));
    }

    // 移掉壞 symlink，堆著的三份一次全跑完：卡死期間沒有任何工作遺失。
    REQUIRE(std::filesystem::remove(base));
    CHECK(exec_world(dir.path) == 0);
    CHECK(ticks(dir) == 3);
    CHECK(read_file(dir.path + "/.aos/turn") == "1\n");
}

// ── #21：去重命中時，來路不明的 `.temp` MUST NOT 被扶正執行 ────────────────
//
// 原始證據 `scripts/v11.sh` 的 15d 段：去重命中 ＋ 手動塞一份與這批毫無關係的
// `inst.json.temp` → `log=[GOOD, UNRELATED_GARBAGE]`，等於執行了未經任何驗證
// 來源的批次。修補後 roll-forward 的錨靠**內容**認身分（逐位元比對），名字只是
// 索引。函式庫層由 `handoff does not roll forward a sibling temp that is not
// this batch` 蓋；這裡補的是 CLI 端「那個批到底有沒有被跑掉」。

TEST_CASE("#21 去重命中時不執行無關的暫存殘骸", "[run][handoff]") {
    // 兩個名字都要測：
    //   `.aos/inst.json.temp`        修補前的共用固定槽位（v11.sh 用的就是它，
    //                                在修補前這一份會被扶正並執行掉）
    //   `.aos/inst-9999-0.json.temp` 修補後找錨的形狀（每行程唯一的兄弟暫存，
    //                                可能是同儕正在飛的批）
    const std::vector<std::string> sibling_names = {"/.aos/inst.json.temp",
                                                    "/.aos/inst-9999-0.json.temp"};
    for (const std::string &sibling_name : sibling_names) {
        INFO("sibling: " << sibling_name);
        TempDir dir;
        REQUIRE(init_world(dir.path) == 0);
        const std::string delivery = inbox_path(dir) + "/1000-0.json";
        write_file(delivery, kTickDelivery);
        REQUIRE(exec_world(dir.path) == 0);
        REQUIRE(ticks(dir) == 1);

        const std::string id = header_id(read_file(head_path(dir)));
        write_file(head_path(dir), make_header(id, false));
        write_file(delivery, kTickDelivery);
        // 一份解析得出、但根本不是這一批的殘骸。
        const std::string sibling = dir.path + sibling_name;
        const std::string garbage =
            R"([{"argv":["/bin/sh","-c","printf U >> unrelated"]}])";
        write_file(sibling, garbage);

        std::string captured;
        CHECK(exec_capturing(dir, captured) == 0);
        CHECK_FALSE(std::filesystem::exists(dir.path + "/unrelated"));
        CHECK(ticks(dir) == 1);
        CHECK(read_file(dir.path + "/.aos/turn") == "1\n");
        // 殘骸原封不動：沒被扶正，也沒被當成自己的殘骸刪掉。
        CHECK(read_file(sibling) == garbage);
    }
}

// ── #26：header 寫失敗 ＋ 投遞刪失敗同時發生時，這一輪 MUST 是致命的 ────────
//
// 原始證據 `scripts/v11.sh` 的 X-1 段：三回合 rc 全 0，同一批 log 行數 1→2→3，
// 沒有任何機制會讓它停。函式庫層的回傳值由 `#26 handoff fails the round when
// the header and the sweep both fail` 蓋；CLI 這一側要看的是**退出碼真的變成 1**
// ——rc=0 的無聲重播才是 agent loop 裡最貴的形狀。

TEST_CASE("#26 header 與 sweep 同時失敗時 exec 回 1", "[run][handoff]") {
    TempDir dir;
    REQUIRE(init_world(dir.path) == 0);
    const std::string inbox = inbox_path(dir);
    write_file(inbox + "/1000-0.json", kTickDelivery);
    // header 的固定槽位佔成目錄 → rename 過去必失敗（HeaderWriteFailed）。
    REQUIRE(std::filesystem::create_directory(head_path(dir)));
    // inbox 唯讀可執行 → 投遞 unlink 不掉（DeliveryRemoveFailed）。
    REQUIRE(chmod(inbox.c_str(), 0500) == 0);

    // root 無視權限位元，chmod 500 擋不住寫入——那時這個場景根本不成立。
    if (access(inbox.c_str(), W_OK) == 0) {
        REQUIRE(chmod(inbox.c_str(), 0700) == 0);  // 讓 TempDir 清得掉
        SUCCEED("running as root: chmod 500 is not enforced, nothing to assert");
        return;
    }

    std::string captured;
    const int status = exec_capturing(dir, captured);
    REQUIRE(chmod(inbox.c_str(), 0700) == 0);  // 先還原，TempDir 才清得掉

    CHECK(status == 1);
    CHECK(captured.find("HeaderWriteFailed") != std::string::npos);
    CHECK(captured.find("DeliveryRemoveFailed") != std::string::npos);
    CHECK(captured.find("cannot aggregate") != std::string::npos);
    // 回合沒開始跑（aggregate 就回非 Ok），PC 不動。
    CHECK_FALSE(std::filesystem::exists(dir.path + "/ticks"));
    CHECK(read_file(dir.path + "/.aos/turn") == "0\n");
}

// ── §D-4「不覆蓋、不合併」的確定性佈置 ──────────────────────────────────────
//
// **這個案例驗的是什麼、沒驗到什麼，要說清楚**：
//
// 驗到的是 **§D-4**「`inst.json` 已有一份沒被讀走時本輪 MUST NOT 發布（不覆蓋、
// 不合併）」——手工先放一份佔位的 `inst.json` 再跑一輪：彙整在第 ⓪ 步的 `lstat`
// 就早退，於是新投遞不發布、不清、header 一個位元組都沒動。
//
// **沒驗到的是 §D-5 的排他發布（`EEXIST` 分支）**。`inst.json` 已存在時彙整根本
// 走不到 rename 那一步，所以這裡碰不到 `publish_exclusive` 的 `EEXIST`。那條分支
// 要「兩個彙整者在 `lstat` 與 rename **之間**交錯」才會走到，公開 API 無法確定性
// 觸發（沒有注入點可以把同儕停在窗口中間），只能靠併發壓力覆蓋——見
// `wf/workflows/build-cycle/archive/m1-loop-side/review/scripts/conc.sh`。

TEST_CASE("inst.json 已有一批時彙整放棄且不動 header", "[run][handoff]") {
    TempDir dir;
    REQUIRE(init_world(dir.path) == 0);
    // 佔位的那一批：假裝同儕剛發布、還沒有人取走。
    write_inst(dir, R"({"argv":["/bin/sh","-c","printf P >> placeholder"]})");
    // 連同它的 header 一起佈置——這一輪 MUST NOT 覆寫它。
    const std::string foreign = make_header("ffffffffffffffff", false);
    write_file(head_path(dir), foreign);
    write_file(inbox_path(dir) + "/10.json", kTickDelivery);

    std::string captured;
    CHECK(exec_capturing(dir, captured) == 0);
    // 佔位那一批照跑（取件不受彙整早退影響），但新投遞完全沒被碰。
    CHECK(read_file(dir.path + "/placeholder") == "P");
    CHECK(read_file(inbox_path(dir) + "/10.json") == kTickDelivery);
    CHECK(read_file(head_path(dir)) == foreign);
    CHECK_FALSE(std::filesystem::exists(dir.path + "/ticks"));

    // 槽位空出來了，下一輪才輪到它——工作是延後，不是遺失。
    CHECK(exec_world(dir.path) == 0);
    CHECK(ticks(dir) == 1);
    CHECK_FALSE(std::filesystem::exists(inbox_path(dir) + "/10.json"));
}
