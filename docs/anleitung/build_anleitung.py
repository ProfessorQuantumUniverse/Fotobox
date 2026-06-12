#!/usr/bin/env python3
"""Erzeugt das (überengineerte) Bedienungs-PDF für die Fotobox.

Aufruf:   python build_anleitung.py
Ergebnis: Fotobox-Anleitung.pdf  (im selben Ordner)

Bilder (automatisch eingebunden, wenn vorhanden):
  * docs/anleitung/fotobox.png .............. Disclaimer-Foto (zerstörte Box)
  * docs/screenshots/01-idle.png u. a. ...... UI-Screenshots der Schritte

Design: dunkle Titel- und Disclaimer-Seite, helle Inhaltsseiten mit Kopf-/
Fußzeile, in Handy-Rahmen gesetzte Screenshots, selbst gezeichnete Vektor-
Icons, farbige Hinweis-Boxen, Spickzettel und Troubleshooting.
"""

import os

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
SHOTS = os.path.join(ROOT, "docs", "screenshots")
OUT = os.path.join(HERE, "Fotobox-Anleitung.pdf")

PAGE_W, PAGE_H = A4

# ── Palette ──────────────────────────────────────────────
BLACK = colors.HexColor("#0b0b0d")
INK = colors.HexColor("#16161a")
DIM = colors.HexColor("#6b6b73")
FAINT = colors.HexColor("#9a9aa2")
WHITE = colors.white
RED = colors.HexColor("#e02424")
RED_DK = colors.HexColor("#b01818")
RED_BG = colors.HexColor("#fdecec")
BLUE = colors.HexColor("#2563c9")
BLUE_BG = colors.HexColor("#eaf1fc")
LINE = colors.HexColor("#e2e2e6")
CARD = colors.HexColor("#f6f6f8")
GREEN = colors.HexColor("#1f9d55")


def asset(*parts):
    p = os.path.join(*parts)
    return p if os.path.isfile(p) else None


def disclaimer_img():
    for n in ("fotobox.png", "fotobox.jpg", "fotobox.jpeg", "fotobox.JPG"):
        p = os.path.join(HERE, n)
        if os.path.isfile(p):
            return p
    return None


# ════════════════════════════════════════════════════════
#  Vektor-Icons (auf Canvas gezeichnet)
# ════════════════════════════════════════════════════════
def icon_camera(c, cx, cy, r, col, lw=2.2):
    """Kamera-im-Ring (wie der Idle-Screen)."""
    c.saveState()
    c.setLineWidth(lw)
    c.setStrokeColor(col)
    c.circle(cx, cy, r, stroke=1, fill=0)
    c.setStrokeColor(colors.HexColor("#3a3a40"))
    c.circle(cx, cy, r * 1.16, stroke=1, fill=0)
    # Body
    bw, bh = r * 1.05, r * 0.62
    c.setStrokeColor(col)
    c.roundRect(cx - bw / 2, cy - bh / 2 - r * 0.05, bw, bh, r * 0.12,
                stroke=1, fill=0)
    # Sucher-Höcker
    c.roundRect(cx - r * 0.16, cy + bh / 2 - r * 0.05, r * 0.32, r * 0.12,
                r * 0.04, stroke=1, fill=0)
    # Linse
    c.circle(cx, cy - r * 0.06, r * 0.22, stroke=1, fill=0)
    c.restoreState()


def icon_power(c, cx, cy, r, col, lw=2.2):
    c.saveState()
    c.setLineWidth(lw)
    c.setStrokeColor(col)
    c.setLineCap(1)
    # offener Kreis (Lücke oben)
    c.arc(cx - r, cy - r, cx + r, cy + r, startAng=70, extent=340)
    c.line(cx, cy, cx, cy + r * 1.18)
    c.restoreState()


def icon_warning(c, cx, cy, r, col, lw=2.0):
    c.saveState()
    c.setLineWidth(lw)
    c.setStrokeColor(col)
    c.setFillColor(col)
    c.setLineJoin(1)
    p = c.beginPath()
    p.moveTo(cx, cy + r)
    p.lineTo(cx + r * 1.12, cy - r * 0.82)
    p.lineTo(cx - r * 1.12, cy - r * 0.82)
    p.close()
    c.drawPath(p, stroke=1, fill=0)
    c.setLineWidth(lw + 0.4)
    c.line(cx, cy + r * 0.32, cx, cy - r * 0.28)
    c.circle(cx, cy - r * 0.56, lw * 0.5, stroke=0, fill=1)
    c.restoreState()


