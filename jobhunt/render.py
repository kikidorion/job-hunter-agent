"""Render resume + cover letter to PDF (headless Chrome) and DOCX (python-docx).
Metadata is rewritten so files carry only the candidate's name: no generator, producer, or tool tags."""
import html
import os
import shutil
import subprocess
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

from docx import Document
from docx.shared import Pt
from pypdf import PdfReader, PdfWriter

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
]


def chrome_path() -> str:
    """CHROME_PATH from .env, else a standard install location, else the first Chrome/Chromium on PATH."""
    if os.environ.get("CHROME_PATH"):
        return os.environ["CHROME_PATH"]
    for c in CHROME_CANDIDATES:
        if Path(c).exists():
            return c
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge"):
        if shutil.which(name):
            return shutil.which(name)
    raise SystemExit("Chrome or Chromium is needed to print PDFs. Install it or set CHROME_PATH in .env.")


def _today() -> str:
    d = date.today()
    return f"{d:%B} {d.day}, {d.year}"  # %-d is not portable to Windows

CSS = """
@page { size: Letter; margin: 0.55in 0.6in; }
body { font-family: Georgia, 'Times New Roman', serif; color: #111; font-size: 10.5pt; line-height: 1.32; }
h1 { font-size: 20pt; margin: 0; letter-spacing: .3px; }
.contact, .headline { font-size: 9.5pt; color: #333; margin-top: 2px; }
.headline { font-style: italic; }
h2 { font-size: 10.5pt; text-transform: uppercase; letter-spacing: 1px; border-bottom: 1px solid #999; margin: 12px 0 5px; padding-bottom: 2px; }
.row { display: flex; justify-content: space-between; font-weight: bold; margin-top: 6px; }
.sub { font-style: italic; }
ul { margin: 3px 0 0 16px; padding: 0; } li { margin: 1.5px 0; }
.skills div { margin: 1.5px 0; }
.letter p { margin: 0 0 11px; font-size: 11pt; line-height: 1.45; }
"""


def _e(s) -> str:
    return html.escape(str(s or ""))


def _contact(p: dict) -> str:
    return " | ".join(_e(x) for x in (p.get("location"), p.get("phone"), p.get("email"), p.get("linkedin"), p.get("github")) if x)


def resume_html(doc: dict, p: dict) -> str:
    exp = "".join(
        f'<div class="row"><span>{_e(e["company"])}</span><span>{_e(e["dates"])}</span></div>'
        f'<div class="sub">{_e(e["title"])}</div><ul>{"".join(f"<li>{_e(b)}</li>" for b in e["bullets"])}</ul>'
        for e in doc["experience"])
    proj = "".join(
        f'<div class="row"><span>{_e(pr["name"])}</span></div><ul>{"".join(f"<li>{_e(b)}</li>" for b in pr["bullets"])}</ul>'
        for pr in doc.get("projects", []))
    edu = "".join(f'<div class="row"><span>{_e(e["degree"])}, {_e(e["school"])}</span><span>{_e(e["dates"])}</span></div>'
                  for e in p["education"])
    skills = "".join(f'<div><b>{_e(s["group"])}:</b> {_e(", ".join(s["items"]))}</div>' for s in doc["skills"])
    return (f"<html><head><meta charset='utf-8'><title>{_e(p['name'])} Resume</title><style>{CSS}</style></head><body>"
            f"<h1>{_e(p['name'])}</h1><div class='headline'>{_e(doc['headline'])}</div><div class='contact'>{_contact(p)}</div>"
            f"<h2>Summary</h2><div>{_e(doc['summary'])}</div>"
            + (f"<h2>Education</h2>{edu}" if doc.get("education_first") else "")
            + f"<h2>Experience</h2>{exp}" + (f"<h2>Projects</h2>{proj}" if proj else "")
            + ("" if doc.get("education_first") else f"<h2>Education</h2>{edu}")
            + f"<h2>Skills</h2><div class='skills'>{skills}</div></body></html>")


def letter_html(doc: dict, p: dict, job: dict) -> str:
    cl = doc["cover_letter"]
    paras = "".join(f"<p>{_e(x)}</p>" for x in [cl["greeting"], *cl["paragraphs"]])
    return (f"<html><head><meta charset='utf-8'><title>{_e(p['name'])} Cover Letter</title><style>{CSS}</style></head><body class='letter'>"
            f"<h1>{_e(p['name'])}</h1><div class='contact'>{_contact(p)}</div><br>"
            f"<p>{_today()}</p><p>{_e(job['company'])}</p>{paras}"
            f"<p>{_e(cl.get('closing', 'Sincerely,'))}<br>{_e(p['name'])}</p></body></html>")


