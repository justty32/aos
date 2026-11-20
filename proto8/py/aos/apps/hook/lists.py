"""lists - where aos-hook takes the points and the hooks lists from: --points FILE and --list FILE, or --agent DEF_DIR (an agent's own declarations and its two hooks layers).

Design: proto8/thinking/2026-11/20/aos-hook-plan-1120/05 (--agent: the declarations = the hook_points of the definition's
interfaces.json, the lists = the definition's hooks file with the stack copy on top, the agent's own on_clock rules);
12 is what holds. Cut 4 kept the list reading here; cut 2a moved it to aos.hook_lists (used through
aos.hook_point.open) and left this file the choice of source. Raises nothing of its own: errors go to fail(code, sentence).

API:
    source(opts, stack, fail) -> {"points": {name: point}, "lists": [paths], "files": how many declarations,
                                  "entry_check": None or function,
                                  "label": what the points are, for messages, "agent": DEF_DIR or None}
        opts = the shared flags (points, list, agent). --agent with --points or --list = ArgumentsBad.
        --agent: no stack = only the definition's layer (check and points may go without one). A definition
        without hook_points has no points (cut 3 adds them to the definitions).
"""
import os

from aos import hook_point


def agent_hooks():
    """aos.agentlib.hooks, imported only for --agent (a plain fire does not pay for it)."""
    from aos.agentlib import hooks
    return hooks


def _points(fail, read, *args):
    try:
        return read(*args)
    except hook_point.PointsBad as e:
        hook_point.call_fail(fail, "PointsBad", str(e))


def source(opts, stack, fail):
    agent = opts.get("agent")
    if agent is None:
        paths = opts.get("points", [])
        if not paths:
            hook_point.call_fail(fail, "ArgumentsBad", "give at least one --points FILE, or --agent DEF_DIR")
        return {"points": _points(fail, hook_point.read, paths), "lists": opts.get("list", []), "files": len(paths),
                "entry_check": None, "label": ", ".join(paths), "agent": None}
    if opts.get("points") or opts.get("list"):
        hook_point.call_fail(fail, "ArgumentsBad", "give either --agent DEF_DIR or --points / --list, not both")
    if not (agent and os.path.isdir(agent)):
        hook_point.call_fail(fail, "ArgumentsBad", "--agent needs an agent definition folder, got %r" % agent)
    agent = os.path.abspath(agent)
    points = _points(fail, hook_point.for_definition, agent)
    hooks = agent_hooks()
    try:
        layers = hooks.layers(agent, stack or agent)
    except hooks.HooksBad as e:
        hook_point.call_fail(fail, "HooksBad", str(e))
    files = len({said["path"] for point in points.values() for said in point["said"]})
    return {"points": points, "lists": layers if stack else layers[:1], "files": files,
            "entry_check": hooks.check_clock,
            "label": "the hook_points of %s" % os.path.join(agent, "interfaces.json"), "agent": agent}
