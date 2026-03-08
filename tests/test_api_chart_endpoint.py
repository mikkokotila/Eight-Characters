import unittest

from fastapi.testclient import TestClient

from eight_characters.main import app


class TestApiChartEndpoint(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    def test_chart_returns_structured_payload(self) -> None:
        response = self.client.post(
            '/api/chart',
            json={
                'date': '1988-02-04',
                'time': '16:30:00',
                'hour_stem': '壬',
                'hour_branch': '申',
                'day_stem': '己',
                'day_branch': '丑',
                'month_stem': '癸',
                'month_branch': '丑',
                'year_stem': '丁',
                'year_branch': '卯',
                'lang': 'en',
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn('header', payload)
        self.assertIn('pillars', payload)
        self.assertEqual(len(payload['pillars']), 4)

    def test_chart_rejects_invalid_stem(self) -> None:
        response = self.client.post(
            '/api/chart',
            json={
                'date': '1988-02-04',
                'time': '16:30:00',
                'hour_stem': 'X',
                'hour_branch': '申',
                'day_stem': '己',
                'day_branch': '丑',
                'month_stem': '癸',
                'month_branch': '丑',
                'year_stem': '丁',
                'year_branch': '卯',
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('Invalid stem', response.json()['detail'])

    def test_chart_rejects_invalid_branch(self) -> None:
        response = self.client.post(
            '/api/chart',
            json={
                'date': '1988-02-04',
                'time': '16:30:00',
                'hour_stem': '壬',
                'hour_branch': 'X',
                'day_stem': '己',
                'day_branch': '丑',
                'month_stem': '癸',
                'month_branch': '丑',
                'year_stem': '丁',
                'year_branch': '卯',
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('Invalid branch', response.json()['detail'])

    def test_chart_rejects_invalid_date_format(self) -> None:
        response = self.client.post(
            '/api/chart',
            json={
                'date': '1988/02/04',
                'time': '16:30:00',
                'hour_stem': '壬',
                'hour_branch': '申',
                'day_stem': '己',
                'day_branch': '丑',
                'month_stem': '癸',
                'month_branch': '丑',
                'year_stem': '丁',
                'year_branch': '卯',
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('date must be in YYYY-MM-DD format.', response.json()['detail'])

    def test_request_validation_errors_are_normalized(self) -> None:
        response = self.client.post(
            '/api/chart',
            json={
                'date': '1988-02-04',
                'time': '16:30:00',
                'hour_stem': '壬',
                'hour_branch': '申',
                'day_branch': '丑',
                'month_stem': '癸',
                'month_branch': '丑',
                'year_stem': '丁',
                'year_branch': '卯',
            },
        )
        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertIn('detail', payload)
        self.assertIsInstance(payload['detail'], str)
        self.assertIn('day_stem', payload['detail'])


if __name__ == '__main__':
    unittest.main()
