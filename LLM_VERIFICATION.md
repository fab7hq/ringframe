# Sandboxed LLM testing and verification

This contract applies whenever RingFrame tests or verifies LLM, agent,
Codex, Claude Code, skill, plugin, or host behavior in a sandbox. A component
plan may strengthen it but must not weaken its authentication, isolation,
evidence, containment, or stochastic-test rules.

## Authenticated sandbox E2E

Any acceptance claim about Codex or Claude Code host behavior must come from a
real authenticated run in an isolated scenario workspace bound to a qualified
host generation. Keep separate `codex` and `claude` generations, each created
from an initially empty host/config home and owning its authentication,
marketplace, tool state, and mutable host state. Never use the operator's normal
mutable host state as a qualification generation.

A host generation is reusable infrastructure, not a subject sample. It is the
exact tuple of provider, host executable and digest, authentication identity,
candidate/plugin/tool bytes, host settings, permission and containment policy,
and adapter protocol/schema. A qualification may reuse an unchanged generation,
but every subject repetition still uses a fresh host session, fresh disposable
Git workspace, and new append-only observation path. Claude and Codex, or two
different generations, never share configuration homes, credentials, caches,
transcripts, or mutable host state.

- Authenticate Codex through its real account/ChatGPT login flow with the
  generation-local `CODEX_HOME`. Authenticate Claude Code through its real
  browser login flow with the generation-local `CLAUDE_CONFIG_DIR`.
- Never copy normal credential files into a generation. Never commit or retain access
  tokens, cookies, credential files, or unsanitized authentication output.
- Prove authentication with a real account-bound host invocation and retain
  only sanitized identity/status evidence needed to bind the observation to
  the generation, host build, model, and time.
- Install exact candidate wheels into generation-owned immutable tool state.
  Add and install the candidate through the real host marketplace commands,
  then invoke the marketplace-installed surface through the real host. Use the
  host's structured automation protocol for repeatable samples; use the native
  TUI only when the frozen claim is specifically about interactive UI behavior.
- Source loading, `--plugin-dir`, copied plugin payloads, pre-existing plugin
  caches, direct CLI calls mislabeled as skill activation, mocks, and
  parent-relayed model prose do not satisfy host E2E.
- Retain sanitized host events, marketplace/plugin/skill identities, exact
  artifact hashes, exact submitted skill input, model and judge observations,
  CLI envelopes, consumer Git state, and before/after product state. Use a
  dedicated activation event when the host emits one. Otherwise bind the exact
  explicit invocation to enabled installed resolution under the frozen host
  contract and narrow the claim to an installed invocation treatment; do not
  invent an activation event. Missing authentication, either required host,
  installed invocation evidence, or real model execution blocks the E2E claim.

## LLM behavior acceptance and Definition of Done

This is the default LLM-testing contract for RingFrame contributors.
It is provider-, model-, host-, and harness-neutral. A component plan may name
a larger sample, stronger rule, or additional required execution strata, but it
must not pool unlike strata, weaken a critical guard, reinterpret observed
results, or omit real-host evidence that its delivery claim requires.

LLM output is stochastic. Prompt-only behavior is influenced, not
deterministically enforced. A test therefore supports only a bounded empirical
claim about the exact configurations observed; it does not prove universal
model behavior.

### 0. Start from the product claim, not the harness

Before designing a test, state what the product is, what value it adds, which
mechanism supplies that value, and what it deliberately does not control. The
test and Definition of Done must follow that capability boundary.

- Classify the product under test: execution harness or policy boundary,
  deterministic tool, host integration, semantic add-in, workflow method, or a
  composition of these. Name which component owns each claimed effect.
- Write a claim-to-mechanism map before test cases. A deterministic guarantee is
  valid only when a deterministic mechanism owned by the product enforces it.
  Skill prose, routing metadata, prompts, examples, and model instructions can
  support bounded behavioral claims; they cannot establish universal agent
  behavior or an authority boundary.
