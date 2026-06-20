"""Build a self-contained HTML report from pipeline results.json: a score-distribution
chart plus a sortable, filterable lead table. No external dependencies - inline SVG/JS."""
from __future__ import annotations
import argparse
import json
from collections import Counter
from html import escape
from pathlib import Path
from string import Template


def build_distribution_svg(scores: list[int], width: int = 700, height: int = 220) -> str:
    bins = Counter(scores)
    if not bins:
        return "<p>No data</p>"
    max_count = max(bins.values())
    sorted_scores = sorted(bins)
    bar_width = width / len(sorted_scores)
    bars = []
    for i, score in enumerate(sorted_scores):
        count = bins[score]
        bar_height = (count / max_count) * (height - 30)
        x = i * bar_width
        y = height - bar_height - 20
        bars.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_width - 2:.1f}" height="{bar_height:.1f}" fill="#4c78a8">'
            f'<title>score {score}: {count} leads</title></rect>'
            f'<text x="{x + bar_width / 2:.1f}" y="{height - 5}" font-size="10" text-anchor="middle">{score}</text>'
        )
    return f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">{"".join(bars)}</svg>'


def build_rows_html(results: list[dict]) -> str:
    rows = []
    for item in results:
        lead = item["lead"]
        types = sorted({r["record_type"] for r in item["records"]})
        rows.append(
            "<tr>"
            f"<td>{item['score']}</td>"
            f"<td>{escape(lead.get('owner_name') or '')}</td>"
            f"<td>{escape(lead.get('property_address') or '')}</td>"
            f"<td>{escape(lead.get('county') or '')}</td>"
            f"<td>{escape(lead.get('state') or '')}</td>"
            f"<td>{escape(', '.join(types))}</td>"
            "</tr>"
        )
    return "\n".join(rows)


HTML_TEMPLATE = Template("""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>REAI Pipeline Results</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 2rem; color: #222; }
  h1 { margin-bottom: 0.2rem; }
  table { border-collapse: collapse; width: 100%; font-size: 14px; }
  th, td { border-bottom: 1px solid #ddd; padding: 6px 10px; text-align: left; }
  th { cursor: pointer; background: #f4f4f4; position: sticky; top: 0; user-select: none; }
  tr:hover { background: #f9f9f9; }
  input#filter { padding: 6px 10px; width: 320px; margin: 10px 0; }
  .stats { margin: 1rem 0 2rem; }
  .stat { display: inline-block; margin-right: 2rem; }
  .stat b { font-size: 1.4rem; display: block; }
</style>
</head>
<body>
<h1>REAI Pipeline Results</h1>

<div class="stats">
  <div class="stat"><b>$lead_count</b>total leads</div>
  <div class="stat"><b>$nonzero_count</b>scored &gt; 0</div>
  <div class="stat"><b>$max_score</b>top score</div>
  <div class="stat"><b>$avg_score</b>average score</div>
</div>

<h2>Score distribution</h2>
$distribution_svg

<h2>Leads (sorted by score)</h2>
<input id="filter" type="text" placeholder="Filter by owner, address, county...">
<table id="leads">
<thead>
<tr>
<th onclick="sortTable(0)">Score</th>
<th onclick="sortTable(1)">Owner</th>
<th onclick="sortTable(2)">Address</th>
<th onclick="sortTable(3)">County</th>
<th onclick="sortTable(4)">State</th>
<th onclick="sortTable(5)">Record Types</th>
</tr>
</thead>
<tbody>
$rows
</tbody>
</table>

<script>
function sortTable(col) {
  const table = document.getElementById("leads");
  const tbody = table.tBodies[0];
  const rows = Array.from(tbody.rows);
  const asc = table.dataset.sortCol == col ? table.dataset.sortDir !== "asc" : true;
  rows.sort((a, b) => {
    const av = a.cells[col].innerText, bv = b.cells[col].innerText;
    const an = parseFloat(av), bn = parseFloat(bv);
    if (!isNaN(an) && !isNaN(bn)) return asc ? an - bn : bn - an;
    return asc ? av.localeCompare(bv) : bv.localeCompare(av);
  });
  rows.forEach(r => tbody.appendChild(r));
  table.dataset.sortCol = col;
  table.dataset.sortDir = asc ? "asc" : "desc";
}
document.getElementById("filter").addEventListener("input", function() {
  const q = this.value.toLowerCase();
  document.querySelectorAll("#leads tbody tr").forEach(row => {
    row.style.display = row.innerText.toLowerCase().includes(q) ? "" : "none";
  });
});
</script>
</body>
</html>
""")


def main():
    p = argparse.ArgumentParser(description="Build an HTML report from pipeline results.json")
    p.add_argument("--input", default="data/output/results.json")
    p.add_argument("--output", default="data/output/results.html")
    args = p.parse_args()

    results = json.loads(Path(args.input).read_text())
    results_sorted = sorted(results, key=lambda item: item["score"], reverse=True)
    scores = [item["score"] for item in results]

    html = HTML_TEMPLATE.substitute(
        lead_count=len(results),
        nonzero_count=sum(1 for s in scores if s > 0),
        max_score=max(scores) if scores else 0,
        avg_score=f"{(sum(scores) / len(scores)) if scores else 0:.1f}",
        distribution_svg=build_distribution_svg(scores),
        rows=build_rows_html(results_sorted),
    )

    output_path = Path(args.output)
    output_path.write_text(html, encoding="utf-8")
    print(f"wrote {output_path}")


if __name__ == "__main__":
    main()