def icon_plug(c, cx, cy, r, col, lw=2.0):
    c.saveState()
    c.setLineWidth(lw)
    c.setStrokeColor(col)
    c.setLineCap(1)
    c.line(cx, cy + r, cx, cy + r * 0.25)
    c.roundRect(cx - r * 0.55, cy - r * 0.4, r * 1.1, r * 0.7, r * 0.12,
                stroke=1, fill=0)
    c.line(cx - r * 0.25, cy + r * 0.55, cx - r * 0.25, cy + r * 0.25)
    c.line(cx + r * 0.25, cy + r * 0.55, cx + r * 0.25, cy + r * 0.25)
    c.line(cx, cy - r * 0.4, cx, cy - r)
    c.restoreState()


def icon_finger(c, cx, cy, r, col, lw=2.0):
    """Antippen: Hand-Andeutung + Tap-Ringe."""
    c.saveState()
    c.setLineWidth(lw)
    c.setStrokeColor(col)
    c.setLineCap(1)
    c.circle(cx, cy + r * 0.1, r * 0.5, stroke=1, fill=0)
    c.setLineWidth(lw * 0.7)
    c.arc(cx - r, cy - r * 0.9, cx + r, cy + r * 1.1, startAng=300, extent=70)
    c.arc(cx - r * 1.35, cy - r * 1.25, cx + r * 1.35, cy + r * 1.45,
          startAng=300, extent=70)
    c.restoreState()


def icon_usb(c, cx, cy, r, col, lw=2.0):
    c.saveState()
    c.setLineWidth(lw)
    c.setStrokeColor(col)
    c.setFillColor(col)
    c.setLineCap(1)
    c.line(cx, cy - r, cx, cy + r * 0.7)
    # Pfeilspitze oben
    p = c.beginPath()
    p.moveTo(cx - r * 0.28, cy + r * 0.42)
    p.lineTo(cx, cy + r * 0.8)
    p.lineTo(cx + r * 0.28, cy + r * 0.42)
    c.drawPath(p, stroke=1, fill=0)
    c.circle(cx, cy - r, r * 0.14, stroke=0, fill=1)
    # Abzweige
    c.line(cx, cy + r * 0.05, cx - r * 0.5, cy - r * 0.25)
    c.circle(cx - r * 0.5, cy - r * 0.25, r * 0.14, stroke=0, fill=1)
    c.line(cx, cy - r * 0.2, cx + r * 0.5, cy - r * 0.45)
    c.rect(cx + r * 0.38, cy - r * 0.6, r * 0.24, r * 0.24, stroke=1, fill=0)
    c.restoreState()


def icon_qr(c, cx, cy, r, col, lw=1.6):
    c.saveState()
    c.setStrokeColor(col)
    c.setFillColor(col)
    c.setLineWidth(lw)
    s = r * 0.62
    for dx, dy in ((-1, 1), (1, 1), (-1, -1)):
        x = cx + dx * r * 0.6 - s / 2
        y = cy + dy * r * 0.6 - s / 2
        c.rect(x, y, s, s, stroke=1, fill=0)
        c.rect(x + s * 0.3, y + s * 0.3, s * 0.4, s * 0.4, stroke=0, fill=1)
    # ein paar Pixel
    c.rect(cx + r * 0.35, cy - r * 0.7, s * 0.3, s * 0.3, stroke=0, fill=1)
    c.rect(cx + r * 0.75, cy - r * 0.3, s * 0.3, s * 0.3, stroke=0, fill=1)
    c.restoreState()


def icon_clock(c, cx, cy, r, col, lw=2.0):
    c.saveState()
    c.setLineWidth(lw)
    c.setStrokeColor(col)
    c.setLineCap(1)
    c.circle(cx, cy, r, stroke=1, fill=0)
    c.line(cx, cy, cx, cy + r * 0.55)
    c.line(cx, cy, cx + r * 0.4, cy)
    c.restoreState()


# ════════════════════════════════════════════════════════
#  Flowables
# ════════════════════════════════════════════════════════
class IconF(Flowable):
    """Ein Vektor-Icon als Flowable (für Tabellenzellen)."""

    def __init__(self, fn, size=16, color=INK, lw=2.0):
        super().__init__()
        self.fn, self.size, self.color, self.lw = fn, size, color, lw
        self.width = self.height = size

    def draw(self):
        self.fn(self.canv, self.size / 2, self.size / 2,
                self.size * 0.42, self.color, self.lw)


