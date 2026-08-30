#include <aos/tool.hpp>

#include "test_support.hpp"

#include <catch2/catch_test_macros.hpp>

TEST_CASE("tool probe accepts structured metainfo") {
    aos::tool::test::TempWorld world("probe-meta");
    const auto script = world.write_script(
        "fake-metainfo.sh",
        "#!/bin/sh\n"
        "if [ \"$1\" = \"--metainfo\" ]; then\n"
        "  echo '{\"description\":\"假的自述工具\",\"args\":\"list\","
        "\"predictability\":\"low\"}'\n"
        "  exit 0\n"
        "fi\n"
        "exit 2\n");
    const aos::tool::Probe probe =
        aos::tool::probe_metainfo({script.string()});
    CHECK(probe.ok);
    CHECK(probe.source == "metainfo");
    CHECK(probe.description == "假的自述工具");
    CHECK(probe.spec.args == "list");
    CHECK(probe.spec.predictability == "low");
}

TEST_CASE("tool probe falls back to the first text header") {
    aos::tool::test::TempWorld world("probe-header");
    const auto script = world.write_script(
        "fake-header.sh", "#!/bin/sh\nprintf '第一行說明\\n第二行\\n'\n");
    const aos::tool::Probe probe =
        aos::tool::probe_metainfo({script.string()});
    CHECK(probe.ok);
    CHECK(probe.source == "header");
    CHECK(probe.description == "第一行說明");
}

TEST_CASE("tool probe reports failing and missing executables without throwing") {
    aos::tool::test::TempWorld world("probe-fail");
    const auto script = world.write_script("fake-fail.sh", "#!/bin/sh\nexit 3\n");
    aos::tool::Probe failed;
    CHECK_NOTHROW(failed = aos::tool::probe_metainfo({script.string()}));
    CHECK_FALSE(failed.ok);
    CHECK_FALSE(failed.detail.empty());

    aos::tool::Probe missing;
    CHECK_NOTHROW(missing = aos::tool::probe_metainfo(
                      {(world.path / "not-there").string()}));
    CHECK_FALSE(missing.ok);
    CHECK_FALSE(missing.detail.empty());
}