def to_pdf(html_text: str, out: Path, author: str, title: str) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        src, raw = Path(tmp) / "in.html", Path(tmp) / "raw.pdf"
        src.write_text(html_text, encoding="utf-8")
        subprocess.run([chrome_path(), "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                        f"--print-to-pdf={raw}", src.as_uri()], check=True, capture_output=True, timeout=90)
        reader, writer = PdfReader(raw), PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        writer.add_metadata({"/Author": author, "/Title": title, "/Creator": author, "/Producer": author})
        with out.open("wb") as f:
            writer.write(f)


def _docx_clean(d: Document, author: str, title: str) -> None:
    cp = d.core_properties  # python-docx defaults would stamp "python-docx" here
    cp.author = cp.last_modified_by = author
    cp.title, cp.subject, cp.comments, cp.keywords, cp.category = title, "", "", "", ""
    cp.created = cp.modified = datetime.now(timezone.utc).replace(microsecond=0)  # template otherwise says 2013
    cp.revision = 1
    style = d.styles["Normal"]
    style.font.name, style.font.size = "Georgia", Pt(10.5)


def _docx_education(d, p: dict) -> None:
    d.add_heading("Education", 1)
    for e in p["education"]:
        d.add_paragraph(f"{e['degree']}, {e['school']} ({e['dates']})")


def resume_docx(doc: dict, p: dict, out: Path) -> None:
    d = Document()
    _docx_clean(d, p["name"], f"{p['name']} Resume")
    d.add_heading(p["name"], 0)
    d.add_paragraph().add_run(doc["headline"]).italic = True
    d.add_paragraph(" | ".join(x for x in (p.get("location"), p.get("phone"), p.get("email"), p.get("linkedin")) if x))
    d.add_heading("Summary", 1); d.add_paragraph(doc["summary"])
    if doc.get("education_first"):
        _docx_education(d, p)
    d.add_heading("Experience", 1)
    for e in doc["experience"]:
        para = d.add_paragraph(); para.add_run(f"{e['company']}, {e['title']}").bold = True; para.add_run(f"   {e['dates']}")
        for b in e["bullets"]:
            d.add_paragraph(b, style="List Bullet")
    if doc.get("projects"):
        d.add_heading("Projects", 1)
        for pr in doc["projects"]:
            d.add_paragraph().add_run(pr["name"]).bold = True
            for b in pr["bullets"]:
                d.add_paragraph(b, style="List Bullet")
    if not doc.get("education_first"):
        _docx_education(d, p)
    d.add_heading("Skills", 1)
    for s in doc["skills"]:
        para = d.add_paragraph(); para.add_run(f"{s['group']}: ").bold = True; para.add_run(", ".join(s["items"]))
    d.save(out)


def letter_docx(doc: dict, p: dict, job: dict, out: Path) -> None:
    d = Document()
    _docx_clean(d, p["name"], f"{p['name']} Cover Letter")
    cl = doc["cover_letter"]
    for line in [p["name"], " | ".join(x for x in (p.get("location"), p.get("phone"), p.get("email")) if x), "",
                 _today(), job["company"], "", cl["greeting"], *cl["paragraphs"],
                 cl.get("closing", "Sincerely,"), p["name"]]:
        d.add_paragraph(line)
    d.save(out)


def render_all(doc: dict, p: dict, job: dict, folder: Path) -> None:
    import json
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "doc.json").write_text(json.dumps(doc, indent=2))  # lets us re-render (fix a name, restyle) without new LLM calls
    stem = p["name"].replace(" ", "_")
    to_pdf(resume_html(doc, p), folder / f"{stem}_Resume.pdf", p["name"], f"{p['name']} Resume")
    to_pdf(letter_html(doc, p, job), folder / f"{stem}_Cover_Letter.pdf", p["name"], f"{p['name']} Cover Letter")
    resume_docx(doc, p, folder / f"{stem}_Resume.docx")
    letter_docx(doc, p, job, folder / f"{stem}_Cover_Letter.docx")