- Do not require an add-in to control capabilities retained by its host. If an
  agent can use a public shell, CLI, API, or native workflow independently of
  the add-in, that use is not proof that the add-in was invoked or that its
  routing policy failed. Test host skill activation from a dedicated retained
  activation event when available. When the host exposes no such event, retain
  the exact submitted explicit invocation, enabled installed payload/config,
  versioned host contract, and resulting structured events, and call the arm an
  installed invocation treatment rather than claiming an unobservable event.
  Test direct tool use as a separate host-behavior observation.
- An `explicit-only` skill claim ordinarily means the host does not
  automatically select or inject that skill. It means that the skill behaves
  correctly when explicitly invoked. It does not mean a host or agent is
  technically unable to reproduce, discover, or directly invoke the underlying
  public operation unless the product also owns and enforces such a capability
  boundary.
- For a semantic add-in, define value relative to a relevant untreated native
  workflow on the same task and execution stratum. Freeze the control,
  treatment, expected improvement, retained capabilities, possible harms, and
  minimum worthwhile effect before calls. Testing treatment alone can establish
  compatibility or task completion, but not add-in value.
- Keep product correctness, host integration, add-in value, and host/model
  behavior as separate claims. Failure of one must not be silently relabeled as
  another, and a test must not expand the product into a harness merely to make
  a desired model behavior deterministic.

The frozen Definition of Done must include this claim-to-mechanism map and a
short non-goals statement. Reject a proposed guard or success criterion when
the product has no mechanism capable of enforcing it, when it contradicts a
public capability, or when passing it would require evaluating a different
product. Such an item may be retained as a diagnostic behavioral question, but
not as a deterministic product gate.

### 1. Separate deterministic and semantic evidence

- Deterministic invariants are exact hard gates: candidate bytes and versions,
  isolation, authentication, installation, skill activation, input and output
  schemas, tool and authority boundaries, provenance, staleness/refusal,
  forbidden effects, and final product or workspace state.
- A tool or authority boundary is a deterministic invariant only when the
  product or declared execution substrate owns it. Do not infer a boundary from
  desired model behavior, skill-selection metadata, or the absence of a tool
  call in a small sample.
- Prefer deterministic graders for mechanically observable facts. Do not ask an
  LLM judge whether a file changed, a command ran, an exact token/URL exists, or
  a schema validates when code can decide it.
- Semantic targets and semantic guards may use model or human judgment. A green
  deterministic gate cannot substitute for missing semantic evidence, and a
  semantic score cannot waive a deterministic or critical failure.

### 2. Enforce containment before testing behavior

A prompt, `AGENTS.md`, `CLAUDE.md`, permission dialogue, or model promise is not
a filesystem, credential, tool, authority, or network boundary. Security and
state-integrity claims must be made true by the execution substrate even when
the subject ignores every instruction.

Keep two claims separate and freeze both before execution:

- **Containment:** whether a forbidden read, write, disclosure, command, network
  effect, or product effect was technically possible and occurred. Containment
  is a deterministic hard gate with zero tolerated forbidden effects.
- **Instruction-following:** whether the subject attempted or proposed an
  out-of-scope action despite the instruction. This is stochastic behavior and
  may be a frozen target, semantic guard, or diagnostic; it cannot substitute
  for containment.

A denied out-of-scope attempt is a valid unfavorable behavior observation, not
an infrastructure error and not evidence that containment failed. A successful
out-of-scope access or effect is a deterministic universal-critical `FAIL`. If
the frozen behavior claim requires no attempted access, score the denied attempt
against that claim as declared. Never reinterpret an old attempt/effect rule
after seeing its result.

#### 2.1 Trusted control plane and sandboxed subject plane

- Use a non-LLM trusted runner to authenticate the host, install and hash the
  candidate, freeze the test, launch isolated subjects and judges, capture raw
  events, grade deterministic facts, and write append-only observations.
