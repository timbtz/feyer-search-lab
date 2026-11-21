"""Adversarial acceptance checks; no JAX installation required."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from lab.jaxcompat import REQUIRED_TESTS, compare_reports, compare_values, merge_receipts


def receipt():
    return dict(setup="voyager", tests={name: dict(status="ok", value=[1., 2.], seconds=0.)
                                      for name in REQUIRED_TESTS})


class AcceptanceTests(unittest.TestCase):
    def test_complete_identical_receipts(self):
        self.assertTrue(compare_reports(receipt(), receipt())["passed"])

    def test_incomplete_or_extra_inventory(self):
        for kind in ("missing", "extra"):
            candidate = receipt()
            if kind == "missing":
                candidate["tests"].pop(REQUIRED_TESTS[-1])
            else:
                candidate["tests"]["invented"] = dict(status="ok", value=1)
            self.assertFalse(compare_reports(receipt(), candidate)["passed"])
        self.assertFalse(compare_reports(dict(setup="voyager", tests={}), dict(setup="voyager", tests={}))["passed"])

    def test_structure_shape_and_empty(self):
        for a, b in [({"a":[1], "b":[2]}, {"a":[1]}),
                     ({"a":[1]}, {"different":[1]}),
                     ([1, 2], [[1, 2]]), ([], []), ({}, {})]:
            with self.subTest(a=a, b=b):
                self.assertFalse(compare_values(a, b)["passed"])

    def test_nonfinite_or_wrong_values(self):
        for value in (float("nan"), float("inf"), -float("inf"), 100.):
            self.assertFalse(compare_values([1.], [value])["passed"])
            self.assertFalse(compare_values([value], [1.])["passed"])
        self.assertTrue(compare_values([1., 1e-30], [1.+1e-7, 2e-30])["passed"])

    def test_bad_reference_unavailable(self):
        reference = receipt()
        reference["tests"][REQUIRED_TESTS[0]] = dict(status="error", error="unsupported")
        result = compare_reports(reference, receipt())
        self.assertFalse(result["passed"])
        self.assertEqual(result["checks"][0]["status"], "unavailable")

    def test_setup_and_tolerance(self):
        candidate = receipt(); candidate["setup"] = "dev"
        self.assertFalse(compare_reports(receipt(), candidate)["passed"])
        for tolerance in (float("nan"), float("inf"), -1.):
            with self.assertRaises(ValueError):
                compare_reports(receipt(), receipt(), tolerance)

    def test_partial_merge_identity(self):
        original = dict(schema_version=2, identity=dict(source="a", harness="x"), tests={"a":1})
        new = dict(schema_version=2, identity=dict(source="a", harness="x"), tests={"b":2})
        self.assertEqual(merge_receipts(original,new)["tests"], {"a":1,"b":2})
        for other in ({}, dict(schema_version=2, identity=dict(source="b", harness="x"))):
            with self.assertRaises(ValueError):
                merge_receipts(other,new)

    def test_cli_failure_exit_and_structured_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); ref=root/'ref.json'; cand=root/'cand.json'; out=root/'out.json'
            ref.write_text(json.dumps(receipt())); cand.write_text(json.dumps(dict(setup="voyager", tests={})))
            process=subprocess.run([sys.executable, str(Path(__file__).with_name('jaxcompat.py')),
                                    'compare', str(ref), str(cand), '--out', str(out)], capture_output=True,text=True)
            self.assertEqual(process.returncode,1,process.stderr)
            self.assertFalse(json.loads(out.read_text())["passed"])


class BoundedTrajectoryTests(unittest.TestCase):
    def test_saved_domain_points(self):
        from lab.bounded_jaxcompat import validate_points
        pairs = [["etmy", "reflectivity"], ["fm2", "tuning"], ["laser", "power"]]
        self.assertTrue(validate_points(pairs, [[0.999, -0.014, 1.]]))
        for points in ([[1.00015,-0.014,1.]], [[0.9,0.,float("nan")]],
                       [[0.9,0.,-1.]], [[0.9]], []):
            self.assertFalse(validate_points(pairs, points))


if __name__ == '__main__':
    unittest.main()
