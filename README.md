# Faster Answers

**Feyer Challenge · START Hack Munich 2026**

Faster optical simulations. A Git-traceable lab for finding, testing, and explaining improvements.

[**Our presentation ↗**](presentation/faster-answers.pdf) · [**Feyer’s introduction ↗**](presentation/feyer-challenge.pdf) · [**Frontend ↗**](https://github.com/timbtz/feyer-search-frontend)

## The challenge

[![Feyer’s vision: AI-invented hardware for medicine, computing, and energy](presentation/feyer-slides/01-vision.png)](presentation/feyer-challenge.pdf#page=1)

[![Feyer’s mission: scale physics simulation and AI exploration across the hardware design space](presentation/feyer-slides/02-mission.png)](presentation/feyer-challenge.pdf#page=2)

**Our task:** accelerate Differometor’s complete first evaluation. **101 frequencies · 193 variables · double precision · physical outputs and gradients preserved.** [Challenge rules →](challenge.pdf)

## Where the original time went: 44.20 seconds

[![Feyer’s original timing breakdown: setup 3.66 seconds, compilation 22.92 seconds, forward simulation 13.29 seconds, sensitivity 1.37 milliseconds, gradient 4.34 seconds; total 44.20 seconds](benchmarks/cpu-baseline.png)](benchmarks/cpu-baseline.json)

*Feyer’s published baseline on one Intel Xeon logical CPU. On our AMD machine, the starting workload took **35.8 s**—the baseline for our speedup.*

[![Our starting profile: 19.5 seconds compiling and 15.3 seconds computing](presentation/slides/02-profile.png)](presentation/faster-answers.pdf#page=2)

## How we solved it

**Exploit sparsity. Execute the traced physics on the host.**

[![Sparse matrices: 2,533 nonzero entries instead of 564,001 dense entries](presentation/slides/03-sparse.png)](presentation/faster-answers.pdf#page=3)

[![Host execution: keep the physics formulas, execute with NumPy and sparse adjoint solves](presentation/slides/04-host-engine.png)](presentation/faster-answers.pdf#page=4)

## From 35.8 seconds to 0.66

[![The final steps: host setup, leaner derivatives, fallback, and compiler settings](presentation/slides/05-last-second.png)](presentation/faster-answers.pdf#page=5)

[![Inside the final 0.66 seconds: 0.26 seconds importing JAX, approximately 0.16 seconds compiling readout, and approximately 0.23 seconds in our build, simulation and gradient code](presentation/slides/14-remaining-time.png)](presentation/faster-answers.pdf#page=14)

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
