# Search-story source kit (presentation history)

The completed [final presentation](../faster-answers.pdf) and [slide exports](../README.md) are now the project’s presentation reference. This folder retains the earlier Claude handoff, evidence, and schematic alternatives. The instructions below describe that historical handoff, not work required to view the finished project.

**Original handoff:** Claude should design and build the Artifact. This folder contains prompts and evidence, not an implemented animation page.

1. Attach your existing slides to Claude as the visual reference.
2. Open **CLAUDE_ARTIFACTS_PROMPTS.md** and paste the shared brief.
3. Paste prompts 1–5 into the same Artifact conversation. Claude owns the layout, SVG diagrams and animation implementation.
4. Use the final polish prompt to check consistency, motion and export.

Suggested sequence after your technical slides: search → validation → architecture → numerical tuning → future application → your existing closing. Replace the old short PASS slide with the expanded validation slide. This places the architecture slide fourth from the end, counting the closing slide.

The prompts ask Claude to create editable diagrams and animations. Two static image backups are now available in `diagrams/`:

- `01-search-convergence.png`: preferred search-story slide: top-to-bottom exploration, pruning, one selected solution, six-setting numerical refinement and original/aLIGO validation. Its graph is schematic, not exact historical lineage. Generation prompt: `diagrams/01-search-convergence-prompt.txt`.
- `01-search-system.png`: earlier architecture pipeline retained as an alternative.
- `02-amd-session-allocation.png`: preferred deployment diagram. AMD 01 holds coordination, queue, numerical optimization and the original ~14 GB RAM evaluator. AMD 02 hosts a shared DeepSeek model. The three hosts illustrate 2/4/6 Claude/Codex session clients, each with four support clients (two Qwen, two DeepSeek). Purple denotes hosted Qwen; blue denotes self-hosted DeepSeek. Counts and the 2+2 support mix are illustrative, not tested capacity. Model size/quantization and measured resource use determine feasible concurrency. Session clients consume host CPU/RAM; local weights consume GPU VRAM and may require host RAM. DeepSeek is one shared model server, not a copy per session. Prompt: `diagrams/02-amd-session-allocation-prompt.txt`.
- `02-amd-three-instance-plan.png`: earlier alternative with five CPU evaluation slots across three hosts.

Both images use a white, black, blue and orange presentation palette. The second is a capacity illustration, not a record of deployed infrastructure. The approximately 14 GB per job refers to the original workload's system RAM, not GPU VRAM. Quick local checks do not replace full physics validation. Raw artifacts remain in evaluation storage; GitHub holds code and published evidence. Detailed routing is schematic.

Generation prompts are saved in `diagrams/PROMPTS.md`. No HTML animation or deck has been built here; Claude still owns that implementation.

## Evidence boundaries

- The final six-setting sweep used enumeration; earlier campaigns used SMAC3.
- Its conclusion was **no admissible improvement within that sweep**, not that the original was globally fastest.
- The host path preserves the tested jit/first-order reverse-gradient interface, not every JAX capability.
- The supplied 0.66 s headline belongs to your chosen submission report; do not mix it with other implementations or measurement scopes.
- Optical instrument design is a future application, not a completed result.

**EVIDENCE.md** supplies the supporting records and caveats. **evidence.json** contains the actual six-setting sweep data. These are for Claude's grounding and presenter notes, not a demand to fill the slide with technical text.

No optimization runs or model workers were launched for this presentation task.
