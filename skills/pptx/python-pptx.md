# python-pptx Tutorial

## Setup & Basic Structure

```python
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

prs = Presentation()
prs.slide_width = Inches(10)
prs.slide_height = Inches(5.625)   # 16:9

slide_layout = prs.slide_layouts[6]  # blank layout
slide = prs.slides.add_slide(slide_layout)

prs.save("Presentation.pptx")
```

## Slide Layouts (built-in indices)

| Index | Layout |
|-------|--------|
| 0 | Title Slide |
| 1 | Title and Content |
| 2 | Title and Two Content |
| 5 | Title Only |
| 6 | Blank |

Use `slide_layouts[6]` (Blank) when building from scratch for full control.

---

## Text Boxes & Formatting

```python
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

# Add a text box
txBox = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(8), Inches(2))
tf = txBox.text_frame
tf.word_wrap = True

# Add a paragraph
p = tf.add_paragraph()
p.text = "Hello World"
p.alignment = PP_ALIGN.CENTER

# Style a run
run = p.runs[0]
run.font.bold = True
run.font.size = Pt(36)
run.font.color.rgb = RGBColor(0x36, 0x36, 0x36)
run.font.name = "Calibri"

# Multiple runs in one paragraph (rich text)
p2 = tf.add_paragraph()
run1 = p2.add_run()
run1.text = "Bold "
run1.font.bold = True
run2 = p2.add_run()
run2.text = "Normal"
run2.font.bold = False
```

### Paragraph Spacing

```python
from pptx.oxml.ns import qn
from lxml import etree

# Space after paragraph (in EMU, 1pt = 12700 EMU)
pPr = p._pPr
if pPr is None:
    pPr = p._p.get_or_add_pPr()
spcAft = etree.SubElement(pPr, qn('a:spcAft'))
spcPts = etree.SubElement(spcAft, qn('a:spcPts'))
spcPts.set('val', '600')   # 6pt space after (val = pt * 100)
```

---

## Lists & Bullets

```python
# Bulleted list via XML
from pptx.oxml.ns import qn
from lxml import etree

txBox = slide.shapes.add_textbox(Inches(0.5), Inches(0.5), Inches(9), Inches(4))
tf = txBox.text_frame
tf.word_wrap = True

items = ["First item", "Second item", "Third item"]
for i, item in enumerate(items):
    p = tf.add_paragraph() if i > 0 else tf.paragraphs[0]
    p.text = item
    p.level = 0

    # Add bullet character
    pPr = p._p.get_or_add_pPr()
    buChar = etree.SubElement(pPr, qn('a:buChar'))
    buChar.set('char', '•')

    run = p.runs[0]
    run.font.size = Pt(16)
```

**Numbered list:**

```python
pPr = p._p.get_or_add_pPr()
buAutoNum = etree.SubElement(pPr, qn('a:buAutoNum'))
buAutoNum.set('type', 'arabicPeriod')   # 1. 2. 3.
```

---

## Shapes

```python
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.util import Emu

# Rectangle
shape = slide.shapes.add_shape(
    MSO_SHAPE_TYPE.AUTO_SHAPE,  # or use pptx.enum.shapes.PP_MEDIA_TYPE
    Inches(0.5), Inches(0.8), Inches(1.5), Inches(3.0)
)
shape.fill.solid()
shape.fill.fore_color.rgb = RGBColor(0xFF, 0x00, 0x00)
shape.line.color.rgb = RGBColor(0x00, 0x00, 0x00)
shape.line.width = Pt(2)

# Use MSO_SHAPE_TYPE constants via pptx.enum.shapes
from pptx.enum.shapes import PP_PLACEHOLDER
```

**Better shape creation using autoshape types:**

```python
from pptx.util import Inches
from pptx.enum.shapes import MSO_CONNECTOR_TYPE
import pptx.oxml.ns as ns
from lxml import etree

# Add rectangle via add_shape (most reliable)
from pptx.util import Inches, Emu
from pptx.dml.color import RGBColor

def add_rect(slide, x, y, w, h, fill_hex, line_hex=None, line_width_pt=0):
    shape = slide.shapes.add_shape(1, Inches(x), Inches(y), Inches(w), Inches(h))
    shape.fill.solid()
    shape.fill.fore_color.rgb = RGBColor.from_string(fill_hex)
    if line_hex:
        shape.line.color.rgb = RGBColor.from_string(line_hex)
        shape.line.width = Pt(line_width_pt)
    else:
        shape.line.fill.background()
    return shape
```

**Line connector:**

```python
from pptx.util import Inches, Pt
connector = slide.shapes.add_connector(
    1,  # MSO_CONNECTOR_TYPE.STRAIGHT
    Inches(1), Inches(3), Inches(6), Inches(3)
)
connector.line.color.rgb = RGBColor(0xFF, 0x00, 0x00)
connector.line.width = Pt(3)
```

---

## Images

```python
from pptx.util import Inches

# From file path
pic = slide.shapes.add_picture("images/chart.png", Inches(1), Inches(1), Inches(5), Inches(3))

# Maintain aspect ratio
from PIL import Image
img = Image.open("photo.jpg")
orig_w, orig_h = img.size
max_h = Inches(3.0)
calc_w = max_h * (orig_w / orig_h)
center_x = (prs.slide_width - calc_w) / 2
slide.shapes.add_picture("photo.jpg", center_x, Inches(1.2), calc_w, max_h)
```

