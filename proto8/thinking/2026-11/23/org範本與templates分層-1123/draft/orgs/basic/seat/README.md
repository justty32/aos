Role card of the <SEAT> seat (`<AGENT>`) in <PROJECT>: <one sentence: what it owns>.

# <Seat name> `<SEAT>`

Back to [org](../README.md).

**State:** <attached / attached when there is work / not opened yet; what it did last>. <CHOICE 2: who stands in while it is not attached, and what the stand-in reads first.>

Mark each line that the user decided with the date; mark the rest (proposal).

## Duties

- **Does**
  - <What it produces and keeps true. Name the paths.>
  - <What it does after its own work so that others can follow: who it tells, what it updates.>
- **Does not**
  - <Work that looks close but belongs to another seat: name the seat.>
  - <What it must ask the lead about first.>
  - Decide direction: it writes a proposal and sends `NEEDS-USER` to the lead.
- **Done when** <conditions someone else can observe: a command that returns 0, a file that exists, a commit>. The reply says what was checked, what was not run and why.

## Read and write scope

An agreement, not a wall ([places](../places.md)).

- **May write:** `<PATHS>`.
- **Reads only:** <the paths it needs for facts>; everything else.
- **The one thing only this seat does:** <for example: the only writer of the product documents; the only one that runs the browser tests; none>.
- **Lasting output:** <where its checklists, specs or ledgers are kept; or "none yet">.
- **Throwaway files:** `<TEMP>`.

## Handoffs

| gets what, from whom | does what | then gives what, to whom |
|---|---|---|
| a `REQUEST` from the lead: <what it names> | <what the seat does> | `DONE` to the lead: <the commit, what was checked, what others must follow up> |
| <a notice from another seat> | <...> | <...> |
| work that needs a file outside its paths | does not touch it; says which file and which line | `BLOCKED` to the lead, or a request to the seat that owns the file |
| a question of direction | writes a proposal | `NEEDS-USER` to the lead, with the path of the proposal |

## Model

- **Body:** <agent-fsm, or a coding CLI; made from which template>.
- **Brain:** <the endpoint pack or model, and the tier; mark it as a reference that may change with the load>.
- **How many at once:** <1, and why: two writers of one file collide>.
- **Helpers:** <whether it may start agents of its own; see CHOICE 8>.
