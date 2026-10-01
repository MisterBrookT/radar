import unittest

from radar.minimal_video import scene_html, semantic_phrases, visual_state, validate_script


class MinimalVideoTests(unittest.TestCase):
    def setUp(self):
        self.scene = {'heading': 'A small pipeline', 'citation': 'Paper · Fig. 10',
                      'visual_type': 'graph',
                      'nodes': [{'id': 'input', 'label': 'Input', 'x': 100, 'y': 150},
                                {'id': 'output', 'label': 'Output', 'x': 600, 'y': 150}],
                      'edges': [{'from': 'input', 'to': 'output'}],
                      'events': [{'id': 'one', 'say': 'Begin with input.', 'subtitle': 'Begin with input.',
                                  'reveal': ['input'], 'focus': ['input']},
                                 {'id': 'two', 'say': 'Then produce output.', 'subtitle': 'Then produce output.',
                                  'reveal': ['output'], 'focus': ['output']}]}

    def test_states_follow_semantic_events(self):
        self.assertEqual(visual_state(self.scene, 0), ({'input'}, {'input'}))
        self.assertEqual(visual_state(self.scene, 1), ({'input', 'output'}, {'output'}))

    def test_later_claim_is_not_rendered_early(self):
        page = scene_html(self.scene, 0, 'Begin with input.', 1)
        self.assertIn('Input', page)
        self.assertNotIn('>Output<', page)
        self.assertNotIn('GenUI Daily', page)

    def test_model_labels_are_escaped(self):
        self.scene['heading'] = '<script>bad()</script>'
        page = scene_html(self.scene, 0, '', 1)
        self.assertNotIn('<script>', page)
        self.assertIn('&lt;script&gt;', page)

    def test_animation_changes_geometry_without_future_claims(self):
        before = scene_html(self.scene, 0, '', 0)
        after = scene_html(self.scene, 0, '', 1)
        self.assertNotEqual(before, after)
        self.assertNotIn('>Output<', before)

    def test_subphrases_keep_their_semantic_event(self):
        events = semantic_phrases([self.scene])
        self.assertEqual([x['event'] for x in events], [0, 1])
        self.assertEqual([x['text'] for x in events], ['Begin with input.', 'Then produce output.'])

    def test_original_figure_uses_narrated_crop(self):
        scene = {'visual_type': 'figure', 'heading': 'Original architecture', 'citation': 'Fig. 10',
                 'image_size': [1000, 600], 'image_data': 'data:image/png;base64,AA==',
                 'overview': [0, 0, 1000, 600],
                 'events': [{'id': 'figure', 'say': 'The summarizer.', 'subtitle': 'The summarizer.',
                             'crop': [100, 100, 300, 200]}]}
        validate_script({'scenes': [scene]})
        self.assertIn('viewBox="100 100 300 200"', scene_html(scene, 0, '', 1))
        self.assertIn('overflow:hidden', scene_html(scene, 0, '', 1))
        self.assertIn('<image ', scene_html(scene, 0, '', 1))
        scene['events'][0]['crop'] = [900, 100, 300, 200]
        with self.assertRaises(ValueError):
            validate_script({'scenes': [scene]})

    def test_bilingual_units_preserve_complete_meanings(self):
        event = self.scene['events'][0]
        event['segments'] = [{'en': 'Begin with input.', 'zh': '从输入开始。'}]
        phrases = semantic_phrases([self.scene])
        self.assertEqual(phrases[0]['subtitle_zh'], '从输入开始。')
        self.assertEqual(phrases[0]['text'], event['say'])
        validate_script({'scenes': [self.scene]})
        event['segments'][0]['en'] = 'Different speech.'
        with self.assertRaises(ValueError):
            validate_script({'scenes': [self.scene]})

    def test_bilingual_caption_escapes_both_languages(self):
        page = scene_html(self.scene, 0, 'Input <unsafe>', 1, '输入<script>')
        self.assertIn('caption-en', page)
        self.assertIn('caption-zh', page)
        self.assertIn('输入&lt;script&gt;', page)
        self.assertNotIn('<script>', page)

    def test_bar_labels_do_not_assume_the_viscanvas_sample_size(self):
        scene = {'visual_type': 'bars', 'heading': 'Success rate', 'maximum': 100,
                 'bars': [{'id': 'result', 'label': 'System', 'value': 67.2, 'display_label': '67.2%'}],
                 'events': [{'id': 'metric', 'say': 'A rate.', 'subtitle': 'A rate.', 'reveal': ['result']}]}
        page = scene_html(scene, 0, 'A rate.')
        self.assertIn('67.2%', page)
        self.assertNotIn('67.2/20', page)

    def test_unknown_node_reference_is_rejected(self):
        self.scene['events'][0]['reveal'] = ['invented']
        with self.assertRaises(ValueError):
            validate_script({'title': 'Test', 'scenes': [self.scene]})
