---
name: claude-certification
description: Use when studying or practicing for the Claude Certified Architect (Foundations) exam across all 5 domains, or when someone asks for certification practice questions, exam prep, or wants to test knowledge of Claude agentic systems, tool design, Claude Code, prompt engineering, or context management.
---

# Claude Certified Architect (Foundations) — Full Exam Practice

## Language

**Default language is English.** Respond in English unless the user explicitly asks to switch to another language. This rule applies to all questions, feedback, and explanations throughout the session.

---

## Exam Overview

| Field | Value |
|---|---|
| Questions | 60 |
| Time limit | 120 minutes |
| Exam fee | $125 USD |
| Passing score | 720/1,000 (scaled) |
| Validity | 12 months |
| Format | Multiple choice; one correct answer, three plausible distractors |
| Structure | 4 scenarios drawn from a bank of 6 |
| Delivery | Online proctored or at a test center |

| Domain | Topic | Weight |
|---|---|---|
| 1 | Agentic Architecture & Orchestration | 27% |
| 2 | Tool Design & MCP Integration | 18% |
| 3 | Claude Code Configuration & Workflows | 20% |
| 4 | Prompt Engineering & Structured Output | 20% |
| 5 | Context Management & Reliability | 15% |

---

## The 6 Official Exam Scenarios

All exam questions are anchored in one of these 6 scenarios. 4 of the 6 appear on any given exam. Know the canonical tool sets and primary domains for each.

| # | Scenario | Canonical Tools / Context | Primary Domains |
|---|---|---|---|
| 1 | **Customer Support Resolution Agent** | `get_customer`, `lookup_order`, `process_refund`, `escalate_to_human` | D1, D2, D5 |
| 2 | **Code Generation with Claude Code** | CLAUDE.md configs, slash commands, plan mode | D3, D5 |
| 3 | **Multi-Agent Research System** | coordinator + web search + doc analysis + synthesis + report agents | D1, D2, D5 |
| 4 | **Developer Productivity with Claude** | `Read`, `Write`, `Bash`, `Grep`, `Glob` + MCP servers | D2, D3, D1 |
| 5 | **Claude Code for CI/CD** | `-p` flag, `--output-format json`, automated PR review | D3, D4 |
| 6 | **Structured Data Extraction** | JSON schemas, `tool_use`, validation-retry loops, `custom_id` | D4, D5 |

---

## Session Format

### On Session Start

1. Greet the user in their language
2. Ask: **"Do you want to practice a specific domain, a specific scenario, or all domains?"**
3. Ask how many questions they want (default: 15)
4. Begin immediately — no teaching upfront

### Question Format

- Present ONE question at a time
- **Scenario-based**: open with the official scenario name (or a scenario-aligned context), then ask what to do
- Options A, B, C, D — one correct, three plausible distractors
- Wait for the user to answer before showing the next question
- Show question number and domain: e.g., **Question 3/15 — Domain 1 (Scenario: Multi-Agent Research System)**

### Answer Distribution Rule — CRITICAL

**You must actively rotate which letter is the correct answer.** Over a 15-question session, target roughly equal distribution: ~4 A, ~4 B, ~3 C, ~4 D. Never let the same letter be correct more than 3 times in a row. Before generating each question, check which letter you've used least recently and bias toward placing the correct answer there.

### Complexity Distribution

Vary difficulty across a session:
- **~30% direct recall**: one concept, direct application (e.g., "what does -p do?")
- **~50% applied scenario**: 2-3 sentence production situation requiring judgment
- **~20% multi-step reasoning**: longer scenario requiring tracing root causes across multiple components; all four options are plausible and require the student to eliminate systematically

### After Each Answer

Show:
1. **CORRECT ✅** or **INCORRECT ❌**
2. **Why the correct answer is right** (2–3 sentences, grounded in the concept)
3. **Why each wrong answer is wrong** — one sentence per distractor explaining the specific flaw

### After All Questions

Show:
- Final score (X/Y)
- List of questions answered incorrectly
- Offer to re-drill weak domains

---

## Domain 1: Agentic Architecture & Orchestration (27%)

### Key concepts to test

**Agentic loop (1.1)**
- Correct termination: check `stop_reason` field — `"end_turn"` = done, `"tool_use"` = continue, `"max_tokens"` = handle truncation
- Anti-pattern 1: checking `if response.content[0].type == "text"` — wrong because model can return text AND tool_use simultaneously
- Anti-pattern 2: checking for natural language signals ("I'm done") — ambiguous and unreliable
- Anti-pattern 3: arbitrary iteration caps as primary stopping mechanism
- Tool results MUST be appended to conversation history before next turn

