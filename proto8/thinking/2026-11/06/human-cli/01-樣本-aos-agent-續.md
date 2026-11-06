← [入口](README.md)｜涵蓋：照慣例後 `aos-agent say --help`、`listen --help` 全文｜上一份 [01-樣本-aos-agent](01-樣本-aos-agent.md)｜下一份 [01-樣本-aos-daemon-ctl](01-樣本-aos-daemon-ctl.md)

# 樣本：aos-agent（續）：say、listen

## `aos-agent say --help`

```
aos-agent say - put one message in the agent's queue

usage: aos-agent [--daemon D] say [--target NAME] [WORDS...]
       ... | aos-agent [--daemon D] say [--target NAME]

WORDS are joined with single spaces into one message. No WORDS (or "-") = the whole of
stdin is the message (one trailing newline dropped); stdin being a terminal = ArgumentsBad.
stdout prints the letter name. A paused or sleeping agent still queues it; a warning says so.

flags:
  -t, --target NAME   which agent (default: $AOS_AGENT)
  -h, --help          show this help

exit codes: 0 queued; 1 error (TargetMissing, InstanceMissing, PostFailed...).
```

## `aos-agent listen --help`

```
aos-agent listen - print the agent's answer

usage: aos-agent [--daemon D] listen [--target NAME] [--timeout-s SECS]
       aos-agent [--daemon D] listen [--target NAME] --last N [--follow]

Without --last: wait for the answer to the latest question and print only its text (so
> file and pipes work; notes go to stderr). --last N prints the last N exchanges as blocks:
a line "== #N", the question lines prefixed "> ", then the answer. --follow keeps printing
new ones; Ctrl-C leaves with exit 0.

flags:
  -t, --target NAME   which agent (default: $AOS_AGENT)
  --timeout-s SECS    give up after SECS seconds (AnswerMissing)
  --last N            show the last N exchanges instead of waiting
  -f, --follow        with --last: keep following
  -h, --help          show this help

exit codes: 0 printed; 1 error (AnswerMissing, QuestionUnknown...); 130 Ctrl-C while waiting.
```

