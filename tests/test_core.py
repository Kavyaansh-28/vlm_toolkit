import unittest

from claims import extract_claims
from correction import corrected_response
from scoring import score_claims


class CoreTests(unittest.TestCase):
    def test_extracts_colour_and_object(self):
        claims = extract_claims("There is a red car and a dog.")
        self.assertIn({"object": "car", "attribute": "color", "value": "red"}, claims)
        self.assertIn({"object": "dog", "attribute": None, "value": None}, claims)

    def test_thresholds(self):
        self.assertEqual(score_claims([{"score": .8}])["decision"], "ACCEPT")
        self.assertEqual(score_claims([{"score": .4}])["decision"], "CORRECT")
        self.assertEqual(score_claims([{"score": .6}])["decision"], "FLAG")

    def test_removes_unverified_object(self):
        answer = corrected_response("A person, a bicycle and a dog.", [{"object": "dog", "status": "NOT VERIFIED"}])
        self.assertNotIn("dog", answer)

    def test_replaces_wrong_colour(self):
        answer = corrected_response("There is a blue car.", [{"object": "car", "status": "INCORRECT", "verified_value": "red"}])
        self.assertEqual(answer, "There is a red car.")


if __name__ == "__main__":
    unittest.main()