**Multi-agent orchestration (1.2)**
- Hub-and-spoke: coordinator at centre, subagents never communicate directly
- Critical isolation: subagents do NOT inherit coordinator's history. Everything must be explicit in their prompt.
- Narrow decomposition failure: root cause is always the coordinator's decomposition logic, NOT downstream agents
- The exam tests tracing failures to their origin (coordinator → not web search agent, not synthesis agent)
- Iterative refinement loops: coordinator evaluates synthesis output for gaps, re-delegates with targeted queries

**Subagent invocation (1.3)**
- Coordinator's `allowedTools` must include `"Task"` to spawn subagents — if omitted, subagent spawning fails
- Parallel spawning: emit multiple Task tool calls in ONE coordinator response (faster than separate turns)
- `fork_session`: independent branches from shared baseline — use for divergent approaches (e.g., comparing two strategies)
- Context passing MUST include structured metadata (source URLs, doc names, page numbers) for attribution
- `AgentDefinition`: configure description, system prompt, and tool restrictions per subagent type

**Workflow enforcement (1.4)**
- Prompt-based guidance = probabilistic (non-zero failure rate)
- Programmatic hooks/gates = deterministic (works every time)
- Rule: financial, security, compliance → programmatic. Style/formatting → prompt is fine.
- Programmatic prerequisite: blocks downstream tool call until prerequisite returns a verified value (e.g., block `process_refund` until `get_customer` returns verified customer ID)
- Handoff summaries must be self-contained (human agent has no transcript access)

**SDK Hooks (1.5)**
- `PostToolUse`: fires AFTER tool execution and BEFORE the model processes the result → primary use is data normalization (Unix timestamps → ISO 8601, numeric codes → human-readable strings)
- Tool call interception: fires BEFORE execution → block or redirect based on business rules (e.g., refund > $500 → route to human escalation)
- A single compliance failure → use hook, never a prompt
- The distinction: PostToolUse = transform result in-flight; interception = prevent action entirely

**Task decomposition (1.6)**
- Fixed sequential (prompt chaining): predetermined steps, reliable, cannot adapt — use for predictable multi-aspect reviews
- Dynamic adaptive: generates subtasks from discoveries at runtime, flexible, less predictable — use for open-ended investigation ("add comprehensive tests to a legacy codebase")
- Attention dilution: too many files in one pass → inconsistent depth. Fix: per-file passes + separate cross-file integration pass

**Session management (1.7)**
- `--resume <session-name>`: continue a specific named session when prior context is still valid
- `fork_session`: create independent branches from a shared analysis baseline — use when exploring divergent approaches simultaneously
- Fresh start + summary injection: use when files changed or context is stale
- After code modifications: inform agent of SPECIFIC file changes, not re-explore everything

---

## Domain 2: Tool Design & MCP Integration (18%)

### Key concepts to test

**Tool descriptions (2.1)**
- Descriptions are THE mechanism for tool selection (not supplementary)
- Minimal descriptions ("Retrieves customer information") cause misrouting between similar tools
- Fix for misrouting: expand descriptions. NOT few-shot examples (wrong root cause), NOT routing classifiers (over-engineered first step)
- Good description includes: purpose, input format, example queries, edge cases, explicit "use THIS vs THAT" boundaries, and "when NOT to use" statement
- System prompt keyword conflicts can override well-written descriptions
- Splitting generic tools: `analyze_document` → `extract_data_points`, `summarize_content`, `verify_claim_against_source`

