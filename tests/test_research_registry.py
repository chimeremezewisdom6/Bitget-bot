import tempfile
import unittest
from pathlib import Path

from research import registry

VALID = """
id = "EXP-0001"
version = "1.0.0"
question = "Does turnover expansion predict continuation?"
hypothesis = "Large turnover with direction continues net of costs."
[event]
type = "turnover_expansion"
[outcomes]
horizons = [5, 15, 30, 60]
[split]
total_days = 30
train_days = 15
validation_days = 7
test_days = 8
embargo_minutes = 60
[decision]
min_events = 200
min_days = 10
ci = 0.95
fdr_q = 0.10
"""


class RegistryTests(unittest.TestCase):
    def write(self, text):
        handle = tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False)
        handle.write(text)
        handle.close()
        return Path(handle.name)

    def test_valid_spec_loads(self):
        path = self.write(VALID)
        spec = registry.load(path)
        self.assertEqual(spec["id"], "EXP-0001")
        self.assertEqual(spec["split"]["train_days"], 15)

    def test_missing_key_is_rejected(self):
        path = self.write(VALID.replace('hypothesis = "Large turnover with direction continues net of costs."\n', ""))
        with self.assertRaises(registry.SpecError):
            registry.load(path)

    def test_wrong_split_is_rejected(self):
        path = self.write(VALID.replace("train_days = 15", "train_days = 14"))
        with self.assertRaises(registry.SpecError):
            registry.load(path)

    def test_missing_event_type_is_rejected(self):
        path = self.write(VALID.replace('type = "turnover_expansion"', 'type = ""'))
        with self.assertRaises(registry.SpecError):
            registry.load(path)


if __name__ == "__main__":
    unittest.main()
