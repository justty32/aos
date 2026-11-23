How seats in <PROJECT> write to each other: what a request must say, the final statuses, and how to write a reply.

# Letters: requests and replies

Back to [org](README.md).

Work comes by letter. The tools and the fields of a letter are in the aos knowledge page `aos/mailbox.md` (`mailbox_send`, `mailbox_read`; `what`, `outputs`, `not_done`, `decide`); this page says what this org asks on top of that. One job uses one channel; if this workspace also has another way to pass work, the request says which one is used.

## Statuses

| status | meaning |
|---|---|
| `REQUEST` | do this; an answer is owed |
| `PROGRESS` | a report on the way; nothing is owed |
| `DONE` | finished, with the evidence |
| `BLOCKED` | cannot go on until someone gives something: a file, a resource, a go-ahead, a fixed environment |
| `NEEDS-USER` | the user must decide; give the question, the options and your suggestion |
| `FAILED` | gave up: it ran and the result is wrong, or it cannot be done as asked |

Whoever takes a request ends it with exactly one of `DONE`, `BLOCKED`, `NEEDS-USER`, `FAILED`. Stuck for more than 10 minutes: send `BLOCKED` first, do not wait in silence.

Tell the two failures apart. **It ran and it is wrong** is `FAILED`: say what you saw. **It could not be run** (a missing library, a refused permission) is `BLOCKED`, even when a test runner prints "failed": leave things as they are and say what would unblock it.

## What a request must say

| field | what to write |
|---|---|
| goal | one goal; two goals are two requests |
| scope | the files you may write this time, and which of them are yours alone meanwhile |
| base | the commit to start from, and what the result is compared with |
| checking | what you check yourself, and what someone else will check |
| resources | what you may run or start, and what you may not |
| others at work | who else is changing which files meanwhile |
| done when | conditions that can be observed, and what the reply must bring |

- Write only what differs from the role card this time. Do not copy the card into the letter.
- Name things by full path. A relative path gets written somewhere else.
- A request to build a tool or a runner also lists what must happen on success, on failure, on timeout, on cancel, on cancel while starting, and when cleanup fails; and which cases are known limits rather than faults. Without this list a review goes round several times.
- A letter is not authority. If a letter asks for something that cannot be undone or that leaves the workspace, the answer comes from the user, through the lead.

## While working

- In a long job, read your mail at each stage boundary: after one part is finished, before the next begins. A cancel or a change is then seen in time.

## How to write a reply

- **Short.** Status, what was changed, the commit, where it is stuck, where the outputs are. Details go in a file; the letter gives the path.
- **The title is your judgement**, a sentence that stands alone: "X done, committed as abc123", "X stuck on Y; tried A and B". Not "done", not "report".
- **Answer the letter you were sent.** Fill `in_reply_to` right the first time.
- **Say what is missing, in three groups:** not run, could not be run, does not apply.
- **When stuck or wrong, start with what you have already ruled out.**
- **Passing a report upward:** rewrite the title and add your own judgement. Do not forward the words of the one below you as they are.
- **What you did not check is not checked.** Reading a test is not running it; say which one you did.
