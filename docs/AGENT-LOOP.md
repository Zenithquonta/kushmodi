# Supervisor / coder execution protocol

## Startup

1. Resolve the user's requested Opus 5.5 and Sonnet 5.5 names to the actual models supported by the available runtime. Record the result. Do not assume the names are valid provider API identifiers.
2. Identify the project root. In the originating workspace it is `/workspace/observatory-profile`; after download/extraction or cloning it is wherever `AGENTS.md` and `HANDOFF.md` reside.
3. Read the gate and handoff, inspect the supplied assets, and fetch the current target repository state if GitHub access is available.
4. Establish a baseline with the quality gate. Record existing failures before changing code.
5. Review the ledger, identify dependencies, and select the smallest independent task that can be completed next.

## Roles and budget

The supervisor owns reasoning, decomposition, review, prioritization and final reporting. Delegate ordinary coding and file changes to the cheaper coder. Do not ask the coder to become the supervisor. Do not give a coder a vague instruction such as "finish the whole project" when a specific rendering, verification or content task can be assigned.

Use one coder for a particular file at a time. Independent tasks may be delegated in parallel only when the runtime supports it and their file ownership is disjoint. An animation builder change and GIF export depend on each other; run those sequentially. Writing the final manifest depends on all asset changes; do it last.

Limit a task to three coder/review attempts before documenting why it cannot be completed. Stop early if the blocker is credentials, an unavailable browser or an unavailable required model. Do not retry the same denied GitHub request in a tight loop.

## Assignment contract

The supervisor sends this structure to the coder:

```text
TASK_ID:
OBJECTIVE:
PROJECT_ROOT:
INPUT_FILES:
ALLOWED_FILES_TO_CHANGE:
DO_NOT_CHANGE:
ACCEPTANCE_CRITERIA:
REQUIRED_CHECKS:
KNOWN_FAILURES_OR_CAVEATS:
EXPECTED_RETURN_FORMAT:
```

For example, a T07 assignment should say exactly which interpolation mismatch to address, allow `scripts/build_animation.py` and corresponding tests, require comparison at multiple timeline samples, and defer GIF regeneration until the revised source is accepted. It should not rewrite the name, remake the approved background, modify the AstroFixxer app or broaden into a hosted website.

## Coder return contract

```text
TASK_ID:
STATUS: ready_for_review | blocked
IMPLEMENTED:
FILES_CHANGED:
VERIFICATION_COMMANDS_AND_RESULTS:
VISUAL_EVIDENCE:
KNOWN_LIMITATIONS:
BLOCKERS:
```

The coder must state when a browser or visual check was unavailable. A generated screenshot file must have actually been inspected before it is cited as visual verification.

## Independent supervisor review

The supervisor reads the changed source/diff, runs appropriate checks and looks at the rendering evidence. Check that results match the actual change rather than accepting a list of impressive-sounding commands.

Return one decision:

- `approve`: all task criteria are met and evidence is sufficient; mark the retained ledger entry `done`.
- `revise`: provide specific observed defects and a focused next assignment; increment the attempt count.
- `blocked`: identify the actual external dependency and the attempted operation; stop dependent tasks, continue independent work.

Do not delete the task, its review record, the source artwork or the user's references when marking it complete.

## Loop pseudocode

```text
load gate, handoff, ledger and baseline evidence
resolve supervisor and coder models
while reviewed required tasks remain:
    choose the next dependency-satisfied task
    if task is awaiting review of existing work:
        supervisor independently reviews the existing artifacts first
    else:
        supervisor assigns bounded work to coder
        coder implements and returns evidence
        supervisor independently reviews
    if approved:
        retain task and mark done with evidence
    elif revision is feasible and attempt < 3:
        issue a narrower correction assignment
    else:
        mark blocked and record why
    regenerate dependent outputs only after source edits are accepted
    refresh the asset manifest after final artifact changes
stop when done or only externally blocked tasks remain
report completed work, actual Git state and remaining blockers
```

## Git gate

The user has explicitly authorized pushing the project to the existing repository. Do the necessary review and checks before the push; do not request the same approval again. If GitHub refuses a write, this is an access failure, not an invitation to bypass authentication, force-push, use an unrelated writable repository or claim publication.

Before committing, fetch current HEAD and the current README. If README content changed since the starting source, reconcile it carefully with the user-approved employer removal and observatory rewrite. Preserve unrelated files using a base tree or an ordinary checked-out Git worktree. Publish source artwork, source scripts, final images/SVG/GIF, entry point and handoff together. Use a coherent commit message and verify the remote afterward.

## Runtime adapter

This repository supplies instructions for an agent-capable runtime, not an Anthropic API client or a background daemon. Use the runtime's actual delegation facility for the selected models. No API keys, pretend model IDs, hardcoded CLI syntax, interactive login sequence or unattended external service is embedded here. The startup prompt is deliberately portable across runtimes.
