# Working instructions

- Before planning or implementing a roadmap stage, read [agent.md](agent.md) and [memory.md](memory.md).
- `agent.md` defines scope, stage order, and acceptance criteria. `memory.md` records verified progress and the next handoff.
- Work on the stage requested by the user. Do not automatically start another stage or expand scope.
- Target structured MCP workflows without user-authored Python or `execute_python` fallbacks. Internal Python implementation and test harnesses remain allowed.
- FEM is out of scope. CAM and BIM are separate, explicitly activated expansion stages.
- Preserve existing workspace changes and user FreeCAD documents. Do not restart the user's FreeCAD session without approval.
- At the end of each stage or partial stage, update `memory.md` with implemented changes, exact verification results, remaining gaps, and the next entry point. Never label untested work as complete.
- Follow the per-stage verification and handoff rules in `agent.md`. A new chat must not assume an old FreeCAD process, connection, or interpreter is still active.
