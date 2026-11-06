#!/usr/bin/env python3
"""GitHub stats card, drawn in the profile style (no third-party stats service).

    python3 stats.py      -> assets/stats.en.svg, assets/stats.ru.svg

Runs daily in .github/workflows/blog.yml with the workflow's GITHUB_TOKEN, so the numbers
match what a visitor sees on the profile. Locally it falls back to `gh auth token`.
Only aggregate counts are drawn; no repository names.
"""
import json, os, subprocess, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
LOGIN = "ilia-ae"
Q = """{user(login:"%s"){
  repositories(ownerAffiliations:OWNER,privacy:PUBLIC,isFork:false,first:100){totalCount nodes{stargazerCount}}
  contributionsCollection{contributionCalendar{totalContributions weeks{contributionDays{contributionCount}}}}}}""" % LOGIN
# Only numbers derived from the contribution calendar plus public repos: the workflow token
# sees private work in the calendar total but splits commits/PRs/issues for public repos
# only, so those would drop from thousands to hundreds on every daily run.
TXT = {"en": dict(c="contributions in a year", a="active days", k="longest streak, days", w="best week",
                  r="public repos", s="stars", ),
       "ru": dict(c="вклад за год", a="активных дней", k="серия подряд, дней", w="лучшая неделя",
                  r="открытых репозиториев", s="звёзд")}


def fetch():
    tok = os.environ.get("GITHUB_TOKEN") or subprocess.run(["gh", "auth", "token"], capture_output=True,
                                                           text=True).stdout.strip()
    req = urllib.request.Request("https://api.github.com/graphql", data=json.dumps({"query": Q}).encode(),
                                 headers={"Authorization": f"bearer {tok}", "User-Agent": "ilia-ae-profile-bot/1.0"})
    u = json.load(urllib.request.urlopen(req, timeout=30))["data"]["user"]
    c, r = u["contributionsCollection"], u["repositories"]
    cal = c["contributionCalendar"]["weeks"]
    weeks = [sum(d["contributionCount"] for d in w["contributionDays"]) for w in cal]
    days = [d["contributionCount"] for w in cal for d in w["contributionDays"]]
    run = best = 0
    for v in days:
        run = run + 1 if v else 0; best = max(best, run)
    return dict(c=c["contributionCalendar"]["totalContributions"], a=sum(1 for v in days if v), k=best,
                w=max(weeks), r=r["totalCount"], s=sum(n["stargazerCount"] for n in r["nodes"]), weeks=weeks)


def _fmt(n, lang):
    return f"{n:,}".replace(",", " " if lang == "ru" else ",")


def svg(d, lang):
    t = TXT[lang]; W, H = 760, 74
    acc, sub = "#4D82E8", "#9aa0a6"
    keys = ["c", "a", "k", "w", "r", "s"]
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
           f'font-family="-apple-system,Segoe UI,Helvetica,Arial,sans-serif">',
           f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="14" fill="#888888" fill-opacity="0.04" '
           f'stroke="#88888850"/>']
    cw = W / len(keys)
    for k, key in enumerate(keys):
        cx = cw * (k + 0.5)
        if k:
            out.append(f'<line x1="{cw*k:.1f}" y1="18" x2="{cw*k:.1f}" y2="56" stroke="#888888" stroke-opacity="0.18"/>')
        out.append(f'<text x="{cx:.1f}" y="38" font-size="20" font-weight="800" fill="{acc}" '
                   f'text-anchor="middle">{_fmt(d[key], lang)}</text>')
        out.append(f'<text x="{cx:.1f}" y="56" font-size="10.5" fill="{sub}" text-anchor="middle">{t[key]}</text>')
    out.append("</svg>")
    return "\n".join(out)


def write():
    d = fetch()
    changed = False
    for lang in TXT:
        fn = os.path.join(HERE, "assets", f"stats.{lang}.svg")
        new = svg(d, lang)
        if not os.path.exists(fn) or open(fn, encoding="utf-8").read() != new:
            open(fn, "w", encoding="utf-8").write(new); changed = True
    return d, changed


if __name__ == "__main__":
    d, ch = write()
    print({k: v for k, v in d.items() if k != "weeks"}, "updated" if ch else "unchanged")
