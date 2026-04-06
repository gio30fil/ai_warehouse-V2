import os
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
font_path = os.path.join(BASE_DIR, "fonts", "DejaVuSans.ttf")

_font_registered = False


def _ensure_font():
    global _font_registered
    if not _font_registered:
        if os.path.exists(font_path):
            pdfmetrics.registerFont(TTFont("DejaVu", font_path))
            _font_registered = True


def create_offer_pdf(products: list) -> str:
    """Generate a PDF with the offer products list."""
    _ensure_font()

    filename = os.path.join(BASE_DIR, "offer.pdf")
    c = canvas.Canvas(filename)

    font_name = "DejaVu" if _font_registered else "Helvetica"
    c.setFont(font_name, 18)
    c.drawString(100, 800, "IFSAS - Προσφορά Προϊόντων")

    y = 760
    c.setFont(font_name, 12)

    for product in products:
        text = str(product)
        text = text.replace("❌", "").replace("\n", "").replace("\r", "").strip()
        c.drawString(100, y, text)
        y -= 25

        if y < 50:
            c.showPage()
            c.setFont(font_name, 12)
            y = 780

    c.save()
    return filename
