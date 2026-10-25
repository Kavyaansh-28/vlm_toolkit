"""Metrics for explicitly labelled records; no synthetic scores are implied."""
from __future__ import annotations

MIN_CALIBRATION_SAMPLES = 30


def _binary_metrics(labels: list[bool], predictions: list[bool]) -> dict:
    tp=sum(a and b for a,b in zip(labels,predictions)); fp=sum(not a and b for a,b in zip(labels,predictions)); fn=sum(a and not b for a,b in zip(labels,predictions))
    precision=tp/(tp+fp) if tp+fp else 0.0; recall=tp/(tp+fn) if tp+fn else 0.0
    return {"accuracy":sum(a==b for a,b in zip(labels,predictions))/len(labels), "precision":precision,
            "recall":recall,"f1":2*precision*recall/(precision+recall) if precision+recall else 0.0}


def classification_metrics(records: list[dict]) -> dict:
    """Calculate labelled binary metrics and binned calibration (minimum 10 rows).

    Records need `expected_reliable` and `reliability` in [0, 1]. Calibration
    needs at least 30 records to avoid presenting tiny-sample diagrams. Optional
    `error_type`/`predicted_error_type` fields produce per-error-type detection stats.
    """
    labelled=[r for r in records if "expected_reliable" in r and "reliability" in r]
    if not labelled:
        return {"available": False,"message":"Calibration unavailable: insufficient evaluation samples. Supply labelled records before reporting metrics.","calibration_available":False}
    y=[bool(r["expected_reliable"]) for r in labelled]
    p=[max(0.0,min(1.0,float(r["reliability"]))) for r in labelled]
    pred=[x>=.5 for x in p]
    result={"available":True,**_binary_metrics(y,pred),"brier":sum((x-int(t))**2 for x,t in zip(p,y))/len(y),"sample_count":len(y)}
    if len(y) < MIN_CALIBRATION_SAMPLES:
        result.update({"calibration_available":False,"ece":None,"reliability_diagram":[],"calibration_message":f"Calibration unavailable: insufficient evaluation samples (need at least {MIN_CALIBRATION_SAMPLES} labelled rows)."})
    else:
        bins=[]
        for index in range(10):
            subset=[(prob,label) for prob,label in zip(p,y) if min(9,int(prob*10))==index]
            if subset:
                bins.append({"lower":index/10,"upper":(index+1)/10,"count":len(subset),"mean_confidence":sum(a for a,_ in subset)/len(subset),"accuracy":sum(int(b) for _,b in subset)/len(subset)})
        result["ece"]=sum(item["count"]/len(y)*abs(item["mean_confidence"]-item["accuracy"]) for item in bins)
        result.update({"calibration_available":True,"reliability_diagram":bins})
    error_types=sorted({r.get("error_type") for r in labelled if r.get("error_type")})
    if error_types:
        result["error_detection"]={}
        for error in error_types:
            truth=[r.get("error_type")==error for r in labelled]
            guessed=[r.get("predicted_error_type")==error for r in labelled]
            result["error_detection"][error]=_binary_metrics(truth,guessed)
    decisions=[r.get("decision") for r in labelled if r.get("decision")]
    if decisions:
        result["abstention_rate"]=sum(x=="ABSTAIN" for x in decisions)/len(decisions)
    if any("corrected_correct" in r for r in labelled):
        correction_rows=[r for r in labelled if "corrected_correct" in r]
        result["correction_success_rate"]=sum(bool(r["corrected_correct"]) for r in correction_rows)/len(correction_rows)
        result["false_correction_rate"]=sum(bool(r.get("false_correction",False)) for r in correction_rows)/len(correction_rows)
    return result
