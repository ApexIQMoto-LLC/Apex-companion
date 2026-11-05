"""Approved, local and read-only Responses API tools for APEX.

No tool here writes to Supabase, runs shell commands, opens URLs, or changes files.
Tool results are untrusted contextual data, not instructions.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .dashboard_state import bounded_ai_context
from .steamworks import SteamworksReader
from .unity_diagnostics import scan_unity_logs
from .intelligence_engine import plan_today


def tool(name, description, properties=None, required=None):
    return {"type":"function", "name":name, "description":description,
            "strict":True, "parameters":{"type":"object", "properties":properties or {},
                                           "required": required or [], "additionalProperties":False}}

TEXT_QUERY={"query":{"type":"string", "description":"Keywords or a short natural-language question (max 250 characters)."}}
TOOL_DEFINITIONS=[
    tool("get_cloud_health", "Fetch owner-authorized current A.R.I.S Cloud aggregated device and beta status; no GPS or user identities."),
    tool("get_steam_growth", "Retrieve owner-authorized Replay Studio Steam daily wishlist report. Adds are not total wishlist count."),
    tool("get_local_research", "Read cached public news and marketing opportunities with timestamps; verify before treating them as facts."),
    tool("recall_memory", "Search locally saved memories and prior chats. Do not treat memories as current external facts.",TEXT_QUERY,["query"]),
    tool("search_approved_code", "Search file snippets from the specifically approved and indexed Unity or code project.",TEXT_QUERY,["query"]),
    tool("inspect_unity_errors", "Read a bounded tail of logs in a user-approved Unity project; no files are changed."),
    tool("search_personal_knowledge", "Find facts in the permission-approved local knowledge graph, with dates, source and confidence. Sensitive categories are unavailable unless the owner enabled AI scope.",TEXT_QUERY,["query"]),
    tool("get_knowledge_graph", "Read a bounded, scoped set of knowledge graph nodes and relationships with source evidence."),
    tool("get_activity_trends", "Summarize counts and coverage of opt-in local activity events. No personal trait conclusions."),
    tool("get_daily_plan", "Read the local goal list and prioritized owner-visible alerts; no calendar writes or automatic purchases."),
    tool("get_data_permissions", "List enabled and disabled data categories, without returning protected content."),
    tool("get_operations_history", "Read verified, recent local operations queue and Unity test outcomes. This is an audit record, not evidence of a deployed fix."),
    tool("search_encrypted_imports", "Search a user-selected, locally encrypted CSV/JSON/ICS/TXT import only if the requested category has separately enabled AI access.",
         {"scope":{"type":"string","enum":["operations","projects","personal","computer","calendar","communications","finance","health"]},
          "query":{"type":"string"}},["scope","query"]),
]


class LiveToolbox:
    def __init__(self, monitor=None, memory=None, indexer=None, approved_project=None,
                 cloud=None, steam=None, marketing=None, news=None, allow_cloud=True,
                 include_editor_logs=False, authorization_check=None, project_authorization_check=None,
                 personal=None, personal_authorization_check=None, intel_alerts=None, import_vault=None,
                 operations=None, operations_authorization_check=None):
        self.monitor=monitor
        self.memory=memory
        self.indexer=indexer
        self.approved_project=Path(approved_project).resolve() if approved_project else None
        self.cloud_cached=cloud
        self.steam_cached=steam
        self.marketing=marketing
        self.news=news
        self.allow_cloud=bool(allow_cloud)
        self.include_editor_logs=bool(include_editor_logs)
        self.authorization_check=authorization_check or (lambda: True)
        self.project_authorization_check=project_authorization_check or (lambda: True)
        self.personal=personal
        self.personal_authorization_check=personal_authorization_check or (lambda: True)
        self.intel_alerts=intel_alerts
        self.import_vault=import_vault
        self.operations=operations
        self.operations_authorization_check=operations_authorization_check or (lambda: True)

    def schemas(self):
        names={"get_local_research", "recall_memory", "search_approved_code", "inspect_unity_errors"}
        if self.allow_cloud:
            names.update(("get_cloud_health", "get_steam_growth"))
        if self.personal is not None:
            names.update(("search_personal_knowledge", "get_knowledge_graph", "get_activity_trends", "get_daily_plan", "get_data_permissions"))
            if self.import_vault is not None:names.add("search_encrypted_imports")
            if self.operations is not None and self.personal.permitted("operations","ai"):
                names.add("get_operations_history")
        return [dict(t) for t in TOOL_DEFINITIONS if t["name"] in names]

    def run(self, name: str, args: dict | None = None) -> dict:
        if args is None:args={}
        if name not in {t["name"] for t in self.schemas()}:
            return {"error":"tool_not_allowed"}
        if not isinstance(args,dict):
            return {"error":"invalid_arguments"}
        query=str(args.get("query", ""))[:250]
        if name=="get_operations_history":
            if (self.operations is None or self.personal is None or
                not self.operations_authorization_check() or not self.personal.permitted("operations","ai")):
                return {"error":"operations_permission_revoked"}
            items=self.operations.recent(15)
            rows=[]
            for row in items:
                result=row.get("result") or {}
                rows.append({"kind":row.get("kind"),"status":row.get("status"),
                             "origin":row.get("origin"),"created_utc":row.get("created_utc"),
                             "state":result.get("state"),"tests_verified":result.get("tests_verified"),
                             "sampled_errors":result.get("sampled_errors"),
                             "sampled_warnings":result.get("sampled_warnings"),
                             "passed":result.get("passed"),"failed":result.get("failed"),
                             "git_tracked_changes":result.get("tracked_changes"),
                             "reason":str(result.get("reason", ""))[:150]})
            if not self.operations_authorization_check() or not self.personal.permitted("operations","ai"):
                return {"error":"operations_permission_revoked"}
            return {"source":"Local operations audit (not production deployment)",
                    "paused":self.operations.paused(),"items":rows,
                    "caveat":"Task completion is not proof of Unity gameplay correctness. Only tests_verified=true confirms a reported Edit Mode test suite passed."}
        if name=="search_encrypted_imports":
            if self.import_vault is None or not self.personal_authorization_check():
                return {"error":"permission_revoked"}
            scope=str(args.get("scope",""))
            try:
                result=self.import_vault.search(scope,query,destination="ai",limit=6)
            except RuntimeError:
                result={"error":"local_encrypted_vault_unavailable"}
            if not self.personal_authorization_check():
                return {"error":"permission_revoked"}
            return {"source":"Owner-selected encrypted local import",**result}
        if name in ("search_personal_knowledge","get_knowledge_graph","get_activity_trends","get_daily_plan","get_data_permissions"):
            if self.personal is None or not self.personal_authorization_check():
                return {"error":"personal_permission_revoked"}
            if name=="search_personal_knowledge":
                result={"source":"Local scoped graph", "matches":self.personal.search(query,destination="ai",limit=8)}
            elif name=="get_knowledge_graph":
                result={"source":"Local scoped knowledge graph",**self.personal.graph_snapshot(destination="ai",limit=22)}
            elif name=="get_activity_trends":
                result={"source":"Local scoped timeline", "trends":self.personal.trends(destination="ai",days=30),
                        "recent":self.personal.timeline(destination="ai",limit=7,days=14)}
            elif name=="get_daily_plan":
                result={"source":"Local goals and observed alerts", "plan":plan_today(self.personal,self.intel_alerts,destination="ai")}
            else:
                result={"source":"Local consent registry", "permissions":self.personal.permissions()}
            if not self.personal_authorization_check():
                return {"error":"personal_permission_revoked"}
            return result
        if name=="get_cloud_health":
            if not self.authorization_check():return {"error":"cloud_user_session_changed"}
            if not self.monitor or not self.monitor.signed_in:
                return {"source":"A.R.I.S Cloud / Supabase RLS", "error":"user_sign_in_required"}
            try:
                snapshot=self.monitor.snapshot()
                if not self.authorization_check():return {"error":"cloud_user_session_changed"}
                self.cloud_cached=snapshot
                return {"source":"A.R.I.S Cloud / authenticated RLS", "checked_at_utc":snapshot.get("checked_at_utc"),
                        "summary":bounded_ai_context(snapshot,None,None,None,True)[:3400]}
            except (RuntimeError,TimeoutError,OSError,ValueError) as ex:
                return {"source":"A.R.I.S Cloud", "error":type(ex).__name__,"cached_available":self.cloud_cached is not None}
        if name=="get_steam_growth":
            if not self.authorization_check():return {"error":"cloud_user_session_changed"}
            if not self.monitor or not self.monitor.signed_in:
                return {"source":"Steam daily reports via Supabase RLS", "error":"user_sign_in_required"}
            try:
                summary=SteamworksReader(self.monitor).fetch(days=30)
                if not self.authorization_check():return {"error":"cloud_user_session_changed"}
                self.steam_cached=summary
                return {"source":"Steamworks scheduled reports via Supabase RLS", "data":{
                    k:summary.get(k) for k in ("status","latest_date","latest","last7_adds","last7_coverage_days")},
                    "caveat":"Daily additions are not the total wishlist count. Missing dates are not zero."}
            except (RuntimeError,TimeoutError,OSError,ValueError) as ex:
                return {"source":"Steamworks via Supabase", "error":type(ex).__name__,"cached_available":self.steam_cached is not None}
        if name=="get_local_research":
            result={"source":"Local cached public RSS", "checked_at_utc":datetime.now(timezone.utc).isoformat(),"verified":False}
            if self.marketing:
                result["marketing"]={"scan_at":self.marketing.get("created_at_utc"),"ideas":[{"title":str(o.get("title",""))[:160],
                    "url":str(o.get("url",""))[:300]} for o in self.marketing.get("opportunities",[])[:5] if isinstance(o,dict)]}
            if self.news:
                result["headlines"]=[{"topic":str(topic)[:80],"titles":[str(o.get("title",""))[:180] for o in items[:3] if isinstance(o,dict)]}
                                     for topic, items in self.news[:3]]
            if not self.marketing and not self.news:result["error"]="No research scan available"
            return result
        if name=="recall_memory":
            if self.memory is None:return {"error":"Memory disabled"}
            return {"source":"Local SQLite memory", "matching":self.memory.search(query,limit=6)}
        if name=="search_approved_code":
            if not self.project_authorization_check():return {"error":"project_permission_revoked"}
            if not self.indexer or not self.approved_project:return {"error":"No project approved or indexed"}
            items=self.indexer.search(query,limit=7,root=self.approved_project)
            if not self.project_authorization_check():return {"error":"project_permission_revoked"}
            root=str(self.approved_project)
            return {"source":"Explicitly approved local code index", "project":self.approved_project.name,
                    "matches":[{"relative_path":str(o["path"]).removeprefix(root).lstrip("/\\")[:220],
                                "excerpt":o["snippet"][:390]} for o in items if Path(o["path"]).is_relative_to(self.approved_project)]}
        if name=="inspect_unity_errors":
            if not self.project_authorization_check():return {"error":"project_permission_revoked"}
            if not self.approved_project:return {"error":"No Unity folder approved"}
            try:
                sampled=scan_unity_logs(self.approved_project, include_editor_log=self.include_editor_logs, max_issues=12)
                if not self.project_authorization_check():return {"error":"project_permission_revoked"}
                return {"source":"Local approved Unity log files",**sampled}
            except (OSError,ValueError) as ex:
                return {"error":type(ex).__name__,"source":"Unity logs"}
        return {"error":"unknown tool"}

    def safe_run(self,name,args,limit=4600) -> str:
        try:
            return json.dumps(self.run(name,args),ensure_ascii=True,default=str)[:limit]
        except Exception as ex:
            # Don't leak a network response body, credentials, source path, etc.
            return json.dumps({"error":"tool_failed","type":type(ex).__name__})
