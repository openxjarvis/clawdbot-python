---
name: docx
description: "Create, read, edit, or manipulate Word documents (.docx files). Use when user mentions 'Word doc', '.docx', or requests reports, memos, letters, templates with headings/tables/page numbers. Covers: create with python-docx, read via pandoc, edit existing via XML unpack/pack. Do NOT use for PDFs, spreadsheets, or Google Docs."
metadata:
  {
    "openclaw":
      {
        "emoji": "📝",
        "always": true,
        "install":
          [
            {
              "id": "uv",
              "kind": "uv",
              "packages": ["python-docx"],
              "label": "Install python-docx (uv)",
            },
          ],
      },
  }
---

# DOCX creation, editing, and analysis

## Overview

A .docx file is a ZIP archive containing XML files.

## Quick Reference

| Task | Approach |
|------|----------|
| Read/analyze content | `pandoc` or unpack for raw XML |
| Create new document | Use `python-docx` — see Creating New Documents below |
| Edit existing document | Unpack → edit XML → repack — see Editing Existing Documents below |

### Converting .doc to .docx

Legacy `.doc` files must be converted before editing:

```bash
python scripts/office/soffice.py --headless --convert-to docx document.doc
```

### Reading Content

```bash
# Text extraction with tracked changes
pandoc --track-changes=all document.docx -o output.md

# Raw XML access
python scripts/office/unpack.py document.docx unpacked/
```

### Converting to Images

```bash
python scripts/office/soffice.py --headless --convert-to pdf document.docx
pdftoppm -jpeg -r 150 document.pdf page
```

### Accepting Tracked Changes

To produce a clean document with all tracked changes accepted (requires LibreOffice):

```bash
python scripts/accept_changes.py input.docx output.docx
```

---

## Creating New Documents

Use `python-docx` to generate .docx files programmatically. Install: `uv pip install python-docx`

### Setup

```python
from docx import Document
from docx.shared import Inches, Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn

doc = Document()
doc.save("output.docx")
```

### Validation

After creating, validate with:

```bash
python scripts/office/validate.py output.docx
```

If validation fails, unpack, fix the XML, and repack.

### Page Size

```python
from docx.shared import Inches
from docx.oxml import OxmlElement

section = doc.sections[0]
section.page_width  = Inches(8.5)   # US Letter
section.page_height = Inches(11)
section.left_margin = section.right_margin = Inches(1)
section.top_margin  = section.bottom_margin = Inches(1)
```

**Common page sizes:**

| Paper | Width | Height |
|-------|-------|--------|
| US Letter | 8.5" | 11" |
| A4 | 8.27" | 11.69" |

**Landscape:**

```python
from docx.enum.section import WD_ORIENT
section.orientation = WD_ORIENT.LANDSCAPE
section.page_width, section.page_height = section.page_height, section.page_width
```

### Headings & Paragraphs

```python
doc.add_heading("Document Title", level=0)   # Title style
doc.add_heading("Chapter 1", level=1)        # Heading 1
doc.add_heading("Section 1.1", level=2)      # Heading 2

p = doc.add_paragraph("Body text here.")
p.alignment = WD_ALIGN_PARAGRAPH.LEFT

# Page break
doc.add_page_break()
```

### Text Formatting (Runs)

```python
p = doc.add_paragraph()
run = p.add_run("Bold italic text")
run.bold = True
run.italic = True
run.font.size = Pt(14)
run.font.color.rgb = RGBColor(0x36, 0x36, 0x36)
run.font.name = "Calibri"
```

### Lists

```python
# Bullet list — use 'List Bullet' style
doc.add_paragraph("First item",  style="List Bullet")
doc.add_paragraph("Second item", style="List Bullet")

# Numbered list — use 'List Number' style
doc.add_paragraph("Step one",   style="List Number")
doc.add_paragraph("Step two",   style="List Number")

# Nested (level 2)
p = doc.add_paragraph("Sub-item", style="List Bullet 2")
```

### Tables

```python
from docx.oxml import OxmlElement
from docx.shared import Inches, RGBColor, Pt

table = doc.add_table(rows=2, cols=3)
table.style = "Table Grid"

# Set column widths
for i, width in enumerate([2.5, 4.0, 1.5]):
    for row in table.rows:
        row.cells[i].width = Inches(width)

# Fill cells
cell = table.cell(0, 0)
cell.text = "Header"
run = cell.paragraphs[0].runs[0]
run.bold = True

# Header row shading
def set_cell_bg(cell, hex_color):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), hex_color)
    shd.set(qn("w:val"), "clear")
    tcPr.append(shd)

set_cell_bg(table.cell(0, 0), "D5E8F0")
```

### Images

```python
from docx.shared import Inches

# Add image (width, optionally height — preserves aspect ratio if height omitted)
doc.add_picture("photo.jpg", width=Inches(4))

# Inside a paragraph (inline)
p = doc.add_paragraph()
run = p.add_run()
run.add_picture("chart.png", width=Inches(6))
```

### Headers & Footers

