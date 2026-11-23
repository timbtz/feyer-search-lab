# Claude Artifacts — five presentation additions

Paste the shared brief first. Then paste prompts 1–5 into the **same Claude conversation and Artifact**. Attach your existing slides as the primary visual reference. Claude should create the diagrams; this kit does not contain finished slide designs. Finish with the QA/polish prompt. Each slide must also have a readable static final frame for PDF export.

These prompts intentionally ask for a selective schematic, not a wall of every experiment. Use the existing slide style as the primary visual reference. Claude owns the creative execution: improve the proposed layouts and transitions where that makes the story clearer, while preserving the facts and distinctions. The architecture and graph descriptions provide content constraints, not mandatory layouts. Claude should make the composition and interaction design decisions.

## Shared brief — paste first

```text
Build five additional animated presentation slides as ONE self-contained Claude Artifact. Use React + SVG if that is natural in your environment; otherwise a single HTML/CSS/JS document. This is an on-stage presentation, not a website or a live metrics dashboard. No backend, API keys, fetching repositories, optimization jobs, or invented telemetry.

Context: START Hack Munich 2026, Feyer: Faster Physics. We optimized Differometor, an optical simulator, and built a reproducible search system around it. The audience includes physicists and engineers. Existing slides use a “My Crush” chat metaphor, huge latency numbers, crisp typography, sparse diagrams and very little text. Preserve that visual language. These additions explain the search and verification rather than repeating the solver technical slides.

Placement: after existing technical slides 1–5, insert these five additions; replace the old short PASS slide with our new validation slide; then return to the existing “Yes!” closing. Within the additions, order: search → validation → architecture → numerical tuning → future application. Architecture therefore sits fourth from the end when the existing closing slide is included.

ART DIRECTION
Use a quiet, light engineering/editorial style, consistent with the supplied deck and our frontend. Primary background white, near-black ink #101116, neutral grey #70747C, thin borders #D9DCE2, pale surfaces #F4F5F7. Exploration/numerical choices use blue #2859E8 and pale blue #EFF4FF. Decision points use burnt orange #B65B16 and pale orange #FFF4E8. Validated outcomes may use restrained green #237A4B. Reserve red for an actual failure, not an inactive branch.
Use the existing deck font if available; otherwise Inter or a system sans-serif. No dependency on premium fonts. 16:9 canvas, designed at 1600×900. About 80px outer margins. Headlines 58–68px, node titles 22–28px, supporting text 20–24px, footnotes at least 16px. Use tabular figures. Keep stroke widths about 1.5–2px, radii 8–12px, almost no shadows. No gradients, glass cards, neon, 3D, starfields, confetti or decorative circuitry. Generous white space. Left-to-right flow. Avoid overlapping edges and tiny technical text.

GRAPH GRAMMAR
An agent session/research direction is a light outlined group. Candidate code revisions are small circles or compact dark cards within it. Numerical configuration menus are BLUE rounded rectangles. Decisions are larger ORANGE circles. An archived/rejected branch is grey and ends with a clear cap/X plus a brief reason. Keep it visible: negative results teach the system. A solid arrow means a proposed source transformation/lineage in the schematic; a dotted/dashed arrow means feedback or an illustrative cross-team connection. Do not invent exact Git ancestry. Evaluation run IDs and commit hashes belong in presenter notes or an optional details panel, not the main slide.

ANIMATION SYSTEM
Use deterministic finite stages, not a random force-directed graph. Fixed coordinates. Every click advances one beat; Space/Right Arrow advances, Left Arrow returns. Provide discreet Play/Pause, Replay and “Final frame” controls; hide them in presentation mode. Auto-play each slide only after the presenter starts it, run once, and hold its last frame. Provide a visible start/end state. Default transitions 450–650ms, stagger children 100–150ms; allow a 1.5–2s hold for each major idea. Trace a path with stroke-dashoffset, then fade its destination into place. Highlight only the currently narrated branch. No endlessly pulsing nodes or looping particle traffic. Respect prefers-reduced-motion; offer a static mode. Reset timers when changing slides; pause on hidden tabs. Render every final frame with no animation dependence so PDF screenshots work.

CONTENT DISCIPLINE
Each slide gets one message, one visual, one short headline and at most ~40 words of supporting copy, excluding node labels/footnotes. Put explanations in presenter notes. Do not add unsolicited dashboard widgets, testimonial copy, product navigation or paragraphs.

FACTS THAT MUST NOT CHANGE
1. Large workload: all 101 frequencies, all 193 design variables, double precision, physical outputs and gradients preserved. One logical CPU for official comparisons. Complete first-run timing includes imports/setup/compilation/simulation/sensitivity/gradients/transfers. Warm time is separate.
2. aLIGO is a second official benchmark, with its own smaller setup and 29 gradient parameters. Its tolerance differs from the large benchmark. Do not draw “193 variables” over both.
3. We added 14 seed-relative cases, saved-output/gradient comparisons, source review and targeted diagnostics. A finite suite is evidence, not proof for every unknown topology. Keep official PASS, extra numerical checks and source review distinct.
4. JAX jit and first-order reverse gradients are supported by the tested host path. Full JVP/Hessian/GPU/higher-order parity is NOT established. Missing higher-order support is a declared scope limit, not automatically a challenge violation.
5. SMAC3 was used in earlier finite-space campaigns. The last SIX-setting SuperLU sweep used exhaustive enumeration. Never rename that last sweep “SMAC” or invent a learned surrogate there.
6. The last sweep found NO admissible improvement over its repaired starting point. It did NOT prove that our original implementation was fastest globally. A separate controlled comparison favored the teammate version on the large benchmark. Do not turn “rejected by additional checks” into “slower.”
7. The system used human coordination plus explicit rules, model sessions, GitHub records and durable evaluation queues. Do not claim fully autonomous discovery of a global optimum, thousands of validated agents or an automatically deployed swarm.
8. Proposed future search over mirror/laser arrangements was NOT performed in this challenge. Label it next application; the physical problem stayed fixed during simulator optimization.
9. This is a schematic historical animation. All optimization is currently stopped. Never label the animation live telemetry.

Create the shared frame, controls and five slide placeholders. Await the slide-specific prompts before filling them. Keep data and narrative strings separate from layout code so a final timing can be corrected without redesign. The supplied 0.66 s deck headline is an external final-submission claim: do not fabricate a new report or reuse it as the time of every node.
```

