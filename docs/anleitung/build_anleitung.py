#!/usr/bin/env python3
"""Erzeugt das Bedienungs-PDF für die Fotobox.

Aufruf:  python build_anleitung.py
Ergebnis: Fotobox-Anleitung.pdf  (im selben Ordner)

Das Disclaimer-Foto (die "zerstörte" Fotobox) wird automatisch eingebettet,
sobald eine Datei namens  fotobox.jpg / .jpeg / .png  in diesem Ordner liegt.
Fehlt sie, erscheint stattdessen ein Platzhalter-Kasten.
"""

import os

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "Fotobox-Anleitung.pdf")

# Farben (Fotobox-Look: dunkel + ein kräftiges Rot für Warnungen)
INK = colors.HexColor("#111111")
DIM = colors.HexColor("#666666")
ACCENT = colors.HexColor("#1a1a1a")
RED = colors.HexColor("#d32020")
RED_BG = colors.HexColor("#fdecec")
LINE = colors.HexColor("#d9d9d9")


def find_image():
    for name in ("fotobox.jpg", "fotobox.jpeg", "fotobox.png", "fotobox.JPG"):
        p = os.path.join(HERE, name)
        if os.path.isfile(p):
            return p
    return None


def styles():
    s = getSampleStyleSheet()
    s.add(ParagraphStyle(
        "Wordmark", parent=s["Title"], fontName="Helvetica-Bold",
        fontSize=30, leading=32, textColor=INK, alignment=TA_CENTER,
        spaceAfter=2,
    ))
    s.add(ParagraphStyle(
        "Sub", parent=s["Normal"], fontSize=12, leading=15, textColor=DIM,
        alignment=TA_CENTER, spaceAfter=12,
    ))
    s.add(ParagraphStyle(
        "Intro", parent=s["Normal"], fontSize=10.5, leading=15, textColor=INK,
        alignment=TA_LEFT, spaceAfter=10,
    ))
    s.add(ParagraphStyle(
        "H2", parent=s["Heading2"], fontName="Helvetica-Bold", fontSize=14,
        leading=18, textColor=colors.white, spaceBefore=4, spaceAfter=6,
    ))
    s.add(ParagraphStyle(
        "Step", parent=s["Normal"], fontSize=11, leading=16, textColor=INK,
        spaceAfter=7, leftIndent=2,
    ))
    s.add(ParagraphStyle(
        "Warn", parent=s["Normal"], fontSize=11, leading=16, textColor=INK,
        spaceAfter=0,
    ))
    s.add(ParagraphStyle(
        "Caption", parent=s["Normal"], fontSize=9, leading=12, textColor=DIM,
        alignment=TA_CENTER, spaceBefore=6,
    ))
    s.add(ParagraphStyle(
        "Punch", parent=s["Normal"], fontName="Helvetica-Bold", fontSize=20,
        leading=26, textColor=RED, alignment=TA_CENTER, spaceBefore=10,
    ))
    s.add(ParagraphStyle(
        "Foot", parent=s["Normal"], fontSize=8, leading=11, textColor=DIM,
        alignment=TA_CENTER,
    ))
    return s


def section_bar(title, st):
    """Dunkler Balken als Abschnitts-Überschrift."""
    p = Paragraph(title, st["H2"])
    t = Table([[p]], colWidths=[17 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), ACCENT),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def warn_box(html, st):
    """Rot hinterlegter Warnkasten mit rotem Balken links."""
    p = Paragraph(html, st["Warn"])
    t = Table([[p]], colWidths=[17 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), RED_BG),
        ("LINEBEFORE", (0, 0), (0, -1), 3, RED),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
    ]))
    return t


