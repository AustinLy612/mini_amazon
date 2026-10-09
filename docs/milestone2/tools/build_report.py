"""Build the member contribution PDF from the reviewed Markdown design.
Requires reportlab; run from any working directory.
"""
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.pagesizes import A4

root = Path(__file__).resolve().parents[1]
styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name='BodyCopy', fontName='Helvetica', fontSize=10, leading=14, spaceAfter=8))
styles.add(ParagraphStyle(name='SectionTitle', fontName='Helvetica-Bold', fontSize=14, leading=18, textColor=colors.HexColor('#153a57'), spaceBefore=15, spaceAfter=8, keepWithNext=True))
styles.add(ParagraphStyle(name='SubTitle', fontName='Helvetica-Bold', fontSize=11, leading=15, spaceBefore=9, spaceAfter=5, keepWithNext=True))
styles.add(ParagraphStyle(name='SmallCopy', fontName='Helvetica', fontSize=8.5, leading=12, spaceAfter=4))


def p(text, style='BodyCopy'):
    return Paragraph(escape(text).replace('`', ''), styles[style])


def footer(canvas, doc):
    canvas.setStrokeColor(colors.HexColor('#d7e1e8'))
    canvas.line(44, 40, A4[0]-44, 40)
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(colors.HexColor('#526574'))
    canvas.drawString(44, 27, 'Mini-Amazon | Ziyi Shen | Cart / Order contribution | 08 Oct 2026')
    canvas.drawRightString(A4[0]-44, 27, str(doc.page))


story = [p('MINI-AMAZON', 'SubTitle'), p('Milestone 2: Cart / Order', 'Title'),
         p('Database design, page flows and team integration', 'SubTitle'),
         p('Prepared for team review. This is the Carts member contribution, not the complete team REPORT.pdf.'),
         p('Implemented: wishlist tutorial and a read-only cart prototype. Planned: cart mutations, checkout and order details.'), Spacer(1, 8)]
source = (root/'CARTS_DESIGN.md').read_text().splitlines()
for line in source:
    if not line or line.startswith('# '):
        continue
    if line.startswith('## '):
        story.append(p(line[3:], 'SectionTitle'))
    elif line.startswith('### '):
        story.append(p(line[4:], 'SubTitle'))
    else:
        story.append(p(line))
    if line.startswith('### Relationships and derived fields'):
        rows = [
            ['Relationship', 'Meaning / key'],
            ['Users -> Orders', 'One buyer, many orders'],
            ['Orders -> OrderItems', 'One order, one or more lines (application invariant)'],
            ['Users + Products -> Inventory', 'Listing key: (seller_id, product_id)'],
            ['Users + Products -> CartItems', 'Cart key: (buyer_id, product_id, seller_id)'],
            ['Users + Products -> OrderItems', 'ID primary key; unique order/product/seller'],
        ]
        table = Table([[p(cell, 'SmallCopy') for cell in row] for row in rows], colWidths=[165, 330], repeatRows=1, hAlign='LEFT')
        table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#eaf1f6')),('VALIGN',(0,0),(-1,-1),'TOP'),('GRID',(0,0),(-1,-1),.4,colors.HexColor('#ccd8e0')),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
        story.extend([table, Spacer(1,10)])

SimpleDocTemplate(str(root/'Cart_Order_Milestone2.pdf'), pagesize=A4, rightMargin=44, leftMargin=44, topMargin=38, bottomMargin=55, title='Mini-Amazon Milestone 2 - Cart / Order', author='Ziyi Shen').build(story, onFirstPage=footer, onLaterPages=footer)
print(root/'Cart_Order_Milestone2.pdf')
