"""Small stdlib-only correctness inspection of the builder's name lookup."""
import ast
import random
from pathlib import Path


source = Path(__file__).resolve().parents[2] / "differometor" / "build.py"
tree = ast.parse(source.read_text())
helper = next(node for node in tree.body
              if isinstance(node, ast.FunctionDef) and node.name == "_parameter_name_lookup")
namespace = {}
exec(compile(ast.Module(body=[helper], type_ignores=[]), str(source), "exec"), namespace)
make_lookup = namespace[helper.name]


def outcome(call, name):
    try:
        return ("value", call(name))
    except ValueError as error:
        return ("error", type(error), str(error))


rng = random.Random(20261122)
checks = 0
for _ in range(300):
    names = [rng.choice(["", "a_x", "b_x", "a_y", "μ_phase", "a'b"])
             for _ in range(rng.randrange(60))]
    if rng.randrange(2):
        names = tuple(names)
    lookup = make_lookup(names)
    for query in ["", "a_x", "b_x", "a_y", "μ_phase", "a'b", "missing"]:
        assert outcome(lookup, query) == outcome(names.index, query)
        checks += 1

# Unhashable elements and custom containers retain equality-based list.index.
class CustomList(list):
    def index(self, name):
        return 17


for names in ([[], "x", "x"], [1, "x"], CustomList(["x"])):
    lookup = make_lookup(names)
    for query in ("x", "missing"):
        assert outcome(lookup, query) == outcome(names.index, query)
        checks += 1

# Every call builds a fresh table after names change; no cross-build state.
names = ["a_x", "b_x", "a_x"]
assert make_lookup(names)("a_x") == 0
names[:] = ["b_x", "a_x"]
assert make_lookup(names)("a_x") == 1
assert make_lookup(["a_x"])("a_x") == 0
print(f"PASS: {checks} lookup comparisons plus three fresh-call checks.")
