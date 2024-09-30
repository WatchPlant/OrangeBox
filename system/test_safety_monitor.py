import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from safety_monitor import (
    BatteryCurrentCheck,
    BatteryLevel,
    BatteryVoltageCheck,
    ChargingState,
    TemperatureCheck,
)


class TestBatteryVoltageCheck(unittest.TestCase):
    def test_initial_status(self):
        checker = BatteryVoltageCheck()
        self.assertEqual(checker.status, BatteryLevel.OK)

    def test_update_and_check(self):
        checker = BatteryVoltageCheck()
        for _ in range(10):
            checker.update(3.4)
        self.assertEqual(checker.check(), BatteryLevel.CRIT)

        checker = BatteryVoltageCheck()
        for _ in range(10):
            checker.update(3.65)
        self.assertEqual(checker.check(), BatteryLevel.LOW1)

        checker = BatteryVoltageCheck()
        checker.status = BatteryLevel.LOW1
        for _ in range(10):
            checker.update(3.55)
        self.assertEqual(checker.check(), BatteryLevel.LOW2)

        checker = BatteryVoltageCheck()
        checker.status = BatteryLevel.LOW2
        for _ in range(10):
            checker.update(3.83)
        self.assertEqual(checker.check(), BatteryLevel.OK)

        checker = BatteryVoltageCheck()
        checker.status = BatteryLevel.LOW1
        for _ in range(10):
            checker.update(3.86)
        self.assertEqual(checker.check(), BatteryLevel.OK)


class TestBatteryCurrentCheck(unittest.TestCase):
    def test_initial_state(self):
        checker = BatteryCurrentCheck()
        self.assertEqual(checker.check(), ChargingState.DEFAULT)

    @patch("safety_monitor.datetime")
    def test_update_and_check(self, mock_datetime):
        # Too short to determine charging state.
        checker = BatteryCurrentCheck()
        for _ in range(12):
            mock_datetime.now.return_value = datetime.now()
            checker.update(80)
        self.assertEqual(checker.check(), ChargingState.CHARGING)

        # Normal charging state.
        start_time = mock_datetime.now.return_value = datetime(2024, 9, 30, 12, 0, 0)
        checker = BatteryCurrentCheck()
        for i in range(13):
            base_current = 150 - i * 10
            for j in range(10):
                mock_datetime.now.return_value = start_time + timedelta(hours=i, seconds=j*5)
                checker.update(base_current + j)
        self.assertEqual(checker.check(), ChargingState.CHARGING)

        # Abnormal charging state.
        start_time = mock_datetime.now.return_value = datetime(2024, 9, 30, 12, 0, 0)
        checker = BatteryCurrentCheck()
        for i in range(13):
            base_current = 150 - i * 1
            for j in range(10):
                mock_datetime.now.return_value = start_time + timedelta(hours=i, seconds=j*5)
                checker.update(base_current + j)
        self.assertEqual(checker.check(), ChargingState.DANGER)


class TestTemperatureCheck(unittest.TestCase):
    def test_initial_check(self):
        checker = TemperatureCheck()
        self.assertTrue(checker.check(50))

    def test_check_over_max_temp(self):
        checker = TemperatureCheck()
        checker.last_update = datetime.now() - timedelta(hours=4)
        self.assertFalse(checker.check(70))

    def test_check_within_max_temp(self):
        checker = TemperatureCheck()
        checker.last_update = datetime.now() - timedelta(hours=2)
        self.assertTrue(checker.check(50))

    def test_check_within_max_temp_with_no_update(self):
        checker = TemperatureCheck()
        self.assertTrue(checker.check(70))


if __name__ == '__main__':
    unittest.main()