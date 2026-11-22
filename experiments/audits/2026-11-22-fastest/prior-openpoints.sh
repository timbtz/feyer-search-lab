#!/bin/sh
# Open-point experiments on CPU 101. Usage: openpoints.sh CANDIDATE_TREE CANDIDATE_TAG
# 1. Modulation-mode cases (question 2) for the unchanged simulator and the candidate.
# 2. Reference reproducibility (questions 7-9): the unchanged simulator with a different
#    legitimate OpenBLAS kernel path (Haswell instead of the default SkylakeX).
set -u
TREE=$1; TAG=$2
cd /tmp/claude-gencheck || exit 1
P=/workspace/venv-feyer/bin/python
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
queue_busy() { ps -eo args | grep -q "[f]eyer-lab.*/runs/.*/code/benchmark.py"; }
wait_idle() { while queue_busy; do sleep 5; done; }
MODES=uifo_amod1,uifo_fmod1
REPRO=dev,dev_randparams,uifo_randparams1,uifo_randparams2,uifo_randparams3,uifo_rand1,uifo_rand3

wait_idle
cp pristine.npz pristine-new.npz
taskset -c 101 $P -u gencheck.py run --tree /workspace/feyer-pristine --cases $MODES --merge --out pristine-new.npz > pristine-modes.log 2>&1 && mv pristine-new.npz pristine.npz

wait_idle
taskset -c 101 $P -u gencheck.py run --tree "$TREE" --out "exact-$TAG.npz" > "exact-$TAG.log" 2>&1
wait_idle
taskset -c 101 $P -u gencheck.py run --tree "$TREE" --cases $MODES --merge --out "exact-$TAG.npz" >> "exact-$TAG.log" 2>&1

wait_idle
OPENBLAS_CORETYPE=HASWELL taskset -c 101 $P -u gencheck.py run --tree /workspace/feyer-pristine --cases $REPRO --out pristine-haswell.npz > pristine-haswell.log 2>&1

echo "== modes: unchanged vs $TAG"; $P gencheck.py compare pristine.npz "exact-$TAG.npz" | grep -E "amod|fmod"
echo "== full: unchanged vs $TAG"; $P gencheck.py compare pristine.npz "exact-$TAG.npz" | grep -vE "amod|fmod"
echo "== reproducibility: unchanged (SkylakeX) vs unchanged (Haswell kernels)"; $P gencheck.py compare pristine.npz pristine-haswell.npz | grep -vE "MISSING|missing"
echo done > openpoints.done
