"""Generate the committed sample deck. Northwind Kites is a made-up company."""

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.util import Inches, Pt

OUTPUT = Path(__file__).parent.parent / "samples" / "northwind_kites_q3.pptx"


def _title_slide(deck: Presentation) -> None:
    slide = deck.slides.add_slide(deck.slide_layouts[0])
    slide.shapes.title.text = "Northwind Kites: Q3 2026 results"
    slide.placeholders[1].text = "A fictional company, for demonstration only"


def _highlights(deck: Presentation) -> None:
    slide = deck.slides.add_slide(deck.slide_layouts[1])
    slide.shapes.title.text = "Q3 highlights"
    slide.placeholders[1].text = (
        "Revenue reached $48M, up 12% from Q2\n"
        "Opened a second factory in Tulsa\n"
        "Customer return rate fell to 1.8%"
    )
    slide.notes_slide.notes_text_frame.text = (
        "The Tulsa factory starts full production in February 2027."
    )


def _revenue_chart(deck: Presentation) -> None:
    slide = deck.slides.add_slide(deck.slide_layouts[5])
    slide.shapes.title.text = "Quarterly revenue and cost"
    data = CategoryChartData()
    data.categories = ["Q4 2025", "Q1 2026", "Q2 2026", "Q3 2026"]
    data.add_series("Revenue ($M)", (31, 38, 42.9, 48))
    data.add_series("Cost ($M)", (24, 27, 30, 33))
    frame = slide.shapes.add_chart(
        XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(1), Inches(1.6), Inches(8), Inches(5.2), data
    )
    frame.chart.has_legend = True
    frame.chart.legend.position = XL_LEGEND_POSITION.BOTTOM
    frame.chart.legend.include_in_layout = False


def _segment_table(deck: Presentation) -> None:
    slide = deck.slides.add_slide(deck.slide_layouts[5])
    slide.shapes.title.text = "Q3 results by segment"
    rows = [
        ("Segment", "Revenue ($M)", "Gross margin", "Units sold"),
        ("Stunt kites", "21.0", "44%", "140,000"),
        ("Beach kites", "18.5", "37%", "310,000"),
        ("Accessories", "8.5", "52%", "95,000"),
    ]
    table = slide.shapes.add_table(4, 4, Inches(0.8), Inches(2), Inches(8.4), Inches(2.4)).table
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            table.cell(r, c).text = value


def _architecture_diagram(deck: Presentation) -> None:
    slide = deck.slides.add_slide(deck.slide_layouts[5])
    slide.shapes.title.text = "Order system architecture"
    boxes = [
        ("Web store", 0.5, 2.2),
        ("Order API", 3.75, 2.2),
        ("Payments", 7.0, 2.2),
        ("Warehouse queue", 3.75, 4.4),
        ("Tulsa factory", 7.0, 4.4),
    ]
    shapes = {}
    for label, left, top in boxes:
        box = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left), Inches(top), Inches(2.5), Inches(1)
        )
        box.text_frame.text = label
        shapes[label] = box
    links = [
        ("Web store", "Order API", 3, 1),
        ("Order API", "Payments", 3, 1),
        ("Order API", "Warehouse queue", 2, 0),
        ("Warehouse queue", "Tulsa factory", 3, 1),
    ]
    for start, end, start_site, end_site in links:
        line = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, 0, 0, 0, 0)
        line.begin_connect(shapes[start], start_site)
        line.end_connect(shapes[end], end_site)


def _pictured_chart_png() -> bytes:
    """A bar chart with no underlying data: only a picture of one."""
    image = Image.new("RGB", (1000, 560), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=26)
    bars = [("North", 41), ("South", 27), ("East", 18), ("West", 14)]
    draw.line((80, 480, 960, 480), fill="black", width=3)
    for i, (region, share) in enumerate(bars):
        left = 130 + i * 205
        top = 480 - share * 9
        draw.rectangle((left, top, left + 130, 480), fill="#2b6cb0")
        draw.text((left + 40, top - 38), f"{share}%", fill="black", font=font)
        draw.text((left + 25, 495), region, fill="black", font=font)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _pictured_chart(deck: Presentation) -> None:
    slide = deck.slides.add_slide(deck.slide_layouts[5])
    slide.shapes.title.text = "Where customers are"
    slide.shapes.add_picture(
        io.BytesIO(_pictured_chart_png()), Inches(1), Inches(1.8), width=Inches(8)
    )


def _risks(deck: Presentation) -> None:
    slide = deck.slides.add_slide(deck.slide_layouts[1])
    slide.shapes.title.text = "Risks and outlook"
    frame = slide.placeholders[1].text_frame
    frame.text = "Ripstop nylon prices rose 9% this year"
    for line in ("Q4 revenue guidance is $52M to $55M", "Spring demand depends on weather"):
        frame.add_paragraph().text = line
    for paragraph in frame.paragraphs:
        for run in paragraph.runs:
            run.font.size = Pt(24)


def main() -> None:
    deck = Presentation()
    deck.slide_width = Inches(10)
    deck.slide_height = Inches(7.5)
    for build in (
        _title_slide,
        _highlights,
        _revenue_chart,
        _segment_table,
        _architecture_diagram,
        _pictured_chart,
        _risks,
    ):
        build(deck)
    OUTPUT.parent.mkdir(exist_ok=True)
    deck.save(str(OUTPUT))
    print(OUTPUT)


if __name__ == "__main__":
    main()
