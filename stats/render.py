#!/usr/bin/env python3
"""Render profile stat cards. Prints aggregates only, never repository names."""

import json
import os
import subprocess
from collections import Counter

USER = "itsrealkaran"
OUT = os.path.dirname(os.path.abspath(__file__))

DIGITS = {
    "0": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
    "2": ["01110", "10001", "00001", "00110", "01000", "10000", "11111"],
    "3": ["11110", "00001", "00001", "01110", "00001", "00001", "11110"],
    "4": ["00010", "00110", "01010", "10010", "11111", "00010", "00010"],
    "5": ["11111", "10000", "11110", "00001", "00001", "10001", "01110"],
    "6": ["01110", "10000", "11110", "10001", "10001", "10001", "01110"],
    "7": ["11111", "00001", "00010", "00100", "01000", "01000", "01000"],
    "8": ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
    "9": ["01110", "10001", "10001", "01111", "00001", "00001", "01110"],
    ",": ["00000", "00000", "00000", "00000", "00000", "00100", "01000"],
}


def gh(args):
    return json.loads(subprocess.check_output(["gh", "api", *args], text=True))


def api(path):
    return gh([path])


def graphql(query, variables):
    args = ["graphql", "-f", f"query={query}"]
    for key, value in variables.items():
        args.extend(["-f", f"{key}={value}"])
    payload = gh(args)
    if payload.get("errors"):
        raise RuntimeError("contribution query failed")
    return payload["data"]


def contribution_total(start, end):
    query = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          contributionCalendar { totalContributions }
        }
      }
    }
    """
    data = graphql(
        query,
        {
            "login": USER,
            "from": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "to": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    )
    return data["user"]["contributionsCollection"]["contributionCalendar"]["totalContributions"]


def contribution_counts():
    from datetime import datetime, timedelta, timezone

    end = datetime.now(timezone.utc).replace(microsecond=0)
    last_year = contribution_total(end - timedelta(days=364), end)
    slices = [
        (datetime(2022, 10, 8, tzinfo=timezone.utc), datetime(2022, 12, 31, 23, 59, 59, tzinfo=timezone.utc)),
        (datetime(2023, 1, 1, tzinfo=timezone.utc), datetime(2023, 12, 31, 23, 59, 59, tzinfo=timezone.utc)),
        (datetime(2024, 1, 1, tzinfo=timezone.utc), datetime(2024, 12, 31, 23, 59, 59, tzinfo=timezone.utc)),
        (datetime(2025, 1, 1, tzinfo=timezone.utc), datetime(2025, 12, 31, 23, 59, 59, tzinfo=timezone.utc)),
        (datetime(2026, 1, 1, tzinfo=timezone.utc), end),
    ]
    all_time = sum(contribution_total(start, stop) for start, stop in slices)
    return last_year, all_time


def owned_repos():
    repos = []
    page = 1
    while True:
        batch = api(
            f"user/repos?per_page=100&page={page}&visibility=all&affiliation=owner"
        )
        if not batch:
            break
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return [repo for repo in repos if not repo.get("fork")]


def languages(repos):
    totals = Counter()
    for repo in repos:
        data = api(f"repos/{repo['full_name']}/languages")
        totals.update(data)
    return totals


def dots(text, x, y, size=3.2, gap=1.6, fill="#f4f4f4"):
    step = size + gap
    parts = []
    cursor = x
    for char in text:
        grid = DIGITS[char]
        for row, bits in enumerate(grid):
            for col, bit in enumerate(bits):
                if bit == "1":
                    cx = cursor + col * step + size / 2
                    cy = y + row * step + size / 2
                    parts.append(
                        f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{size/2:.1f}" fill="{fill}"/>'
                    )
        cursor += 5 * step + 3
    width = cursor - x - 3
    return "".join(parts), width


def card_open(width, height):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img">'
        f'<rect width="{width}" height="{height}" rx="0" fill="#0a0a0a"/>'
        f'<rect x="22" y="24" width="7" height="7" fill="#ff2a2a"/>'
    )


def contributions_svg(last_year, all_time, stars):
    last = f"{last_year:,}"
    total = f"{all_time:,}"
    left, left_w = dots(last, 22, 62)
    right, _ = dots(total, 22 + left_w + 48, 62)
    return f'''{card_open(495, 196)}
  <title>{last} contributions in the last 12 months. {total} since October 2022. {stars} stars on owned repositories. Includes private contributions.</title>
  <text x="38" y="32" fill="#f4f4f4" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="12" letter-spacing="2.4">CONTRIBUTIONS</text>
  <text x="473" y="32" fill="#8d8d8d" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="11" letter-spacing="1.4" text-anchor="end">PUBLIC + PRIVATE</text>
  {left}{right}
  <text x="22" y="128" fill="#8d8d8d" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="11" letter-spacing="1.6">LAST 12 MONTHS</text>
  <text x="{22 + left_w + 48}" y="128" fill="#8d8d8d" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="11" letter-spacing="1.6">SINCE OCT 2022</text>
  <line x1="22" y1="148" x2="473" y2="148" stroke="#242424" stroke-dasharray="1 4"/>
  <text x="22" y="174" fill="#f4f4f4" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="13" letter-spacing="1.2">{stars} STARS ON OWNED REPOS</text>
</svg>
'''


def languages_svg(totals):
    grand = sum(totals.values()) or 1
    rows = totals.most_common(5)
    height = 58 + len(rows) * 28 + 28
    summary = ", ".join(f"{name} {100 * amount / grand:.1f}%" for name, amount in rows)
    body = [card_open(495, height)]
    body.append(f"<title>Languages across public and private repositories: {summary}. Forks excluded.</title>")
    body.append(
        '<text x="38" y="32" fill="#f4f4f4" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="12" letter-spacing="2.4">LANGUAGES</text>'
    )
    body.append(
        '<text x="473" y="32" fill="#8d8d8d" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="11" letter-spacing="1.4" text-anchor="end">PUBLIC + PRIVATE</text>'
    )
    for index, (name, amount) in enumerate(rows):
        y = 64 + index * 28
        pct = 100 * amount / grand
        bar = max(2, 250 * pct / 100)
        body.append(
            f'<text x="22" y="{y}" fill="#f4f4f4" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="13">{name}</text>'
        )
        body.append(
            f'<text x="150" y="{y}" fill="#8d8d8d" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="12">{pct:.1f}%</text>'
        )
        body.append(f'<rect x="210" y="{y - 9}" width="250" height="6" fill="#1c1c1c"/>')
        body.append(f'<rect x="210" y="{y - 9}" width="{bar:.1f}" height="6" fill="#f4f4f4"/>')
    body.append(
        f'<text x="22" y="{height - 16}" fill="#8d8d8d" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="11" letter-spacing="1.2">FORKS EXCLUDED</text>'
    )
    body.append("</svg>")
    return "\n".join(body)


def main():
    repos = owned_repos()
    stars = sum(repo["stargazers_count"] for repo in repos)
    langs = languages(repos)
    last_year, all_time = contribution_counts()
    with open(os.path.join(OUT, "contributions.svg"), "w") as handle:
        handle.write(contributions_svg(last_year, all_time, stars))
    with open(os.path.join(OUT, "languages.svg"), "w") as handle:
        handle.write(languages_svg(langs))
    grand = sum(langs.values()) or 1
    print("repos", len(repos))
    print("last_year", last_year)
    print("all_time", all_time)
    print("stars", stars)
    print("languages", [(name, round(100 * amount / grand, 1)) for name, amount in langs.most_common(5)])


if __name__ == "__main__":
    main()
