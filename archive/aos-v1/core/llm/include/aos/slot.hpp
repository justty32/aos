#pragma once

#include <aos/export.h>

#include <filesystem>
#include <optional>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

namespace aos::llm {

/* 取槽等到逾時（或該 CPU 上限為 0）。呼叫者的約定：stderr 印一行
   waiting-llm，exit 75（EX_TEMPFAIL）；這不算失敗，下回合再來。 */
class AOS_API WaitingLlm : public std::runtime_error {
public:
    explicit WaitingLlm(const std::string &message);
};

struct CpuLimit {
    /* 沒有設定＝不限＝完全不取槽（維持現狀）。 */
    std::optional<int> max_inflight;
    long wait_ms = 60000;
};

/* $AOS_HOME，否則 $HOME/.aos。 */
AOS_API std::filesystem::path aos_home();

/* folder 是「世界資料夾」；空的話從 $AOS_FOLDER，否則從 cwd 往上找最近
   含 .aos/ 的目錄，再否則 cwd。 */
AOS_API std::filesystem::path resolve_world(
    const std::filesystem::path &folder = {});

/* 使用者層 <aos_home>/cpus.json（權威）與世界層 <world>/.aos/llm.json 合併。 */
AOS_API CpuLimit read_limit(std::string_view cpu,
                            const std::filesystem::path &folder = {});

/* 持有中的槽。解構或 release() 時放掉；行程死掉核心自動放。 */
class AOS_API Slot {
public:
    Slot() = default;
    ~Slot();
    Slot(Slot &&other) noexcept;
    Slot &operator=(Slot &&other) noexcept;
    Slot(const Slot &) = delete;
    Slot &operator=(const Slot &) = delete;

    /* true＝真的佔了一個槽；false＝該 CPU 沒設上限，空 guard。 */
    bool held() const noexcept;
    /* 佔到第幾號槽（0..N-1）；沒佔＝-1。 */
    int index() const noexcept;
    void release() noexcept;

    /* 內部用。 */
    Slot(int descriptor, int index) noexcept;

private:
    int descriptor_ = -1;
    int index_ = -1;
};

/* 取一個 cpu 的槽。沒設上限＝直接回傳空 Slot（不佔、不等、不建目錄）。
   槽滿就排隊：priority 大者先，同優先度依到達時間；等超過 wait_ms 丟
   WaitingLlm。max_inflight <= 0 立刻丟 WaitingLlm。 */
AOS_API Slot acquire(std::string_view cpu, int priority = 0,
                     const std::filesystem::path &folder = {});

struct SlotStatus {
    std::string cpu;
    int max_inflight = 0;
    int held = 0;
    int waiting = 0;
    long wait_ms = 0;
};

/* 所有「有設上限」的 CPU 目前的佔用／等待，依 cpu 名排序。 */
AOS_API std::vector<SlotStatus> slot_status(
    const std::filesystem::path &folder = {});

}  // namespace aos::llm