```python
section = doc.sections[0]

# Header
header = section.header
header.paragraphs[0].text = "My Company — Confidential"

# Footer with page number
from docx.oxml import OxmlElement
footer = section.footer
p = footer.paragraphs[0]
p.text = "Page "
run = p.add_run()
fldChar = OxmlElement("w:fldChar")
fldChar.set(qn("w:fldCharType"), "begin")
run._r.append(fldChar)
instrText = OxmlElement("w:instrText")
instrText.text = "PAGE"
run._r.append(instrText)
fldChar2 = OxmlElement("w:fldChar")
fldChar2.set(qn("w:fldCharType"), "end")
run._r.append(fldChar2)
```

### Hyperlinks

```python
from docx.oxml.shared import OxmlElement, qn
import docx.opc.constants

def add_hyperlink(paragraph, url, text):
    part = paragraph.part
    r_id = part.relate_to(url, docx.opc.constants.RELATIONSHIP_TYPE.HYPERLINK, is_external=True)
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), r_id)
    run = OxmlElement("w:r")
    rPr = OxmlElement("w:rPr")
    rStyle = OxmlElement("w:rStyle")
    rStyle.set(qn("w:val"), "Hyperlink")
    rPr.append(rStyle)
    run.append(rPr)
    t = OxmlElement("w:t")
    t.text = text
    run.append(t)
    hyperlink.append(run)
    paragraph._p.append(hyperlink)

p = doc.add_paragraph("Visit ")
add_hyperlink(p, "https://example.com", "Example Site")
```

### Critical Rules for python-docx

- **Units**: Always use `Inches()`, `Pt()`, `Cm()` — never raw integers
- **Lists**: Use built-in styles `'List Bullet'`, `'List Number'` — never manual bullet characters
- **Page breaks**: `doc.add_page_break()` or `run.add_break(WD_BREAK.PAGE)`
- **Table widths**: Set per-cell widths explicitly after adding the table
- **Images**: Omit `height` to auto-preserve aspect ratio
- **Never `\n` in runs**: Use separate paragraphs or `run.add_break()`

---

## Editing Existing Documents

**Follow all 3 steps in order.**

### Step 1: Unpack
```bash
python scripts/office/unpack.py document.docx unpacked/
```
Extracts XML, pretty-prints, merges adjacent runs, and converts smart quotes to XML entities (`&#x201C;` etc.) so they survive editing. Use `--merge-runs false` to skip run merging.

### Step 2: Edit XML

Edit files in `unpacked/word/`. See XML Reference below for patterns.

**Use "Claude" as the author** for tracked changes and comments, unless the user explicitly requests use of a different name.

**Use the Edit tool directly for string replacement. Do not write Python scripts.** Scripts introduce unnecessary complexity. The Edit tool shows exactly what is being replaced.

**CRITICAL: Use smart quotes for new content.** When adding text with apostrophes or quotes, use XML entities to produce smart quotes:
```xml
<!-- Use these entities for professional typography -->
<w:t>Here&#x2019;s a quote: &#x201C;Hello&#x201D;</w:t>
```
| Entity | Character |
|--------|-----------|
| `&#x2018;` | ‘ (left single) |
| `&#x2019;` | ’ (right single / apostrophe) |
| `&#x201C;` | “ (left double) |
| `&#x201D;` | ” (right double) |

**Adding comments:** Use `comment.py` to handle boilerplate across multiple XML files (text must be pre-escaped XML):
```bash
python scripts/comment.py unpacked/ 0 "Comment text with &amp; and &#x2019;"
python scripts/comment.py unpacked/ 1 "Reply text" --parent 0  # reply to comment 0
python scripts/comment.py unpacked/ 0 "Text" --author "Custom Author"  # custom author name
```
Then add markers to document.xml (see Comments in XML Reference).

### Step 3: Pack
```bash
python scripts/office/pack.py unpacked/ output.docx --original document.docx
```
Validates with auto-repair, condenses XML, and creates DOCX. Use `--validate false` to skip.

**Auto-repair will fix:**
- `durableId` >= 0x7FFFFFFF (regenerates valid ID)
- Missing `xml:space="preserve"` on `<w:t>` with whitespace

**Auto-repair won't fix:**
- Malformed XML, invalid element nesting, missing relationships, schema violations

### Common Pitfalls

- **Replace entire `<w:r>` elements**: When adding tracked changes, replace the whole `<w:r>...</w:r>` block with `<w:del>...<w:ins>...` as siblings. Don't inject tracked change tags inside a run.
- **Preserve `<w:rPr>` formatting**: Copy the original run's `<w:rPr>` block into your tracked change runs to maintain bold, font size, etc.

---

## XML Reference

### Schema Compliance

- **Element order in `<w:pPr>`**: `<w:pStyle>`, `<w:numPr>`, `<w:spacing>`, `<w:ind>`, `<w:jc>`, `<w:rPr>` last
- **Whitespace**: Add `xml:space="preserve"` to `<w:t>` with leading/trailing spaces
- **RSIDs**: Must be 8-digit hex (e.g., `00AB1234`)

### Tracked Changes

