# Demo images

Put 4–5 images you have the rights to here (your own photos are best). They're used by `demo/DEMO.md`:

| File | Content | Shows |
|---|---|---|
| `table_iv.jpg` | A person in a **red shirt** and **blue jeans** (beach optional) | Attribute swap + object deletion (paper Table IV) |
| `street.jpg` | Street scene with people and cars | Hallucinated-object deletion |
| `small_object.jpg` | A small or partly hidden object | ABSTAIN → Review queue |
| `two_dogs.jpg` | Exactly two dogs | Count verification |

COCO images also work for quick tests, for example:
`curl -L http://images.cocodataset.org/val2014/COCO_val2014_000000310196.jpg -o test_images/coco_snow.jpg`