def build():
    st = styles()
    doc = SimpleDocTemplate(
        OUT, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=1.1 * cm, bottomMargin=1.2 * cm,
        title="Fotobox – Bedienungsanleitung", author="Fotobox",
    )
    story = []

    # ── Kopf ─────────────────────────────────────────────
    story.append(Paragraph("F O T O B O X", st["Wordmark"]))
    story.append(Paragraph("Bedienungsanleitung", st["Sub"]))
    story.append(Paragraph(
        "Diese Anleitung erklärt, wie die Fotobox <b>aufgebaut</b>, "
        "<b>bedient</b> und – ganz wichtig – <b>richtig ausgeschaltet</b> "
        "wird. Bitte vor der Veranstaltung einmal in Ruhe durchlesen.",
        st["Intro"]))

    # ── 1. Aufbau & Einschalten ──────────────────────────
    story.append(section_bar("1 &nbsp;&nbsp; Aufbau &amp; Einschalten", st))
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        "<b>1.</b> Beide Stecker einstecken – Strom für den Mini-Computer "
        "und für Kamera/Beleuchtung.", st["Step"]))
    story.append(warn_box(
        "<b><font color='#d32020'>ACHTUNG:</font></b> Vorher sicherstellen, "
        "dass <b>keine falsche oder fremde Spannung</b> anliegt. Eine "
        "falsche Spannung zerstört die Elektronik <b>sofort und "
        "irreparabel</b> – das lässt sich danach nicht mehr reparieren.",
        st))
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "<b>2.</b> Hinten den <b>Vorhang öffnen</b>. An der Kamera auf dem "
        "<b>Touchscreen auf OK</b> tippen (Uhrzeit/Datum bestätigen).",
        st["Step"]))
    story.append(Paragraph(
        "<b>3.</b> Jetzt startet das System. Das <b>dauert etwas</b> "
        "(ein bis zwei Minuten).", st["Step"]))
    story.append(Paragraph(
        "<b>4.</b> Zwischendurch erscheint kurz ein <b>weißer Bildschirm</b> "
        "– das ist normal. Einfach rund <b>30 Sekunden warten</b>. "
        "Danach erscheint das FOTOBOX-Interface.", st["Step"]))

    story.append(Spacer(1, 10))

    # ── 2. Fotos machen ──────────────────────────────────
    story.append(section_bar("2 &nbsp;&nbsp; Fotos machen", st))
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        "&bull; Auf den <b>Startbildschirm tippen</b> (dort steht <b>Foto "
        "machen</b>) – <b>oder</b> den großen Auslöse-Knopf drücken.",
        st["Step"]))
    story.append(Paragraph(
        "&bull; Es läuft ein <b>Countdown</b>, dann wird das Foto "
        "aufgenommen.", st["Step"]))
    story.append(Paragraph(
        "&bull; Danach erscheint die <b>Vorschau</b>: <b>Nochmal</b> für ein "
        "weiteres Foto, <b>Fertig</b> zum Teilen.", st["Step"]))
    story.append(Paragraph(
        "&bull; Zum Teilen baut die Box ein <b>eigenes WLAN</b> auf: mit dem "
        "<b>ersten QR-Code</b> verbindet sich das Handy mit dem WLAN, mit dem "
        "<b>zweiten QR-Code</b> öffnet sich die Download-Seite.", st["Step"]))
    story.append(Paragraph(
        "&bull; <i>Optional:</i> Steckt ein <b>USB-Stick</b> in der Box, "
        "werden alle Fotos automatisch zusätzlich darauf gesichert.",
        st["Step"]))

    story.append(Spacer(1, 10))

    # ── 3. Ausschalten ───────────────────────────────────
    story.append(section_bar("3 &nbsp;&nbsp; Ausschalten – nach der Party", st))
    story.append(Spacer(1, 8))
    story.append(warn_box(
        "<b><font color='#d32020'>NIEMALS</font></b> einfach den <b>Stecker "
        "ziehen!</b> Dabei kann die Speicherkarte und das System beschädigt "
        "werden – im schlimmsten Fall startet die Box danach nicht mehr.",
        st))
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "<b>1.</b> Auf dem Startbildschirm <b>5× schnell in die obere rechte "
        "Ecke</b> tippen.", st["Step"]))
    story.append(Paragraph(
        "<b>2.</b> Im Menü auf <b>Herunterfahren</b> tippen.", st["Step"]))
    story.append(Paragraph(
        "<b>3.</b> Warten, bis der <b>Bildschirm komplett schwarz/aus</b> "
        "ist. <b>Erst dann</b> die Stecker ziehen.", st["Step"]))

    # ── Disclaimer-Seite ─────────────────────────────────
    story.append(PageBreak())
    story.append(Spacer(1, 6))
    story.append(section_bar("Disclaimer", st))
    story.append(Spacer(1, 10))

    img_path = find_image()
    if img_path:
        # Bild auf max. Breite skalieren, Seitenverhältnis halten.
        from reportlab.lib.utils import ImageReader
        iw, ih = ImageReader(img_path).getSize()
        max_w = 12.5 * cm
        max_h = 15 * cm
        ratio = min(max_w / iw, max_h / ih)
        img = Image(img_path, width=iw * ratio, height=ih * ratio)
        img.hAlign = "CENTER"
        story.append(img)
    else:
        ph = Table([[Paragraph(
            "Hier kommt das Foto der Fotobox hin.<br/>"
            "(Datei <b>fotobox.jpg</b> in diesen Ordner legen "
            "und neu erzeugen.)",
            ParagraphStyle("ph", fontSize=10, leading=14,
                           textColor=DIM, alignment=TA_CENTER))]],
            colWidths=[12.5 * cm], rowHeights=[8 * cm])
        ph.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 1, LINE),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        ph.hAlign = "CENTER"
        story.append(ph)

    story.append(Paragraph(
        "(KI-bearbeitetes Bild – keine echte Aufnahme.)", st["Caption"]))
    story.append(Paragraph(
        "Wenn die Fotobox nach dem Abiball <font color='#d32020'>SO</font> "
        "aussieht,<br/>habt <font color='#d32020'>IHR</font> ein Problem.",
        st["Punch"]))

    doc.build(story)
    print("PDF geschrieben:", OUT, "| Bild:", img_path or "(Platzhalter)")


if __name__ == "__main__":
    build()
