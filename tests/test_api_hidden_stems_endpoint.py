import unittest

from fastapi.testclient import TestClient

from eight_characters.main import app


class TestApiHiddenStemsEndpoint(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    def test_hidden_stems_canonical_pillars(self) -> None:
        response = self.client.post(
            '/api/hidden_stems',
            json={
                'year_pillar': '丁卯',
                'month_pillar': '癸丑',
                'day_pillar': '己丑',
                'hour_pillar': '壬申',
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()['hidden_stems']
        self.assertEqual(payload['year']['hidden_stems'], ['乙'])
        self.assertEqual(payload['month']['hidden_stems'], ['己', '癸', '辛'])
        self.assertEqual(payload['day']['hidden_stems'], ['己', '癸', '辛'])
        self.assertEqual(payload['hour']['hidden_stems'], ['庚', '壬', '戊'])

    def test_hidden_stems_accepts_bazi_output(self) -> None:
        bazi_response = self.client.post(
            '/api/bazi',
            json={
                'date': '1988-02-04',
                'time': '16:30:00',
                'location': {
                    'timezone': 'Asia/Shanghai',
                    'longitude': 104.066,
                    'latitude': 30.658,
                },
            },
        )
        self.assertEqual(bazi_response.status_code, 200)
        pillars = bazi_response.json()['four_pillars']
        to_text = lambda p: f"{p['stem']['chinese']}{p['branch']['chinese']}"

        hs_response = self.client.post(
            '/api/hidden_stems',
            json={
                'year_pillar': to_text(pillars['year']),
                'month_pillar': to_text(pillars['month']),
                'day_pillar': to_text(pillars['day']),
                'hour_pillar': to_text(pillars['hour']),
            },
        )
        self.assertEqual(hs_response.status_code, 200)
        hs_payload = hs_response.json()['hidden_stems']
        for pillar_name in ('year', 'month', 'day', 'hour'):
            self.assertGreater(len(hs_payload[pillar_name]['hidden_stems']), 0)

    def test_invalid_pillar_length_rejected(self) -> None:
        response = self.client.post(
            '/api/hidden_stems',
            json={
                'year_pillar': '丁卯甲',
                'month_pillar': '癸丑',
                'day_pillar': '己丑',
                'hour_pillar': '壬申',
            },
        )
        self.assertEqual(response.status_code, 400)

    def test_invalid_branch_rejected(self) -> None:
        response = self.client.post(
            '/api/hidden_stems',
            json={
                'year_pillar': '丁A',
                'month_pillar': '癸丑',
                'day_pillar': '己丑',
                'hour_pillar': '壬申',
            },
        )
        self.assertEqual(response.status_code, 400)


if __name__ == '__main__':
    unittest.main()
