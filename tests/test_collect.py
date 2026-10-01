import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import httpx
from radar import collect
from radar.common import load


class CollectTests(unittest.TestCase):
    def test_oai_error_is_not_a_successful_empty_feed(self):
        xml = '<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/"><error code="badArgument">Set does not exist</error></OAI-PMH>'
        response = httpx.Response(200, text=xml, request=httpx.Request('GET', collect.OAI))
        with patch.object(collect.httpx, 'get', return_value=response) as get:
            with self.assertRaisesRegex(ValueError, 'badArgument'):
                collect.arxiv_papers(14, max_pages=8)
            self.assertEqual(get.call_args.kwargs['params']['set'], 'cs')

    def test_arxiv_failure_preserves_live_hn_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            with patch.object(collect, 'arxiv_papers', side_effect=httpx.ReadTimeout('timeout')), patch.object(collect, 'x_posts', return_value=[]), patch.object(collect, 'hn_stories', return_value=[{'id':'live', 'date':'2026-10-01'}]):
                collect.run(p, max_pages=2, end_date='2026-10-01')
            self.assertEqual(load(p/'candidates.json'), [{'id':'live', 'date':'2026-10-01'}])
            self.assertEqual(load(p/'collection-status.json')['arxiv'], 'ReadTimeout')

    def test_weekly_window_is_shared_and_stale_sources_are_removed(self):
        live = {'id': 'new', 'date': '2026-10-01'}
        stale = {'id': 'old', 'date': '2026-09-24'}
        with tempfile.TemporaryDirectory() as tmp, patch.object(collect, 'arxiv_papers', return_value=[]) as papers, patch.object(collect, 'x_posts', return_value=[live, stale]) as posts, patch.object(collect, 'hn_stories', return_value=[]) as hn:
            root = Path(tmp)
            collect.run(root, end_date='2026-10-01')
            self.assertEqual(load(root/'candidates.json'), [live])
            self.assertEqual(papers.call_args.args[0], 7)
            self.assertEqual(posts.call_args.args[0], 7)
            self.assertEqual(hn.call_args.args[0], 7)
            self.assertEqual(load(root/'collection-status.json')['window'],
                             {'start': '2026-09-25', 'end_inclusive': '2026-10-01', 'timezone': 'UTC'})

    def test_weekly_empty_window_can_be_recorded_without_fabrication(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(collect, 'arxiv_papers', return_value=[]), patch.object(collect, 'x_posts', return_value=[]), patch.object(collect, 'hn_stories', return_value=[]):
            root = Path(tmp)
            collect.run(root, end_date='2026-10-01', allow_empty=True)
            self.assertEqual(load(root/'candidates.json'), [])

    def test_successive_weeks_do_not_overlap(self):
        first_start, first_end = collect.date_window(7, '2026-10-01')
        next_start, next_end = collect.date_window(7, '2026-10-08')
        self.assertEqual((next_start-first_end).days, 1)
        self.assertEqual((first_end-first_start).days, 6)
        self.assertEqual((next_end-next_start).days, 6)

    def test_oai_updated_record_does_not_hide_in_week_publication(self):
        body = b'''<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/">
          <ListRecords><record><header><datestamp>2026-10-07</datestamp></header><metadata>
          <arXiv xmlns="http://arxiv.org/OAI/arXiv/"><id>2609.12345</id><created>2026-09-26</created>
          <title>Generative UI</title><abstract>Interface generation</abstract><categories>cs.HC</categories>
          </arXiv></metadata></record></ListRecords></OAI-PMH>'''
        response = httpx.Response(200, content=body, request=httpx.Request('GET', collect.OAI))
        with patch.object(collect.httpx, 'get', return_value=response) as get:
            papers = collect.arxiv_papers(7, end_date='2026-10-01')
        self.assertEqual([p['date'] for p in papers], ['2026-09-26'])
        self.assertNotIn('until', get.call_args.kwargs['params'])

    def test_all_sources_empty_fails(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(collect, 'arxiv_papers', return_value=[]), patch.object(collect, 'x_posts', return_value=[]), patch.object(collect, 'hn_stories', return_value=[]):
            with self.assertRaises(ValueError):
                collect.run(Path(tmp), max_pages=2)
