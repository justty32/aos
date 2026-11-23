Nine choices an org makes once: answer each here, then write the answer where the other files say `CHOICE n`.

# Choices

Working orgs differ in exactly these places. No answer is the right one; each line under "pick" says when it fits. Write your answer after **Ours:** and keep this file as the record of what was chosen and who chose it (the user, or a proposal the user has not confirmed).

## 1. What body does the lead have?

- **A coding CLI (an eca).** It has the CLI's own tools, can look at images, and can start its own subagents. Pick it when the lead reads much code or checks pictures.
- **An agent-fsm.** It has only the aos tools you give it and asks its brain through the llm kernel. Pick it when the work is documents and letters and the tool set should stay small.

**Ours:** <...>

## 2. Are the seats always attached?

- **Always attached, restarted when they exit.** Each seat keeps its conversation. Pick it when work comes all the time and seats talk back and forth.
- **Attached when there is work.** The seat is its card and its notes; while it is not attached, the lead sends a stand-in that reads the card and the notes first and writes what it learned back before it stops. Pick it when work comes now and then. A seat attached as the lead's subagent counts against the lead's limit of subagents even while it sleeps.
- **Made for one batch and removed.** Pick it when each batch needs the user's go-ahead and nothing should carry over from the last batch.

**Ours:** <...>

## 3. How are the seats cut?

- **By what they may write.** One seat owns one folder. Two seats never write the same file, and no seat exists only to pass work on.
- **By the stage of the work.** Design, build, review, test, integrate. Pick it when every change must pass the same line of checks.

Open a seat only when it has paths of its own and rules that must outlive one job. Everything else is a single job the lead gives out.

**Ours:** <...>

## 4. Who commits?

- **One seat is the only gate.** It commits what has passed the checks and changes no content. Pick it with seats cut by stage.
- **Each seat commits inside its own paths and reports afterwards.** It asks the lead first when the change leaves its paths, removes files, or touches running agents. Pick it with seats cut by what they write.
- **Only the lead.** Pick it when the shared files have one writer anyway.

**Ours:** <...>

## 5. How is work checked by someone who did not do it?

- **A standing review seat** (and a test seat) that every change passes.
- **A checker for each batch**, a different instance from the writer, that reads the sources and not the writer's own account; at most <N> rounds, then stop and tell the user.
- **The lead checks the evidence**; a second pair of eyes is a single job when asked for.

**Ours:** <...>

## 6. What do you do about a change you did not make?

- **Outside your paths it is expected; inside your paths, stop and ask the lead.** Pick it when several seats work in one checkout at once.
- **Anything the request did not list: stop and ask.** Pick it when a wrong write is costly and few agents work at a time.

**Ours:** <...>

## 7. Where do throwaway files and a seat's own notes go?

- **Throwaway files:** a folder outside version control, written here as `<TEMP>`: a path outside the repo, or an ignored `temp/` inside the seat's own folder. It may be cleaned at any time; what must stay is moved into `wf/`.
- **Notes:** a seat that is not always attached needs a notes file that the next one in the seat reads first. Say where it is, or say that seats keep no notes and put them in their replies.
- **Lasting output** (checklists, specs, ledgers): in `wf/org/<SEAT>/assets/`, or in the seat's own folder. Pick one.

**Ours:** <...>

## 8. May a seat start subordinates, or improve itself when idle?

- **No.** Only the lead starts agents.
- **Yes, with rules.** A subordinate gets a definition made for it with only the tools the job needs, and none that could give it more (changing its own tools, starting agents, making definitions); its request names what it may read and write; the reply says who was started, what they did, and that they are gone. Improvements come only from things done at least twice, one per idle period, logged, and they stop when real work arrives.

**Ours:** <...>

## 9. Where do the definitions live, and are they copies?

- **Where:** next to the org (`wf/org/defs/<SEAT>/`), in a folder for aos settings (`wf/aos/defs/<SEAT>/`), or nowhere: several seats use one stock template and only their cards differ.
- **Copy or link:** a definition that links to the stock agent-fsm programs is small and follows aos when it is updated; a full copy keeps working unchanged and must be updated by hand.

Either way the system text only names the seat and the files to read first. The card is the one place where duties are written.

**Ours:** <...>
