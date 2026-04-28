import os
from openpyxl import Workbook

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def create_offer_excel(products: list) -> str:
    """Generate an Excel file with the offer products list."""
    filename = os.path.join(BASE_DIR, "AI WAREHOUSE ASSISTANT.xlsx")
    wb = Workbook()
    ws = wb.active
    ws.title = "AI Warehouse Assistant"

    # Add header
    ws.append(["Τεμάχια", "S1 Code", "Factory Code", "Περιγραφή"])
    
    # Add products
    for product in products:
        if isinstance(product, dict):
            qty = product.get('qty', 1)
            code = product.get('code', '')
            factory = product.get('factory', '')
            desc = product.get('desc', '')
            ws.append([qty, code, factory, desc])
        else:
            ws.append(["-", "-", "-", str(product)])

    # Adjust column widths
    ws.column_dimensions['A'].width = 10
    ws.column_dimensions['B'].width = 15
    ws.column_dimensions['C'].width = 25
    ws.column_dimensions['D'].width = 80

    wb.save(filename)
    return filename


