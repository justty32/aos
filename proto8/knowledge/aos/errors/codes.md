# Error codes

What each Code ending means and what to do.

The Code is the word right after `error: `. Its ending:

| ending | meaning | what to do |
|---|---|---|
| `...Bad` | something you gave is malformed or not allowed (`ArgumentsBad`, `PathBad`, `RequestBad`, `NameBad`) | fix the argument and retry once |
| `...Missing` | something that should exist does not (`PathMissing`, `FileMissing`, `WsMissing`, `DaemonMissing`, `AnswerMissing`, `BudgetMissing`) | create it, wait for it, or report that it is not there. Do not retry blindly |
| `...Unknown` | a name was not found in a list (`OpUnknown`, `FlagUnknown`, `CommandUnknown`, `ChildUnknown`, `EndpointUnknown`, `ToolUnknown`) | list what exists, then use a name from the list |
| `...Failed` | an action was attempted and failed (`WriteFailed`, `LaunchFailed`, `EndpointFailed`, `CommandFailed`) | usually environmental; retry once, then report |
| `...Exists` | something with that name is already there (`ToolExists`, `InstanceExists`, `AgentExists`, `LetterExists`) | do not overwrite. Pick another name; use `override` only if you mean to replace |
| `...Rejected` | a gatekeeper said no (`AddRejected`, `CtlRejected`) | this is a decision. Adapt (remove something, ask for less) or report. Never loop |
| `...Internal` | a bug in the program | report it with the full line |

The Codes you will meet most: sibling node `errors/common`.
