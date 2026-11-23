# Faster Answers

**Feyer Challenge · START Hack Munich 2026**

Faster optical simulations. A Git-traceable lab for finding, testing, and explaining improvements.

[**Our presentation ↗**](presentation/faster-answers.pdf) · [**Feyer’s challenge ↗**](challenge.pdf) · [**Frontend ↗**](https://github.com/timbtz/feyer-search-frontend)

## The challenge

Accelerate Differometor’s complete first evaluation: **101 frequencies · 193 variables · double precision · physical outputs and gradients preserved.**

<table>
<tr>
<td width="50%" align="center"><a href="challenge.pdf"><img src="presentation/challenge/01-brief.png" alt="Feyer’s original Faster Physics challenge brief" width="100%"></a></td>
<td width="50%" align="center"><a href="media/uifo.png"><img src="media/uifo.png" alt="Original Differometor illustration of the optical interferometer setup" width="100%"></a></td>
</tr>
<tr><td align="center">Feyer’s original brief · click to open PDF</td><td align="center">Optical setup · original Differometor visual</td></tr>
</table>

## Our solution

**Exploit sparsity. Execute the traced physics on the host.**

[![Sparse matrices: 2,533 nonzero entries instead of 564,001 dense entries](presentation/slides/03-sparse.png)](presentation/faster-answers.pdf#page=3)

[![Host execution: keep the physics formulas, execute with NumPy and sparse adjoint solves](presentation/slides/04-host-engine.png)](presentation/faster-answers.pdf#page=4)

## From 35.8 seconds to 0.66

[![The final steps: host setup, leaner derivatives, fallback, and compiler settings](presentation/slides/05-last-second.png)](presentation/faster-answers.pdf#page=5)

*Final-pitch measurements; approximately 55× overall. The host-engine slide’s 20× compares against the original baseline. [Exact revisions, validation, and measurement scopes →](docs/RESULTS.md)*

## The Git-traceable operating loop

**Explore → commit → evaluate → learn. Every candidate has a revision; every result has evidence.**

[![Our agentic loop: coordinate, explore, version, evaluate, tune, and learn](presentation/slides/08-agent-loop.png)](presentation/faster-answers.pdf#page=8)

[![Selected search directions: compiler changes, linear algebra, and the host-execution breakthrough](presentation/slides/09-search.png)](presentation/faster-answers.pdf#page=9)

*Search-story schematic. Inspect recorded ancestry and individual runs in the [frontend](https://github.com/timbtz/feyer-search-frontend).*

## Two repositories, one system

| [Challenge lab](https://github.com/timbtz/feyer-search-lab) | [Search frontend](https://github.com/timbtz/feyer-search-frontend) |
| --- | --- |
| Agents, Git history, evaluator, validation, feedback | Search graph, exact revisions, timings, recorded decisions |

[**Architecture**](docs/ARCHITECTURE.md) · [**Run the lab**](lab/README.md) · [**Run the frontend**](https://github.com/timbtz/feyer-search-frontend#try-it) · [**Benchmark setup**](docs/CHALLENGE.md) · [**Full slide deck**](presentation/faster-answers.pdf)

Based on [Differometor](README.upstream.md) · [MIT license](LICENSE).