## Prompt 1 — broad search and the escape branch

```text
Fill slide 1: “The breakthrough was a new branch.”

Purpose: show how our search expanded, learned, closed unproductive branches and escaped a plateau through a different implementation strategy. This is NOT a literal run-by-run replay. Build a wide, left-to-right graph with three distinct research lanes, each containing only 2–4 representative nodes. Use the group/node/decision grammar from the shared brief. No hairball.

Visual composition:
- Start left with a large dark node labelled “35.8 s” and “Baseline”.
- Fork into three light session containers: “Compilation”, “Linear algebra”, “Execution model”.
- In the compilation lane reveal “≈28 s” then “≈20 s”. End with an orange decision “Plateau”; keep the branch in grey rather than erasing it.
- The linear-algebra lane shows “Reuse LU” and an offshoot “Numerical review”. Give the held offshoot an orange, not green, status. This is a separate lesson, not an accepted speed milestone.
- The execution-model lane reveals “Sparse structure · ≈11.5 s”, then a distinct orange hinge labelled “Change strategy”. From it, trace a strong blue edge into “Host execution · 1.74 s”, and finally “Sub-1 s”. Give the last transition space and a short pause; it is the visual payoff.
- An optional tiny phase badge beneath the 11.5s node says “~8 s still compiling”. Never make 8s a total-time milestone.
- A small dashed feedback loop leads from a measurement icon back to the next branch decision. Do not draw backwards ancestry edges or imply automatic code merges.
- Include tiny in-slide caption: “Selected team milestones · schematic, not a literal commit DAG”.

Animation beats (~18s or six clicks):
1. Baseline alone. The empty horizontal space communicates how much remains to explore.
2. Three branches unfold; session containers appear before their candidate dots.
3. Early improvements appear on the upper lane. Measurements attach to nodes only after a small evaluation marker returns.
4. Upper offshoots lose emphasis and terminate with “plateau” / “review”. Their nodes stay visible; all tested history is retained.
5. Lower lane’s “Change strategy” circle enlarges subtly once. The blue path leaves the plateau, moving into the host execution representation.
6. “Sub-1 s” settles at the right. Hold the whole graph with one clear highlighted path and dim but readable discarded paths.

Do not count down 35.8 continuously to 0.66; that would imply measurements we did not make. Do not add fabricated 17s or 8s total-runtime nodes. The early lab milestones and teammate host-engine milestones are parallel team evidence; their connecting overview is schematic, not asserted Git parentage.

Presenter notes (roughly 25 seconds): “We didn’t ask one agent to keep polishing one implementation. We separated directions, measured complete evaluations and fed the results back. Some branches plateaued or needed numerical review. The major gain came from changing how the same physics was executed—not from dropping part of the workload.”
```