class Shot(Flowable):
    """Screenshot im Handy-Rahmen (dunkle Lünette + runde Ecken)."""

    def __init__(self, path, width, radius=12, bezel=5,
                 bezelcol=colors.HexColor("#1d1d22"), caption=None):
        super().__init__()
        iw, ih = ImageReader(path).getSize()
        self.path = path
        self.w = width
        self.h = width * ih / iw
        self.r = radius
        self.b = bezel
        self.bezelcol = bezelcol
        self.caption = caption
        self.cap_h = 13 if caption else 0
        self.width = self.w + 2 * bezel
        self.height = self.h + 2 * bezel + self.cap_h

    def draw(self):
        c = self.canv
        b, w, h, r = self.b, self.w, self.h, self.r
        y0 = self.cap_h
        # Schatten
        c.saveState()
        c.setFillColor(colors.HexColor("#00000022"))
        c.roundRect(-b + 1.5, y0 - b - 1.5, w + 2 * b, h + 2 * b, r + b,
                    stroke=0, fill=1)
        c.restoreState()
        # Lünette
        c.setFillColor(self.bezelcol)
        c.roundRect(-b, y0 - b, w + 2 * b, h + 2 * b, r + b, stroke=0, fill=1)
        # Bild rund beschnitten
        c.saveState()
        p = c.beginPath()
        p.roundRect(0, y0, w, h, r)
        c.clipPath(p, stroke=0, fill=0)
        c.drawImage(self.path, 0, y0, w, h, preserveAspectRatio=False,
                    mask=None)
        c.restoreState()
        # feiner Rand
        c.setStrokeColor(colors.HexColor("#33333a"))
        c.setLineWidth(0.6)
        c.roundRect(0, y0, w, h, r, stroke=1, fill=0)
        if self.caption:
            c.setFillColor(DIM)
            c.setFont("Helvetica", 8)
            c.drawCentredString(w / 2, 2, self.caption)


class CornerTapArt(Flowable):
    """Illustration: Handy mit hervorgehobener oberer rechter Ecke + 5x."""

    def __init__(self, width=5.6 * cm):
        super().__init__()
        self.width = width
        self.height = width * 1.5

    def draw(self):
        c = self.canv
        w, h = self.width, self.height
        # Telefon
        c.setFillColor(BLACK)
        c.roundRect(0, 0, w, h, 12, stroke=0, fill=1)
        c.setStrokeColor(colors.HexColor("#2a2a30"))
        c.setLineWidth(1)
        c.roundRect(0, 0, w, h, 12, stroke=1, fill=0)
        # Mini-Kamera-Icon mittig (Idle-Andeutung)
        icon_camera(c, w / 2, h * 0.52, w * 0.16, colors.HexColor("#cfcfd6"),
                    lw=1.4)
        c.setFillColor(colors.HexColor("#cfcfd6"))
        c.setFont("Helvetica-Bold", 9)
        c.drawCentredString(w / 2, h * 0.34, "FOTOBOX")
        # Eck-Zone (oben rechts, ein Drittel)
        zw, zh = w / 3, h / 3
        c.saveState()
        c.setFillColor(colors.HexColor("#e0242422"))
        c.setStrokeColor(RED)
        c.setDash(3, 2)
        c.setLineWidth(1.2)
        c.rect(w - zw, h - zh, zw, zh, stroke=1, fill=1)
        c.restoreState()
        # Tap-Ringe in der Ecke
        tx, ty = w - zw * 0.45, h - zh * 0.45
        c.setStrokeColor(RED)
        for rr, lw in ((6, 2.2), (11, 1.4), (16, 0.9)):
            c.setLineWidth(lw)
            c.circle(tx, ty, rr, stroke=1, fill=0)
        c.setFillColor(RED)
        c.circle(tx, ty, 2.4, stroke=0, fill=1)
        # "5×"-Badge
        c.setFillColor(RED)
        c.circle(w - zw - 6, h - zh - 6, 13, stroke=0, fill=1)
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 12)
        c.drawCentredString(w - zw - 6, h - zh - 10, "5×")


class Rule(Flowable):
    def __init__(self, width, color=LINE, thick=0.7):
        super().__init__()
        self.width, self.color, self.thick = width, color, thick
        self.height = thick

    def draw(self):
        self.canv.setStrokeColor(self.color)
        self.canv.setLineWidth(self.thick)
        self.canv.line(0, 0, self.width, 0)


