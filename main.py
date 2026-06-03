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
_visit_count = 0

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
    return JSONResponse({"status": "ok", "visit_count": _visit_count, "tools_count": len(load_tools())})

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
    global _visit_count
    _visit_count += 1
    tools = load_tools()
    cats = sorted(set(t["cat_name"] for t in tools))
    if q:
        ql = q.lower().strip()
        match = [t for t in tools if t["name"].lower() == ql]
        if not match:
            match = [t for t in tools if ql in t["name"].lower()]
        if match:
            return RedirectResponse(f"/tool/{match[0]['id']}", status_code=302)
    if cat:
        tools = [t for t in tools if t["cat_name"] == cat]
    # Build cat_counts for display
    all_tools = load_tools()
    cat_counts = {}
    for t in all_tools:
        cn = t["cat_name"]
        cat_counts[cn] = cat_counts.get(cn, 0) + 1
    return env.get_template("index.html").render(
        tools=tools, categories=cats, active_cat=cat, cat_counts=cat_counts
    )

@app.get("/category/{slug}", response_class=HTMLResponse)
async def category(slug: str):
    tools = [t for t in load_tools() if t["cat"] == slug]
    if not tools: return env.get_template("404.html").render()
    return env.get_template("category.html").render(tools=tools, cat_name=tools[0]["cat_name"])

@app.get("/tool/{tool_id}", response_class=HTMLResponse)
async def tool_detail(tool_id: str, request: Request):
    tools = load_tools()
    tool = next((t for t in tools if t["id"] == tool_id), None)
    if not tool: return env.get_template("404.html").render()
    related = [t for t in tools if t["cat"] == tool["cat"] and t["id"] != tool_id][:4]
    return env.get_template("tool.html").render(tool=tool, related=related, request=request)
