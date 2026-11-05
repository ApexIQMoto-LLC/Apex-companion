"""Conservative, no-API inference over source-labelled local history."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timezone
import re

from .memory import keywords


def consolidate(store, memory=None, *, limit=90) -> dict:
    """Deduplicate existing explicit owner memories into evidence-linked graph facts.

    This never guesses a psychological trait or turns an AI answer into an owner fact.
    Existing memory entries remain untouched, with deletion still managed separately.
    """
    if memory is None or not store.permitted("projects", "local"):
        return {"imported":0,"reused":0,"status":"not_authorized_or_no_memories"}
    entries=memory.list_memories(limit=limit)
    imported=0; seen=set(); duplicates=0
    for item in reversed(entries):
        fact=str(item.get("fact", ""))[:700]
        normalized=" ".join(fact.lower().split())
        if normalized in seen:
            duplicates+=1; continue
        seen.add(normalized)
        if len(fact)<8:continue
        # Do not automatically reclassify old personal, medical, banking or
        # relationship facts as harmless project knowledge. Only project-topic
        # matches are consolidated without extra owner consent.
        project_terms=("apexiq","replay studio","unity","steam","aris","hardware","beta rider","device test","ride manager")
        if not any(term in normalized for term in project_terms):
            continue
        # A source-tagged *owner-approved statement*, not a model inference.
        store.add_entity("decision", fact[:130], fact,scope="projects",source="conversation",
                         source_ref="memory:"+str(item.get("id")),observed_at=item.get("created_at"),confidence=1.0)
        imported+=1
    if imported:
        store.remember_insight(f"Imported {imported} explicit owner memories with their original dates; not verified current facts.",
                               "MemoryVault explicit entries",imported,scope="projects")
    return {"imported":imported,"reused":duplicates,"status":"ok"}


def cluster_related_facts(store,scope="projects",minimum=3):
    """Identify repeated *topics*, not personality or cause-and-effect claims."""
    if not store.permitted(scope,"local"):
        return []
    exported=store.export_scope(scope)
    nodes=exported["entities"]
    groups=defaultdict(list)
    for node in nodes:
        for word in keywords(node["title"]):
            if len(word)>=5:
                groups[word].append(node)
    candidates=[]
    for term,items in groups.items():
        ids={r["id"] for r in items}
        if len(ids)>=minimum:
            distinct_sources={r["source"] for r in items}
            candidates.append({"theme":term,"related_facts":len(ids),"sources":sorted(distinct_sources)})
    candidates.sort(key=lambda i:i["related_facts"],reverse=True)
    return candidates[:8]


def plan_today(store,alert_center=None,*, destination="local"):
    existing=store.list_plan(destination=destination,limit=24)
    today=date.today().isoformat()
    ranked=[]
    for task in existing:
        due=task.get("due_day")
        late=(due is not None and due<today)
        score=max(0,6-int(task["priority"]))+(3 if late else 2 if due==today else 0)
        ranked.append({"type":"saved_goal","task_id":task["id"],"title":task["title"],
                       "reason":task["rationale"] or "Saved owner priority", "status":task["status"],
                       "due_day":due,"score":score,"scope":task["scope"],"source":task["source"]})
    # High-priority alerts are *recommendations* only. No new tasks are
    # silently committed to the owner's schedule or calendar.
    if alert_center and store.permitted("operations",destination):
        for alert in alert_center.recent(limit=18,only_unread=True):
            text=str(alert["title"])
            ranked.append({"type":"alert_recommendation","task_id":None,
                           "title":"Review: "+text,
                           "reason":str(alert["details"])[:240],"status":"suggested",
                           "due_day":None,"score":6 if alert["severity"]=="warning" else 4,
                           "scope":"operations","source":"local_alert:"+str(alert["id"])})
    ranked.sort(key=lambda r:(-r["score"],r["due_day"] or "9999-12-31",r["title"]))
    return {"generated_at_utc":datetime.now(timezone.utc).isoformat(),"items":ranked[:12],
            "caveat":"Recommendations come only from saved goals and observed alerts; not a full personal calendar."}


def analysis_report(store, *, destination="local",memory=None):
    trends=store.trends(destination=destination,days=30)
    themes=cluster_related_facts(store) if destination=="local" else []
    plan=plan_today(store,destination=destination)
    return {"trends":trends,"topic_clusters":themes[:4],"plan":plan,
            "caveat":"Correlations and topic counts are observational. The system cannot infer hidden motives or diagnose health."}
