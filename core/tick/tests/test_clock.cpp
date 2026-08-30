#include "test_support.hpp"

#include <cstdint>
#include <string>
#include <string_view>
#include <vector>

namespace aos::tick::test {

TEST_CASE("期間只接受正整數與單一單位") {
    std::int64_t seconds = 0;
    REQUIRE(parse_duration("7d", seconds));
    REQUIRE(seconds == 7 * 86400);
    REQUIRE(parse_duration("30m", seconds));
    REQUIRE(seconds == 1800);
    REQUIRE(parse_duration("2s", seconds));
    REQUIRE(seconds == 2);
    REQUIRE(parse_duration("1h", seconds));
    REQUIRE(seconds == 3600);

    for (std::string_view bad : {"0d", "1h30m", "5", "d", "-1d", ""}) {
        REQUIRE_FALSE(parse_duration(bad, seconds));
    }
}

TEST_CASE("時間戳解析位移並能依時區格式化") {
    Instant taipei = 0;
    Instant utc = 0;
    REQUIRE(parse_timestamp("2026-08-30T17:00:05+08:00", taipei));
    REQUIRE(parse_timestamp("2026-08-30T09:00:05Z", utc));
    REQUIRE(taipei == utc);
    REQUIRE(format_timestamp(taipei, "Asia/Taipei") ==
            "2026-08-30T17:00:05+08:00");
    REQUIRE(format_timestamp(taipei, "UTC") ==
            "2026-08-30T09:00:05+00:00");

    for (std::string_view bad : {"2026-8-30T09:00:05Z",
                                 "2026-08-30 09:00:05Z",
                                 "2026-02-30T09:00:05Z",
                                 "2026-08-30T24:00:00Z",
                                 "2026-08-30T09:00Z",
                                 "2026-08-30T09:00:05+8:00"}) {
        REQUIRE_FALSE(parse_timestamp(bad, utc));
    }
}

TEST_CASE("無位移時刻以指定時區往返") {
    Instant at = 0;
    REQUIRE(parse_at("2026-09-01 17:00", "Asia/Taipei", at));
    REQUIRE(format_at(at, "Asia/Taipei") == "2026-09-01 17:00");
    REQUIRE_FALSE(parse_at("2026-9-1 5:00", "Asia/Taipei", at));
    REQUIRE_FALSE(parse_at("2026-09-01T17:00", "Asia/Taipei", at));
    REQUIRE_FALSE(parse_at("2026-13-01 00:00", "Asia/Taipei", at));
}

TEST_CASE("UTC epoch 轉台北當地時間含 ISO 星期") {
    // 1788080400 是 2026-08-30 09:00 UTC；台北加八小時，該日為週日。
    LocalTime local;
    std::string error;
    REQUIRE(to_local(1788080400, "Asia/Taipei", local, error));
    REQUIRE(local.year == 2026);
    REQUIRE(local.month == 8);
    REQUIRE(local.day == 30);
    REQUIRE(local.hour == 17);
    REQUIRE(local.minute == 0);
    REQUIRE(local.second == 0);
    REQUIRE(local.weekday == 7);
}

TEST_CASE("時區名稱驗證會攔住例外") {
    REQUIRE(valid_zone("Asia/Taipei"));
    REQUIRE_FALSE(valid_zone("Nowhere/Nope"));
}

TEST_CASE("識別碼字集長度與撞名尾碼") {
    REQUIRE(valid_id("Abc_09.ok-name"));
    REQUIRE(valid_id(std::string(64, 'a')));
    REQUIRE_FALSE(valid_id(""));
    REQUIRE_FALSE(valid_id("bad/id"));
    REQUIRE_FALSE(valid_id("含中文"));
    REQUIRE_FALSE(valid_id(std::string(65, 'a')));

    const std::string first = make_id("r", 123456, {});
    REQUIRE(first.starts_with("r-"));
    const std::vector<std::string> taken{first, first + "-2"};
    REQUIRE(make_id("r", 123456, taken) == first + "-3");
}

}  // namespace aos::tick::test