- Give the model-visible subject plane only the minimum declared capabilities.
  Prefer an OS/container sandbox or a capability-restricted tool proxy. If a
  host's built-in sandbox restricts writes but permits broad reads, or covers
  Bash but not Read/Write/MCP or other tools, it is insufficient by itself.
- Define explicit allowed-read, allowed-write, denied-read, denied-write,
  allowed-network, denied-network, executable/tool, environment, temporary-path,
  and Unix-socket policies. Apply them to every tool route, subprocess, hook,
  plugin, skill, MCP server, shell, and helper available to the subject.
- A qualification may retain unrestricted model-visible network access when
  network isolation is not part of the product or claim. Declare the denied
  network set as empty, keep that capability identical across comparative arms,
  test the required positive route, and score unauthorized factual use as
  instruction-following or grounding. Never describe that configuration as
  network-contained or use it for an offline/no-egress claim.
- Authentication material may be usable by the trusted host process but must
  not be readable through model-visible tools. Do not mount or expose raw
  tokens, cookies, credential files, keychain export, or unsanitized environment
  values to the subject. If the host cannot separate authenticated operation
  from model-visible credentials, mark that execution tuple unsupported.
- Perform marketplace installation in the trusted setup phase. Freeze exact
  artifact hashes afterward and make installed candidate/tool state read-only
  during subject execution except for explicitly declared runtime/cache paths.
  The trusted runner, not the subject, owns immutable raw observations.
- Do not use approval- or sandbox-bypass flags as the boundary. Such a flag is
  allowed only when a stronger outer boundary already enforces every declared
  denial and the frozen test records why it is necessary.

#### 2.2 Mandatory containment preflight

Before the first subject or judge call in every lane and required stratum, run
and retain deterministic positive and negative controls against the exact final
runner configuration:

- allowed reads, writes, executable calls, provider access, and required runtime
  paths succeed;
- source repositories, sibling lanes, operator home/archive paths, credential
  locations, undeclared temporary paths, and forbidden network destinations
  cannot be read, written, listed, or reached through exposed tools;
- absolute paths, `..` traversal, symlink/hardlink escapes, globs, subprocesses,
  hooks, environment variables, Unix sockets, alternate tools, and MCP routes do
  not bypass the policy; and
- denial events, exit status, filesystem/product before-and-after state, policy
  digest, runner build, and exact allowed/denied matrix are retained.

Preflight uses synthetic canaries, never real secrets. If any negative control
succeeds, any required positive control fails, or an available tool route is
untested, the containment gate is `FAIL` or `INCONCLUSIVE` as predeclared. Stop
before semantic calls; a prompt asking the LLM not to use the open route does
not cure the failure.

#### 2.3 Terminal results and successor qualifications

Each qualification has its own immutable ID and state:

```text
FROZEN -> RUNNING -> PASS | FAIL | INCONCLUSIVE
```

The three outcomes are terminal. A changed prompt, threshold, guard scope,
grader, judge, sample design, tool policy, sandbox, runner, or evidence rule
requires a new qualification ID, with the old outcome retained and linked as
its predecessor. Every successor execution uses fresh sessions, disposable
workspaces, observations, and subject samples. It may reuse an authenticated
host generation only when that generation's complete tuple is unchanged. A
host executable/version, authentication identity, candidate/plugin/tool digest,
host setting, permission/containment policy, or adapter protocol/schema change
requires a new initially empty generation and fresh authentication. Exact
candidate artifact hashes may remain the same, but the new run is a successor
qualification, not a retry that replaces the prior evidence.

A successor analysis may reuse an immutable subject corpus only when that reuse
was frozen before unblinding, or when the result is explicitly diagnostic and
cannot qualify a release. Changing an acceptance rule, threshold, guard, grader,
or judge after seeing an outcome requires a fresh independent acceptance sample;
the old corpus cannot be rescored to rescue the failed or inconclusive result.
Results from a predecessor must never be pooled into a changed execution
stratum to manufacture a pass.

### 3. Declare execution strata; never average them together

