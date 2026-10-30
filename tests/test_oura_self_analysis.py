import unittest
from datetime import date
import oura_self_analysis as app

class TestSmoke(unittest.TestCase):
    def test_collection_config(self):
        self.assertEqual(app.COLLECTIONS['daily_sleep'], 'daily')
        self.assertIn('sleep', app.DEFAULT_COLLECTIONS)

    def test_token_requirements(self):
        with self.assertRaises(app.OuraError):
            app.token_save({'access_token': 'example', 'expires_in': 123})

    def test_record_identity(self):
        self.assertEqual(app.record_identity('daily_sleep', {'id': 'abc'}), 'abc')

if __name__ == '__main__':
    unittest.main()