## Prompt 2 — validation and the JAX trade-off

```text
Fill slide 2: “PASS was the beginning.”

Purpose: make the audience understand that aggressive optimization can preserve a public test while breaking a more general assumption. We expanded the evidence, and we explicitly bounded the API claims. Keep this a visual confidence-building story, not a wall of disclaimers.

Visual: a candidate token travels left-to-right through FOUR clean gates:
1. “Large benchmark” — small sublabel “101 frequencies · 193 variables”.
2. “aLIGO” — “Second optical setup”.
3. “14 extra cases” — “Outputs + gradients”.
4. “Source audit” — “Generic, not fixture-specific”.
Use small green ticks for a passed gate and a larger orange review state for an unresolved issue. Below, a narrow capability strip with “jit ✓”, “reverse gradients ✓”, and “JVP / Hessian — scoped out”. Make the last chip neutral, not red: it is a declared host-path limitation, not automatically an organizer-rule breach.

Animation (~16s / five clicks):
1. A dark “Fast candidate” token enters the large benchmark gate and gets a tick.
2. aLIGO appears as a visibly different small optical schematic; a second tick.
3. Fourteen tiny case markers fan out, grouped rather than individually labelled. Their public/seed-relative status is an additional layer of evidence, never “all possible setups”.
4. At source audit the token turns amber. Reveal only the short label “Approximate adjoint shortcut”. A thin discarded vector component is shown becoming large after an inverse: a very small orange arrow becomes a visible arrow. This conveys amplification without a slide of equations.
5. A dashed repair edge leads to “Explicit adjoint solve”. End with “Measure → verify → repair” and the capability strip. Do NOT end with a universal “everything passed” stamp or automatically connect this repaired branch to the existing deck’s 0.66s headline.

Important provenance: the approximate-adjoint problem was found in one of OUR experimental branches, including an earlier incumbent. It was not a demonstrated fault of the teammate’s fastest host engine. Public benchmark PASS and 14 seed-case PASS did not catch that algebraic risk; source review did. The repaired branch passed its subsequent public and seed tests. Keep these identities distinct in notes.

Optional presenter-only expand: fixed precision/full inputs/unchanged benchmark; positive sensitivity; finite outputs and nonzero gradients; official finite-difference sanity checks; raw arrays; matched hardware/repetitions; unsupported components and API capability review. aLIGO’s own bound is 1e-6; the large log-sensitivity bound is 1e-5. Do not loosen thresholds in the animation to force a green outcome.

Presenter notes (~30 seconds): “A benchmark PASS is necessary, but it’s not a proof for an unseen instrument. We added the second official setup, 14 extra cases, output and gradient comparisons, and source review. That last step caught an unsafe approximation even after tests passed. We restored explicit solves. We also state the trade-off: jit and first-order reverse gradients work; full JAX API parity is not our claim.”
```

## Prompt 3 — system architecture, fourth from the end

