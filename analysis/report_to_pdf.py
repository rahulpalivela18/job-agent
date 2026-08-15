"""
analysis/report_to_pdf.py

Render research_report.md to a styled single-page-per-content PDF using
markdown -> HTML -> Playwright (headless Chromium). Charts are embedded from
analysis/charts/.

Usage: python analysis/report_to_pdf.py [input_md] [output_pdf]
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_IN = ROOT / "research_report.md"
DEFAULT_OUT = ROOT / "research_report.pdf"

CSS = """
body {
  font-family: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  font-size: 11pt;
  line-height: 1.55;
  color: #1a1a1a;
  max-width: 780px;
  margin: 0 auto;
  padding: 24px 32px;
}
h1 { font-size: 21pt; line-height: 1.25; border-bottom: 2px solid #4a90e2; padding-bottom: 8px; }
h2 { font-size: 15pt; margin-top: 22px; border-bottom: 1px solid #ddd; padding-bottom: 4px; }
h3 { font-size: 12.5pt; margin-top: 16px; }
code { background: #f4f4f4; padding: 1px 4px; border-radius: 3px; font-size: 9.5pt; }
pre { background: #f6f8fa; padding: 10px; border-radius: 5px; overflow-x: auto; font-size: 9pt; }
table { border-collapse: collapse; width: 100%; margin: 12px 0; font-size: 10pt; }
th, td { border: 1px solid #ccc; padding: 6px 8px; text-align: left; }
th { background: #eaf3ff; }
img { max-width: 100%; display: block; margin: 12px auto; }
blockquote { border-left: 3px solid #4a90e2; margin: 0; padding-left: 12px; color: #555; }
a { color: #4a90e2; }
.meta { color: #666; font-size: 10.5pt; margin-bottom: 24px; }
"""


def main():
    md_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_IN
    pdf_path = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OUT

    import markdown as md

    html_body = md.markdown(
        md_path.read_text(),
        extensions=["tables", "fenced_code", "nl2br"],
    )
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>{CSS}</style></head>
<body>{html_body}</body></html>"""

    tmp_html = ROOT / "analysis" / "results" / "_report_tmp.html"
    tmp_html.write_text(html)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(tmp_html.as_uri(), wait_until="load")
        page.pdf(
            path=str(pdf_path),
            format="letter",
            print_background=True,
            margin={
                "top": "0.6in",
                "bottom": "0.6in",
                "left": "0.7in",
                "right": "0.7in",
            },
        )
        browser.close()

    print(f"PDF written: {pdf_path} ({pdf_path.stat().st_size / 1024:.0f} KB)")
    tmp_html.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
