# Plan 0006: Build Lead Classification And Draft Reply Workflow

GitHub issue: #6, "Build lead classification and draft reply workflow"

## Goal

Connect stored lead records to assistant-style outputs so a new lead can be
classified, escalated or drafted, and moved to the right next status.

This phase should create a deterministic dry-run workflow that is ready for a
future Openclaw/model adapter, but it must not require Openclaw authentication
or make real model/API calls yet.

## Scope

Implement:

- assistant workflow schemas for classification, escalation, draft reply, and
  audit records
- per-client draft/audit output storage outside git
- deterministic local dry-run assistant logic for representative lead types
- command to process one lead
- command to process new leads
- tests for genuine quote request, complaint, spam, out-of-scope, and price
  safety
- docs explaining the workflow and what is still mocked

Defer:

- real Openclaw execution
- OpenAI/API/model calls
- Telegram approval messages
- sending email/SMS/WhatsApp replies
- webhook receiver
- scheduling/cron
- weekly reports

## Important Boundary

This plan intentionally does **not** onboard/authenticate Openclaw yet.

Build the deterministic harness first so that, when Openclaw is connected in a
later plan, there is a clear adapter point and command to exercise.

The assistant prompt library in `openclaw/agents/followup-assistant/` is the
source for desired output shapes and safety rules. The dry-run implementation
may use deterministic heuristics, but it must preserve those output shapes and
the MVP safety posture.

## Runtime State Layout

Continue using the canonical state root from `docs/local-state.md`:

```text
/var/openclaw/
  clients/
    <client-slug>/
      leads.jsonl
      drafts.jsonl
      audit.jsonl
```

Development/tests must use `LOCAL_GROWTH_STATE_ROOT`.

Add helpers in `lead_hub.storage` or a focused new module for:

- `drafts_path(client_slug)`
- `audit_path(client_slug)`
- append/read draft outputs
- append/read audit events

Never commit runtime output files.

## Output Schemas

Create a focused schema module, for example:

`lead_hub/schemas/assistant_workflow.py`

Recommended models:

- `EscalationCheck`
- `LeadClassification`
- `DraftReply`
- `AssistantRun`
- `AuditEvent`

The schemas should be JSON-serializable and validate:

- `approval_required` is always true for draft replies
- classification is one of the prompt taxonomy values
- recommended statuses are valid `LeadStatus` values
- escalated runs include an escalation reason
- spam runs do not include a draft reply
- draft bodies do not include obvious invented fixed prices in dry-run examples

Use the prompt files' required output fields as the baseline.

## Dry-Run Classification Rules

Implement deterministic classification sufficient for tests and operator dry
runs. Keep it deliberately conservative.

Suggested rules:

- complaint/dispute/refund/legal/insurance/safety/hazard/threat keywords →
  escalation required, classification `complaint_or_dispute` or
  `urgent_or_safety`, status `escalated`, no customer draft
- spam/SEO/marketing/backlink/crypto style content → classification `spam`,
  status `spam`, no draft
- service request not matching configured service slugs/names and not empty →
  classification `out_of_scope`, status `escalated` or `needs_human_review`,
  no autonomous draft
- in-scope normal enquiry → classification `genuine_lead`, status
  `awaiting_approval`, draft reply created
- ambiguous missing service → classification `needs_human_review`, status
  `escalated` or `needs_reply_draft` only if the draft is safely generic and
  still requires approval

Bias toward escalation/review. The MVP must not be clever at the expense of
safety.

## Draft Reply Rules

For in-scope genuine leads, generate a safe draft reply:

- use `config.tone.style`, `config.tone.length`, and `config.tone.sign_off`
- mention the requested service only if it is configured
- do not invent prices
- do not promise availability, dates, job completion, refunds, guarantees, or
  outcomes
- ask a concise next-step question
- always set `approval_required: true`
- include operator notes explaining any assumptions

This can be template-based in this plan. The purpose is to prove the workflow
and storage boundaries before live Openclaw drafting.

## Commands

Add one or both commands, keeping usage explicit and Python 3.11-safe:

```bash
LOCAL_GROWTH_STATE_ROOT="$(mktemp -d)" python3.11 -m lead_hub.process_lead example-client <lead-id> --dry-run
LOCAL_GROWTH_STATE_ROOT="$(mktemp -d)" python3.11 -m lead_hub.process_new_leads example-client --dry-run
```