```text
Fill slide 3: “Every experiment taught the next.”

Create the architecture diagram yourself from the specification below, matching the typography and spacing of the supplied deck. This is the main system-design pitch, not another performance chart. It sits fourth from the end when the two remaining additions and the existing closing slide follow it.

One large horizontal architecture diagram, with FIVE readable stages:
“Coordinate” → “Explore” → “Version” → “Evaluate” → “Learn”.

Under Coordinate: one orange decision node, “choose / fork / stop”. Coordinator means humans plus explicit search rules; do not pretend every decision was autonomous.
Under Explore: two small session containers “Claude” and “Codex”, each with 2–3 candidate commit dots; a separate BLUE rectangle “Numerical search” with “SMAC3 / enumerate”. A tiny merge junction may show an explicitly proposed combination, followed by new validation. No instant green merge.
Under Version: a crisp GitHub block, “branches + exact SHAs”. Show parent pointers and an owned branch, not a giant Git logo. Agents edit isolated worktrees; supervisors commit/push.
Under Evaluate: a queue pill “durable run ID”, leading to “AMD · 1 logical CPU”. Show two stacked task cards “Large” and “aLIGO”. CPU, not GPU computation. Explain neither VRAM nor 48 credits here.
Under Learn: a small report glyph with “time / phases / checks”. Below it, “recorded evidence”. Draw a distinct dashed return path under the diagram to the coordinator, labelled “feedback”. GitHub also receives published result summaries; large raw arrays/logs belong to evaluator artifact storage. Distinguish those locations.

Animate a single candidate packet, not dozens:
1. Orange coordinator chooses a direction.
2. One session emits a candidate; a tiny SHA attaches.
3. GitHub records the revision; the supervisor relays that exact source via the queue. Do not imply GitHub itself executes or that a moving branch is the unit being benchmarked.
4. AMD runs the two tasks serially; checks return with measured phase bars.
5. The evidence packet returns, and the coordinator either extends or closes a branch. The map remains acyclic for code lineage; only the feedback loop returns.

One small bottom caption: “One candidate. One revision. Reproducible evidence.”
Keep UUIDs, CPU affinity IDs, sampled RSS details, SSH commands and schema names in presenter notes/back-up diagram only. No containers are required in this main view. Do not show distributed services/cloud resources we did not deploy.

Presenter notes (~25 seconds): “The useful output isn’t just a fast function. It’s a search process we can reproduce. Every direction has an owner, each candidate has an exact revision, and each run returns evidence. GitHub connects the branches and results. The queue and supervisors keep experiments comparable while the feedback tells us what to try next.”
```

## Prompt 4 — numerical search near the frontier, with an honest ending

```text
Fill slide 4: “Faster on the stopwatch. Not better enough to keep.”

Purpose: after an architectural breakthrough, illustrate model-free numerical tuning over a fixed implementation menu. Make this an animation that visibly keeps the starting candidate when apparent gains fail additional checks. This is NOT a claim that the original was globally fastest.

Top-left a small two-step strip: “Earlier: SMAC3” → “This 6-choice sweep: enumerate”. A note in presenter notes explains that SMAC3 used a random-forest surrogate/expected improvement in earlier campaigns; six choices are cheap enough to cover exhaustively. Do not animate a trained surrogate picking the last sweep’s points.

Main visual: a dark starting node “Default”, then SIX BLUE rounded rectangles in a compact 2×3 grid. Label them Default / Relax 4 / Panel 8 / Panel 8 + relax 4 / Panel 16 / Panel 16 + relax 4. Keep physical topology, input parameters, precision and refinement fixed. These are SuperLU implementation settings, not mirror positions or the 193 physical design variables.

Use this exact data, one cold-checkout measurement per setting (not medians):
Default: large0.852731, aLIGO0.530437, officialpass, extrapass.
Relax4: large0.855784, aLIGO0.530816, officialpass, extrafail.
Panel8: large0.855807, aLIGO0.531165, officialpass, extrafail.
Panel8+relax4: large0.845224, aLIGO0.522221, officialpass, extrafail.
Panel16: large0.860740, aLIGO0.528449, officialpass, extrafail.
Panel16+relax4: large0.844503, aLIGO0.527698, officialpass, extrafail.

Animation (~17s / six clicks):
1. Starting node and six empty configuration cards appear.
2. Cards are evaluated serially, one at a time. Each gets its large-case time rounded to milliseconds; full data available in presenter-only details.
3. Panel16+relax4 briefly receives a BLUE “looks faster” outline: 0.8445s vs0.8527s. Do not color it green or call it a winner.
4. All cards reach an ORANGE decision circle “Validate”. Two small outcome rows appear: “Official: 6/6” and “Extra checks: 1/6”. Caption clarifies “passed configurations”, not test count.
5. Five cards become grey with orange X/review marks; preserve their timings. Labels show “additional mismatch”, not “slow”. The default stays dark with its original extra-check tick.
6. The outgoing thick path returns to a retained-parent card: “No admissible improvement”. Smaller subline: “Keep the starting candidate for this sweep.” No trophies/confetti. A final bracket around the six cards says “bounded search complete”.

Do not show or invent confirmation pairs: none were triggered in this sweep. Repeat confirmation is part of the system’s promotion policy, not an event that happened here. Do not use the deck’s0.66s value as this sweep’s seed. That belongs to another exact implementation/measurement. A small footer says “Full workloads · one CPU · all samples retained”.

Presenter notes (~25 seconds): “We used numerical search where the choices were explicit. Some settings looked faster, but every nondefault setting failed an additional comparison. We didn’t change the checks to keep a nicer number. The search gave us a bounded negative result: this menu did not improve the starting candidate.”
```

