"""Constancia del expediente: metadatos y auditoría sin reproducir PII."""
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from . import audit_service, request_service


def request_pdf(ticket_id):
    req = request_service.get_request(ticket_id)
    data = req.to_dict()
    _, logs = audit_service.query_logs(ticket_id=ticket_id, limit=1000)
    stream = BytesIO()
    styles = getSampleStyleSheet()
    story = [Paragraph("Constancia de solicitud DSAR", styles["Title"]), Spacer(1, 0.6 * cm)]
    for label, field in (("Ticket", "ticket_id"), ("Derecho solicitado", "request_type"),
                         ("Estado", "status"), ("Recepción", "received_at"),
                         ("Fecha límite interna", "due_at"), ("Cierre", "completed_at")):
        story.append(Paragraph(f"<b>{label}:</b> {escape(str(data[field] or 'Pendiente'))}", styles["Normal"]))
        story.append(Spacer(1, 0.2 * cm))
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph("Trazabilidad (últimos 1000 eventos)", styles["Heading2"]))
    rows = [["Fecha UTC", "Acción", "Resultado"]]
    for entry in reversed(logs):
        item = entry.to_dict()
        rows.append([Paragraph(escape(item["timestamp"]), styles["BodyText"]),
                     Paragraph(escape(item["action"]), styles["BodyText"]),
                     Paragraph(escape(item["outcome"]), styles["BodyText"])])
    table = Table(rows, colWidths=[6 * cm, 7 * cm, 3 * cm], repeatRows=1)
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1B365D")),
                              ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                              ("VALIGN", (0, 0), (-1, -1), "TOP"),
                              ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey)]))
    story.extend([table, Spacer(1, 0.6 * cm), Paragraph(
        "Constancia académica de seguimiento. No incluye documento, correo, texto de la solicitud ni datos de terceros. "
        "No acredita la identidad del solicitante ni certifica cumplimiento normativo.", styles["Normal"])])
    SimpleDocTemplate(stream, title="Constancia DSAR", author="Agente DSAR").build(story)
    audit_service.record("REPORT_GENERATED", entity_type="dsar_request", entity_id=str(req.id), ticket_id=ticket_id)
    stream.seek(0)
    return stream
