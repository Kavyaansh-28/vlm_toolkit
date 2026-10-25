from claims.extractor import extract
from claims.vocab import coco_classes, find_objects, surface_forms, to_class


def _set(claims):
    return {(c.type, c.subject, c.attribute, c.value, c.object) for c in claims}


def test_vocabulary_has_80_coco_classes():
    classes = coco_classes()
    assert len(classes) == 80 and "dining table" in classes and "hair drier" in classes


def test_to_class_synonyms_plurals_irregulars():
    assert to_class("men") == "person" and to_class("children") == "person"
    assert to_class("dining tables") == "dining table" and to_class("puppies") == "dog"
    assert to_class("bus") == "bus" and to_class("knives") == "knife"
    assert to_class("shirt") == "shirt" and to_class("shirt", include_extra=False) is None


def test_find_objects_longest_match_no_overlap():
    found = [cls for cls, _, _ in find_objects("a hot dog next to a dog and a fire hydrant")]
    assert found == ["hot dog", "dog", "fire hydrant"]


def test_orange_colour_is_not_the_fruit():
    assert [c for c, _, _ in find_objects("an orange cat beside an orange")] == ["cat", "orange"]


def test_surface_forms_cover_synonyms_and_plurals():
    forms = surface_forms("person")
    assert "men" in forms and "woman" in forms and "people" in forms


def test_rich_sentence():
    claims = extract("A woman in a blue shirt is sitting on a wooden bench next to two dogs. The bench is brown.")
    got = _set(claims)
    assert {("object", "person", None, None, None), ("object", "shirt", None, None, None), ("object", "bench", None, None, None),
            ("object", "dog", None, None, None)} <= got
    assert ("attribute", "shirt", "color", "blue", None) in got
    assert ("attribute", "bench", "material", "wooden", None) in got
    assert ("attribute", "bench", "color", "brown", None) in got
    assert ("quantity", "dog", None, 2, None) in got
    assert any(t == "relation" and o == "dog" for t, _, _, _, o in got)


def test_claim_text_is_sentence_span_and_surface_recorded():
    claims = extract("A cat sleeps. Three men stand near a bus.")
    person = next(c for c in claims if c.subject == "person" and c.type == "object")
    assert person.text == "Three men stand near a bus." and person.surface == "men"


def test_coordinated_attributes():
    got = _set(extract("A red and white bus."))
    assert ("attribute", "bus", "color", "red", None) in got and ("attribute", "bus", "color", "white", None) in got


def test_stable_ids_are_deterministic():
    assert [c.id for c in extract("A red car.")] == [c.id for c in extract("A red car.")]