## Prompt 5 — reusable system, future optical design

```text
Fill slide 5: “Today: optimize the simulator. Next: explore the instrument.”

Purpose: bridge from this hackathon case to Feyer’s larger vision of AI-driven hardware discovery. It is a credible next application, not a claim we already solved optical design or that more agents guarantee progress.

Visual: two large zones linked by the same small search/evaluate/learn loop.
Left, solid outline, label “Built here”. Inside, show three code-structure alternatives, an immutable candidate marker, and a verified evaluation report. Brief sublabel: “Implementation search”.
Right, dashed outline, label “Next application”. Inside, draw a clean optical schematic with a laser, three mirrors, beam paths and a detector. Reveal two alternative arrangements as faint thumbnails. These are schematics, not a physically validated optical design. Brief sublabel: “Design search”.
Between them: one broad horizontal arrow labelled “Reuse the search infrastructure”. The repeated small loop has only three icons/words: propose → simulate → verify. Under the future side, two restrained chips: “Domain objective” and “New validity constraints”. This makes clear that moving to another physics domain needs a new evaluator, operators and domain review.

Animation (~12s / four clicks):
1. Show only the built implementation-search system, with one candidate and its evidence.
2. Abstract it into the compact three-step loop; move the loop toward the centre without a dramatic camera zoom.
3. Reveal the dashed optical-design panel. Three mirror-arrangement thumbnails appear as alternatives, with QUESTION markers, not PASS badges.
4. End on a shared sentence: “Explore more ideas. Keep the evidence.” Hold. Then the existing closing chat slide can show the fast reply again.

Do not animate this future search finding an optimal detector, a valid new instrument, or a speedup. Do not add “solves any physics domain” or claim that changing mirror positions was part of our fixed-workload benchmark optimization. Avoid marketing superlatives such as revolutionary, autonomous scientist, unlimited search or guaranteed discovery.

Presenter notes (~20 seconds): “Feyer’s larger problem is exploring hardware designs with simulation. Here we tested the infrastructure on simulator implementation. The next application is to search actual arrangements, with new objectives and physics-specific validity checks. We have built the experiment record and feedback machinery; applying it to instrument design remains the next step.”
```

## Final QA and visual polish — paste last

```text
Audit and polish the five-slide Artifact without adding features or changing claims.

1. Compare typography, margins, line weights and chat-header styling against the supplied deck. Use its actual font/color choices where available. Align all slides to one grid. Main diagrams should occupy roughly70% of the canvas; narration belongs in notes.
2. Test every slide in1600×900 and 1920×1080, and at a laptop viewport. No label clipping, offscreen nodes, overlapping edge text, moving layout or unreadable captions. Keep the SVG viewBox and scale it uniformly; do not reflow a presentation graph into a vertical website on a desktop.
3. Verify manual steps, replay, pause/resume, final-frame rendering, hidden-tab pausing and reduced motion. No stale timer from another slide may change the current slide. Print/PDF mode must show each final frame on a separate landscape page without controls.
4. Export an editable SVG of the main architecture and a higher-detail backup showing session→candidate SHA→run ID→artifact and the separate feedback loop. Keep vector text selectable. Offer a clean screenshot/final-frame option.
5. Check factual distinctions: measured team history versus illustrative schematic; official PASS versus extra checks versus source review; candidate versus session versus run; earlier SMAC3 versus final enumeration; complete first run versus warm runtime; implementation settings versus physical variables; measured results versus future application.
6. The numerical ending must say “No admissible improvement in this sweep,” not “our original is fastest.” No invented 17 s / 8 s total-time milestones, no 0.66 s attached to the 0.853 s sweep, no full-JAX-parity badge, no automatic green status for every extra test.
7. Keep the supplied 0.66 s headline as externally supplied deck data pending its exact report. If you mention30,000 evaluations/hour, explicitly label it warm throughput from ~0.12 s, not a consequence of 0.66 s first-run latency.
8. Remove all generic AI-design clutter: no animated backgrounds, flashy gradient orbs, excessive cards, fake metrics, logo walls, confetti, promotional CTAs or live status claims.

Return the finished Artifact with all five slides, plus a very short note listing any unsupported claim you intentionally did not implement. Do not claim to have run physics benchmarks.
```
