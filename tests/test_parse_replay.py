import unittest

from showdown_pipeline.parser import parse_replay_payload


class ParseReplayTests(unittest.TestCase):
    def test_parses_two_team_records(self) -> None:
        payload = {
            "format": "gen9ou",
            "rating": 1600,
            "uploadtime": 1_700_000_000,
            "log": "\n".join([
                "|player|p1|Alice|1|1725",
                "|player|p2|Bob|2|1580",
                "|poke|p1|Great Tusk, M|",
                "|poke|p1|Kingambit, F|",
                "|poke|p2|Dragapult, M|",
                "|turn|1",
                "|switch|p1a: Tusk|Great Tusk, L100, M|100/100",
                "|switch|p2a: Pult|Dragapult, L100, M|100/100",
                "|turn|7",
                "|faint|p2a: Pult",
                "|turn|28",
                "|win|Alice",
            ]),
        }

        frame = parse_replay_payload("gen9ou-test", payload).sort("player")

        self.assertEqual(frame.height, 2)
        alice = frame.filter(frame["player"] == "Alice").row(0, named=True)
        bob = frame.filter(frame["player"] == "Bob").row(0, named=True)
        self.assertTrue(alice["won"])
        self.assertFalse(bob["won"])
        self.assertEqual(alice["rating"], 1725)
        self.assertEqual(bob["rating"], 1580)
        self.assertEqual(alice["turns"], 28)
        self.assertEqual(alice["pokemon"], ["Great Tusk, M", "Kingambit, F"])
        self.assertEqual(alice["schema_version"], 2)
        self.assertTrue(alice["got_first_ko"])
        self.assertFalse(bob["got_first_ko"])
        self.assertEqual(alice["first_ko_turn"], 7)
        self.assertEqual(alice["first_ko_player"], "Alice")
        self.assertEqual(alice["first_ko_victim"], "Dragapult")
        self.assertFalse(alice["first_ko_tied"])
        self.assertEqual(alice["total_faints"], 1)

    def test_marks_same_turn_double_ko_as_ambiguous(self) -> None:
        payload = {
            "format": "gen9ou",
            "rating": 1700,
            "uploadtime": 1_700_000_000,
            "log": "\n".join([
                "|player|p1|Alice|",
                "|player|p2|Bob|",
                "|turn|12",
                "|faint|p2a: Pult",
                "|faint|p1a: Tusk",
                "|win|Alice",
            ]),
        }

        frame = parse_replay_payload("gen9ou-double-ko", payload)

        self.assertEqual(frame["first_ko_tied"].to_list(), [True, True])
        self.assertEqual(frame["got_first_ko"].to_list(), [None, None])
        self.assertEqual(frame["first_ko_turn"].to_list(), [12, 12])
        self.assertEqual(frame["total_faints"].to_list(), [2, 2])

    def test_distinguishes_parsed_no_ko_replay_from_legacy_data(self) -> None:
        payload = {
            "format": "gen9ou",
            "rating": None,
            "uploadtime": 1_700_000_000,
            "log": "\n".join([
                "|player|p1|Alice|",
                "|player|p2|Bob|",
                "|turn|4",
                "|win|Bob",
            ]),
        }

        frame = parse_replay_payload("gen9ou-forfeit", payload)

        self.assertEqual(frame["schema_version"].to_list(), [2, 2])
        self.assertEqual(frame["total_faints"].to_list(), [0, 0])
        self.assertEqual(frame["got_first_ko"].to_list(), [None, None])
        self.assertEqual(frame["first_ko_turn"].to_list(), [None, None])


if __name__ == "__main__":
    unittest.main()
