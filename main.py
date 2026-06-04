from fastapi import FastAPI, Query, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse, Response, JSONResponse
from jinja2 import Environment, FileSystemLoader
from urllib.parse import urlparse
from xml.etree.ElementTree import Element, SubElement, tostring
import json, os, time

BASE = os.path.dirname(os.path.abspath(__file__))
SITE_DOMAIN = os.getenv("SITE_DOMAIN", "aitools.example.com")
SITE_URL = f"https://{SITE_DOMAIN}"

class StaticFilesWithCache(StaticFiles):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_response(self, path: str, scope):
        resp = super().get_response(path, scope)
        if isinstance(resp, Response):
            resp.headers["Cache-Control"] = "public, max-age=86400"
        return resp

app = FastAPI(title="AI工具导航")
app.mount("/static", StaticFilesWithCache(directory=f"{BASE}/static"), name="static")
env = Environment(loader=FileSystemLoader(f"{BASE}/templates"))

_tools_cache = None
_tools_cache_time = 0
TOOLS_CACHE_TTL = 300  # 5 minutes

# 访问统计（持久化到文件）
STATS_FILE = f"{BASE}/data/visits.json"

def _load_stats():
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE) as f:
            return json.load(f)
    return {"total": 0, "pages": {"home": 0, "category": 0, "tool": 0}, "daily": {}, "categories": {}, "tools": {}}

def _save_stats(s):
    with open(STATS_FILE, "w") as f:
        json.dump(s, f, ensure_ascii=False, indent=2)

def track_visit(page, extra=None):
    s = _load_stats()
    today = time.strftime("%Y-%m-%d")
    s["total"] += 1
    s["pages"][page] = s["pages"].get(page, 0) + 1
    if today not in s["daily"]:
        s["daily"][today] = {}
    s["daily"][today][page] = s["daily"][today].get(page, 0) + 1
    if extra:
        if page == "category":
            s["categories"][extra] = s["categories"].get(extra, 0) + 1
        elif page == "tool":
            s["tools"][extra] = s["tools"].get(extra, 0) + 1
    _save_stats(s)

def load_tools():
    global _tools_cache, _tools_cache_time
    now = time.time()
    if _tools_cache is not None and (now - _tools_cache_time) < TOOLS_CACHE_TTL:
        return _tools_cache
    with open(f"{BASE}/data/tools.json") as f:
        tools = json.load(f)
    for t in tools:
        domain = urlparse(t["url"]).netloc
        t["favicon"] = f"https://www.google.com/s2/favicons?domain={domain}&sz=64"
    _tools_cache = tools
    _tools_cache_time = now
    return tools

@app.get("/health")
async def health():
    s = _load_stats()
    return JSONResponse({"status": "ok", "visit_count": s["total"], "tools_count": len(load_tools())})

@app.get("/robots.txt", response_class=Response)
async def robots():
    body = f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n"
    return Response(content=body, media_type="text/plain")

@app.get("/sitemap.xml", response_class=Response)
async def sitemap():
    tools = load_tools()
    cats = sorted(set((t["cat"], t["cat_name"]) for t in tools))
    urlset = Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
    # Home
    u = SubElement(urlset, "url"); SubElement(u, "loc").text = f"{SITE_URL}/"
    SubElement(u, "changefreq").text = "daily"; SubElement(u, "priority").text = "1.0"
    # Category pages
    for cat, _ in cats:
        u = SubElement(urlset, "url")
        SubElement(u, "loc").text = f"{SITE_URL}/category/{cat}"
        SubElement(u, "changefreq").text = "weekly"; SubElement(u, "priority").text = "0.8"
    # Tool pages
    for t in tools:
        u = SubElement(urlset, "url")
        SubElement(u, "loc").text = f"{SITE_URL}/tool/{t['id']}"
        SubElement(u, "changefreq").text = "monthly"; SubElement(u, "priority").text = "0.6"
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n' + tostring(urlset, encoding="unicode")
    return Response(content=xml, media_type="application/xml")

