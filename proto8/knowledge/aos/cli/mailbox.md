# Mailbox for humans

Use aos-mailbox to read and send mailbox letters from a shell. Your own stack is `-s STACK`, default `~/.aos/stack` (`$AOS_LINUX_USER_STACK` changes it; set it to the user zone `~/.aos/user`, see `aos/user_zone.md`, and use `aos-user`, not `aos-mailbox read`, for the letters waiting there).

```sh
aos-mailbox where                         # your mailbox folder
aos-mailbox peek                          # letters waiting
aos-mailbox read [--all] [--keep | --drop] [--keep-to FILE]   # --keep-to: append one JSON line per letter to FILE
aos-mailbox send --to bob [-d DAEMON] --status REQUEST --title "one line" "what to do"
aos-mailbox send --box PATH --status DONE --title "one line" "the answer"   # WHAT `-` reads stdin
aos-mailbox send ... --keep-to FILE ...  # also append one JSON line for the sent letter to FILE
```

STATUS words and answering rules are the same as for agents: `aos/mailbox.md#/Mailbox rules`.

read exits 10 when there is no letter. A user-zone letter is archived even without `--keep`; `--drop` removes it instead (`--keep` and `--drop` exclude each other). send also takes `--outputs TEXT`, `--not-done TEXT`, `--decide TEXT`, `--in-reply-to LETTER` and `--from NAME` (default `$USER`). `peek` and `read` take `-j`. Codes: `StatusBad`, `MailboxMissing`/`MailboxBad` (`--box` is not a mailbox), `InstanceMissing` (`--to` has no stack), `StackMissing`, `LaunchFailed`, `CommandFailed`, `WriteFailed`, `CommandUnknown` (see aos/errors.md). More flags: run `aos-mailbox --help`.