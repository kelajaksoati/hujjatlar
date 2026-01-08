import os
import openpyxl
from openpyxl.styles import Font
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from io import BytesIO
from docx import Document

def smart_rename(filename):
    base_name, extension = os.path.splitext(filename)
    clean_name = base_name.replace("_", " ").replace("-", " ").strip()
    if 'bsb' in clean_name.lower():
        name_only = clean_name.lower().replace('bsb', '').strip()
        clean_name = f"BSB {name_only.upper()}"
    else:
        clean_name = clean_name.title()
    return f"@ISH_REJA_UZ_{clean_name.replace(' ', '_')}{extension.lower()}"

def edit_excel(path):
    try:
        wb = openpyxl.load_workbook(path)
        for ws in wb.worksheets:
            ws.insert_rows(1)
            ws['A1'] = "@ish_reja_uz kanali uchun maxsus tayyorlandi"
            ws['A1'].font = Font(bold=True, color="FF0000", size=12)
        wb.save(path)
    except Exception as e: print(f"Excel error: {e}")

def add_pdf_watermark(path):
    try:
        reader = PdfReader(path); writer = PdfWriter()
        packet = BytesIO(); can = canvas.Canvas(packet)
        can.setFont("Helvetica-Bold", 45); can.setFillGray(0.5, 0.15); can.saveState()
        can.translate(300, 450); can.rotate(45)
        can.drawCentredString(0, 0, "@ish_reja_uz"); can.restoreState(); can.save()
        packet.seek(0); watermark_page = PdfReader(packet).pages[0]
        for page in reader.pages:
            page.merge_page(watermark_page)
            writer.add_page(page)
        with open(path, "wb") as f: writer.write(f)
    except Exception as e: print(f"PDF error: {e}")

def edit_docx(path):
    try:
        doc = Document(path)
        if doc.paragraphs: doc.paragraphs[0].insert_paragraph_before("@ish_reja_uz kanali uchun maxsus tayyorlandi")
        else: doc.add_paragraph("@ish_reja_uz kanali uchun maxsus tayyorlandi")
        doc.save(path)
    except Exception as e: print(f"Docx error: {e}")