Behavior:

- validate client config first
- load leads from JSONL
- process only `new` leads for bulk command
- single-lead command should reject missing lead IDs clearly
- write an `AssistantRun` to `drafts.jsonl` for every processed lead
- append an `AuditEvent` to `audit.jsonl` for every processed lead
- update lead status based on classification
- print a concise operator summary
- `--dry-run` should mean "use deterministic local assistant", not "no writes".
  If Claude chooses no-write dry-run semantics, rename the flag to avoid
  ambiguity and document it. For this plan, writes are expected.

## Tests

Required test cases:

- genuine quote request produces a draft, status `awaiting_approval`, and no
  invented price
- complaint/dispute escalates immediately, status `escalated`, no draft body
- spam becomes status `spam`, no draft body
- out-of-scope request escalates or needs human review, no unsafe draft
- missing lead ID exits nonzero
- bulk command processes only `new` leads
- draft and audit JSONL files are written under `LOCAL_GROWTH_STATE_ROOT`
- client config identity mismatch behavior remains covered
- approval is always required for any draft
- deterministic output examples contain no real client data

Use fictional data only.

## Documentation Updates

- Update `README.md` development status and command list.
- Update `lead_hub/README.md` with new commands and output files.
- Update `docs/local-state.md` to include `drafts.jsonl` and `audit.jsonl`.
- Add a workflow doc if useful, e.g. `docs/assistant-workflow.md`.
- Update this plan's checkboxes and execution notes.

## Tasks

- [ ] Review prompt output shapes in `openclaw/agents/followup-assistant/prompts/`.
- [ ] Add assistant workflow schemas.
- [ ] Add draft/audit storage helpers.
- [ ] Add deterministic dry-run classification logic.
- [ ] Add deterministic safe draft reply logic.
- [ ] Add command to process one lead.
- [ ] Add command to process new leads in bulk.
- [ ] Update lead statuses as part of processing.
- [ ] Write `drafts.jsonl` assistant run records.
- [ ] Write `audit.jsonl` audit records.
- [ ] Add tests for genuine lead drafting.
- [ ] Add tests for complaint escalation.
- [ ] Add tests for spam handling.
- [ ] Add tests for out-of-scope handling.
- [ ] Add tests for storage paths and command behavior.
- [ ] Update README/docs.
- [ ] Update this plan's checkboxes and execution notes.

## Verification

- [ ] `python3.11 --version` satisfies `pyproject.toml`.
- [ ] `python3.11 -m pip install -e ".[dev]"` succeeds.
- [ ] `LOCAL_GROWTH_STATE_ROOT="$(mktemp -d)" python3.11 -m lead_hub.manual_lead example-client --name "Draft Test" --email "draft@example.invalid" --service "eicr" --message "Please quote for an EICR"` succeeds.
- [ ] `LOCAL_GROWTH_STATE_ROOT="<same tmp dir>" python3.11 -m lead_hub.process_new_leads example-client --dry-run` succeeds and prints a concise summary.
- [ ] `LOCAL_GROWTH_STATE_ROOT="<same tmp dir>" python3.11 -m lead_hub.list_leads example-client` shows the processed lead status changed.
- [ ] `python3.11 -m pytest tests/` succeeds.
- [ ] `python3.11 -m compileall lead_hub openclaw tests -q` succeeds.
- [ ] `rg -n --pcre2 "python3(?!\\.11)|python -m|state/<|config.example.yaml" README.md docs lead_hub tests planning openclaw pyproject.toml`
      returns no unapproved stale command/path references.
- [ ] `rg -n "approval_required.*false|send without|fixed price|guarantee|available tomorrow" lead_hub tests openclaw`
      returns no unsafe dry-run output, unless an execution note explains a
      quoted negative rule or test assertion.
- [ ] `git status --short` shows only intentional changes before commit.

## Branch And PR

- [ ] Create a branch named `codex/ops-lead-draft-workflow`.
- [ ] Commit with a clear message.
- [ ] Open a draft pull request linked to issue #6.
- [ ] PR description includes workflow decisions, dry-run semantics, storage
      paths, deferred Openclaw integration, and verification commands run.

## Execution Notes

- Pending.
