import unittest

import sys
import os

sys.path.append(os.path.abspath("..\\"))

from api_client import EntsoeClient
from datetime import datetime


class TestDocumentParsing(unittest.TestCase):
    client: EntsoeClient

    def setUp(self) -> None:
        self.client = EntsoeClient("fake-key")
        return super().setUp()

    def test_be_60m(self):
        with open(".\\datasets\\BE_60M.xml") as f:
            data = f.read()

        self.maxDiff = None
        self.assertDictEqual(
            self.client.parse_price_document(data),
            {
                datetime.fromisoformat("2024-10-07T22:00:00Z"): 64.98,
                datetime.fromisoformat("2024-10-07T23:00:00Z"): 57.86,
                datetime.fromisoformat("2024-10-08T00:00:00Z"): 53.73,
                datetime.fromisoformat("2024-10-08T01:00:00Z"): 47.52,
                datetime.fromisoformat("2024-10-08T02:00:00Z"): 47.05,
                datetime.fromisoformat("2024-10-08T03:00:00Z"): 56.89,
                datetime.fromisoformat("2024-10-08T04:00:00Z"): 77.77,
                datetime.fromisoformat("2024-10-08T05:00:00Z"): 88.24,
                datetime.fromisoformat("2024-10-08T06:00:00Z"): 100,
                datetime.fromisoformat("2024-10-08T07:00:00Z"): 84.92,
                datetime.fromisoformat("2024-10-08T08:00:00Z"): 74.6,
                datetime.fromisoformat("2024-10-08T09:00:00Z"): 68.82,
                datetime.fromisoformat("2024-10-08T10:00:00Z"): 60.56,
                datetime.fromisoformat("2024-10-08T11:00:00Z"): 63.86,
                datetime.fromisoformat("2024-10-08T12:00:00Z"): 68.1,
                datetime.fromisoformat("2024-10-08T13:00:00Z"): 68.37,
                datetime.fromisoformat("2024-10-08T14:00:00Z"): 76.35,
                datetime.fromisoformat("2024-10-08T15:00:00Z"): 54.04,
                datetime.fromisoformat("2024-10-08T16:00:00Z"): 98.97,
                datetime.fromisoformat("2024-10-08T17:00:00Z"): 115.47,
                datetime.fromisoformat("2024-10-08T18:00:00Z"): 86.85,
                datetime.fromisoformat("2024-10-08T19:00:00Z"): 69.59,
                datetime.fromisoformat("2024-10-08T20:00:00Z"): 57.42,
                datetime.fromisoformat("2024-10-08T21:00:00Z"): 50,
            },
        )

    def test_be_60m_15m_mix(self):
        with open("./datasets/BE_60M_15M_mix.xml") as f:
            data = f.read()

        self.maxDiff = None
        self.assertDictEqual(
            self.client.parse_price_document(data),
            {
                # part 1 - 15M resolution
                datetime.fromisoformat("2024-10-05T22:00:00Z"): 55.35,
                datetime.fromisoformat("2024-10-05T23:00:00Z"): 44.22,
                datetime.fromisoformat("2024-10-06T00:00:00Z"): 40.32,
                datetime.fromisoformat("2024-10-06T01:00:00Z"): 31.86,
                datetime.fromisoformat("2024-10-06T02:00:00Z"): 28.37,
                datetime.fromisoformat("2024-10-06T03:00:00Z"): 28.71,
                datetime.fromisoformat("2024-10-06T04:00:00Z"): 31.75,
                datetime.fromisoformat("2024-10-06T05:00:00Z"): 35.47,
                datetime.fromisoformat("2024-10-06T06:00:00Z"): 37.8,
                datetime.fromisoformat("2024-10-06T07:00:00Z"): 33.31,
                datetime.fromisoformat("2024-10-06T08:00:00Z"): 33.79,
                datetime.fromisoformat("2024-10-06T09:00:00Z"): 16.68,
                datetime.fromisoformat("2024-10-06T10:00:00Z"): 5.25,
                datetime.fromisoformat("2024-10-06T11:00:00Z"): -0.01,
                datetime.fromisoformat(
                    "2024-10-06T12:00:00Z"
                ): -0.01,  # repeated value, not present in the dataset!
                datetime.fromisoformat("2024-10-06T13:00:00Z"): 0.2,
                datetime.fromisoformat("2024-10-06T14:00:00Z"): 48.4,
                datetime.fromisoformat("2024-10-06T15:00:00Z"): 50.01,
                datetime.fromisoformat("2024-10-06T16:00:00Z"): 65.63,
                datetime.fromisoformat("2024-10-06T17:00:00Z"): 77.18,
                datetime.fromisoformat("2024-10-06T18:00:00Z"): 81.92,
                datetime.fromisoformat("2024-10-06T19:00:00Z"): 64.36,
                datetime.fromisoformat("2024-10-06T20:00:00Z"): 60.79,
                datetime.fromisoformat("2024-10-06T21:00:00Z"): 52.33,
                # part 2 - 15M resolution
                datetime.fromisoformat("2024-10-06T22:00:00Z"): 34.58,
                datetime.fromisoformat("2024-10-06T23:00:00Z"): 35.34,
                datetime.fromisoformat("2024-10-07T00:00:00Z"): 33.25,
                datetime.fromisoformat("2024-10-07T01:00:00Z"): 29.48,
                datetime.fromisoformat("2024-10-07T02:00:00Z"): 31.88,
                datetime.fromisoformat("2024-10-07T03:00:00Z"): 41.35,
                datetime.fromisoformat("2024-10-07T04:00:00Z"): 57.14,
                datetime.fromisoformat("2024-10-07T05:00:00Z"): 91.84,
                datetime.fromisoformat("2024-10-07T06:00:00Z"): 108.32,
                datetime.fromisoformat("2024-10-07T07:00:00Z"): 91.8,
                datetime.fromisoformat("2024-10-07T08:00:00Z"): 66.05,
                datetime.fromisoformat("2024-10-07T09:00:00Z"): 60.21,
                datetime.fromisoformat("2024-10-07T10:00:00Z"): 56.02,
                datetime.fromisoformat("2024-10-07T11:00:00Z"): 43.29,
                datetime.fromisoformat("2024-10-07T12:00:00Z"): 55,
                datetime.fromisoformat("2024-10-07T13:00:00Z"): 57.6,
                datetime.fromisoformat("2024-10-07T14:00:00Z"): 81.16,
                datetime.fromisoformat("2024-10-07T15:00:00Z"): 104.54,
                datetime.fromisoformat("2024-10-07T16:00:00Z"): 159.2,
                datetime.fromisoformat("2024-10-07T17:00:00Z"): 149.41,
                datetime.fromisoformat("2024-10-07T18:00:00Z"): 121.49,
                datetime.fromisoformat("2024-10-07T19:00:00Z"): 90,
                datetime.fromisoformat("2024-10-07T20:00:00Z"): 90.44,
                datetime.fromisoformat("2024-10-07T21:00:00Z"): 77.18,
                # part 3 - 60M resolution
                datetime.fromisoformat("2024-10-07T22:00:00Z"): 64.98,
                datetime.fromisoformat("2024-10-07T23:00:00Z"): 57.86,
                datetime.fromisoformat("2024-10-08T00:00:00Z"): 53.73,
                datetime.fromisoformat("2024-10-08T01:00:00Z"): 47.52,
                datetime.fromisoformat("2024-10-08T02:00:00Z"): 47.05,
                datetime.fromisoformat("2024-10-08T03:00:00Z"): 56.89,
                datetime.fromisoformat("2024-10-08T04:00:00Z"): 77.77,
                datetime.fromisoformat("2024-10-08T05:00:00Z"): 88.24,
                datetime.fromisoformat("2024-10-08T06:00:00Z"): 100,
                datetime.fromisoformat("2024-10-08T07:00:00Z"): 84.92,
                datetime.fromisoformat("2024-10-08T08:00:00Z"): 74.6,
                datetime.fromisoformat("2024-10-08T09:00:00Z"): 68.82,
                datetime.fromisoformat("2024-10-08T10:00:00Z"): 60.56,
                datetime.fromisoformat("2024-10-08T11:00:00Z"): 63.86,
                datetime.fromisoformat("2024-10-08T12:00:00Z"): 68.1,
                datetime.fromisoformat("2024-10-08T13:00:00Z"): 68.37,
                datetime.fromisoformat("2024-10-08T14:00:00Z"): 76.35,
                datetime.fromisoformat("2024-10-08T15:00:00Z"): 54.04,
                datetime.fromisoformat("2024-10-08T16:00:00Z"): 98.97,
                datetime.fromisoformat("2024-10-08T17:00:00Z"): 115.47,
                datetime.fromisoformat("2024-10-08T18:00:00Z"): 86.85,
                datetime.fromisoformat("2024-10-08T19:00:00Z"): 69.59,
                datetime.fromisoformat("2024-10-08T20:00:00Z"): 57.42,
                datetime.fromisoformat("2024-10-08T21:00:00Z"): 50,
            },
        )

    def test_de_60m_15m_overlap(self):
        with open("./datasets/DE_60M_15M_overlap.xml") as f:
            data = f.read()

        self.maxDiff = None
        self.assertDictEqual(
            self.client.parse_price_document(data),
            {
                # part 1 - 60M resolution
                datetime.fromisoformat("2024-10-05T22:00:00Z"): 67.04,
                datetime.fromisoformat("2024-10-05T23:00:00Z"): 63.97,
                datetime.fromisoformat("2024-10-06T00:00:00Z"): 62.83,
                datetime.fromisoformat("2024-10-06T01:00:00Z"): 63.35,
                datetime.fromisoformat("2024-10-06T02:00:00Z"): 62.71,
                datetime.fromisoformat("2024-10-06T03:00:00Z"): 63.97,
                datetime.fromisoformat("2024-10-06T04:00:00Z"): 63.41,
                datetime.fromisoformat("2024-10-06T05:00:00Z"): 72.81,
                datetime.fromisoformat("2024-10-06T06:00:00Z"): 77.2,
                datetime.fromisoformat("2024-10-06T07:00:00Z"): 66.06,
                datetime.fromisoformat("2024-10-06T08:00:00Z"): 35.28,
                datetime.fromisoformat("2024-10-06T09:00:00Z"): 16.68,
                datetime.fromisoformat("2024-10-06T10:00:00Z"): 5.25,
                datetime.fromisoformat("2024-10-06T11:00:00Z"): -0.01,
                datetime.fromisoformat(
                    "2024-10-06T12:00:00Z"
                ): -0.01,  # repeated value, not present in the dataset!
                datetime.fromisoformat("2024-10-06T13:00:00Z"): 0.2,
                datetime.fromisoformat("2024-10-06T14:00:00Z"): 59.6,
                datetime.fromisoformat("2024-10-06T15:00:00Z"): 90.94,
                datetime.fromisoformat("2024-10-06T16:00:00Z"): 106.3,
                datetime.fromisoformat("2024-10-06T17:00:00Z"): 97.22,
                datetime.fromisoformat("2024-10-06T18:00:00Z"): 72.98,
                datetime.fromisoformat("2024-10-06T19:00:00Z"): 59.37,
                datetime.fromisoformat("2024-10-06T20:00:00Z"): 58.69,
                datetime.fromisoformat("2024-10-06T21:00:00Z"): 51.71,
                # part 2 - 60M resolution
                datetime.fromisoformat("2024-10-06T22:00:00Z"): 34.58,
                datetime.fromisoformat("2024-10-06T23:00:00Z"): 35.34,
                datetime.fromisoformat("2024-10-07T00:00:00Z"): 33.25,
                datetime.fromisoformat("2024-10-07T01:00:00Z"): 30.15,
                datetime.fromisoformat("2024-10-07T02:00:00Z"): 36.09,
                datetime.fromisoformat("2024-10-07T03:00:00Z"): 46.73,
                datetime.fromisoformat("2024-10-07T04:00:00Z"): 67.59,
                datetime.fromisoformat("2024-10-07T05:00:00Z"): 100.92,
                datetime.fromisoformat("2024-10-07T06:00:00Z"): 108.32,
                datetime.fromisoformat("2024-10-07T07:00:00Z"): 91.86,
                datetime.fromisoformat("2024-10-07T08:00:00Z"): 66.09,
                datetime.fromisoformat("2024-10-07T09:00:00Z"): 60.22,
                datetime.fromisoformat("2024-10-07T10:00:00Z"): 54.11,
                datetime.fromisoformat("2024-10-07T11:00:00Z"): 43.29,
                datetime.fromisoformat("2024-10-07T12:00:00Z"): 55,
                datetime.fromisoformat("2024-10-07T13:00:00Z"): 67.01,
                datetime.fromisoformat("2024-10-07T14:00:00Z"): 97.9,
                datetime.fromisoformat("2024-10-07T15:00:00Z"): 120.71,
                datetime.fromisoformat("2024-10-07T16:00:00Z"): 237.65,
                datetime.fromisoformat("2024-10-07T17:00:00Z"): 229.53,
                datetime.fromisoformat("2024-10-07T18:00:00Z"): 121.98,
                datetime.fromisoformat("2024-10-07T19:00:00Z"): 99.93,
                datetime.fromisoformat("2024-10-07T20:00:00Z"): 91.91,
                datetime.fromisoformat("2024-10-07T21:00:00Z"): 79.12,
            },
        )

    def test_be_15M_avg(self):
        with open("./datasets/BE_15M_avg.xml") as f:
            data = f.read()

        self.maxDiff = None
        self.assertDictEqual(
            self.client.parse_price_document(data),
            {
                # part 1 - 15M resolution
                datetime.fromisoformat("2024-10-05T22:00:00Z"): 39.06,  # average
                datetime.fromisoformat("2024-10-05T23:00:00Z"): 44.22,  # average
                datetime.fromisoformat("2024-10-06T00:00:00Z"): 36.30,  # average
                datetime.fromisoformat("2024-10-06T01:00:00Z"): 36.30,  # extended
                datetime.fromisoformat("2024-10-06T02:00:00Z"): 36.30,  # extended
                # part 2 - 60M resolution
                datetime.fromisoformat("2024-10-06T03:00:00Z"): 64.98,
                datetime.fromisoformat("2024-10-06T04:00:00Z"): 64.98,  # extended
                datetime.fromisoformat("2024-10-06T05:00:00Z"): 57.86,
            },
        )

    def test_be_exact4(self):
        with open("./datasets/BE_15M_exact4.xml") as f:
            data = f.read()

        self.maxDiff = None
        self.assertDictEqual(
            self.client.parse_price_document(data),
            {
                # part 1 - 15M resolution
                datetime.fromisoformat("2024-10-05T22:00:00Z"): 42.94,  # average
            },
        )


if __name__ == "__main__":
    unittest.main()
