# Diagram generation prompts

Generated with the built-in image-generation tool. Static presentation backups; Claude owns editable slides and animations.

## 1. Search system

Create a beautiful, exceptionally clean, slide-ready SYSTEM ARCHITECTURE DIAGRAM. This is a designed vector-like infographic image, NOT a website mockup, not a photo. Landscape 16:9, high resolution, crisp legible typography. White background. Quiet modern engineering editorial aesthetic, inspired by minimal scientific product presentations: near-black ink #101116, soft gray surfaces #F4F5F7, thin gray borders #D9DCE2, restrained cobalt blue #2859E8 for evaluation/search, warm burnt-orange #B65B16 for decisions. Generous whitespace, precise aligned baseline, restrained rounded rectangles. No gradients, shadows, 3D, decorative circuit textures or neon. Use a tasteful modern sans-serif. Main title big, labels large and few. Everything should be understood at presentation distance.

Title upper left exactly: "Every experiment teaches the next."
Small upper-right eyebrow: "FEYER / SEARCH SYSTEM"

Main diagram occupies the middle 65% of the slide. A simple left-to-right chain of FIVE modules with clear arrows. Each has a small outlined pictogram, a bold short heading, and only the specified supporting text:
1. "Explore" — below "Claude · Codex", below "Isolated branches". Icon: branching graph, with a few small candidate circles inside a pale session frame.
2. "Version" — below "GitHub", below "Exact commit". Icon: three connected commit circles, NOT a generic cloud server pretending to execute code.
3. "Queue" — below "Durable run ID", below "Fixed budget". Blue-tinted rounded rectangle, simple stacked task cards.
4. "Evaluate" — below "AMD · CPU", below "Large + aLIGO". Subtle blue accent, small processor icon; two miniature test cards. This is CPU benchmarking, do NOT depict the GPU as performing the physics.
5. "Learn" — below "Time · gradients · checks". Icon: three little measured bars and a check/review mark.

Above the Explore module, an ORANGE outlined decision circle with text "Choose" and a small subtitle "fork / refine / stop". Connect it to Explore with one downward arrow. The circle represents a coordinator with explicit rules, not magic automatic optimality.

A single elegant thin BLUE dashed feedback line returns BELOW the five modules from Learn to the orange Choose circle through an uncluttered outside route. Label this lower line "Measured feedback". Keep this feedback visually distinct from the solid forward arrows. No tangled arrows, no crossing text, no dense wiring. A small gray side branch beside the exploration graph ends in a stop cap, showing an archived direction, labelled "Keep the history".

Small bottom statement in near-black, centered: "Candidate → commit → run → evidence"
Smaller bottom-left caption: "Simplified architecture · not live telemetry"

The slide should look polished and professionally art-directed with large empty margins. NO additional text, no fabricated numbers, no database/API/cost clutter. All required text must be correctly spelled. All connectors must terminate visibly and logically. Prioritize clean composition and strong typography over tiny details.

## 2. Proposed AMD deployment

Create a second beautiful, exceptionally clean, slide-ready SYSTEM DEPLOYMENT DIAGRAM, matching a minimal white scientific presentation. Landscape 16:9, high resolution, crisp typography. Flat vector-like infographic, white background, near-black #101116, gray #70747C, thin borders #D9DCE2, very pale gray #F4F5F7, cobalt blue #2859E8 for evaluation workers/queue, warm orange #B65B16 for the coordinator. Generous whitespace. No gradients, 3D, dramatic shadows, neon, clouds full of clipart, or tiny paragraphs.

Title upper left: "One search. Three AMD instances."
Directly beneath, small but readable badge: "PROPOSED SCALE-OUT"
This is a proposed capacity layout, NOT a claim it was deployed or that five GPUs did physics.

At upper left, a small card "Agent sessions" with sublabel "Quick local checks".
At upper center, a wide clean GitHub record card: heading "GitHub"; supporting line "Tasks · code · published evidence". A simple branching-commit glyph. Arrow Agent sessions → GitHub. Github stores/version-controls work, it is NOT the machine that executes benchmarks.

Below, THREE generously sized equal-width SERVER CARDS in a row, labelled "AMD 01", "AMD 02", "AMD 03". Each is a GPU-equipped host; the physics evaluation boxes inside are explicitly CPU workers.
AMD 01 contains an orange small module "Coordinator", then a blue small module "Durable queue". Below them two blue-outlined worker tiles side-by-side: "CPU eval 1", "CPU eval 2".
AMD 02 contains two blue-outlined worker tiles side-by-side: "CPU eval 3", "CPU eval 4". Small text above: "Workers claim jobs".
AMD 03 contains one blue-outlined worker tile: "CPU eval 5". Beneath, a distinct DASHED outlined optional module: "GPU · local model", with small label "Optional". Keep the GPU box visually separate from the CPU evaluation tile.

Arrow GitHub → Coordinator with tiny label "Pinned source + task".
The queue in AMD 01 routes to the CPU workers in all three server cards; draw a clean horizontal distribution bus above or between cards with neat downward arrows to each pool, no crossed lines. Local AMD 01 queue also routes to its own two workers. The queue controls claims, not GitHub alone. Add one small return arrow from the optional GPU model to the Agent sessions/shared proposal path, labelled "Proposals"; do not route the model directly into correctness verdicts.

A lower shared results band beneath all three server cards: heading "Reports + raw artifacts". Supporting line "Times · outputs · gradients". Thin collection arrows from the worker cards down into this band; a dashed feedback line from this band returns to the Coordinator, labelled "Feedback". A short upward reference/link arrow to GitHub may be included only if uncluttered, label "Publish summaries". It is okay to omit that extra arrow if the result is cleaner; do not suggest every large raw array is committed into GitHub.

Bottom footer, two short lines, fully legible:
"5 evaluation slots · 3 GPU-equipped hosts"
"Sized for the original ≈14 GB RAM / job · RAM-aware admission · isolated final timings"

A separate small caption near the local-check card or bottom: "Quick checks ≠ full physics validation"

Visual hierarchy: main title, three host cards, five BLUE worker tiles, one ORANGE coordinator, one dashed optional GPU model, and one common results strip. Limit text to the specified labels. The three AMD machines have large CPU RAM budgets independent of GPU VRAM; DO NOT put '14 GB VRAM' anywhere. No five-GPU claim, no actual deployment claim, no benchmark acceleration on GPU. This should be a refined, simple architecture slide with a transparent, believable proposed orchestration model.
