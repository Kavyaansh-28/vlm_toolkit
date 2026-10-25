from evaluation.chair import chair, mentioned_objects


def test_chair_hand_computed():
    rows = [{"final_text": "A dog and a cat on a couch.", "gt_objects": ["dog", "couch"]},
            {"final_text": "A man rides a horse.", "gt_objects": ["person", "horse"]}]
    m = chair(rows)
    assert m["CHAIR_S"] == .5 and m["CHAIR_I"] == 1 / 5 and m["object_recall"] == 1.0


def test_chair_uses_synonyms_and_ignores_non_coco_words():
    assert mentioned_objects("Two puppies and a sofa near a red shirt.") == {"dog", "couch"}


def test_object_recall_exposes_over_deletion():
    rows = [{"final_text": "A dog.", "gt_objects": ["dog", "cat"]}]
    assert chair(rows)["object_recall"] == .5


def test_not_run_without_rows():
    assert chair([])["status"] == "NOT RUN"
