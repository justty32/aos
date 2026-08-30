#include <aos/tick.hpp>

#include <aos/agent.hpp>
#include <aos/wire.hpp>

#include <exception>
#include <optional>
#include <string>
#include <utility>
#include <vector>

namespace aos::tick {
namespace {

enum class PlanSource { routine, schedule };
enum class PlanKind { error, run, ask, missed };

struct PlanItem {
    PlanSource source;
    PlanKind kind;
    std::size_t index;
    Event event;
    std::string message;
};

std::string instruction_id(const std::string &id, std::uint64_t turn) {
    return "hb-" + id + "-" + std::to_string(turn);
}

std::string join_argv(const std::vector<std::string> &argv) {
    std::string text = "argv:";
    for (const auto &argument : argv) text += " " + argument;
    return text;
}

std::string missed_message(const ScheduleItem &item, Instant now,
                           const Config &config) {
    Instant at = 0;
    parse_at(item.at, config.tz, at);
    const std::string content = item.run.argv.empty()
                                    ? item.run.ask
                                    : join_argv(item.run.argv);
    return "這項行程錯過了：原定 " + format_at(at, config.tz) +
           "，現在是 " + format_at(now, config.tz) + "。\n內容：" +
           content + "\n要補做還是跳過？";
}

std::vector<PlanItem> make_plan(
    const std::vector<Routine> &routines,
    const std::vector<ScheduleItem> &schedule, Instant now,
    const Config &config, const std::optional<std::string> &agent_name,
    std::uint64_t turn) {
    std::vector<PlanItem> plan;
    const std::string agent_target = agent_name.value_or("none");

    for (std::size_t index = 0; index < routines.size(); ++index) {
        const auto &routine = routines[index];
        std::string due_error;
        if (!routine_due(routine, now, config.tz, due_error)) {
            if (!due_error.empty()) {
                plan.push_back({PlanSource::routine, PlanKind::error, index,
                                {"error", routine.id, due_error}, {}});
            }
            continue;
        }
        if (!routine.run.argv.empty()) {
            plan.push_back({PlanSource::routine, PlanKind::run, index,
                            {"run", routine.id,
                             instruction_id(routine.id, turn)},
                            {}});
        } else {
            plan.push_back({PlanSource::routine, PlanKind::ask, index,
                            {"ask", routine.id, agent_target},
                            routine.run.ask});
        }
    }

    for (std::size_t index = 0; index < schedule.size(); ++index) {
        const auto &item = schedule[index];
        std::string state_error;
        const ScheduleState state =
            schedule_state(item, now, config, state_error);
        if (!state_error.empty()) {
            plan.push_back({PlanSource::schedule, PlanKind::error, index,
                            {"error", item.id, state_error}, {}});
            continue;
        }
        if (state == ScheduleState::pending) continue;
        if (state == ScheduleState::missed) {
            plan.push_back({PlanSource::schedule, PlanKind::missed, index,
                            {"missed", item.id, agent_target},
                            missed_message(item, now, config)});
        } else if (!item.run.argv.empty()) {
            plan.push_back({PlanSource::schedule, PlanKind::run, index,
                            {"run", item.id, instruction_id(item.id, turn)},
                            {}});
        } else {
            plan.push_back({PlanSource::schedule, PlanKind::ask, index,
                            {"ask", item.id, agent_target}, item.run.ask});
        }
    }
    return plan;
}

std::vector<Event> planned_events(const std::vector<PlanItem> &plan) {
    std::vector<Event> events;
    events.reserve(plan.size());
    for (const auto &item : plan) events.push_back(item.event);
    return events;
}

Event say_message(const loop::Layout &layout, const PlanItem &item) {
    if (item.event.target == "none") return item.event;
    try {
        agent::say(layout.folder, item.event.target, item.message);
        return item.event;
    } catch (const std::exception &exception) {
        return {"error", item.event.id, exception.what()};
    } catch (...) {
        return {"error", item.event.id, "agent::say 發生未知例外"};
    }
}

}  // namespace

bool run_tick(const loop::Layout &layout, Instant now,
              const TickOptions &options, TickReport &report,
              std::string &error) {
    error.clear();
    report = {};
    try {
        const Paths paths = paths_of(layout);
        Config config;
        if (!read_config(paths.config_file, config, error)) return false;
        if (!valid_zone(config.tz)) {
            error = "時區不合法: " + config.tz;
            return false;
        }

        std::vector<Routine> routines;
        std::vector<ScheduleItem> schedule;
        if (!read_routines(paths.routines_file, routines, error)) return false;
        if (!read_schedule(paths.schedule_file, schedule, error)) return false;

        const std::optional<std::string> agent_name = single_agent(layout);
        const std::vector<PlanItem> plan =
            make_plan(routines, schedule, now, config, agent_name, options.turn);
        if (options.dry_run) {
            report.events = planned_events(plan);
            report.line = format_log_line(now, config.tz, options.turn,
                                          report.events);
            return true;
        }

        bool routines_changed = false;
        bool schedule_changed = false;
        std::vector<bool> remove_schedule(schedule.size(), false);
        const std::string last_run = format_timestamp(now, config.tz);

        for (const auto &item : plan) {
            if (item.kind == PlanKind::error) {
                report.events.push_back(item.event);
                continue;
            }

            Event result = item.event;
            bool succeeded = true;
            if (item.kind == PlanKind::run) {
                const Run &run = item.source == PlanSource::routine
                                     ? routines[item.index].run
                                     : schedule[item.index].run;
                wire::Inst inst;
                inst.id = item.event.target;
                inst.argv = run.argv;
                std::string deliver_error;
                if (!loop::deliver(layout, inst, deliver_error)) {
                    result = {"error", item.event.id, deliver_error};
                    succeeded = false;
                }
            } else {
                result = say_message(layout, item);
                succeeded = result.kind != "error";
            }
            report.events.push_back(std::move(result));
            if (!succeeded) continue;

            if (item.source == PlanSource::routine) {
                routines[item.index].last_run = last_run;
                routines_changed = true;
            } else {
                remove_schedule[item.index] = true;
                schedule_changed = true;
            }
        }

        if (schedule_changed) {
            std::vector<ScheduleItem> remaining;
            remaining.reserve(schedule.size());
            for (std::size_t index = 0; index < schedule.size(); ++index) {
                if (!remove_schedule[index]) {
                    remaining.push_back(std::move(schedule[index]));
                }
            }
            schedule = std::move(remaining);
        }

        report.line =
            format_log_line(now, config.tz, options.turn, report.events);
        if (routines_changed &&
            !write_routines(paths.routines_file, routines, now, config.tz,
                            error)) {
            return false;
        }
        if (schedule_changed &&
            !write_schedule(paths.schedule_file, schedule, now, config.tz,
                            error)) {
            return false;
        }
        if (!append_log(paths.log_file, report.line, error)) return false;
        return true;
    } catch (const std::exception &exception) {
        error = "心跳發生例外: " + std::string(exception.what());
        return false;
    } catch (...) {
        error = "心跳發生未知例外";
        return false;
    }
}

}  // namespace aos::tick
