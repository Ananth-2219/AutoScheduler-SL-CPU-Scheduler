"""Reproduce the selected original-v5 response-advantage demo through the API."""
import hashlib
import json
import unittest


class SwitchingDemoTests(unittest.TestCase):
    def test_original_v5_response_demo_is_reproducible_and_matches_playback(self):
        from fastapi.testclient import TestClient
        from dashboard.app import app
        from dashboard.adapter import catalog, simulation, _original_v5, DYNAMIC_V5_ARTIFACT
        simulation.cache_clear()
        with TestClient(app) as client:
            response = client.get('/api/simulation', params={
                'workload': 'dynamic_response_advantage', 'algorithm': 'Dynamic ML (v5)'})
            self.assertEqual(response.status_code, 200)
            data = response.json()
        self.assertEqual(data['dynamic_model']['artifact'], DYNAMIC_V5_ARTIFACT)
        self.assertEqual(data['dynamic_model']['version'], 'v5')
        self.assertEqual(data['dynamic_model']['switch_margin'], 0.005)
        self.assertEqual(_original_v5()[1].mlfq_quanta, (1, 2, 4))
        self.assertEqual(_original_v5()[1].mlfq_aging_threshold, 40)
        self.assertEqual(len(data['reproducibility']['input_processes']), 14)
        self.assertEqual(data['reproducibility']['workload_id'], 'dynamic_response_advantage')
        events = data['policy_transitions']
        self.assertEqual([(e['effective_tick'], e['from_policy'], e['to_policy'], e['reason']) for e in events],
                         [(22, 'MLFQ', 'Priority', 'accepted'), (52, 'Priority', 'MLFQ', 'excursion_expired')])
        self.assertTrue(all(e['decision_tick'] == e['effective_tick'] for e in events))
        self.assertEqual(hashlib.sha256(json.dumps(data['timeline']).encode()).hexdigest(),
                         'cb2a66838b852c6aee164ffae4c2841d0a79215ab21e8d8da4dd092536943f80')
        comparison = data['response_comparison']
        dynamic, baseline = comparison['original_v5'], comparison['tuned_mlfq']
        for key, left, right in [('avg_response', 24/14, 31/14), ('p95_response', 4.35, 5.0),
                                 ('avg_waiting', 78.5, 90.71428571428571),
                                 ('weighted_score', 0.08660452383024976, 0.1601457426009788)]:
            self.assertAlmostEqual(dynamic[key], left, places=12)
            self.assertAlmostEqual(baseline[key], right, places=12)
        self.assertLess(dynamic['avg_response'], baseline['avg_response'])
        self.assertLessEqual(dynamic['p95_response'], baseline['p95_response'])
        self.assertEqual(len(data['processes']), 14)
        for frame in data['frames']:
            past = [e for e in events if e['effective_tick'] <= frame['tick']]
            self.assertEqual(frame['active_policy'], past[-1]['to_policy'] if past else 'MLFQ')
        self.assertEqual([(p['start'], p['end'], p['policy']) for p in data['policy_timeline']],
                         [(0, 22, 'MLFQ'), (22, 52, 'Priority'), (52, 254, 'MLFQ')])
        ids = [w['id'] for w in catalog()['workloads']]
        self.assertIn('dynamic_response_advantage', ids)
        self.assertNotIn('dynamic_multi_policy', ids)
        self.assertIn('short_jobs', ids)
        self.assertEqual(data['reproducibility']['api_request'],
                         '/api/simulation?workload=dynamic_response_advantage&algorithm=Dynamic+ML+%28v5%29')
