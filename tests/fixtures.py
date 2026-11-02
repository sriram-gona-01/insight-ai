"""Small synthetic documents, generated in code."""

from pathlib import Path

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE
from pptx.util import Inches
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle


def make_pptx(path: Path, label: str = "Acme") -> Path:
    """Slide 1 has text and notes, slide 2 a table, slide 3 is hidden, slide 4 a chart."""
    deck = Presentation()
    blank_title = deck.slide_layouts[5]

    slide = deck.slides.add_slide(deck.slide_layouts[1])
    slide.shapes.title.text = f"{label} overview"
    slide.placeholders[1].text = "Revenue grew in every region"
    slide.notes_slide.notes_text_frame.text = "Mention the new Tulsa plant"

    slide = deck.slides.add_slide(blank_title)
    slide.shapes.title.text = f"{label} margins"
    table = slide.shapes.add_table(2, 2, Inches(1), Inches(2), Inches(6), Inches(1)).table
    table.cell(0, 0).text = "Segment"
    table.cell(0, 1).text = "Margin"
    table.cell(1, 0).text = "Cloud"
    table.cell(1, 1).text = "41%"

    hidden = deck.slides.add_slide(blank_title)
    hidden.shapes.title.text = "Hidden slide"
    hidden._element.set("show", "0")

    slide = deck.slides.add_slide(blank_title)
    slide.shapes.title.text = f"{label} quarterly revenue"
    data = CategoryChartData()
    data.categories = ["Q1", "Q2"]
    data.add_series("Revenue", (10.5, 12))
    data.add_series("Cost", (4, 5))
    slide.shapes.add_chart(
        XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(1), Inches(2), Inches(6), Inches(4), data
    )

    deck.save(str(path))
    return path


def make_pdf(path: Path, label: str = "Acme") -> Path:
    """Page 1 has text and a bordered table, page 2 has text and a lone bordered box."""
    pdf = canvas.Canvas(str(path), pagesize=letter)
    pdf.drawString(72, 720, f"{label} financial summary")
    pdf.drawString(72, 700, "Operating income improved")
    table = Table([["Year", "Income"], ["2024", "77"]])
    table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 1, colors.black)]))
    table.wrapOn(pdf, 300, 200)
    table.drawOn(pdf, 72, 600)
    pdf.showPage()

    pdf.drawString(72, 720, f"{label} outlook")
    pdf.rect(60, 680, 300, 30)
    pdf.drawString(72, 690, "Text inside a box")
    pdf.showPage()
    pdf.save()
    return path
