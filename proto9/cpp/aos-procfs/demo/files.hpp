// files.hpp：aos-procfs-demo 擺出來的有結構的檔（status、settings、attrs）各一張欄位表；純文字與 json 都從這裡生。
#pragma once

#include "aos/procfs.hpp"

#include <optional>
#include <string>

// status 裡信箱的那幾行（不帶 aos_；Embed 進 status、字首 mail_）
#define DEMO_MAIL_FIELDS(F)                          \
    F(long long, waiting, Always)                    \
    F(long long, writing, Always)                    \
    F(long long, bytes, Always)                      \
    F(long long, delivered, Always)                  \
    F(long long, taken, Always)                      \
    F(long long, refused, Always)                    \
    F(long long, dropped_stale, Always)              \
    F(std::string, last_refusal, Always)             \
    F(std::string, refusing, Always)                 \
    F(std::string, last_name, Always)                \
    F(std::optional<long long>, last_bytes, Always)
AOS_RECORD(DemoMailStatus, DEMO_MAIL_FIELDS)

#define DEMO_STATUS_FIELDS(F)                        \
    F(std::string, aos_name, Always)                 \
    F(std::string, aos_phase, Always)                \
    F(long long, aos_pid, Always)                    \
    F(std::string, aos_started_at, Always)           \
    F(aos::procfs::Feedback, aos_ctl_, Embed)        \
    F(DemoMailStatus, mail_, Embed)
AOS_RECORD(DemoStatus, DEMO_STATUS_FIELDS)

// aos_mailbox＝掛了的時候信投到哪（硬碟上的）；demo 沒有，空的（寫 -）。
// aos_obey＝外來登記時 daemon 可以對它下哪幾個字（例 "stop kill"）；沒給 --obey 就整行不寫
#define DEMO_SETTINGS_FIELDS(F)                      \
    F(std::string, aos_persists, Always)             \
    F(std::string, aos_mailbox, Always)              \
    F(std::string, aos_obey, OmitEmpty)
AOS_RECORD(DemoSettings, DEMO_SETTINGS_FIELDS)

#define DEMO_ATTRS_FIELDS(F)                         \
    F(std::string, aos_kind, Always)                 \
    F(std::string, aos_live, Always)                 \
    F(std::string, aos_mailbox, Always)
AOS_RECORD(DemoAttrs, DEMO_ATTRS_FIELDS)
