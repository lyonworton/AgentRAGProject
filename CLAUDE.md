# CLAUDE.md

## 1. GateGuard Preflight Rule

Before calling Edit / Write / Bash, **always complete the following preflight checks proactively**. Do NOT wait for GateGuard to block you before doing them.

### Before Edit
1. Grep for all files that import/require the target file
2. List the public functions/classes/exports affected by this change
3. If the file reads/writes data, note field names, structure, and date format (use redacted or synthetic values — never paste raw production data)
4. Quote the user's current instruction verbatim

### Before Write (new file)
1. Name the file(s) and line(s) that will call this new file
2. Glob to confirm no existing file serves the same purpose
3. If the file reads/writes data, note field names, structure, and date format
4. Quote the user's current instruction verbatim

### Before Bash (first routine command this session)
1. Summarize the current task in one sentence
2. State what this specific command verifies or produces

### Before Bash (destructive: rm -rf, git reset --hard, git push --force, git clean -f, DROP TABLE, DELETE FROM, TRUNCATE, dd)
1. List all files/data this command will modify or delete
2. Write a one-line rollback procedure
3. Quote the user's current instruction verbatim

Present the preflight results as a brief summary, then execute the operation directly.

## 2. Karpathy Guidelines

Behavioral guidelines to reduce common LLM coding mistakes. **Tradeoff:** these bias toward caution over speed. For trivial tasks, use judgment.

### 2.1 Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2.2 Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 2.3 Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it — don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

### 2.4 Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.