---

## Tables

```python
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor

rows, cols = 3, 3
table = slide.shapes.add_table(rows, cols, Inches(1), Inches(1), Inches(8), Inches(2)).table

# Set column widths
table.columns[0].width = Inches(3)
table.columns[1].width = Inches(3)
table.columns[2].width = Inches(2)

# Fill cells
cell = table.cell(0, 0)
cell.text = "Header"
cell.fill.solid()
cell.fill.fore_color.rgb = RGBColor(0x66, 0x99, 0xCC)

para = cell.text_frame.paragraphs[0]
para.runs[0].font.bold = True
para.runs[0].font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
```

---

## Charts

```python
from pptx.util import Inches
from pptx.chart.data import ChartData
from pptx.enum.chart import XL_CHART_TYPE

# Bar chart
chart_data = ChartData()
chart_data.categories = ['Q1', 'Q2', 'Q3', 'Q4']
chart_data.add_series('Sales', (4500, 5500, 6200, 7100))

chart = slide.shapes.add_chart(
    XL_CHART_TYPE.COLUMN_CLUSTERED,
    Inches(0.5), Inches(0.6), Inches(6), Inches(3),
    chart_data
).chart

chart.has_title = True
chart.chart_title.text_frame.text = "Quarterly Sales"

# Line chart
chart_data2 = ChartData()
chart_data2.categories = ['Jan', 'Feb', 'Mar']
chart_data2.add_series('Temp', (32, 35, 42))
slide.shapes.add_chart(XL_CHART_TYPE.LINE, Inches(0.5), Inches(4), Inches(6), Inches(3), chart_data2)

# Pie chart
chart_data3 = ChartData()
chart_data3.categories = ['A', 'B', 'Other']
chart_data3.add_series('Share', (35, 45, 20))
slide.shapes.add_chart(XL_CHART_TYPE.PIE, Inches(7), Inches(1), Inches(5), Inches(4), chart_data3)
```

---

## Slide Backgrounds

```python
from pptx.dml.color import RGBColor
from pptx.oxml.ns import qn
from lxml import etree

# Solid color background
background = slide.background
fill = background.fill
fill.solid()
fill.fore_color.rgb = RGBColor(0x1E, 0x27, 0x61)

# Image background
from pptx.util import Inches
pic = slide.shapes.add_picture(
    "bg.jpg", 0, 0,
    prs.slide_width, prs.slide_height
)
# Move image to back
slide.shapes._spTree.remove(pic._element)
slide.shapes._spTree.insert(2, pic._element)
```

---

## Slide Masters & Layouts

```python
# List available layouts
for i, layout in enumerate(prs.slide_layouts):
    print(i, layout.name)

# Add slide with specific layout
slide = prs.slides.add_slide(prs.slide_layouts[1])  # Title and Content

# Use placeholder
title_ph = slide.placeholders[0]
title_ph.text = "My Title"
body_ph = slide.placeholders[1]
tf = body_ph.text_frame
tf.text = "First bullet"
tf.add_paragraph().text = "Second bullet"
```

---

## python-pptx Color Helper

```python
from pptx.dml.color import RGBColor

# From hex string (no # prefix needed for RGBColor.from_string)
color = RGBColor.from_string("FF0000")   # Red

# From individual RGB values
color = RGBColor(0xFF, 0x00, 0x00)
```

---

## Generating from Config (generate_ppt.py)

For creating presentations from a JSON config (the quick-start approach), use the existing helper script:

```bash
python scripts/generate_ppt.py \
  --config /tmp/presentation_config.json \
  --output ~/presentations/output.pptx
```

Config format:

```json
{
  "title": "Presentation Title",
  "slides": [
    {
      "layout": "title",
      "title": "Main Title",
      "subtitle": "Subtitle text"
    },
    {
      "layout": "content",
      "title": "Slide Title",
      "content": {
        "bullets": ["First point", "Second point", "Third point"]
      }
    },
    {
      "layout": "section",
      "title": "Section Header"
    }
  ]
}
```

---

## Common Pitfalls

1. **Units**: Always use `Inches()`, `Pt()`, or `Emu()` — never raw integers for positions/sizes
2. **Color**: Use `RGBColor(r, g, b)` with integers 0-255, or `RGBColor.from_string("RRGGBB")` (no `#`)
3. **Text frame paragraphs**: First paragraph always exists as `tf.paragraphs[0]` — don't add a paragraph before setting it
4. **XML manipulation**: When python-pptx API lacks a feature, go direct with `lxml`:
   ```python
   from pptx.oxml.ns import qn
   from lxml import etree
   element = shape._element
   ```
5. **Save frequently**: python-pptx does not auto-save; call `prs.save("output.pptx")` at the end

---

## Quick Reference

- **Chart types**: `XL_CHART_TYPE.COLUMN_CLUSTERED`, `LINE`, `PIE`, `DOUGHNUT`, `BAR_CLUSTERED`
- **Alignment**: `PP_ALIGN.LEFT`, `CENTER`, `RIGHT`
- **Slide dimensions**: `prs.slide_width`, `prs.slide_height` (in EMU; `Inches(10)` = 9144000 EMU)
- **Font**: `run.font.bold`, `.italic`, `.size`, `.color.rgb`, `.name`