# ════════════════════════════════════════════════════════
#  Styles
# ════════════════════════════════════════════════════════
def make_styles():
    s = getSampleStyleSheet()
    add = s.add
    add(ParagraphStyle("Intro", parent=s["Normal"], fontSize=10.5, leading=15,
                       textColor=INK, alignment=TA_LEFT, spaceAfter=4))
    add(ParagraphStyle("Lead", parent=s["Normal"], fontSize=11.5, leading=16,
                       textColor=INK, spaceAfter=10))
    add(ParagraphStyle("Sec", parent=s["Normal"], fontName="Helvetica-Bold",
                       fontSize=15, leading=18, textColor=WHITE))
    add(ParagraphStyle("SecNo", parent=s["Normal"], fontName="Helvetica-Bold",
                       fontSize=15, leading=18, textColor=RED))
    add(ParagraphStyle("StepN", parent=s["Normal"], fontName="Helvetica-Bold",
                       fontSize=13, leading=15, textColor=WHITE,
                       alignment=TA_CENTER))
    add(ParagraphStyle("StepH", parent=s["Normal"], fontName="Helvetica-Bold",
                       fontSize=11.5, leading=14, textColor=INK, spaceAfter=2))
    add(ParagraphStyle("StepB", parent=s["Normal"], fontSize=10, leading=14,
                       textColor=colors.HexColor("#33333a")))
    add(ParagraphStyle("Warn", parent=s["Normal"], fontSize=10.5, leading=15,
                       textColor=INK))
    add(ParagraphStyle("WarnH", parent=s["Normal"], fontName="Helvetica-Bold",
                       fontSize=11, leading=14, textColor=RED_DK, spaceAfter=2))
    add(ParagraphStyle("InfoH", parent=s["Normal"], fontName="Helvetica-Bold",
                       fontSize=11, leading=14, textColor=BLUE, spaceAfter=2))
    add(ParagraphStyle("Cheat", parent=s["Normal"], fontSize=9.5, leading=14,
                       textColor=INK))
    add(ParagraphStyle("CheatH", parent=s["Normal"], fontName="Helvetica-Bold",
                       fontSize=11, leading=14, textColor=INK, spaceAfter=4))
    add(ParagraphStyle("TblH", parent=s["Normal"], fontName="Helvetica-Bold",
                       fontSize=9.5, leading=12, textColor=WHITE))
    add(ParagraphStyle("TblL", parent=s["Normal"], fontName="Helvetica-Bold",
                       fontSize=9.5, leading=12, textColor=INK))
    add(ParagraphStyle("TblR", parent=s["Normal"], fontSize=9.5, leading=12,
                       textColor=colors.HexColor("#33333a")))
    add(ParagraphStyle("DiscCap", parent=s["Normal"], fontSize=9, leading=12,
                       textColor=FAINT, alignment=TA_CENTER, spaceBefore=8))
    add(ParagraphStyle("Punch", parent=s["Normal"], fontName="Helvetica-Bold",
                       fontSize=21, leading=27, textColor=WHITE,
                       alignment=TA_CENTER, spaceBefore=14))
    return s


# ════════════════════════════════════════════════════════
#  Bausteine
# ════════════════════════════════════════════════════════
def section_header(no, title, icon_fn, st, width):
    """Dunkler Balken: Nummer (rot) · Icon · Titel."""
    num = Paragraph(str(no), st["SecNo"])
    ic = IconF(icon_fn, size=20, color=WHITE, lw=1.8)
    ttl = Paragraph(title, st["Sec"])
    t = Table([[num, ic, ttl]], colWidths=[1.0 * cm, 0.9 * cm, width - 1.9 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), INK),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (0, 0), 12),
        ("LEFTPADDING", (1, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LINEAFTER", (0, 0), (0, 0), 1, colors.HexColor("#3a3a42")),
        ("RIGHTPADDING", (0, 0), (0, 0), 8),
    ]))
    return t