**Error handling (2.2)**
- Four error categories: Transient (retry), Validation (fix input), Business (not retryable, use alternative workflow), Permission (escalate to human)
- Three-field structured error: `errorCategory` + `isRetryable` boolean + human-readable description
- MCP `isError` flag: set to `true` in the tool response to signal a tool-level failure back to the agent
- **CRITICAL exam distinction**: access failure (tool couldn't reach source → consider retry per isRetryable) vs valid empty result (source reached, no matches found → do NOT retry — this is a legitimate success)
- Silent suppression (empty result marked as success) = anti-pattern; prevents recovery
- Workflow termination on single failure = anti-pattern; throws away partial results

**Tool distribution (2.3)**
- Optimal: 4-5 tools per agent, scoped to role — more tools degrades selection reliability
- `tool_choice` options: `"auto"` (model decides whether to call a tool), `"any"` (model MUST call a tool, chooses which), `{"type": "tool", "name": "X"}` (force specific tool)
- **Exam trap**: `"any"` ≠ `"auto"`. `"any"` guarantees a tool call; `"auto"` may return conversational text
- Scoped cross-role tools: give synthesis agent a constrained `verify_fact` instead of routing through coordinator for 85% simple lookups

**MCP configuration (2.4)**
- Project-level: `.mcp.json` in repo root → version-controlled, shared with team
- User-level: `~/.claude.json` → personal, NOT shared via version control
- `${GITHUB_TOKEN}` syntax in `.mcp.json` keeps credentials out of version control
- Use existing community servers first; build custom only for team-specific workflows
- MCP resources: expose content catalogs (issue summaries, doc hierarchies, DB schemas) to reduce exploratory tool calls

**Built-in tools (2.5)**
- `Grep`: searches file CONTENTS — use to find function callers, imports, error messages, patterns
- `Glob`: matches file PATHS — use to find files by extension or naming pattern (`**/*.test.tsx`)
- `Edit`: targeted modification with unique text anchors. Fallback: `Read` + `Write` for full file
- `Bash`: run shell commands, scripts, tests
- Exploration order: Grep entry points → Read to follow imports. Do NOT read all files upfront.

---

## Domain 3: Claude Code Configuration & Workflows (20%)

### Key concepts to test

**CLAUDE.md hierarchy (3.1)**
- User-level (`~/.claude/CLAUDE.md`): only YOU, not version-controlled, NOT shared via git
- Project-level (`.claude/CLAUDE.md` or root `CLAUDE.md`): everyone, version-controlled
- Directory-level: applies when working in that specific directory only
- Exam trap: new team member not getting instructions → root cause is user-level instead of project-level config
- `/memory` command: debugging tool for inspecting what CLAUDE.md files are loaded; use when Claude behavior is inconsistent across sessions
- `@import` syntax: references external files to keep CLAUDE.md modular (e.g., `@import ./rules/testing.md`)
- `.claude/rules/` for topic-specific rule files

**Custom commands and skills (3.2)**
- `.claude/commands/` = project-scoped slash commands, shared via git → use for team-wide workflows
- `~/.claude/commands/` = personal slash commands, not shared
- Skill frontmatter fields: `context: fork` (isolated sub-agent, verbose output stays contained), `allowed-tools` (restricts tool access), `argument-hint` (prompts for parameters when invoked without args)
- `context: fork` use case: codebase analysis, brainstorming, any skill that produces verbose exploratory output
- Skills = on-demand, task-specific. CLAUDE.md = always-loaded, universal standards. Never mix these.

**Path-specific rules (3.3)**
- `.claude/rules/` files with YAML frontmatter `paths:` field containing glob patterns (e.g., `paths: ["**/*.test.tsx"]`)
- **Key advantage over directory CLAUDE.md**: glob patterns activate rules on matching files across the ENTIRE codebase, not just within a specific directory
- Loads ONLY when editing matching files → token efficiency
- Use when conventions must apply to file types spread throughout the codebase

**Plan mode vs direct execution (3.4)**
- Plan mode when: large-scale changes, multiple valid approaches, architectural decisions, multi-file modifications (45+ files)
- Direct execution when: well-understood single-file bug fix, clear limited scope, simple validation addition
- `Explore` subagent: isolates verbose codebase discovery from main conversation context, returns summaries → prevents context bloat during investigation phases
- Common pattern: plan mode for investigation → direct execution for implementation

**Iterative refinement (3.5)**
- Concrete input/output examples beat prose descriptions (2-3 examples covering edge cases)
- Test-driven iteration: write tests first, share failing tests with Claude to guide implementation
- Interview pattern: instruct Claude to ask clarifying questions BEFORE implementing (surfaces cache invalidation strategies, failure modes, etc.)
- Batch feedback when fixes interact; sequential feedback when issues are independent
- Most effective: provide examples of what you want AND examples of what you don't want

**CI/CD integration (3.6)**
- `-p` flag: non-interactive mode. Without it, CI job hangs waiting for input. **This is tested as a specific exam trap.**
- **Exam traps**: the correct flag is `-p`, NOT `--batch`, NOT `CLAUDE_HEADLESS=true`, NOT stdin redirect from `/dev/null`
- `--output-format json`: machine-parseable structured findings for automated CI posting
- Same session that generated code is LESS effective at reviewing it (retains reasoning context, less likely to question own decisions)
- Independent review instance (fresh session, no prior context) catches more subtle issues
- Re-reviews: include prior findings, instruct to report ONLY new/unaddressed issues

---

## Domain 4: Prompt Engineering & Structured Output (20%)

### Key concepts to test

**Explicit criteria (4.1)**
- Vague: "be conservative." Specific: "Flag only when claimed behaviour contradicts actual code. Skip style preferences."
- High false positive rates in ONE category destroy trust in ALL categories
- Fix: temporarily disable high-FP categories while improving prompts for them
- Severity calibration requires actual CODE EXAMPLES, not prose descriptions
- Frame explicit criteria as false-positive reduction mechanisms

**Few-shot prompting (4.2)**
- Most effective technique for consistency — beats more instructions or confidence thresholds
- Deploy when: inconsistent formatting, inconsistent judgment on ambiguous cases, extraction misses existing information
- Construct: 2-4 examples, each showing REASONING for choice over plausible alternatives
- Enables generalisation to novel patterns, not just memorisation
- Include examples of what NOT to extract to reduce false positives

**Structured output with tool_use (4.3)**
- `tool_use` with JSON schema eliminates syntax errors. Prompt-based JSON can produce malformed output.
- `tool_use` does NOT prevent: semantic errors (line items not summing to total), field placement errors, fabrication
- `tool_choice "any"`: must call a tool, chooses which (use when: guaranteed structured output, unknown doc types)
- `tool_choice {type: "tool", name: "X"}`: forced specific tool (use when: ensure a specific extraction runs before enrichment)
- Schema design for fabrication prevention: use optional/nullable fields (`{"type": ["string", "null"]}`) for data that may be absent. "unclear" enum for ambiguous cases. "other" + detail string for extensible categories.
- `strict: true` in tool definition: enforces schema exactly — required fields cannot be null (use when absolutely required; forces model to provide a value)

**Validation-retry loops (4.4)**
- Retry with: original document + failed extraction + specific validation error
- Effective for: format mismatches, structural errors, misplaced values
- NOT effective for: information genuinely absent from source
- `detected_pattern` fields: track what triggered each finding, enables systematic prompt improvement
- Max 3 retry attempts before raising an error

**Batch processing (4.5)**
- Batch API: 50% cost savings, up to 24-hour processing window, no latency SLA
- **Critical constraint**: Batch API does NOT support multi-turn tool calling
- Use Batch API for: latency-tolerant workflows (overnight reports, weekly audits, nightly test generation)
- Use synchronous API for: blocking workflows (pre-merge checks, developer waits for result)
- **Exam trap**: using batch for everything. Keep blocking workflows synchronous.
- Results available for 29 days; match results to requests via `custom_id`

**Multi-instance review (4.6)**
- Same session reviewing its own output = less effective (retains reasoning context, less likely to question decisions)
- Independent instance without prior context catches more subtle issues than self-review instructions
- Per-file local passes + separate cross-file integration pass = prevents attention dilution and contradictory findings
- Confidence-based routing: low-confidence findings → human review. Calibrate with labelled validation sets.

---

## Domain 5: Context Management & Reliability (15%)

### Key concepts to test

**Context preservation (5.1)**
- **Case facts block**: persistent block prepended to every prompt containing transactional specifics (order IDs, `$247.83`, exact amounts). NEVER summarize this block — it must stay verbatim.
- Progressive summarisation trap: compresses specific values ("$247.83 for order #8891") into vague summaries ("a refund was discussed")
- **Lost in the middle effect**: models process beginning and end reliably, middle may be missed. Fix: key summaries at the START, explicit section headers throughout
- Trim verbose tool results to relevant fields BEFORE appending to context
- Upstream agent optimisation: return structured key facts, not verbose reasoning chains

**Escalation and ambiguity (5.2)**
- **Three valid escalation triggers**:
  1. Explicit human request — honor IMMEDIATELY, no investigation first
  2. Policy gap — no rule covers the situation
  3. Inability to make progress after N attempts
- **Invalid triggers**: sentiment/frustration alone, self-reported confidence scores
- Frustration nuance: if issue is straightforward + customer is frustrated → acknowledge + offer resolution. Only escalate if customer REITERATES human preference after you offer help.
- Ambiguous customer match: ask for additional identifiers. Do NOT select based on heuristics (e.g., most recent order, alphabetical first match).

**Error propagation (5.3)**
- Structured error context: failure type + what was attempted + partial results + alternative approaches
- Anti-pattern 1: silent suppression (empty result marked success) → prevents any recovery
- Anti-pattern 2: workflow termination on single failure → throws away partial results
- Access failure vs valid empty result (same concept as Domain 2 — reinforced across domains)
- Coverage annotations: note which findings are well-supported vs which areas have gaps due to unavailable sources

**Codebase exploration (5.4)**
- Context degradation symptom: agent starts referencing "typical patterns" instead of specific class names discovered earlier → context filled with discovery output
- Mitigations: scratchpad files (write findings to file, keep main context clean), subagent delegation (Explore subagent), summary injection before next phase, `/compact` to compress conversation history
- `/compact` use case: when Claude Code context fills up during long sessions — compresses history to free space
- Crash recovery: each agent exports structured state to manifest file; coordinator loads manifest on resume

**Human review and confidence (5.5)**
- 97% overall accuracy can hide 40% error rate on a specific document type
- Always validate by document type AND field segment before automating
- Stratified random sampling of high-confidence extractions detects novel error patterns
- Field-level confidence calibration with labelled validation sets
- Route low-confidence findings to human review; don't rely solely on aggregate accuracy

**Information provenance (5.6)**
- Each finding needs: claim + source URL + document name + relevant excerpt + publication date
- Two conflicting credible sources: annotate BOTH with attribution. Do NOT arbitrarily select one.
- Temporal awareness: different publication dates explain different numbers (not contradictions)
- Coordinator role: detect conflicts, annotate both values with source, let synthesis decide how to reconcile
- Rendering: financial data → tables, news → prose, technical findings → structured lists

---

## Question Generation Guidelines

When generating questions:

1. **Always scenario-based** — open with the official scenario name or a scenario-aligned production context (agent behaving unexpectedly, CI breaking, misrouted tool call, etc.)
2. **One clearly correct answer** — grounded in the concepts above
3. **Three plausible distractors** — use the specific wrong patterns the exam favours (see distractor bank below)
4. **Cover all domains proportionally** over a full session: ~4 D1, ~3 D2, ~3 D3, ~3 D4, ~2 D5 per 15 questions
5. **Vary difficulty**: ~30% direct recall, ~50% applied scenario, ~20% multi-step reasoning
6. **Vary the correct answer letter**: track which letter (A/B/C/D) you've used. Never let one letter dominate. Target ~25% each over a session. Never use the same correct letter 3 times in a row.
7. **Match official exam style**:
   - **Scenario**: 2–4 sentences with specific metrics (percentages, latency numbers, error rates, file counts) and exact tool/config names
   - **Question stem**: one sentence using patterns like "What change would most effectively address this issue?", "What is the most likely root cause?", "Which approach should you take first?"
   - **Options A–D**: 1–2 sentences each, concrete — name the exact mechanism, flag, tool, or configuration
8. **Complex question pattern** (use for 20% of questions): state a scenario, then describe what a candidate might naively do and why it's wrong as part of the question setup, forcing multi-step elimination

---

## Distractor Bank (reuse these patterns)

| Situation | Correct answer | Common distractors |
|---|---|---|
| High-stakes compliance failure | Programmatic hook/gate | Enhanced system prompt, few-shot examples, routing classifier |
| Agent terminates prematurely | Check `stop_reason` | Check content type, add iteration cap, parse natural language |
| Multi-agent coverage gap | Coordinator decomposition | Web search subagent, synthesis subagent, retrieval subagent |
| Tool misrouting | Expand tool descriptions | Add routing classifier, merge tools, add few-shot |
| New team member not getting instructions | Move to project-level CLAUDE.md | Update user-level, add to skills, use /memory |
| CI pipeline hangs | Add `-p` flag | Add `--batch`, set `CLAUDE_HEADLESS=true`, redirect stdin from `/dev/null` |
| Tool returns empty array, agent retries | Valid empty result — do NOT retry | Retry with backoff, escalate immediately, check permissions |
| Synthesis report has no attribution | Fix context passing (add structured metadata) | Fix synthesis agent prompt, fix web search agent, fix coordinator |
| PostToolUse timing question | Fires AFTER execution, BEFORE model processes result | Fires before execution, fires after model responds, fires at end of loop |
| tool_choice "any" vs "auto" | `"any"` forces a tool call | `"auto"` also forces a tool call (wrong — auto allows free text) |
| Customer explicitly requests human | Escalate immediately, no investigation | Investigate first, assess confidence score, check sentiment |
| Batch API for pre-merge check | Keep synchronous (blocking) | Use batch with status polling; add timeout fallback |
| Batch API multi-turn tool calling | Not supported | Fully supported; requires special flag |
| `.mcp.json` vs `~/.claude.json` | `.mcp.json` = project-level (shared); `~/.claude.json` = user-level (personal) | Reversed; or using `.claude/mcp_settings.json` (wrong filename) |
| Slash commands shared with team | `.claude/commands/` (version-controlled) | `~/.claude/commands/`, CLAUDE.md, config.json |
| Lost-in-middle in long context | Key summary at START + section headers | Use larger context window, split into chunks, use streaming |
| Context degradation in codebase exploration | Scratchpad files + /compact + subagent delegation | Clear conversation, restart session, add more tokens |