@app.get("/", response_class=HTMLResponse)
async def home(q: str = Query(default=""), cat: str = Query(default="")):
    track_visit("home")
    tools = load_tools()
    cats = sorted(set(t["cat_name"] for t in tools))
    search_no_result = False
    search_query = ""
    if q:
        ql = q.lower().strip()
        search_query = q
        match = [t for t in tools if t["name"].lower() == ql]
        if not match:
            match = [t for t in tools if ql in t["name"].lower()]
        if match:
            return RedirectResponse(f"/tool/{match[0]['id']}", status_code=302)
        else:
            search_no_result = True
    if cat:
        tools = [t for t in tools if t["cat_name"] == cat]
    # Build cat_counts for display
    all_tools = load_tools()
    cat_counts = {}
    for t in all_tools:
        cn = t["cat_name"]
        cat_counts[cn] = cat_counts.get(cn, 0) + 1
    # Hot tools for no-result suggestions
    hot_ids = ["chatgpt", "claude", "deepseek", "midjourney", "cursor", "suno"]
    hot_tools = [t for t in all_tools if t["id"] in hot_ids]
    return env.get_template("index.html").render(
        tools=tools, categories=cats, active_cat=cat, cat_counts=cat_counts,
        search_no_result=search_no_result, search_query=search_query, hot_tools=hot_tools,
        SITE_URL=SITE_URL
    )

@app.get("/category/{slug}", response_class=HTMLResponse)
async def category(slug: str):
    tools = [t for t in load_tools() if t["cat"] == slug]
    if not tools: return env.get_template("404.html").render()
    track_visit("category", tools[0]["cat_name"])
    return env.get_template("category.html").render(tools=tools, cat_name=tools[0]["cat_name"], SITE_URL=SITE_URL, slug=slug)

@app.get("/tool/{tool_id}", response_class=HTMLResponse)
async def tool_detail(tool_id: str, request: Request):
    tools = load_tools()
    tool = next((t for t in tools if t["id"] == tool_id), None)
    if not tool: return env.get_template("404.html").render()
    track_visit("tool", tool["id"])
    related = [t for t in tools if t["cat"] == tool["cat"] and t["id"] != tool_id][:8]
    # 随机选 4-6 个不同分类（排除当前工具的分类）
    import random
    all_cats = sorted(set(t["cat_name"] for t in tools if t["cat"] != tool["cat"]))
    random.shuffle(all_cats)
    other_cats = all_cats[:6]
    return env.get_template("tool.html").render(
        tool=tool, related=related, other_cats=other_cats, request=request, SITE_URL=SITE_URL
    )

@app.get("/stats", response_class=HTMLResponse)
async def stats():
    s = _load_stats()
    today = time.strftime("%Y-%m-%d")
    today_stats = s["daily"].get(today, {})
    # 热门分类 top 10
    top_cats = sorted(s["categories"].items(), key=lambda x: -x[1])[:10]
    # 热门工具 top 20
    top_tools_raw = sorted(s["tools"].items(), key=lambda x: -x[1])[:20]
    all_tools = {t["id"]: t for t in load_tools()}
    top_tools = [(all_tools.get(tid, {"name": tid}), cnt) for tid, cnt in top_tools_raw]
    # 最近 7 天趋势
    from datetime import datetime, timedelta
    days = []
    for i in range(6, -1, -1):
        d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        day_data = s["daily"].get(d, {})
        days.append({"date": d, "total": sum(day_data.values()), "detail": day_data})
    return env.get_template("stats.html").render(
        stats=s, today=today_stats, today_date=today,
        top_cats=top_cats, top_tools=top_tools, days=days
    )

# Google verification: serve google*.html from static/ at root (must be last)
@app.get("/{filename}", response_class=HTMLResponse)
async def google_verify(filename: str):
    if filename.startswith("google") and filename.endswith(".html"):
        path = os.path.join(BASE, "static", filename)
        if os.path.exists(path):
            with open(path) as f:
                return HTMLResponse(content=f.read())
    return env.get_template("404.html").render()
