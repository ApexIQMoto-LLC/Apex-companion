"""APEX Business Studio: local-first marketing attribution and content operations.

No platform accounts, credentials, contacts, private rider records or production
cloud data are accessed by this module. Imports are owner-selected CSV exports.
No publishing, outreach, ad changes, paid AI calls or network requests occur.
"""
from __future__ import annotations

import csv
from contextlib import contextmanager
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import io
import json
from pathlib import Path
import re
import sqlite3
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4

PRODUCTS = ("hardware", "replay_studio")
PLATFORMS = ("instagram", "tiktok", "youtube", "website", "meta_ads", "tiktok_ads", "google_ads", "other")
CATEGORIES = ("telemetry_demo", "riding_pov", "replay_studio", "product_intro", "creator_review", "education", "other")
EVENTS = ("website_visit", "beta_application", "qualified_beta", "beta_activated", "purchase", "steam_visit", "steam_wishlist")
STAGES = ("research", "shortlisted", "contacted", "responded", "negotiating", "active", "completed", "declined")
DRAFT_STATES = ("idea", "review", "approved", "produced", "published", "discarded")
MAX_CSV_BYTES = 4_000_000
MAX_CSV_ROWS = 10_000


def _utc():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _text(value, field="value", max_len=240, *, required=True):
    value = str(value or "").strip()
    if (required and not value) or len(value) > max_len or "\x00" in value:
        raise ValueError(f"Invalid {field}; use 1–{max_len} characters")
    return value


def _enum(value, allowed, field):
    value = _text(value, field).lower()
    if value not in allowed:
        raise ValueError(f"Unknown {field}: {value}")
    return value


def _day(value):
    value = _text(value, "date", 10)
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise ValueError("Date must be YYYY-MM-DD") from exc


def _nonnegative(value, field, maximum=10**11):
    if isinstance(value, bool):
        raise ValueError(f"Invalid {field}")
    raw = str(value or "0").strip()
    if not re.fullmatch(r"\d+", raw):
        raise ValueError(f"{field} must be a nonnegative integer")
    result = int(raw)
    if result > maximum:
        raise ValueError(f"{field} exceeds maximum")
    return result


def cents(value, field="amount"):
    try:
        dec = Decimal(str(value).strip())
        if not dec.is_finite() or dec < 0 or dec > Decimal("100000000"):
            raise ValueError(f"Invalid {field}")
        if dec.as_tuple().exponent < -2:
            raise ValueError(f"{field} supports at most two decimal places")
        return int((dec * 100).to_integral_value(rounding=ROUND_HALF_UP))
    except (InvalidOperation, TypeError) as exc:
        raise ValueError(f"Invalid {field}") from exc


def utm_link(destination, source, medium, campaign, content=""):
    """Construct a trackable destination without silently removing custom params."""
    destination = _text(destination, "destination URL", 2048)
    url = urlsplit(destination)
    if url.scheme != "https" or not url.hostname or url.username or url.password:
        raise ValueError("Use an HTTPS destination without URL credentials")
    allowed = {"utm_source": source, "utm_medium": medium, "utm_campaign": campaign}
    if content:
        allowed["utm_content"] = content
    for key, value in list(allowed.items()):
        text = _text(value, key, 100)
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_\-.]{0,99}", text):
            raise ValueError(f"Invalid {key}; use letters, numbers, dashes or underscores")
        allowed[key] = text
    params = [(k, v) for k, v in parse_qsl(url.query, keep_blank_values=True)
              if k.lower() not in ("utm_source", "utm_medium", "utm_campaign", "utm_content")]
    params.extend(allowed.items())
    return urlunsplit((url.scheme, url.netloc, url.path, urlencode(params), url.fragment))