def step(no, head, body, st, width, icon_fn=None):
    """Schritt-Karte: nummeriertes Badge + Text (+ optionales Icon)."""
    badge = Table([[Paragraph(str(no), st["StepN"])]], colWidths=[0.8 * cm],
                  rowHeights=[0.8 * cm])
    badge.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), RED),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROUNDEDCORNERS", [4, 4, 4, 4]),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    txt = [Paragraph(head, st["StepH"])]
    if body:
        txt.append(Paragraph(body, st["StepB"]))
    cells = [badge, txt]
    widths = [1.1 * cm, width - 1.1 * cm]
    if icon_fn is not None:
        cells.append(IconF(icon_fn, size=22, color=DIM, lw=1.8))
        widths = [1.1 * cm, width - 2.2 * cm, 1.1 * cm]
    t = Table([cells], colWidths=widths)
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (0, 0), "TOP"),
        ("VALIGN", (1, 0), (1, 0), "MIDDLE"),
        ("VALIGN", (-1, 0), (-1, 0), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def callout(icon_fn, head, body, st, width, kind="warn"):
    if kind == "warn":
        bg, bar, hs = RED_BG, RED, st["WarnH"]
    else:
        bg, bar, hs = BLUE_BG, BLUE, st["InfoH"]
    ic = IconF(icon_fn, size=22, color=bar, lw=2.0)
    inner = [Paragraph(head, hs), Paragraph(body, st["Warn"])]
    t = Table([[ic, inner]], colWidths=[1.1 * cm, width - 1.1 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("LINEBEFORE", (0, 0), (0, -1), 3, bar),
        ("VALIGN", (0, 0), (0, 0), "TOP"),
        ("VALIGN", (1, 0), (1, 0), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (0, 0), 12),
        ("LEFTPADDING", (1, 0), (1, 0), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    return t


# ════════════════════════════════════════════════════════
#  Seiten-Dekoration (Hintergründe, Kopf/Fuß)
# ════════════════════════════════════════════════════════
def on_cover(c, doc):
    c.saveState()
    c.setFillColor(BLACK)
    c.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)
    cx = PAGE_W / 2
    # Hero-Kamera
    icon_camera(c, cx, PAGE_H - 250, 52, WHITE, lw=2.6)
    # Wordmark
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 46)
    c.drawCentredString(cx, PAGE_H - 360, "F O T O B O X")
    c.setFillColor(FAINT)
    c.setFont("Helvetica", 13)
    c.drawCentredString(cx, PAGE_H - 392, "B E D I E N U N G S A N L E I T U N G")
    # Trennlinie
    c.setStrokeColor(RED)
    c.setLineWidth(2)
    c.line(cx - 40, PAGE_H - 418, cx + 40, PAGE_H - 418)
    # Untertitel-Claim
    c.setFillColor(colors.HexColor("#c9c9d2"))
    c.setFont("Helvetica", 12)
    c.drawCentredString(cx, PAGE_H - 452,
                        "Aufbauen · Fotos schießen · sauber ausschalten")
    # Mini-Schritt-Reihe unten
    items = [("1", "Einstecken"), ("2", "OK an Kamera"),
             ("3", "Loslegen"), ("4", "Herunterfahren")]
    n = len(items)
    gap = 118
    startx = cx - gap * (n - 1) / 2
    for i, (num, lab) in enumerate(items):
        x = startx + i * gap
        c.setStrokeColor(RED)
        c.setLineWidth(1.4)
        c.circle(x, 250, 16, stroke=1, fill=0)
        c.setFillColor(RED)
        c.setFont("Helvetica-Bold", 13)
        c.drawCentredString(x, 245, num)
        c.setFillColor(colors.HexColor("#c9c9d2"))
        c.setFont("Helvetica", 8.5)
        c.drawCentredString(x, 228, lab)
        if i < n - 1:
            c.setStrokeColor(colors.HexColor("#39393f"))
            c.setLineWidth(1)
            c.line(x + 22, 250, x + gap - 22, 250)
    # Fuß
    c.setFillColor(colors.HexColor("#55555c"))
    c.setFont("Helvetica", 9)
    c.drawCentredString(cx, 70, "Abiball-Edition  ·  bitte vor der Party lesen")
    c.restoreState()


def on_content(c, doc):
    c.saveState()
    # Kopf
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 11)
    icon_camera(c, 52, PAGE_H - 38, 8, INK, lw=1.1)
    c.drawString(66, PAGE_H - 42, "FOTOBOX")
    c.setFillColor(DIM)
    c.setFont("Helvetica", 9)
    c.drawRightString(PAGE_W - 50, PAGE_H - 42, "Bedienungsanleitung")
    c.setStrokeColor(LINE)
    c.setLineWidth(0.8)
    c.line(50, PAGE_H - 52, PAGE_W - 50, PAGE_H - 52)
    # linker Akzentstreifen
    c.setStrokeColor(RED)
    c.setLineWidth(3)
    c.line(50, PAGE_H - 60, 50, 60)
    # Fuß
    c.setStrokeColor(LINE)
    c.setLineWidth(0.8)
    c.line(50, 50, PAGE_W - 50, 50)
    c.setFillColor(DIM)
    c.setFont("Helvetica", 8)
    c.drawString(50, 38, "Aufbau · Bedienung · Ausschalten")
    c.setFillColor(RED)
    c.setFont("Helvetica-Bold", 8)
    c.drawRightString(PAGE_W - 50, 38, "NIEMALS den Stecker ziehen!")
    c.setFillColor(DIM)
    c.setFont("Helvetica", 8.5)
    c.drawCentredString(PAGE_W / 2, 38, "– %d –" % c.getPageNumber())
    c.restoreState()


def on_disclaimer(c, doc):
    c.saveState()
    c.setFillColor(BLACK)
    c.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)
    # schwaches Power-Watermark
    icon_power(c, PAGE_W - 70, PAGE_H - 70, 16, colors.HexColor("#2a2a30"),
               lw=2.2)
    c.setStrokeColor(colors.HexColor("#1d1d22"))
    c.setLineWidth(1)
    c.line(50, 60, PAGE_W - 50, 60)
    c.setFillColor(colors.HexColor("#55555c"))
    c.setFont("Helvetica", 8.5)
    c.drawString(50, 46, "FOTOBOX · Bedienungsanleitung")
    c.drawRightString(PAGE_W - 50, 46, "Disclaimer")
    c.restoreState()


