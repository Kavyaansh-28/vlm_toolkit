from __future__ import annotations
from core.schemas import Claim

def graph_data(claims: list[Claim]) -> dict:
    nodes, edges, graph_claims = {}, [], []
    for claim in claims:
        nodes.setdefault(claim.subject, {"id": claim.subject, "label": claim.subject, "kind": "object"})
        if claim.instance_id:
            nodes.setdefault(claim.instance_id, {"id": claim.instance_id, "label": claim.instance_id, "kind": "object_instance", "class": claim.subject})
            edges.append({"source": claim.subject, "target": claim.instance_id, "label": "instance"})
        if claim.type == "attribute":
            target = f"{claim.subject}:{claim.attribute}:{claim.value}"
            nodes[target] = {"id": target, "label": str(claim.value), "kind": "attribute_value", "attribute": claim.attribute}
            edges.append({"source": claim.instance_id or claim.subject, "target": target, "label": claim.attribute, "claim_id": claim.id})
        elif claim.type == "relation" and claim.object:
            nodes.setdefault(claim.object, {"id": claim.object, "label": claim.object, "kind": "object"})
            edges.append({"source": claim.instance_id or claim.subject, "target": claim.object, "label": str(claim.value), "claim_id": claim.id})
        elif claim.type == "quantity":
            edges.append({"source": claim.subject, "target": f"quantity:{claim.subject}:{claim.value}", "label": "quantity", "claim_id": claim.id})
            nodes[f"quantity:{claim.subject}:{claim.value}"] = {"id": f"quantity:{claim.subject}:{claim.value}", "label": str(claim.value), "kind": "quantity"}
        graph_claims.append({"id": claim.id, "type": claim.type, "subject": claim.subject, "attribute": claim.attribute, "value": claim.value, "object": claim.object, "instance_id": claim.instance_id})
    return {"nodes": list(nodes.values()), "edges": edges, "claims": graph_claims}
