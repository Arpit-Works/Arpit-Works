"""Generates profile/github-stats.svg: current streak + most used languages."""
import os, sys, json, datetime as dt, urllib.request
from xml.sax.saxutils import escape

USER = os.environ.get("GH_USER", "Arpit-Works")
TOKEN = os.environ.get("GH_TOKEN", "")
OUT = os.environ.get("OUT", "profile/github-stats.svg")
MOCK = os.environ.get("MOCK") == "1"

LANG_COLORS = {
    "TypeScript": "#3178C6", "JavaScript": "#F1E05A", "Python": "#3572A5",
    "Shell": "#89E051", "HTML": "#E34C26", "CSS": "#8E5CD9", "Go": "#00ADD8",
    "Java": "#B07219", "Dockerfile": "#2496ED", "SCSS": "#C6538C",
}
FALLBACK = ["#3FB950", "#58A6FF", "#D2A8FF", "#F78166", "#E3B341", "#79C0FF"]


def gql(query, variables=None):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables or {}}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if "errors" in data:
        sys.exit(f"GraphQL error: {data['errors']}")
    return data["data"]


def fetch_days():
    """Return {date: contributionCount} across the account's lifetime."""
    created = gql("query($u:String!){user(login:$u){createdAt}}", {"u": USER})["user"]["createdAt"]
    start_year = int(created[:4])
    today = dt.date.today()
    days = {}
    q = """query($u:String!,$f:DateTime!,$t:DateTime!){user(login:$u){contributionsCollection(from:$f,to:$t){
      contributionCalendar{weeks{contributionDays{date contributionCount}}}}}}"""
    for y in range(start_year, today.year + 1):
        f = f"{y}-01-01T00:00:00Z"
        t = f"{y}-12-31T23:59:59Z"
        cal = gql(q, {"u": USER, "f": f, "t": t})["user"]["contributionsCollection"]["contributionCalendar"]
        for w in cal["weeks"]:
            for d in w["contributionDays"]:
                days[dt.date.fromisoformat(d["date"])] = d["contributionCount"]
    return days


def current_streak(days):
    today = dt.date.today()
    cur = today if days.get(today, 0) > 0 else today - dt.timedelta(days=1)  # grace for today
    n, start = 0, None
    while days.get(cur, 0) > 0:
        n += 1
        start = cur
        cur -= dt.timedelta(days=1)
    return n, start


def fetch_languages():
    q = """query($u:String!){user(login:$u){repositories(first:100,ownerAffiliations:OWNER,isFork:false){nodes{
      languages(first:10,orderBy:{field:SIZE,direction:DESC}){edges{size node{name color}}}}}}}"""
    totals, colors = {}, {}
    for repo in gql(q, {"u": USER})["user"]["repositories"]["nodes"]:
        for e in repo["languages"]["edges"]:
            n = e["node"]["name"]
            totals[n] = totals.get(n, 0) + e["size"]
            colors[n] = e["node"]["color"]
    return totals, colors


def render(streak, since, langs, colors):
    W, H = 840, 230
    total = sum(langs.values()) or 1
    top = sorted(langs.items(), key=lambda x: -x[1])[:6]
    other = total - sum(v for _, v in top)
    items = [(n, v / total * 100) for n, v in top]
    if other > 0 and len(langs) > 6:
        items.append(("Other", other / total * 100))

    def color(i, n):
        if n == "Other":
            return "#6E7681"
        return LANG_COLORS.get(n) or colors.get(n) or FALLBACK[i % len(FALLBACK)]

    # stacked bar
    bx, by, bw, bh = 400, 78, 400, 10
    bar, x = [], bx
    for i, (n, p) in enumerate(items):
        w = bw * p / 100
        bar.append(f'<rect x="{x:.2f}" y="{by}" width="{max(w - 2, 1):.2f}" height="{bh}" fill="{color(i, n)}"/>')
        x += w

    # legend: 2 columns x 4 rows
    legend = []
    for i, (n, p) in enumerate(items):
        col, row = divmod(i, 4)
        lx, ly = bx + col * 205, 126 + row * 26
        legend.append(
            f'<circle cx="{lx + 5}" cy="{ly - 4}" r="4.5" fill="{color(i, n)}"/>'
            f'<text x="{lx + 18}" y="{ly}" class="lang">{escape(n)}</text>'
            f'<text x="{lx + 185}" y="{ly}" class="pct" text-anchor="end">{p:.1f}%</text>'
        )

    since_txt = since.strftime("%b %d, %Y") if since else "No active streak"
    unit = "day" if streak == 1 else "days"

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Current streak and top languages">
<defs>
  <linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#3FB950"/><stop offset="1" stop-color="#58A6FF"/></linearGradient>
  <clipPath id="r"><rect x="{bx}" y="{by}" width="{bw}" height="{bh}" rx="5"/></clipPath>
</defs>
<style>
  text{{font-family:-apple-system,'Segoe UI',Helvetica,Arial,sans-serif}}
  .label{{font-size:11px;letter-spacing:1.6px;fill:#7D8590;font-weight:600}}
  .big{{font-size:68px;font-weight:700;fill:url(#g)}}
  .unit{{font-size:18px;fill:#C9D1D9;font-weight:500}}
  .sub{{font-size:12px;fill:#7D8590}}
  .lang{{font-size:13px;fill:#C9D1D9}}
  .pct{{font-size:12px;fill:#7D8590;font-family:ui-monospace,'SF Mono',Menlo,Consolas,monospace}}
</style>
<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="12" fill="#0D1117" stroke="#30363D"/>
<rect x="0.5" y="0.5" width="{W - 1}" height="3" rx="1.5" fill="url(#g)" opacity="0.9"/>

<text x="40" y="52" class="label">CURRENT STREAK</text>
<text x="40" y="132" class="big">{streak}</text>
<text x="{40 + 22 + 40 * len(str(streak))}" y="132" class="unit">{unit}</text>
<text x="40" y="162" class="sub">Since {since_txt}</text>
<text x="40" y="184" class="sub">@{escape(USER)} · contributions on GitHub</text>

<line x1="350" y1="36" x2="350" y2="{H - 36}" stroke="#21262D"/>

<text x="{bx}" y="52" class="label">MOST USED LANGUAGES</text>
<g clip-path="url(#r)">{''.join(bar)}</g>
{''.join(legend)}
</svg>'''


def main():
    if MOCK:
        streak, since = 23, dt.date.today() - dt.timedelta(days=22)
        langs = {"TypeScript": 520, "JavaScript": 230, "Python": 120, "Shell": 60, "HTML": 45, "CSS": 25}
        colors = {}
    else:
        if not TOKEN:
            sys.exit("GH_TOKEN is missing")
        streak, since = current_streak(fetch_days())
        langs, colors = fetch_languages()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w", encoding="utf-8").write(render(streak, since, langs, colors))
    print(f"wrote {OUT} (streak={streak})")


if __name__ == "__main__":
    main()
