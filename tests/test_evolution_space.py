import hashlib
from pathlib import Path
import subprocess
import unittest

from lab.evolution_space import (DEFAULTS, SOURCE_SHA256, assignments,
    content_identity, materialize, parse_recipe, source_from_git, validate)


class SpaceTests(unittest.TestCase):
    def test_finite_menu_has_no_inactive_or_duplicate_choices(self):
        rows = assignments()
        self.assertEqual(len(rows), 15)
        self.assertEqual(len({str(sorted(r.items())) for r in rows}), 15)
        self.assertTrue(all(r['checkpoint'] or r['prevent_cse'] is False for r in rows))

    def test_boolean_integer_and_unknown_values_cannot_alias(self):
        for change in ({'checkpoint': 1}, {'map_batch_size': True},
                       {'map_batch_size': 3}, {'checkpoint': False, 'prevent_cse': True}):
            with self.assertRaises(ValueError):
                validate(dict(DEFAULTS, **change))

    def test_recipe_is_menu_selection_not_executable_text(self):
        choices = assignments(dimensions=['map_batch_size'])
        result, why = parse_recipe('```json\n{"choice":1,"rationale":"Test one batch"}\n```', choices)
        self.assertEqual(result['map_batch_size'], 1)
        for text in ('{"choice":true,"rationale":"bad"}',
                     '{"choice":99,"rationale":"bad"}',
                     '{"choice":1,"rationale":"bad","command":"echo bad"}',
                     'print("not JSON")'):
            with self.assertRaises(ValueError):
                parse_recipe(text, choices)

    def test_seed_and_every_assignment_render_deterministically(self):
        repo = Path(__file__).resolve().parents[1]
        try:
            source = source_from_git(repo)
        except subprocess.CalledProcessError:
            self.skipTest('Historical seed commit not present in shallow checkout')
        self.assertEqual(content_identity(source), SOURCE_SHA256)
        self.assertEqual(materialize(source, DEFAULTS), source)
        rendered = [materialize(source, p) for p in assignments()]
        self.assertEqual(len({content_identity(s) for s in rendered}), 15)
        for result in rendered:
            compile(result, '<candidate>', 'exec')
        with self.assertRaises(ValueError):
            materialize(source + '\n', DEFAULTS)


if __name__ == '__main__':
    unittest.main()