# ════════════════════════════════════════════════════════
#  Dokument
# ════════════════════════════════════════════════════════
def build():
    st = make_styles()
    CW = PAGE_W - 100  # nutzbare Breite bei 50pt-Rändern

    doc = BaseDocTemplate(
        OUT, pagesize=A4,
        leftMargin=50, rightMargin=50, topMargin=64, bottomMargin=62,
        title="Fotobox – Bedienungsanleitung", author="Fotobox",
    )
    content_frame = Frame(64, 60, PAGE_W - 64 - 50, PAGE_H - 64 - 60,
                          id="content", leftPadding=0, rightPadding=0,
                          topPadding=0, bottomPadding=0)
    disc_frame = Frame(50, 90, PAGE_W - 100, PAGE_H - 200, id="disc",
                       leftPadding=0, rightPadding=0)
    full = Frame(0, 0, PAGE_W, PAGE_H, id="full")
    doc.addPageTemplates([
        PageTemplate(id="cover", frames=[full], onPage=on_cover),
        PageTemplate(id="content", frames=[content_frame], onPage=on_content),
        PageTemplate(id="disclaimer", frames=[disc_frame], onPage=on_disclaimer),
    ])

    CWc = PAGE_W - 64 - 50  # Inhaltsrahmen-Breite
    story = []

    # ── Cover (leer; alles via on_cover) ────────────────
    story.append(Spacer(1, 2))
    story.append(NextPageTemplate("content"))
    story.append(PageBreak())

    # ── Intro / Auf einen Blick ─────────────────────────
    story.append(Paragraph(
        "Diese Anleitung bringt dich in <b>vier Schritten</b> durch einen "
        "Fotobox-Abend – vom Einstecken bis zum sicheren Ausschalten. "
        "Die wichtigste Regel steht gleich unten in Rot.", st["Lead"]))
    story.append(callout(
        icon_warning,
        "Die eine Regel, die zählt",
        "Die Box wird <b>immer über das Menü heruntergefahren</b> "
        "(Abschnitt 3) – <b>niemals</b> einfach den Stecker ziehen. "
        "Sonst kann die Speicherkarte kaputtgehen.",
        st, CWc, kind="warn"))
    story.append(Spacer(1, 14))

    # ── Abschnitt 1 ─────────────────────────────────────
    story.append(section_header(1, "Aufbau &amp; Einschalten", icon_plug, st, CWc))
    story.append(Spacer(1, 8))

    idle = asset(SHOTS, "01-idle.png")
    left_w = CWc - 5.4 * cm if idle else CWc
    steps1 = [
        step(1, "Beide Stecker einstecken",
             "Strom für den Mini-Computer und für Kamera/Beleuchtung.",
             st, left_w, icon_fn=icon_plug),
        callout(icon_warning, "Achtung: Spannung prüfen",
                "Vorher sicherstellen, dass <b>keine falsche oder fremde "
                "Spannung</b> anliegt. Falsche Spannung zerstört die "
                "Elektronik <b>sofort und irreparabel</b>.",
                st, left_w, kind="warn"),
        step(2, "An der Kamera OK drücken",
             "Hinten den <b>Vorhang öffnen</b> und auf dem "
             "<b>Kamera-Touchscreen auf OK</b> tippen (Datum/Uhrzeit).",
             st, left_w, icon_fn=icon_camera),
        step(3, "Starten lassen (1–2 Minuten)",
             "Das System bootet. Kurz erscheint ein <b>weißer Bildschirm</b> "
             "– das ist normal: rund <b>30 Sekunden warten</b>.",
             st, left_w, icon_fn=icon_clock),
        step(4, "Interface erscheint",
             "Sobald der Kamera-Kreis (siehe rechts) zu sehen ist, ist die "
             "Box <b>startklar</b>.",
             st, left_w, icon_fn=icon_camera),
    ]
    if idle:
        shot = Shot(idle, width=4.8 * cm, caption="Startbildschirm")
        steps_stack = Table([[s] for s in steps1], colWidths=[left_w])
        steps_stack.setStyle(TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 1),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ]))
        row = Table([[steps_stack, shot]],
                    colWidths=[left_w, 5.4 * cm])
        row.setStyle(TableStyle([
            ("VALIGN", (0, 0), (0, 0), "TOP"),
            ("VALIGN", (1, 0), (1, 0), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(row)
    else:
        story.extend(steps1)
    story.append(Spacer(1, 16))

    # ── Abschnitt 2 ─────────────────────────────────────
    story.append(section_header(2, "Fotos machen", icon_camera, st, CWc))
    story.append(Spacer(1, 8))
    story.append(step(
        1, "Auslösen",
        "Auf den <b>Startbildschirm tippen</b> – oder den großen "
        "<b>Auslöse-Knopf</b> drücken.", st, CWc, icon_fn=icon_finger))
    story.append(step(
        2, "Countdown &amp; Foto",
        "Es läuft ein Countdown, dann wird das Foto aufgenommen und in der "
        "Vorschau gezeigt: <b>Nochmal</b> oder <b>Fertig</b>.",
        st, CWc, icon_fn=icon_clock))
    story.append(step(
        3, "Teilen per QR-Code",
        "Die Box baut ein <b>eigenes WLAN</b> auf: <b>erster QR-Code</b> = "
        "mit WLAN verbinden, <b>zweiter QR-Code</b> = Download-Seite.",
        st, CWc, icon_fn=icon_qr))
    story.append(Spacer(1, 8))

    # Screenshot-Flussband
    flow = [(asset(SHOTS, "02-countdown.png"), "Countdown"),
            (asset(SHOTS, "03-review.png"), "Vorschau"),
            (asset(SHOTS, "04-qr-hotspot.png"), "QR-Code")]
    flow = [(p, c) for p, c in flow if p]
    if flow:
        cells = [Shot(p, width=4.2 * cm, caption=c) for p, c in flow]
        # Pfeile zwischen den Shots
        row_cells = []
        for i, cell in enumerate(cells):
            row_cells.append(cell)
            if i < len(cells) - 1:
                row_cells.append(IconF(
                    lambda c, x, y, r, col, lw: (
                        c.setStrokeColor(col), c.setLineWidth(lw),
                        c.setLineCap(1),
                        c.line(x - r, y, x + r, y),
                        c.line(x + r * 0.3, y + r * 0.5, x + r, y),
                        c.line(x + r * 0.3, y - r * 0.5, x + r, y)),
                    size=18, color=FAINT, lw=1.6))
        nshot = len(cells)
        cw = []
        for i in range(len(row_cells)):
            cw.append(4.6 * cm if i % 2 == 0 else 0.7 * cm)
        strip = Table([row_cells], colWidths=cw)
        strip.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(strip)
    story.append(Spacer(1, 8))
    story.append(callout(
        icon_usb, "Tipp: USB-Stick = automatisches Backup",
        "Steckt ein <b>USB-Stick</b> in der Box, werden alle Fotos "
        "automatisch zusätzlich darauf gesichert.",
        st, CWc, kind="info"))
    story.append(Spacer(1, 16))

    # ── Abschnitt 3 ─────────────────────────────────────
    story.append(KeepTogether(section_header(3, "Ausschalten – nach der Party",
                                              icon_power, st, CWc)))
    story.append(Spacer(1, 8))
    story.append(callout(
        icon_warning, "Niemals den Stecker ziehen",
        "Hartes Ausschalten kann die Speicherkarte und das System "
        "beschädigen – im schlimmsten Fall startet die Box danach "
        "<b>nicht mehr</b>. Immer über das Menü herunterfahren.",
        st, CWc, kind="warn"))
    story.append(Spacer(1, 8))

    art = CornerTapArt(width=5.0 * cm)
    s_w = CWc - 5.6 * cm
    shutdown_steps = Table([
        [step(1, "Obere rechte Ecke",
              "Auf dem Startbildschirm <b>5× schnell in die obere rechte "
              "Ecke</b> tippen (siehe rechts).", st, s_w, icon_fn=icon_finger)],
        [step(2, "Herunterfahren wählen",
              "Im Menü auf <b>Herunterfahren</b> tippen. (Alternativ "
              "<b>Neustart</b>.)", st, s_w, icon_fn=icon_power)],
        [step(3, "Warten, dann Stecker",
              "Warten, bis der <b>Bildschirm komplett schwarz</b> ist. "
              "<b>Erst dann</b> die Stecker ziehen.", st, s_w, icon_fn=icon_plug)],
    ], colWidths=[s_w])
    shutdown_steps.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    row3 = Table([[shutdown_steps, art]], colWidths=[s_w, 5.6 * cm])
    row3.setStyle(TableStyle([
        ("VALIGN", (0, 0), (0, 0), "MIDDLE"),
        ("VALIGN", (1, 0), (1, 0), "MIDDLE"),
        ("ALIGN", (1, 0), (1, 0), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(row3)
    story.append(Spacer(1, 18))

    # ── Spickzettel + Troubleshooting nebeneinander ─────
    cheat = [
        Paragraph("Spickzettel", st["CheatH"]),
        Paragraph("<b>Foto:</b> Bildschirm tippen / Knopf", st["Cheat"]),
        Paragraph("<b>Nochmal/Fertig:</b> nach der Aufnahme", st["Cheat"]),
        Paragraph("<b>Teilen:</b> 2 QR-Codes scannen", st["Cheat"]),
        Paragraph("<b>Aus:</b> 5× oben rechts → Herunterfahren", st["Cheat"]),
        Paragraph("<b>Backup:</b> USB-Stick einstecken", st["Cheat"]),
    ]
    cheat_tbl = Table([[c] for c in cheat], colWidths=[CWc / 2 - 0.3 * cm])
    cheat_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CARD),
        ("BOX", (0, 0), (-1, -1), 0.7, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (0, 0), 12), ("BOTTOMPADDING", (-1, -1), (-1, -1), 12),
        ("TOPPADDING", (0, 1), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -2), 3),
    ]))

    tb_head = [Paragraph("Problem", st["TblH"]), Paragraph("Lösung", st["TblH"])]
    tb_rows = [
        ("Weißer Bildschirm", "Normal beim Start – 30 s warten."),
        ("Tippen reagiert nicht", "Kurz warten, bis das Interface ganz da ist."),
        ("Kein Foto", "Vorhang offen? Kamera an &amp; OK bestätigt?"),
        ("QR/WLAN klappt nicht", "Näher rangehen, WLAN neu wählen."),
    ]
    data = [tb_head] + [[Paragraph(a, st["TblL"]), Paragraph(b, st["TblR"])]
                        for a, b in tb_rows]
    tb = Table(data, colWidths=[CWc / 2 * 0.42, CWc / 2 * 0.58 - 0.6 * cm])
    tb.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), INK),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, CARD]),
        ("BOX", (0, 0), (-1, -1), 0.7, LINE),
        ("INNERGRID", (0, 1), (-1, -1), 0.5, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))

    title_row = Table(
        [[Paragraph("Troubleshooting", st["CheatH"])]],
        colWidths=[CWc / 2 - 0.3 * cm])
    title_row.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 0)]))
    right_col = Table([[title_row], [tb]], colWidths=[CWc / 2 - 0.3 * cm])
    right_col.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("VALIGN", (0, 0), (-1, -1), "TOP")]))

    two = Table([[cheat_tbl, right_col]],
                colWidths=[CWc / 2 - 0.3 * cm + 0.6 * cm, CWc / 2 - 0.3 * cm])
    two.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (0, 0), 0), ("RIGHTPADDING", (0, 0), (0, 0), 12),
        ("LEFTPADDING", (1, 0), (1, 0), 0), ("RIGHTPADDING", (1, 0), (1, 0), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(KeepTogether(two))
    story.append(Spacer(1, 22))

    # ── Abschluss-Banner ────────────────────────────────
    close_ic = IconF(icon_power, size=26, color=WHITE, lw=2.2)
    close_txt = [
        Paragraph(
            "Zum Schluss des Abends",
            ParagraphStyle("ch", fontName="Helvetica-Bold", fontSize=12,
                           leading=15, textColor=WHITE, spaceAfter=3)),
        Paragraph(
            "<b>5× oben rechts</b> &nbsp;→&nbsp; <b>Herunterfahren</b> "
            "&nbsp;→&nbsp; warten, bis schwarz &nbsp;→&nbsp; <b>erst dann</b> "
            "die Stecker ziehen. Danke!",
            ParagraphStyle("cb", fontSize=10.5, leading=15,
                           textColor=colors.HexColor("#d8d8de"))),
    ]
    banner = Table([[close_ic, close_txt]], colWidths=[1.4 * cm, CWc - 1.4 * cm])
    banner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), INK),
        ("LINEBEFORE", (0, 0), (0, -1), 3, RED),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (0, 0), 14),
        ("LEFTPADDING", (1, 0), (1, 0), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 14),
        ("TOPPADDING", (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
    ]))
    story.append(banner)

    # ── Disclaimer ──────────────────────────────────────
    story.append(NextPageTemplate("disclaimer"))
    story.append(PageBreak())
    img = disclaimer_img()
    if img:
        story.append(Spacer(1, 6))
        story.append(Shot(img, width=9.2 * cm, radius=10, bezel=6,
                          bezelcol=colors.HexColor("#15151a")))
        story[-1].hAlign = "CENTER"
    story.append(Paragraph("( KI-bearbeitetes Bild – keine echte Aufnahme. )",
                           st["DiscCap"]))
    story.append(Paragraph(
        "Wenn die Fotobox nach dem Abiball "
        "<font color='#e02424'>SO</font> aussieht,<br/>"
        "habt <font color='#e02424'>IHR</font> ein Problem.", st["Punch"]))

    # zentrierte Disclaimer-Inhalte
    for fl in story:
        if isinstance(fl, Shot):
            fl.hAlign = "CENTER"

    doc.build(story)
    print("PDF geschrieben:", OUT)
    print("  Disclaimer-Bild:", img or "(fehlt – Platzhalter)")


if __name__ == "__main__":
    build()
