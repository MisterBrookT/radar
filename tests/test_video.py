import unittest
from radar.video import diagram


class DiagramTests(unittest.TestCase):
    def test_flow_escapes_model_text(self):
        result = diagram({'type': 'flow', 'nodes': ['<script>', 'UI']})
        self.assertIn('&lt;script&gt;', result)
        self.assertNotIn('<script>', result)
        self.assertIn('→', result)

    def test_invalid_plan_is_ignored(self):
        self.assertEqual(diagram({'type': 'javascript', 'nodes': ['A', 'B']}), '')
        self.assertEqual(diagram(None), '')

    def test_limit_nodes(self):
        self.assertEqual(diagram({'type': 'cards', 'nodes': ['A'] * 8}).count('node'), 4)