Before the first subject or judge call, declare every configuration for which
the acceptance claim is intended to hold. One execution stratum is the exact
tuple of:

```text
provider + resolved model/version + effort/reasoning level + host/tool build
+ system/developer/user prompt or skill digest + tool/permission policy
+ containment implementation/preflight digest + sampling settings when exposed
+ harness/grader/judge versions
```

- Run and report each required stratum independently. Do not pool repetitions
  across providers, models, effort levels, hosts, prompt revisions, or tool
  policies to manufacture one passing rate.
- A cross-provider or cross-model claim passes only when every required stratum
  passes. If any required stratum fails, the combined claim is `FAIL`; if none
  fails but one is inconclusive, the combined claim is `INCONCLUSIVE`.
- A changed tuple is a new stratum, not a retry or replacement. If a provider
  exposes only an alias and the resolved model cannot be retained, disclose the
  gap and do not claim version-specific coverage.
- In a comparative add-in test, control and treatment are arms within the same
  stratum only when host, resolved model, effort, task, fixture, tool authority,
  and sampling settings are identical. The treatment may add only the frozen
  product surface being evaluated. Any other difference is a different stratum
  or a confound that must be disclosed.

### 4. Freeze the experiment before calls

Commit or otherwise immutably digest the complete test definition before any
subject or judge call. It must predeclare:

- the product classification, value claim, claim-to-mechanism map, and non-goals;
- required strata, arms, fixtures, prompts/treatments, and independence rules;
- target valid sample size and maximum total attempts per declared cell and
  stratum;
- target criteria, their application scope, and the success threshold;
- separate containment, instruction-following, task-success, and diagnostic
  claims, including how a denied attempt is scored for each;
- critical guards, diagnostic checks, and deterministic or semantic grader for
  each item;
- the complete capability matrix and containment-preflight cases;
- judge-panel composition, blinding, aggregation, and disagreement handling;
- treatment of timeouts, refusals, malformed output, and infrastructure errors;
- the exact `PASS | FAIL | INCONCLUSIVE` decision rule; and
- retained artifacts, source/product before-and-after state, and claim scope.

For an add-in-value claim, also predeclare the untreated native baseline, the
smallest meaningful improvement, and guardrails against treatment regressions.
Use paired fixtures or another frozen blocking design when task variance could
hide the treatment effect. Do not treat successful installation, skill
activation, or task completion as evidence of incremental value by itself.

Subject repetitions use fresh sessions and fresh disposable workspaces with the
same frozen inputs. They must not share conversational state or see earlier
outputs. Judges are blind to arm labels and one another's votes; a second panel
must not see the first panel's answers or rationales.

Judges receive only the frozen rubric and immutable, normalized evidence needed
for their semantic questions. They must not share the subject session, inspect
mutable subject workspaces, or have authority to alter the evidence or product.
Each judge configuration must pass a predeclared calibration set containing
known positive, negative, and disagreement cases before its votes count. A
calibration failure makes that judge configuration unusable for the frozen test;
do not silently replace it after viewing subject results.

### 5. Default release-qualification rule

Unless an authoritative plan predeclares a stronger justified design, use this
rule independently for every required stratum:

1. Obtain at least three valid independent subject outputs per declared test
   cell (for example, a single target cell or each control/treatment arm).
2. Use two independent blind judge panels. Each panel uses three independent
   votes per output and semantic question; a 2-of-3 majority determines that
   panel's answer. One judge call may answer all frozen questions for one output.
3. Derive the complete acceptance verdict separately from each panel. For a
   single-cell behavior test, both panels must independently show target success
   of at least 2/3. For a comparative test, both panels must independently show
   control headroom of at least 2/3 and treatment target success of at least
   2/3.
4. Deterministic critical guards are decided by deterministic evidence; any
   violation is `FAIL` and is not sent to a model for adjudication. For semantic
   critical guards, both panels must independently show zero violations. A
   semantic critical violation found by either panel prevents `PASS`; agreement
   by both panels on the violation is `FAIL`, while panel disagreement is
   `INCONCLUSIVE`.
