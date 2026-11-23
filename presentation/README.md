# Faster Answers — final presentation

[Project overview](../README.md) · [Final deck (PDF)](faster-answers.pdf) · [Original challenge (PDF)](../challenge.pdf) · [Results and scope](../docs/RESULTS.md)

`faster-answers.pdf` is a byte-for-byte copy of the supplied **Faster Answers v2 — Feyer Challenge Pitch.pdf**. It contains the final 14-page pitch, including the backup timing breakdown. Images in `slides/` are direct renders of that PDF, not recreated illustrations.

| PDF pages | Story |
| --- | --- |
| 1–2 | Why waiting matters; profile the original computation |
| 3–4 | Sparse linear algebra and the host execution engine |
| 5 | Reduce remaining setup, derivative and compilation overhead |
| 6–7 | Validation, source review, and the six-setting numerical sweep |
| 8–9 | Agentic experiment loop and selected research directions |
| 10–11 | Future application: searching for new physical designs |
| 12–13 | Final headline and closing |
| 14 | Backup: what remains in the final first-run time |

The [results guide](../docs/RESULTS.md) distinguishes deck milestones, exact lab candidates and measurement regimes. Slide 9 is a schematic search story, not a literal commit DAG. Design search on pages 10–11 is future work.

## Reusing the visuals

The README and both frontends use selected PNG exports at 1440 pixels wide. [`slides/manifest.json`](slides/manifest.json) records page numbers and SHA-256 hashes, plus the source PDF hash. To regenerate with PyMuPDF available:

```bash
python3 presentation/render_slides.py
```

This is a documentation utility; PyMuPDF is not a simulator or evaluator dependency. The frontend uses a subset under `story-assets/`; deliberately sync those files to both frontend copies when updating the deck.

[`search-story/`](search-story/README.md) retains earlier storyboard prompts, source notes, schematic alternatives, and machine-readable sweep evidence. Its deployment illustrations are planning aids, not evidence of installed capacity. Use the final PDF as the presentation reference and recorded experiment artifacts as measurement evidence.

## Frontend screenshot

[`screenshots/search-map.png`](screenshots/search-map.png) shows the standalone frontend with its existing saved experiment snapshot, in focus mode at 50% graph zoom. It is a historical observation, not live service status. The visible early campaign timings are separate from the final presentation milestones. [`screenshots/source.json`](screenshots/source.json) records the source snapshot hash.