class BusinessStudioStore:
    """Persist public/aggregated marketing evidence independently of personal memory."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._db() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS campaigns (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, product TEXT NOT NULL,
                source TEXT NOT NULL, medium TEXT NOT NULL, destination TEXT NOT NULL,
                tag TEXT NOT NULL UNIQUE, spend_cents INTEGER NOT NULL DEFAULT 0,
                created_utc TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS posts (
                platform TEXT NOT NULL, post_id TEXT NOT NULL, title TEXT NOT NULL,
                category TEXT NOT NULL, campaign_id TEXT,
                created_utc TEXT NOT NULL,
                PRIMARY KEY(platform,post_id));
            CREATE TABLE IF NOT EXISTS metric_snapshots (
                platform TEXT NOT NULL, post_id TEXT NOT NULL, day TEXT NOT NULL,
                views INTEGER NOT NULL, likes INTEGER NOT NULL,
                comments INTEGER NOT NULL, shares INTEGER NOT NULL,
                saves INTEGER NOT NULL, clicks INTEGER NOT NULL,
                watch_seconds INTEGER NOT NULL, source TEXT NOT NULL,
                imported_utc TEXT NOT NULL,
                PRIMARY KEY(platform,post_id,day));
            CREATE TABLE IF NOT EXISTS conversions (
                id TEXT PRIMARY KEY, day TEXT NOT NULL, campaign_id TEXT NOT NULL,
                event_type TEXT NOT NULL, quantity INTEGER NOT NULL,
                revenue_cents INTEGER NOT NULL, source TEXT NOT NULL,
                external_ref TEXT UNIQUE, imported_utc TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS creators (
                id TEXT PRIMARY KEY, platform TEXT NOT NULL, handle TEXT NOT NULL,
                niche TEXT NOT NULL, stage TEXT NOT NULL, notes TEXT NOT NULL,
                last_contact TEXT, created_utc TEXT NOT NULL,
                UNIQUE(platform,handle));
            CREATE TABLE IF NOT EXISTS drafts (
                id TEXT PRIMARY KEY, day TEXT NOT NULL, product TEXT NOT NULL,
                category TEXT NOT NULL, campaign_id TEXT, headline TEXT NOT NULL,
                hooks_json TEXT NOT NULL, script TEXT NOT NULL, shot_list TEXT NOT NULL,
                caption TEXT NOT NULL, cta TEXT NOT NULL, status TEXT NOT NULL,
                origin TEXT NOT NULL, created_utc TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS idx_posts_campaign ON posts(campaign_id);
            CREATE INDEX IF NOT EXISTS idx_conversions_campaign ON conversions(campaign_id);
            CREATE INDEX IF NOT EXISTS idx_drafts_status ON drafts(status);
            """)

    @contextmanager
    def _db(self):
        db = sqlite3.connect(str(self.path), timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def campaign(self, name, product, source, medium, destination, *, spend="0", tag=None):
        product = _enum(product, PRODUCTS, "product")
        name = _text(name, "campaign name", 140)
        source = _text(source, "source", 90).lower()
        medium = _text(medium, "medium", 90).lower()
        tag = _text(tag or re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-"), "campaign tag", 90)
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,89}", tag):
            raise ValueError("Invalid campaign tag")
        destination = _text(destination, "destination", 2048)
        utm_link(destination, source, medium, tag)
        ident = uuid4().hex
        with self._db() as db:
            db.execute("INSERT INTO campaigns VALUES (?,?,?,?,?,?,?,?,?)",
                       (ident, name, product, source, medium, destination, tag, cents(spend), _utc()))
        return ident

    def campaigns(self):
        with self._db() as db:
            return [dict(r) for r in db.execute("SELECT * FROM campaigns ORDER BY created_utc DESC,id DESC")]

    def tracking_url(self, campaign_id, content=""):
        with self._db() as db:
            row = db.execute("SELECT * FROM campaigns WHERE id=?", (campaign_id,)).fetchone()
        if row is None:
            raise ValueError("Select an existing campaign")
        return utm_link(row["destination"], row["source"], row["medium"], row["tag"], content)

    def add_creator(self, platform, handle, niche="motorcycle", stage="research", notes=""):
        platform = _enum(platform, PLATFORMS, "platform")
        if platform not in ("instagram", "tiktok", "youtube", "other"):
            raise ValueError("Creator platform must be a social platform")
        handle = _text(handle, "creator handle", 100)
        niche = _text(niche, "niche", 140)
        notes = _text(notes, "notes", 1200, required=False)
        stage = _enum(stage, STAGES, "stage")
        ident = uuid4().hex
        with self._db() as db:
            db.execute("INSERT INTO creators VALUES (?,?,?,?,?,?,?,?)",
                       (ident, platform, handle, niche, stage, notes, None, _utc()))
        return ident

    def creators(self):
        with self._db() as db:
            return [dict(r) for r in db.execute("SELECT * FROM creators ORDER BY created_utc DESC")]

    def update_creator(self, creator_id, stage, notes=None):
        stage = _enum(stage, STAGES, "stage")
        with self._db() as db:
            row = db.execute("SELECT notes FROM creators WHERE id=?", (creator_id,)).fetchone()
            if row is None:
                raise ValueError("Unknown creator")
            previous = row["notes"]
            db.execute("UPDATE creators SET stage=?,notes=?,last_contact=? WHERE id=?",
                       (stage, previous if notes is None else _text(notes,"notes",1200,required=False),
                        date.today().isoformat() if stage in ("contacted", "responded", "negotiating") else None, creator_id))

    def record_event(self, campaign_id, event_type, *, day=None, quantity=1, revenue="0", source="manual", external_ref=None):
        event_type = _enum(event_type, EVENTS, "event")
        day = _day(day or date.today().isoformat())
        quantity = _nonnegative(quantity, "quantity", 10**8)
        if quantity == 0:
            raise ValueError("Event quantity must be positive")
        revenue_cents = cents(revenue, "revenue")
        if event_type != "purchase" and revenue_cents:
            raise ValueError("Only purchases may record revenue")
        source = _text(source, "source", 80)
        ref = _text(external_ref, "external reference", 200, required=False) or None
        with self._db() as db:
            if not db.execute("SELECT 1 FROM campaigns WHERE id=?", (campaign_id,)).fetchone():
                raise ValueError("Unknown campaign")
            db.execute("INSERT INTO conversions VALUES (?,?,?,?,?,?,?,?,?)",
                       (uuid4().hex, day, campaign_id, event_type, quantity, revenue_cents,
                        source, ref, _utc()))

    def upsert_metric(self, *, platform, post_id, day, views, likes=0, comments=0, shares=0,
                      saves=0, clicks=0, watch_seconds=0, title="Untitled", category="other",
                      campaign_id=None, source="owner_csv"):
        platform = _enum(platform, PLATFORMS, "platform")
        if platform not in ("instagram", "tiktok", "youtube"):
            raise ValueError("Post metrics must belong to Instagram, TikTok or YouTube")
        post_id = _text(post_id, "post ID", 140)
        day = _day(day)
        category = _enum(category, CATEGORIES, "category")
        title = _text(title or "Untitled", "title", 180)
        values = [_nonnegative(v, n) for n, v in (("views",views),("likes",likes),
                    ("comments",comments),("shares",shares),("saves",saves),
                    ("clicks",clicks),("watch_seconds",watch_seconds))]
        source = _text(source, "source", 80)
        if campaign_id:
            with self._db() as db:
                if not db.execute("SELECT 1 FROM campaigns WHERE id=?", (campaign_id,)).fetchone():
                    raise ValueError("Unknown campaign")
        with self._db() as db:
            db.execute("""INSERT INTO posts VALUES (?,?,?,?,?,?)
                        ON CONFLICT(platform,post_id) DO UPDATE SET
                        title=excluded.title,category=excluded.category,
                        campaign_id=COALESCE(excluded.campaign_id,posts.campaign_id)""",
                       (platform,post_id,title,category,campaign_id,_utc()))
            db.execute("""INSERT INTO metric_snapshots VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                        ON CONFLICT(platform,post_id,day) DO UPDATE SET
                        views=excluded.views,likes=excluded.likes,comments=excluded.comments,
                        shares=excluded.shares,saves=excluded.saves,clicks=excluded.clicks,
                        watch_seconds=excluded.watch_seconds,source=excluded.source,
                        imported_utc=excluded.imported_utc""",
                       (platform,post_id,day,*values,source,_utc()))

    @staticmethod
    def _read_csv(path):
        path = Path(path)
        if not path.is_file() or path.stat().st_size > MAX_CSV_BYTES:
            raise ValueError("CSV must be an existing file smaller than 4 MB")
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                raise ValueError("CSV headers are missing")
            fields = set(reader.fieldnames)
            for line_no, row in enumerate(reader, 2):
                if line_no > MAX_CSV_ROWS + 1:
                    raise ValueError("CSV exceeds 10,000 rows")
                if None in row:
                    raise ValueError(f"Row {line_no} has too many columns")
                yield fields, line_no, row

    def import_csv(self, path, kind):
        """Atomic import; reimporting metrics replaces same-day snapshots.

        Conversion rows need unique external_ref for idempotency; never assume
        a missing reference identifies a unique conversion across imports.
        """
        if kind not in ("metrics", "events"):
            raise ValueError("Unknown import type")
        rows = list(self._read_csv(path))
        if not rows:
            raise ValueError("CSV has no rows")
        required = {"metrics": {"platform","post_id","day","views"},
                    "events": {"campaign_id","day","event_type","quantity","external_ref"}}[kind]
        if not required.issubset(rows[0][0]):
            raise ValueError("CSV missing required columns: " + ", ".join(sorted(required - rows[0][0])))
        # Fully validate before writing any rows. Imports are transactional.
        prepared = []
        campaign_ids = {c["id"] for c in self.campaigns()}
        for _, line_no, row in rows:
            try:
                if kind == "metrics":
                    platform = _enum(row["platform"], PLATFORMS, "platform")
                    if platform not in ("instagram","tiktok","youtube"):
                        raise ValueError("Unsupported metrics platform")
                    cid = (row.get("campaign_id") or "").strip() or None
                    if cid and cid not in campaign_ids:
                        raise ValueError("Unknown campaign_id")
                    prepared.append((platform, _text(row["post_id"],"post ID",140), _day(row["day"]),
                            *[_nonnegative(row.get(key) or "0",key) for key in
                               ("views","likes","comments","shares","saves","clicks","watch_seconds")],
                            _text(row.get("title") or "Untitled","title",180),
                            _enum(row.get("category") or "other",CATEGORIES,"category"),cid))
                else:
                    cid = _text(row["campaign_id"],"campaign ID",100)
                    if cid not in campaign_ids:
                        raise ValueError("Unknown campaign_id")
                    event = _enum(row["event_type"],EVENTS,"event")
                    qty = _nonnegative(row["quantity"],"quantity",10**8)
                    if qty == 0:
                        raise ValueError("Quantity must be positive")
                    ref = _text(row["external_ref"],"external_ref",200)
                    revenue = cents(row.get("revenue_usd") or "0", "revenue")
                    if event!="purchase" and revenue:
                        raise ValueError("Only purchase events may record revenue")
                    prepared.append((cid,_day(row["day"]),event,qty,revenue,ref,
                                     _text(row.get("source") or "owner_csv","source",80)))
            except ValueError as exc:
                raise ValueError(f"CSV row {line_no}: {exc}") from exc
        with self._db() as db:
            if kind == "metrics":
                for p in prepared:
                    platform, post_id, day, *rest = p
                    vals = rest[:7]
                    title, category, cid = rest[7:]
                    db.execute("""INSERT INTO posts VALUES (?,?,?,?,?,?)
                                ON CONFLICT(platform,post_id) DO UPDATE SET
                                title=excluded.title,category=excluded.category,
                                campaign_id=COALESCE(excluded.campaign_id,posts.campaign_id)""",
                               (platform,post_id,title,category,cid,_utc()))
                    db.execute("""INSERT INTO metric_snapshots VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                                ON CONFLICT(platform,post_id,day) DO UPDATE SET
                                views=excluded.views,likes=excluded.likes,comments=excluded.comments,
                                shares=excluded.shares,saves=excluded.saves,clicks=excluded.clicks,
                                watch_seconds=excluded.watch_seconds,source=excluded.source,
                                imported_utc=excluded.imported_utc""",
                               (platform,post_id,day,*vals,"owner_csv",_utc()))
            else:
                for cid,day,event,qty,revenue,ref,source in prepared:
                    db.execute("""INSERT INTO conversions VALUES (?,?,?,?,?,?,?,?,?)
                                ON CONFLICT(external_ref) DO UPDATE SET
                                day=excluded.day,campaign_id=excluded.campaign_id,
                                event_type=excluded.event_type,quantity=excluded.quantity,
                                revenue_cents=excluded.revenue_cents,source=excluded.source,
                                imported_utc=excluded.imported_utc""",
                               (uuid4().hex,day,cid,event,qty,revenue,source,ref,_utc()))
        return len(prepared)

    def overview(self):
        """Latest cumulative snapshot per post; never sum cumulative snapshots across days."""
        with self._db() as db:
            posts = [dict(r) for r in db.execute("""SELECT p.*, m.day, m.views,m.likes,m.comments,m.shares,
                m.saves,m.clicks,m.watch_seconds FROM posts p JOIN metric_snapshots m
                ON m.platform=p.platform AND m.post_id=p.post_id
                AND m.day=(SELECT MAX(x.day) FROM metric_snapshots x
                           WHERE x.platform=p.platform AND x.post_id=p.post_id)
                ORDER BY m.views DESC""")]
            events = [dict(r) for r in db.execute("SELECT * FROM conversions")]
            campaigns = [dict(r) for r in db.execute("SELECT * FROM campaigns")]
            creators = [dict(r) for r in db.execute("SELECT * FROM creators")]
            drafts = [dict(r) for r in db.execute("SELECT * FROM drafts ORDER BY created_utc DESC LIMIT 80")]
        total_events = {event:sum(r["quantity"] for r in events if r["event_type"]==event) for event in EVENTS}
        grouped = {}
        for c in campaigns:
            ident = c["id"]
            e = [r for r in events if r["campaign_id"]==ident]
            p = [r for r in posts if r["campaign_id"]==ident]
            grouped[ident] = {
                "name": c["name"], "product":c["product"], "source":c["source"],
                "spend_cents":c["spend_cents"],
                "views":sum(r["views"] for r in p),
                "clicks":sum(r["clicks"] for r in p),
                "website_visits":sum(r["quantity"] for r in e if r["event_type"]=="website_visit"),
                "applications":sum(r["quantity"] for r in e if r["event_type"]=="beta_application"),
                "qualified":sum(r["quantity"] for r in e if r["event_type"]=="qualified_beta"),
                "purchases":sum(r["quantity"] for r in e if r["event_type"]=="purchase"),
                "revenue_cents":sum(r["revenue_cents"] for r in e if r["event_type"]=="purchase"),
            }
            stats = grouped[ident]
            stats["cost_per_application_usd"] = round(stats["spend_cents"]/stats["applications"]/100,2) if stats["applications"] else None
            stats["cost_per_qualified_usd"] = round(stats["spend_cents"]/stats["qualified"]/100,2) if stats["qualified"] else None
        by_platform = {platform:{"posts":len([p for p in posts if p["platform"]==platform]),
                                 "views":sum(p["views"] for p in posts if p["platform"]==platform)}
                       for platform in ("instagram","tiktok","youtube")}
        return {"campaigns":campaigns,"campaign_performance":grouped,"posts":posts,
                "events":total_events,"creators":creators,"drafts":drafts,"by_platform":by_platform,
                "beta_goal":10,"goal_qualified":total_events["qualified_beta"],
                "updated_utc":_utc(),"disclaimer":"Offline user-imported snapshots; metrics definitions vary by platform. Attributed events require tracked links/IDs. No live platform access."}

    def create_draft(self, product="hardware", category="telemetry_demo", campaign_id=None,
                     *, day=None, origin="manual"):
        product = _enum(product,PRODUCTS,"product")
        category = _enum(category,CATEGORIES,"category")
        day = _day(day or date.today().isoformat())
        if campaign_id and campaign_id not in {r["id"] for r in self.campaigns()}:
            raise ValueError("Unknown campaign")
        # Template-driven, no paid model calls. Intentionally do not claim data-driven wins.
        base = {
            "telemetry_demo":("What your motorcycle doesn't tell you",
                "Riding footage with a clean overlay reveals speed, route and lean estimates.",
                "Road POV → telemetry reveal → ARIS insight → device detail → call to action"),
            "riding_pov":("The view is only half the story",
                "A scenic route is exciting; the data helps you understand the ride.",
                "Cinematic corner → rider POV → overlay → scenic exit"),
            "replay_studio":("Ride it again. Understand every second.",
                "Show a real supported Replay Studio replay with 3D camera changes and synchronized signals.",
                "In-game garage → replay view → telemetry overlay → analysis → Steam page"),
            "product_intro":("A new way to understand your ride",
                "Introduce ApexIQ with a clear demonstration of a feature verified on working hardware.",
                "Show device → installed mount → real ride → clear result → application page"),
            "creator_review":("Real rider. Real testing.",
                "Invite an approved beta creator to share a genuine riding demonstration and independent feedback.",
                "Creator intro → riding sequence → data reveal → honest feedback → application page"),
            "education":("One riding metric worth understanding",
                "Explain a supported telemetry metric, what it means and what it cannot tell you.",
                "Question → on-screen example → plain-English explanation → disclaimer → CTA"),
            "other":("ApexIQ rider update",
                "Share one verified development or beta milestone with riders.",
                "What's new → working demonstration → what comes next → CTA"),
        }
        headline, script, shot = base[category]
        if product=="replay_studio" and category=="telemetry_demo":
            script = "Show a genuine recorded ride in Replay Studio, then reveal synchronized 3D replay and available telemetry."
            shot = "Real ride record → 3D replay → synchronized data → Steam CTA"
        hooks = [headline, "Here's what we learned from this ride", "Watch the data appear after this corner"]
        cta = "View Replay Studio on Steam" if product=="replay_studio" else "Apply to test ApexIQ Moto"
        caption = f"{headline}. {script} {cta}. #motorcycle #apexiq"
        ident=uuid4().hex
        with self._db() as db:
            db.execute("INSERT INTO drafts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                       (ident,day,product,category,campaign_id,headline,json.dumps(hooks),
                        script,shot,caption,cta,"idea",origin,_utc()))
        return ident

    def ensure_daily_draft(self, day=None):
        """Idempotent and entirely local: at most one daily draft on opt-in."""
        day = _day(day or date.today().isoformat())
        with self._db() as db:
            existing=db.execute("SELECT id FROM drafts WHERE day=? AND origin='daily_local' LIMIT 1",(day,)).fetchone()
        if existing:
            return existing["id"], False
        category = ("telemetry_demo","riding_pov","replay_studio","education","product_intro","creator_review","other")[date.fromisoformat(day).toordinal()%7]
        product = "replay_studio" if category == "replay_studio" else "hardware"
        return self.create_draft(product,category,day=day,origin="daily_local"), True

    def set_draft_status(self, draft_id, status):
        status = _enum(status,DRAFT_STATES,"draft status")
        with self._db() as db:
            count=db.execute("UPDATE drafts SET status=? WHERE id=?", (status,draft_id)).rowcount
        if not count:
            raise ValueError("Unknown draft")

    def get_draft(self,draft_id):
        with self._db() as db:
            row=db.execute("SELECT * FROM drafts WHERE id=?",(draft_id,)).fetchone()
        if not row:
            raise ValueError("Unknown draft")
        value=dict(row)
        value["hooks"]=json.loads(value.pop("hooks_json"))
        return value

    def draft_markdown(self, draft_id):
        row=self.get_draft(draft_id)
        lines=[f"# {row['headline']}","",f"Product: {row['product']}",f"Category: {row['category']}",
               f"Status: {row['status']} (not automatically published)","","## Hooks"]
        lines.extend(f"- {s}" for s in row["hooks"])
        lines.extend(["","## Script",row["script"],"","## Shot list",row["shot_list"],
                      "","## Caption",row["caption"],"","## CTA",row["cta"],
                      "","Requires verification of depicted feature claims and owner review before publishing."])
        return "\n".join(lines)

    def analysis(self):
        """Cautious deterministic findings; do not infer causes from tiny samples."""
        overview=self.overview()
        posts=overview["posts"]
        lines=["APEX BUSINESS STUDIO / VERIFIED LOCAL DATA SUMMARY",
               "No live social API connections are active. Imported data and manual events only."]
        if not posts:
            lines.append("No post metrics imported yet. Import a platform CSV export using the documented template.")
        for platform, stat in overview["by_platform"].items():
            lines.append(f"{platform}: {stat['posts']} posts with metrics; {stat['views']:,} platform-defined views")
        if overview["campaigns"]:
            lines.append("CAMPAIGN ATTRIBUTION (explicitly tagged events only):")
            for ident, v in overview["campaign_performance"].items():
                cpa = "unknown" if v["cost_per_application_usd"] is None else f"${v['cost_per_application_usd']:.2f}"
                lines.append(f"{v['name']}: {v['applications']} applications, {v['qualified']} qualified, "
                             f"{v['purchases']} purchases, spend ${v['spend_cents']/100:.2f}, CPA {cpa}")
        lines.append(f"Qualified beta events: {overview['goal_qualified']}/{overview['beta_goal']} target (local attributed records; may exclude other applicants).")
        lines.append("Do not infer that a high-view video caused conversions without campaign/referral attribution. "
                     "Do not add Instagram/TikTok/YouTube views into a comparable universal engagement metric.")
        if len(posts)<5:
            lines.append("Sample is small; do not rank hooks as statistically proven winners.")
        return "\n".join(lines)


METRICS_TEMPLATE = "platform,post_id,day,views,likes,comments,shares,saves,clicks,watch_seconds,title,category,campaign_id\n"
EVENTS_TEMPLATE = "campaign_id,day,event_type,quantity,revenue_usd,source,external_ref\n"