5. Return `PASS` only if all deterministic gates pass and both panels
   independently return `PASS`. Return `FAIL` for a deterministic failure or
   when both panels independently fail the same required threshold or critical
   guard. All other outcomes are `INCONCLUSIVE`.

The stability requirement applies to the independently derived acceptance
verdict and every critical guard, not exact agreement on every noncritical
judge atom. Retain and report all item-level disagreement even when it does not
change the verdict.

Classify every guard by scope before execution:

- **Universal critical:** safety, authority, fabricated execution/retrieval,
  provenance, forbidden effects, and final-state integrity. Applies to every
  arm and can never be averaged away.
- **Cell-conditional critical:** facts or constraints that must hold only in a
  declared cell, such as when evidence or a treatment is supplied. Outside that
  cell the same observation may establish headroom rather than safety.
- **Diagnostic:** useful for understanding behavior but incapable of changing
  acceptance. Disagreement is reported variance, not a hidden failure.

Do not label a requirement diagnostic merely to obtain a pass. If violating it
could make the accepted product unsafe, unauthorized, falsely grounded, or
materially incorrect, it is critical.

The default three-valid-output design is a bounded release-qualification bar,
not a population reliability estimate. A claim such as "at least 95% reliable"
requires a separately frozen, adequately powered sample and a predeclared
confidence interval whose lower bound meets the claimed rate. The 2-of-3 rule
cannot support an SLO, provider ranking, or universal success percentage.

### 6. Attempts, errors, and immutable evidence

- Retain every subject call, judge vote, error, prompt, raw output, grading
  envelope, and state observation. Never discard, replace, or selectively quote
  a valid unfavorable output.
- A timeout, provider refusal, malformed envelope, or infrastructure failure is
  unjudged, not a semantic pass or failure. A replacement call is allowed only
  within the frozen maximum-attempt budget; it does not erase the failed call.
- A denied forbidden command or tool request is a valid judged subject attempt,
  not a timeout or infrastructure failure. A successful forbidden access or
  effect is a terminal deterministic failure for that qualification.
- If the minimum valid sample is not reached, judge panels disagree on the
  acceptance verdict or a critical guard, required provenance is missing, or a
  required stratum cannot run, the result is `INCONCLUSIVE` and blocks the
  acceptance claim.
- A stable missed threshold or stable critical violation is `FAIL`, not
  stochastic noise to average away.

### 7. LLM test Definition of Done

An LLM behavior test is done only when:

- the product classification, value claim, claim-to-mechanism map, and non-goals
  are explicit, internally consistent, and reflected in every critical gate;
- the frozen definition predates every counted call;
- the exact final containment configuration passed its complete preflight before
  any counted subject or judge call;
- every required stratum has its own complete valid sample and verdict;
- deterministic gates and before/after state checks are complete;
- both independent panels and all individual votes are retained;
- every attempt, including errors and unfavorable outputs, remains visible;
- the result is exactly `PASS`, `FAIL`, or `INCONCLUSIVE` under the frozen rule;
- the conclusion names the observed provider, resolved model, effort, host/build,
  prompt/probe digest, tool policy, containment/preflight digest, qualification
  ID and predecessor, sample, judges, date, rates, denied attempts,
  disagreements, and limitations; and
- the public claim is no broader than the strata and sample that passed.

For a semantic add-in, completion additionally requires a valid untreated
native comparison for every claimed stratum, the frozen minimum worthwhile
effect to be met by both panels, and all predeclared no-regression guards to
pass. If only treatment samples exist, report installed-host compatibility or a
bounded treatment observation, never proven add-in value.

Never lower or rewrite a threshold after observing results. Never reclassify a
failed guard, narrow its scope, change a prompt, swap a judge, or add samples to
rescue an existing experiment. Any such change requires a new immutable test or
Probe; retain the prior outcome and state why the successor design changed.
