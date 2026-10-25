# 5-minute demo script

**Setup (before the audience arrives)**
- `scripts\dev.ps1` (Windows) or `./dev-frontend.sh` (macOS). Open `http://127.0.0.1:3000/analyze`.
- Run one analysis beforehand so the Grounding DINO and CLIP weights are loaded and cached.
- Have the images from `test_images/` ready, plus `results/RESULTS.md` if the Kaggle run has finished.

## 1. The problem (30 s)
VLMs make two kinds of mistakes:
- **hallucinated objects:** they mention things that aren't in the image;
- **mis-bound attributes:** they give an object the wrong colour or material, such as "blue shirt, red jeans" when the colours are swapped.

The toolkit catches and fixes both at inference time, without retraining the model.

## 2. Paper Table IV, live (90 s)
1. Upload the red-shirt / blue-jeans photo.
2. Open **Controlled candidate override** and paste:
   `A person in a blue shirt and red jeans stands on the beach holding a surfboard.`
3. Click **Run reliability analysis**, then show:
   - **Evidence canvas:** Grounding DINO boxes.
   - **Claim verification and action** table:
     - person: ACCEPT
     - shirt: CORRECT (swap shirt ↔ jeans), with the crop thumbnail
     - jeans: CORRECT (swap)
     - surfboard: CORRECT (delete, no evidence)
   - **Correction** diff: *"A person in a red shirt and blue jeans stands on the beach."*

   The binding check is done on the object's *own crop*, so blue elsewhere in the image can't validate "blue shirt".

## 3. Re-ranking and abstention (60 s)
1. Use the street or snow image with two candidates:
   `A skier in a red jacket holds a snowboard next to a dog. ||| A person with a snowboard stands on the snow.`
2. On the **Candidates** page, show:
   - candidate 1 has low R, with unclear claims flagged;
   - candidate 2 is selected with **RERANK** and the stated reason (R below the threshold vs. a reliable alternative);
   - the Eq. 3 terms in the reliability panel: mean v, agreement A_j, and p_j ("n/a (API model)" for Gemini, real for `hf-local`).

## 4. Human review (45 s)
Use an image with a small or ambiguous object, then open **Review**:
- flagged claims appear with their crop, v and explanation;
- label one as "Claim is true", reload, and show that the label persisted (audit log).

## 5. Benchmarks (60 s)
Open **Evaluation** and walk through the POPE and CHAIR tables:
- **POPE:** base vs. toolkit across random / popular / adversarial;
- **CHAIR:** CHAIR_S / CHAIR_I / recall for every ablation, plus the latency ratio.

How the numbers were produced: Kaggle T4 → HF dataset repo, with thresholds tuned on a held-out split. Be explicit that POPE and CHAIR measure object hallucination only.

## Offline fallback
If Wi-Fi or an API key fails:
- `python demo_paper_example.py` prints the Table IV trace with no models and no network;
- the manual candidate override needs no API key, only the cached verifier weights.