**Insertion:**
```xml
<w:ins w:id="1" w:author="Claude" w:date="2025-01-01T00:00:00Z">
  <w:r><w:t>inserted text</w:t></w:r>
</w:ins>
```

**Deletion:**
```xml
<w:del w:id="2" w:author="Claude" w:date="2025-01-01T00:00:00Z">
  <w:r><w:delText>deleted text</w:delText></w:r>
</w:del>
```

**Inside `<w:del>`**: Use `<w:delText>` instead of `<w:t>`, and `<w:delInstrText>` instead of `<w:instrText>`.

**Minimal edits** - only mark what changes:
```xml
<!-- Change "30 days" to "60 days" -->
<w:r><w:t>The term is </w:t></w:r>
<w:del w:id="1" w:author="Claude" w:date="...">
  <w:r><w:delText>30</w:delText></w:r>
</w:del>
<w:ins w:id="2" w:author="Claude" w:date="...">
  <w:r><w:t>60</w:t></w:r>
</w:ins>
<w:r><w:t> days.</w:t></w:r>
```

**Deleting entire paragraphs/list items** - when removing ALL content from a paragraph, also mark the paragraph mark as deleted so it merges with the next paragraph. Add `<w:del/>` inside `<w:pPr><w:rPr>`:
```xml
<w:p>
  <w:pPr>
    <w:numPr>...</w:numPr>  <!-- list numbering if present -->
    <w:rPr>
      <w:del w:id="1" w:author="Claude" w:date="2025-01-01T00:00:00Z"/>
    </w:rPr>
  </w:pPr>
  <w:del w:id="2" w:author="Claude" w:date="2025-01-01T00:00:00Z">
    <w:r><w:delText>Entire paragraph content being deleted...</w:delText></w:r>
  </w:del>
</w:p>
```
Without the `<w:del/>` in `<w:pPr><w:rPr>`, accepting changes leaves an empty paragraph/list item.

**Rejecting another author's insertion** - nest deletion inside their insertion:
```xml
<w:ins w:author="Jane" w:id="5">
  <w:del w:author="Claude" w:id="10">
    <w:r><w:delText>their inserted text</w:delText></w:r>
  </w:del>
</w:ins>
```

**Restoring another author's deletion** - add insertion after (don't modify their deletion):
```xml
<w:del w:author="Jane" w:id="5">
  <w:r><w:delText>deleted text</w:delText></w:r>
</w:del>
<w:ins w:author="Claude" w:id="10">
  <w:r><w:t>deleted text</w:t></w:r>
</w:ins>
```

### Comments

After running `comment.py` (see Step 2), add markers to document.xml. For replies, use `--parent` flag and nest markers inside the parent's.

**CRITICAL: `<w:commentRangeStart>` and `<w:commentRangeEnd>` are siblings of `<w:r>`, never inside `<w:r>`.**

```xml
<!-- Comment markers are direct children of w:p, never inside w:r -->
<w:commentRangeStart w:id="0"/>
<w:del w:id="1" w:author="Claude" w:date="2025-01-01T00:00:00Z">
  <w:r><w:delText>deleted</w:delText></w:r>
</w:del>
<w:r><w:t> more text</w:t></w:r>
<w:commentRangeEnd w:id="0"/>
<w:r><w:rPr><w:rStyle w:val="CommentReference"/></w:rPr><w:commentReference w:id="0"/></w:r>

<!-- Comment 0 with reply 1 nested inside -->
<w:commentRangeStart w:id="0"/>
  <w:commentRangeStart w:id="1"/>
  <w:r><w:t>text</w:t></w:r>
  <w:commentRangeEnd w:id="1"/>
<w:commentRangeEnd w:id="0"/>
<w:r><w:rPr><w:rStyle w:val="CommentReference"/></w:rPr><w:commentReference w:id="0"/></w:r>
<w:r><w:rPr><w:rStyle w:val="CommentReference"/></w:rPr><w:commentReference w:id="1"/></w:r>
```

### Images

1. Add image file to `word/media/`
2. Add relationship to `word/_rels/document.xml.rels`:
```xml
<Relationship Id="rId5" Type=".../image" Target="media/image1.png"/>
```
3. Add content type to `[Content_Types].xml`:
```xml
<Default Extension="png" ContentType="image/png"/>
```
4. Reference in document.xml:
```xml
<w:drawing>
  <wp:inline>
    <wp:extent cx="914400" cy="914400"/>  <!-- EMUs: 914400 = 1 inch -->
    <a:graphic>
      <a:graphicData uri=".../picture">
        <pic:pic>
          <pic:blipFill><a:blip r:embed="rId5"/></pic:blipFill>
        </pic:pic>
      </a:graphicData>
    </a:graphic>
  </wp:inline>
</w:drawing>
```

---

## Dependencies

```bash
# Core Python library
uv pip install python-docx

# System tools (macOS)
brew install pandoc libreoffice poppler
```

- **python-docx** — create and edit .docx programmatically
- **pandoc** — text extraction and format conversion
- **LibreOffice** (`soffice`) — PDF/image conversion (via `scripts/office/soffice.py`)
- **Poppler** (`pdftoppm`) — PDF to images
