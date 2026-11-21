# First-evaluation versus warm-output consistency

Read-only checks of existing artifacts found **bitwise equality for every saved array** in both selected candidates. No benchmarks were run and no remote artifact or source file was changed.

The screen archive contains outputs from its first evaluation. The full archive contains outputs from the official benchmark's last warm repetition. These are independent processes evaluating the same exact commit, not two snapshots from one process. Both job metadata and report source commit were checked against the expected candidate SHA.

| Candidate | Exact SHA | Screening job | Full job | Strict comparison | Every saved array bitwise equal |
| --- | --- | --- | --- | --- | --- |
| 2 | `7f3cf9c316ce87a98afccb402bffc34e4ff71532` | `c778afc254774a8fa06a48d537060e5f` | `a7b341dc0cc64363922bcb3023a14537` | PASS | Yes |
| 8 | `1e552d675c3795265be8af1ac23ffb61f90f30b1` | `3acee14fc06b43b187d28b89a49cf4ae` | `2cab1e4043ea42849eff58278d16bab6` | PASS | Yes |

| Saved array | Candidate 2 max absolute difference | Candidate 8 max absolute difference | Strict check and bitwise equality |
| --- | ---: | ---: | --- |
| carrier | 0 | 0 | Both pass and are bitwise equal |
| signal | 0 | 0 | Both pass and are bitwise equal |
| noise | 0 | 0 | Both pass and are bitwise equal |
| sensitivity | 0 | 0 | Both pass and are bitwise equal |
| powers | 0 | 0 | Both pass and are bitwise equal |
| gradient | 0 | 0 | Both pass and are bitwise equal |
| parameters | 0 | 0 | Both pass and are bitwise equal |
| frequencies | 0 | 0 | Both pass and are bitwise equal |

Shapes and dtypes match, and every value is finite. Bitwise comparison uses each array's C-order bytes after verifying shape and dtype; this distinguishes signed-zero or other bit-pattern changes that ordinary numerical equality could hide.

Scalar loss is not included in the NPZ archives. As a separate check, the loss values recorded in each candidate's screen and full JSON reports also compare exactly equal as parsed JSON floats. This does not claim bitwise equality of an unrecorded array object.

The current deployed comparator was imported from `/workspace/feyer-lab/control/lab/compare_arrays.py` using `/workspace/venv-feyer/bin/python`. Its hash, evaluator hashes, archive paths, per-array shapes/dtypes/errors and reported loss checks are recorded in [first-warm.json](first-warm.json).

This closes the observed first-versus-warm consistency question for these selected artifacts. It does not prove consistency for arbitrary future/stateful candidates. Candidate 2's disagreement with the original baseline remains a separate numerical-review issue: agreement with its own warm run does not make it pass the baseline regression gate. Candidate 8 retains its previously established full-validation result.
