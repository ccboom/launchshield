from __future__ import annotations

import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile


EMU_PER_INCH = 914400
LANG = "en-US"
TITLE_FONT = "Trebuchet MS"
BODY_FONT = "Calibri"

SLIDE_W = 10.0
SLIDE_H = 5.625

ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT / "docs" / "hackathon"
OUTPUT_PATH = DOCS_DIR / "LaunchShield-Swarm-Slide-Presentation.pptx"
TEMPLATE_PATH = Path(
    r"C:\Program Files\Microsoft Office\root\Templates\2052\WidescreenPresentation.potx"
)

DARK = "081B29"
DARK_ALT = "12314A"
LIGHT_BG = "F4F7FB"
WHITE = "FFFFFF"
TEXT = "102A43"
MUTED = "627D98"
ACCENT = "19C2A0"
ACCENT_DARK = "0E5E57"
ACCENT_SOFT = "E3FAF5"
BLUE = "2D6CDF"
BLUE_SOFT = "E8F0FE"
GOLD_SOFT = "FFF4D6"
RED = "D64550"
RED_SOFT = "FCE8EA"
GREEN = "0F9D58"
GREEN_SOFT = "E4F6EC"
LINE = "D9E2EC"


def emu(inches: float) -> int:
    return int(round(inches * EMU_PER_INCH))


def esc(value: str) -> str:
    return escape(value)


def para(
    text: str,
    size: int,
    color: str,
    *,
    bold: bool = False,
    font: str = BODY_FONT,
    align: str = "l",
) -> dict[str, object]:
    return {
        "text": text,
        "size": size,
        "color": color,
        "bold": bold,
        "font": font,
        "align": align,
    }


class SlideBuilder:
    def __init__(self) -> None:
        self.shape_id = 2
        self.elements: list[str] = []

    def _next_id(self) -> int:
        current = self.shape_id
        self.shape_id += 1
        return current

    def _paragraphs_xml(self, paragraphs: list[dict[str, object]]) -> str:
        built: list[str] = []
        for paragraph in paragraphs:
            bold_attr = ' b="1"' if paragraph["bold"] else ""
            size = paragraph["size"]
            color = paragraph["color"]
            font = paragraph["font"]
            align = paragraph["align"]
            text = esc(str(paragraph["text"]))
            built.append(
                f"<a:p><a:pPr marL=\"0\" indent=\"0\" algn=\"{align}\"><a:buNone/></a:pPr>"
                f"<a:r><a:rPr lang=\"{LANG}\" sz=\"{size}\"{bold_attr}>"
                f"<a:solidFill><a:srgbClr val=\"{color}\"/></a:solidFill>"
                f"<a:latin typeface=\"{font}\"/><a:ea typeface=\"{font}\"/><a:cs typeface=\"{font}\"/>"
                f"</a:rPr><a:t>{text}</a:t></a:r>"
                f"<a:endParaRPr lang=\"{LANG}\" sz=\"{size}\">"
                f"<a:solidFill><a:srgbClr val=\"{color}\"/></a:solidFill></a:endParaRPr></a:p>"
            )
        return "".join(built)

    def box(
        self,
        *,
        x: float,
        y: float,
        w: float,
        h: float,
        fill: str | None = None,
        line: str | None = None,
        radius: bool = False,
        paragraphs: list[dict[str, object]] | None = None,
        margin: float = 0.12,
        anchor: str = "t",
    ) -> None:
        shape_id = self._next_id()
        geometry = "roundRect" if radius else "rect"
        fill_xml = (
            f"<a:solidFill><a:srgbClr val=\"{fill}\"/></a:solidFill>" if fill else "<a:noFill/>"
        )
        line_xml = (
            f"<a:ln w=\"12700\"><a:solidFill><a:srgbClr val=\"{line}\"/></a:solidFill></a:ln>"
            if line
            else "<a:ln><a:noFill/></a:ln>"
        )
        body = (
            f"<a:bodyPr wrap=\"square\" lIns=\"{emu(margin)}\" tIns=\"{emu(margin)}\" "
            f"rIns=\"{emu(margin)}\" bIns=\"{emu(margin)}\" anchor=\"{anchor}\"/>"
        )
        paras = self._paragraphs_xml(paragraphs or [para("", 1400, TEXT)])
        self.elements.append(
            f"<p:sp><p:nvSpPr><p:cNvPr id=\"{shape_id}\" name=\"Shape {shape_id}\"/>"
            "<p:cNvSpPr/><p:nvPr/></p:nvSpPr>"
            f"<p:spPr><a:xfrm><a:off x=\"{emu(x)}\" y=\"{emu(y)}\"/>"
            f"<a:ext cx=\"{emu(w)}\" cy=\"{emu(h)}\"/></a:xfrm>"
            f"<a:prstGeom prst=\"{geometry}\"><a:avLst/></a:prstGeom>{fill_xml}{line_xml}</p:spPr>"
            f"<p:txBody>{body}<a:lstStyle/>{paras}</p:txBody></p:sp>"
        )

    def text(
        self,
        *,
        x: float,
        y: float,
        w: float,
        h: float,
        paragraphs: list[dict[str, object]],
        margin: float = 0.0,
        anchor: str = "t",
    ) -> None:
        self.box(
            x=x,
            y=y,
            w=w,
            h=h,
            paragraphs=paragraphs,
            margin=margin,
            anchor=anchor,
        )

    def chip(self, *, x: float, y: float, w: float, h: float, label: str, fill: str, color: str) -> None:
        self.box(
            x=x,
            y=y,
            w=w,
            h=h,
            fill=fill,
            radius=True,
            paragraphs=[para(label, 1200, color, bold=True, align="ctr")],
            margin=0.05,
            anchor="ctr",
        )

    def xml(self) -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
            'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
            "<p:cSld><p:spTree>"
            '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
            "<p:grpSpPr><a:xfrm><a:off x=\"0\" y=\"0\"/><a:ext cx=\"0\" cy=\"0\"/>"
            "<a:chOff x=\"0\" y=\"0\"/><a:chExt cx=\"0\" cy=\"0\"/></a:xfrm></p:grpSpPr>"
            + "".join(self.elements)
            + "</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>"
        )


def slide_rel_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" '
        'Target="../slideLayouts/slideLayout7.xml"/>'
        "</Relationships>"
    )


def slide_1() -> str:
    s = SlideBuilder()
    s.box(x=0, y=0, w=SLIDE_W, h=SLIDE_H, fill=DARK)
    s.chip(x=0.6, y=0.45, w=2.6, h=0.34, label="AI security micropayments on Arc", fill=ACCENT, color=DARK)
    s.text(x=0.6, y=0.98, w=5.8, h=0.7, paragraphs=[para("LaunchShield Swarm", 3000, WHITE, bold=True, font=TITLE_FONT)])
    s.text(
        x=0.6,
        y=1.8,
        w=5.9,
        h=1.0,
        paragraphs=[
            para("AI security is already a swarm of tiny actions.", 2000, WHITE, bold=True, font=TITLE_FONT),
            para("Billing and proving each action is the missing layer.", 2000, ACCENT, bold=True, font=TITLE_FONT),
        ],
    )
    s.text(
        x=0.6,
        y=3.0,
        w=5.8,
        h=0.9,
        paragraphs=[
            para("One audit becomes dozens of atomic security tool calls.", 1500, WHITE, bold=True),
            para("LaunchShield turns those calls into a live execution feed, a live billing feed, and a verifiable evidence trail.", 1300, "DCE7F3"),
        ],
    )
    s.box(
        x=6.55,
        y=0.98,
        w=2.85,
        h=2.25,
        fill=DARK_ALT,
        line=ACCENT,
        radius=True,
        paragraphs=[
            para("63", 2800, ACCENT, bold=True, font=TITLE_FONT, align="ctr"),
            para("paid invocations", 1300, WHITE, bold=True, align="ctr"),
            para("in the preset stress run", 1100, "A9BCD0", align="ctr"),
            para("$0.001 - $0.008 per call", 1200, "FFF4D6", bold=True, align="ctr"),
        ],
        anchor="ctr",
    )
    s.box(
        x=6.55,
        y=3.45,
        w=2.85,
        h=1.05,
        fill="0E2336",
        radius=True,
        paragraphs=[
            para("Core proof", 1100, ACCENT, bold=True),
            para("billing row + result + settlement reference", 1200, WHITE),
        ],
    )
    chips = [
        (0.6, 1.3, "Repo scans"),
        (2.1, 1.45, "Dependency checks"),
        (3.78, 1.55, "Browser probes"),
        (5.58, 1.6, "Deep LLM review"),
        (7.48, 1.45, "Fix suggestions"),
    ]
    for x, w, label in chips:
        s.chip(x=x, y=4.55, w=w, h=0.38, label=label, fill=ACCENT_SOFT, color=ACCENT_DARK)
    s.text(x=0.62, y=5.08, w=8.7, h=0.22, paragraphs=[para("Red Snail hackathon submission deck", 1000, "A9BCD0")])
    return s.xml()


def slide_2() -> str:
    s = SlideBuilder()
    s.box(x=0, y=0, w=SLIDE_W, h=SLIDE_H, fill=LIGHT_BG)
    s.text(x=0.55, y=0.42, w=8.9, h=0.48, paragraphs=[para("The execution model already changed. The payment model did not.", 2200, TEXT, bold=True, font=TITLE_FONT)])
    s.text(x=0.55, y=0.92, w=8.6, h=0.36, paragraphs=[para("AI security work creates many high-signal actions with very low value per call.", 1350, MUTED)])
    s.box(
        x=0.55,
        y=1.45,
        w=3.05,
        h=2.95,
        fill=DARK,
        radius=True,
        paragraphs=[
            para("1 audit", 1500, "B6C8D8", align="ctr"),
            para("40-60", 2800, ACCENT, bold=True, font=TITLE_FONT, align="ctr"),
            para("atomic tool calls", 1600, WHITE, bold=True, align="ctr"),
            para("Each call matters. Each call is too cheap for legacy settlement.", 1200, "DCE7F3", align="ctr"),
        ],
        anchor="ctr",
    )
    cards = [
        ("Sub-cent value", "Many tasks cost less than one cent."),
        ("High trust requirement", "Security buyers want proof and provenance."),
        ("Bad legacy fit", "Card rails and high-gas chains crush margin."),
    ]
    y = 1.45
    for title, body in cards:
        s.box(x=4.0, y=y, w=5.4, h=0.82, fill=WHITE, line=LINE, radius=True, paragraphs=[para(title, 1350, TEXT, bold=True), para(body, 1150, MUTED)])
        y += 0.95
    s.box(x=0.55, y=4.6, w=8.85, h=0.5, fill=ACCENT_SOFT, radius=True, paragraphs=[para("Flat pricing hides execution quality, hides cost structure, and hides proof of delivery.", 1180, ACCENT_DARK, bold=True, align="ctr")], margin=0.08, anchor="ctr")
    return s.xml()


def slide_3() -> str:
    s = SlideBuilder()
    s.box(x=0, y=0, w=SLIDE_W, h=SLIDE_H, fill=LIGHT_BG)
    s.text(x=0.55, y=0.42, w=8.9, h=0.48, paragraphs=[para("Micropayments turn AI work from a black box into a priced workflow.", 2150, TEXT, bold=True, font=TITLE_FONT)])
    s.text(x=0.55, y=0.92, w=8.7, h=0.3, paragraphs=[para("When each invocation has a price, a result, and a receipt, the workflow becomes commercially legible.", 1300, MUTED)])
    cards = [
        ("01", "Invocation", "Which tool ran against which target."),
        ("02", "Price", "A stablecoin-denominated micro-charge."),
        ("03", "Result", "A concrete finding, proof, or artifact."),
        ("04", "Receipt", "A settlement reference that can be checked."),
    ]
    x = 0.55
    for idx, title, body in cards:
        s.box(x=x, y=1.55, w=2.1, h=2.05, fill=WHITE, line=LINE, radius=True, paragraphs=[para(idx, 1300, ACCENT, bold=True), para(title, 1550, TEXT, bold=True, font=TITLE_FONT), para(body, 1120, MUTED)])
        x += 2.25
    s.box(x=0.55, y=4.05, w=8.85, h=0.82, fill=WHITE, line=LINE, radius=True, paragraphs=[para("Why it matters", 1300, TEXT, bold=True), para("Buyers see what happened. Builders see where value is created. Security teams get proof instead of a black-box summary.", 1140, MUTED)])
    return s.xml()


def slide_4() -> str:
    s = SlideBuilder()
    s.box(x=0, y=0, w=SLIDE_W, h=SLIDE_H, fill=LIGHT_BG)
    s.text(x=0.55, y=0.42, w=8.9, h=0.48, paragraphs=[para("What LaunchShield Swarm does", 2200, TEXT, bold=True, font=TITLE_FONT)])
    s.text(x=0.55, y=0.92, w=8.7, h=0.35, paragraphs=[para("One AI security audit is broken into priced micro-tasks and rendered live.", 1320, MUTED)])
    s.box(
        x=0.55,
        y=1.45,
        w=3.15,
        h=3.2,
        fill=WHITE,
        line=LINE,
        radius=True,
        paragraphs=[
            para("A single run includes", 1350, TEXT, bold=True),
            para("- Repository file scanning", 1180, MUTED),
            para("- Dependency vulnerability lookups", 1180, MUTED),
            para("- Live site probing", 1180, MUTED),
            para("- Deep LLM review of high-risk findings", 1180, MUTED),
            para("- Verification and fix suggestions", 1180, MUTED),
        ],
    )
    s.box(
        x=4.0,
        y=1.45,
        w=5.4,
        h=3.2,
        fill=DARK_ALT,
        radius=True,
        paragraphs=[
            para("Live product loop", 1350, ACCENT, bold=True),
            para("1. Trigger a run", 1240, WHITE, bold=True),
            para("2. Fan out into atomic tool calls", 1180, "DCE7F3"),
            para("3. Stream execution + billing together", 1180, "DCE7F3"),
            para("4. Surface findings and profitability in one UI", 1180, "DCE7F3"),
            para("5. Attach payment references and evidence", 1180, "DCE7F3"),
        ],
    )
    s.chip(x=4.1, y=4.82, w=1.6, h=0.35, label="Atomic tool calls", fill=BLUE_SOFT, color=BLUE)
    s.chip(x=5.95, y=4.82, w=1.95, h=0.35, label="Live billing waterfall", fill=ACCENT_SOFT, color=ACCENT_DARK)
    s.chip(x=8.15, y=4.82, w=1.15, h=0.35, label="Evidence", fill=GOLD_SOFT, color="8A5A00")
    return s.xml()


def slide_5() -> str:
    s = SlideBuilder()
    s.box(x=0, y=0, w=SLIDE_W, h=SLIDE_H, fill=LIGHT_BG)
    s.text(x=0.55, y=0.42, w=8.9, h=0.48, paragraphs=[para("System architecture", 2200, TEXT, bold=True, font=TITLE_FONT)])
    s.text(x=0.55, y=0.92, w=8.7, h=0.35, paragraphs=[para("A provider-based orchestration layer turns AI security work into billable, observable execution.", 1300, MUTED)])
    layers = [
        (1.45, BLUE_SOFT, BLUE, "Frontend", "FastAPI web app   |   templated UI   |   SSE event stream"),
        (2.52, WHITE, TEXT, "Core runtime", "Orchestrator   |   pricing engine   |   run storage + profitability"),
        (3.74, ACCENT_SOFT, ACCENT_DARK, "Provider adapters", "GitHub / repo source   |   browser + LLM + AIsa   |   Arc / Circle"),
    ]
    for y, fill, color, title, body in layers:
        s.box(x=0.65, y=y, w=8.7, h=0.88, fill=fill, line=LINE if fill == WHITE else None, radius=True, paragraphs=[para(title, 1450, color, bold=True, font=TITLE_FONT), para(body, 1160, TEXT if fill == WHITE else color)], margin=0.14, anchor="ctr")
    s.box(x=0.65, y=4.85, w=8.7, h=0.42, fill=WHITE, line=LINE, radius=True, paragraphs=[para("Mock-first by default. Real providers can be enabled one by one. Full repository scan mode is supported.", 1080, MUTED, align="ctr")], margin=0.08, anchor="ctr")
    return s.xml()


def slide_6() -> str:
    s = SlideBuilder()
    s.box(x=0, y=0, w=SLIDE_W, h=SLIDE_H, fill=LIGHT_BG)
    s.text(x=0.55, y=0.42, w=8.9, h=0.48, paragraphs=[para("One run becomes a live waterfall of paid actions", 2200, TEXT, bold=True, font=TITLE_FONT)])
    s.text(x=0.55, y=0.92, w=8.7, h=0.35, paragraphs=[para("The billing feed is product proof, not decoration.", 1320, MUTED)])
    rows = [
        "22:15:37   file_scan       launchshield/app.py        0.001 USDC",
        "22:15:42   dep_lookup      fastapi>=0.110            0.001 USDC",
        "22:15:49   site_probe      target / headers          0.001 USDC",
        "22:15:55   deep_analysis   dangerous_eval            0.008 USDC",
        "22:16:03   aisa_verify     hardcoded_secret          0.001 USDC",
        "22:16:12   fix_suggestion  repo_scan.py:49           0.001 USDC",
    ]
    s.box(x=0.55, y=1.45, w=5.2, h=3.45, fill=DARK, radius=True, paragraphs=[para("Preset stress run", 1300, ACCENT, bold=True)] + [para(row, 1100, WHITE, font="Consolas") for row in rows], margin=0.14)
    stats = [
        ("63", "paid tool invocations", ACCENT_SOFT, ACCENT_DARK),
        ("$0.001-$0.008", "per call pricing", BLUE_SOFT, BLUE),
        ("Live refs", "each row can carry a settlement reference", GOLD_SOFT, "8A5A00"),
    ]
    y = 1.45
    for big, label, fill, color in stats:
        s.box(x=6.05, y=y, w=3.35, h=0.88, fill=fill, radius=True, paragraphs=[para(big, 1850, color, bold=True, font=TITLE_FONT), para(label, 1080, color)], anchor="ctr")
        y += 1.02
    s.box(x=6.05, y=4.55, w=3.35, h=0.35, fill=WHITE, line=LINE, radius=True, paragraphs=[para("Cost and provenance stay visible at tool-call granularity.", 1020, MUTED, align="ctr")], margin=0.06, anchor="ctr")
    return s.xml()


def slide_7() -> str:
    s = SlideBuilder()
    s.box(x=0, y=0, w=SLIDE_W, h=SLIDE_H, fill=LIGHT_BG)
    s.text(x=0.55, y=0.42, w=8.9, h=0.48, paragraphs=[para("High-signal outputs, not vague summaries", 2200, TEXT, bold=True, font=TITLE_FONT)])
    s.text(x=0.55, y=0.92, w=8.7, h=0.35, paragraphs=[para("The run produces concrete findings, deeper review, and fix guidance.", 1300, MUTED)])
    findings = [
        ("High", RED, "Hardcoded secret exposure", "Credential material in source indicates unsafe secret handling."),
        ("High", RED, "dangerous_eval in repo_scan.py:49", "eval() on untrusted input creates a code injection path."),
        ("High", "8A5A00", "Missing security headers", "Missing CSP / HSTS / X-Frame-Options weakens browser hardening."),
    ]
    y = 1.45
    for level, color, title, body in findings:
        s.box(x=0.55, y=y, w=5.2, h=0.9, fill=WHITE, line=LINE, radius=True, paragraphs=[para(level, 1050, color, bold=True), para(title, 1300, TEXT, bold=True), para(body, 1060, MUTED)])
        y += 1.04
    s.box(
        x=6.05,
        y=1.45,
        w=3.35,
        h=3.0,
        fill=DARK_ALT,
        radius=True,
        paragraphs=[
            para("Verification path", 1300, ACCENT, bold=True),
            para("Rule engine", 1200, WHITE, bold=True),
            para("Static heuristics flag high-confidence issues.", 1080, "DCE7F3"),
            para("Deep analysis", 1200, WHITE, bold=True),
            para("OpenAI-compatible review adds context and severity detail.", 1080, "DCE7F3"),
            para("Fix suggestion", 1200, WHITE, bold=True),
            para("Actionable remediation closes the loop.", 1080, "DCE7F3"),
        ],
    )
    s.box(x=6.05, y=4.62, w=3.35, h=0.28, fill=ACCENT_SOFT, radius=True, paragraphs=[para("Finding cards can be traced back to per-call billing rows.", 1000, ACCENT_DARK, align="ctr")], margin=0.06, anchor="ctr")
    return s.xml()


def slide_8() -> str:
    s = SlideBuilder()
    s.box(x=0, y=0, w=SLIDE_W, h=SLIDE_H, fill=LIGHT_BG)
    s.text(x=0.55, y=0.42, w=8.9, h=0.48, paragraphs=[para("Proof of settlement on Circle and Arc", 2200, TEXT, bold=True, font=TITLE_FONT)])
    s.text(x=0.55, y=0.92, w=8.7, h=0.35, paragraphs=[para("Billing row -> payment reference -> Circle console -> Arc explorer.", 1320, MUTED)])
    chain = [("Billing row", 1.9), ("Payment ref", 1.9), ("Circle console", 2.1), ("Arc explorer", 2.0)]
    x = 0.55
    for idx, (label, width) in enumerate(chain):
        s.box(x=x, y=1.5, w=width, h=0.55, fill=WHITE, line=LINE, radius=True, paragraphs=[para(label, 1200, TEXT, bold=True, align="ctr")], anchor="ctr")
        x += width
        if idx < len(chain) - 1:
            s.text(x=x + 0.02, y=1.66, w=0.3, h=0.2, paragraphs=[para("->", 1400, ACCENT, bold=True, align="ctr", font=TITLE_FONT)], anchor="ctr")
            x += 0.45
    panels = [
        (0.55, "Circle receipt panel", "Settlement receipt / console verification / amount + reference"),
        (5.02, "Arc explorer panel", "On-chain transaction proof / tx hash / explorer deep link"),
    ]
    for x, title, body in panels:
        s.box(x=x, y=2.45, w=4.35, h=2.15, fill=WHITE, line=LINE, radius=True, paragraphs=[para(title, 1400, TEXT, bold=True, font=TITLE_FONT, align="ctr"), para("Evidence placeholder", 1200, ACCENT, bold=True, align="ctr"), para(body, 1100, MUTED, align="ctr")], anchor="ctr")
    return s.xml()


def slide_9() -> str:
    s = SlideBuilder()
    s.box(x=0, y=0, w=SLIDE_W, h=SLIDE_H, fill=LIGHT_BG)
    s.text(x=0.55, y=0.42, w=8.9, h=0.48, paragraphs=[para("Why Arc + stablecoin settlement matters economically", 2100, TEXT, bold=True, font=TITLE_FONT)])
    s.text(x=0.55, y=0.92, w=8.7, h=0.35, paragraphs=[para("Traditional gas-heavy settlement destroys the margin of high-frequency AI security workflows.", 1300, MUTED)])
    s.box(x=0.55, y=1.42, w=8.85, h=0.45, fill=WHITE, line=LINE, radius=True, paragraphs=[para("Example workflow service cost: 0.152", 1180, TEXT, bold=True, align="ctr")], anchor="ctr")
    s.box(x=0.55, y=2.0, w=4.1, h=2.25, fill=RED_SOFT, radius=True, paragraphs=[para("Traditional EVM", 1500, RED, bold=True, font=TITLE_FONT), para("$3.15", 2700, RED, bold=True, font=TITLE_FONT), para("estimated gas overhead", 1200, RED), para("Same workflow. Margin gets crushed before the product scales.", 1120, TEXT)], anchor="ctr")
    s.box(x=5.3, y=2.0, w=4.1, h=2.25, fill=GREEN_SOFT, radius=True, paragraphs=[para("Arc + Circle", 1500, GREEN, bold=True, font=TITLE_FONT), para("0.152 USDC", 2500, GREEN, bold=True, font=TITLE_FONT), para("settled workflow cost", 1200, GREEN), para("Fair usage-based billing stays commercially viable.", 1120, TEXT)], anchor="ctr")
    chips = [(0.7, 1.75, "High frequency"), (2.65, 1.75, "Low ticket size"), (4.6, 1.95, "Many repeated actions"), (6.95, 1.75, "Margin-sensitive")]
    for x, w, label in chips:
        s.chip(x=x, y=4.72, w=w, h=0.35, label=label, fill=WHITE, color=MUTED)
    return s.xml()


def slide_10() -> str:
    s = SlideBuilder()
    s.box(x=0, y=0, w=SLIDE_W, h=SLIDE_H, fill=LIGHT_BG)
    s.text(x=0.55, y=0.42, w=8.9, h=0.48, paragraphs=[para("Who needs this first", 2200, TEXT, bold=True, font=TITLE_FONT)])
    s.text(x=0.55, y=0.92, w=8.7, h=0.35, paragraphs=[para("The first wedge is any team that already feels the pain of opaque AI cost and opaque AI provenance.", 1280, MUTED)])
    cards = [
        (0.55, 1.45, "AppSec teams", "High trust requirements. Clear security outputs."),
        (5.0, 1.45, "Security consultancies", "Per-call proof helps justify delivered work."),
        (0.55, 2.85, "AI agent platforms", "Need usage-based monetization primitives."),
        (5.0, 2.85, "Developer tool marketplaces", "Need transparent pricing for agent actions."),
    ]
    for x, y, title, body in cards:
        s.box(x=x, y=y, w=4.0, h=1.05, fill=WHITE, line=LINE, radius=True, paragraphs=[para(title, 1400, TEXT, bold=True, font=TITLE_FONT), para(body, 1120, MUTED)])
    s.box(x=0.8, y=4.45, w=8.35, h=0.52, fill=DARK_ALT, radius=True, paragraphs=[para("\"I cannot ship an agent that costs more to settle than it charges.\"", 1350, WHITE, bold=True, align="ctr", font=TITLE_FONT)], anchor="ctr")
    return s.xml()


def slide_11() -> str:
    s = SlideBuilder()
    s.box(x=0, y=0, w=SLIDE_W, h=SLIDE_H, fill=LIGHT_BG)
    s.text(x=0.55, y=0.42, w=8.9, h=0.48, paragraphs=[para("Roadmap", 2200, TEXT, bold=True, font=TITLE_FONT)])
    s.text(x=0.55, y=0.92, w=8.7, h=0.35, paragraphs=[para("This MVP proves the workflow. The roadmap expands precision, integrations, and deployment depth.", 1280, MUTED)])
    columns = [
        (0.55, BLUE_SOFT, BLUE, "Near term", ["Multi-tenant runs and team workspaces", "Richer scanners and better findings", "Deeper AIsa integration", "More real-provider hardening"]),
        (3.55, WHITE, TEXT, "Mid term", ["Agent marketplace integrations", "Repeatable production billing flows", "Better dashboards for many tiny settlements"]),
        (6.55, ACCENT_SOFT, ACCENT_DARK, "Long term", ["Arc mainnet launch", "Production-grade usage-based security workflows", "Agent work priced, settled, and audited natively"]),
    ]
    for x, fill, color, title, items in columns:
        s.box(x=x, y=1.45, w=2.7, h=3.4, fill=fill, line=LINE if fill == WHITE else None, radius=True, paragraphs=[para(title, 1450, color, bold=True, font=TITLE_FONT)] + [para(f"- {item}", 1100, TEXT if fill == WHITE else color) for item in items])
    return s.xml()


def slide_12() -> str:
    s = SlideBuilder()
    s.box(x=0, y=0, w=SLIDE_W, h=SLIDE_H, fill=DARK)
    s.chip(x=0.6, y=0.52, w=1.5, h=0.34, label="Closing", fill=ACCENT, color=DARK)
    s.text(x=0.6, y=1.05, w=6.0, h=0.7, paragraphs=[para("LaunchShield Swarm", 3000, WHITE, bold=True, font=TITLE_FONT)])
    s.text(x=0.6, y=1.9, w=6.4, h=0.75, paragraphs=[para("Billable. Traceable. Verifiable AI security workflows.", 2000, ACCENT, bold=True, font=TITLE_FONT), para("Arc and Circle make the workflow economically viable.", 1350, "DCE7F3")])
    cards = [
        (0.65, "Billable", ACCENT_SOFT, ACCENT_DARK),
        (3.1, "Traceable", BLUE_SOFT, BLUE),
        (5.55, "Verifiable", GOLD_SOFT, "8A5A00"),
    ]
    for x, label, fill, color in cards:
        s.box(x=x, y=3.05, w=2.15, h=0.8, fill=fill, radius=True, paragraphs=[para(label, 1600, color, bold=True, font=TITLE_FONT, align="ctr"), para("AI security at tool-call granularity", 1000, color, align="ctr")], anchor="ctr")
    s.box(x=6.95, y=1.25, w=2.45, h=2.1, fill=DARK_ALT, line=ACCENT, radius=True, paragraphs=[para("Product thesis", 1250, ACCENT, bold=True), para("Any AI workflow that becomes many tiny valuable actions will need native micropayment rails.", 1180, WHITE)])
    s.text(x=0.62, y=4.78, w=8.7, h=0.45, paragraphs=[para("GitHub: github.com/Abdullahccgdq/launchshield", 1080, "B6C8D8"), para("Demo: launchshield-swarm.fly.dev   |   Team: Red Snail", 1080, "B6C8D8")])
    return s.xml()


SLIDES = [
    ("LaunchShield Swarm", slide_1),
    ("The execution model already changed. The payment model did not.", slide_2),
    ("Micropayments turn AI work from a black box into a priced workflow.", slide_3),
    ("What LaunchShield Swarm does", slide_4),
    ("System architecture", slide_5),
    ("One run becomes a live waterfall of paid actions", slide_6),
    ("High-signal outputs, not vague summaries", slide_7),
    ("Proof of settlement on Circle and Arc", slide_8),
    ("Why Arc + stablecoin settlement matters economically", slide_9),
    ("Who needs this first", slide_10),
    ("Roadmap", slide_11),
    ("LaunchShield Swarm", slide_12),
]


def update_content_types(path: Path, slide_count: int) -> None:
    content = path.read_text(encoding="utf-8")
    content = content.replace(
        "application/vnd.openxmlformats-officedocument.presentationml.template.main+xml",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml",
    )
    for index in range(9, slide_count + 1):
        marker = f'/ppt/slides/slide{index}.xml'
        if marker not in content:
            override = (
                f'<Override PartName="/ppt/slides/slide{index}.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
            )
            content = content.replace("</Types>", override + "</Types>")
    path.write_text(content, encoding="utf-8")


def update_presentation_rels(path: Path, slide_count: int) -> None:
    content = path.read_text(encoding="utf-8")
    existing_ids = [int(value) for value in re.findall(r'Id="rId(\d+)"', content)]
    next_id = max(existing_ids) + 1
    for slide_index in range(9, slide_count + 1):
        target = f'slides/slide{slide_index}.xml'
        if target not in content:
            rel_xml = (
                f'<Relationship Id="rId{next_id}" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" '
                f'Target="{target}"/>'
            )
            content = content.replace("</Relationships>", rel_xml + "</Relationships>")
            next_id += 1
    path.write_text(content, encoding="utf-8")


def update_presentation_xml(path: Path, slide_count: int) -> None:
    content = path.read_text(encoding="utf-8")
    ids = list(range(256, 256 + slide_count))
    rel_ids = list(range(2, 10)) + list(range(15, 15 + max(0, slide_count - 8)))
    sld_id_list = "<p:sldIdLst>" + "".join(
        f'<p:sldId id="{slide_id}" r:id="rId{rel_id}"/>'
        for slide_id, rel_id in zip(ids, rel_ids)
    ) + "</p:sldIdLst>"
    content = re.sub(r"<p:sldIdLst>.*?</p:sldIdLst>", sld_id_list, content, count=1)
    path.write_text(content, encoding="utf-8")


def build_app_xml(titles: list[str]) -> str:
    title_nodes = "".join(f"<vt:lpstr>{esc(title)}</vt:lpstr>" for title in ["LaunchShield Swarm", *titles])
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
        'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
        "<Template></Template><TotalTime>0</TotalTime><Words>0</Words>"
        "<Application>Microsoft Office PowerPoint</Application>"
        "<PresentationFormat>Widescreen (16:9)</PresentationFormat>"
        "<Paragraphs>0</Paragraphs>"
        f"<Slides>{len(titles)}</Slides><Notes>0</Notes><HiddenSlides>0</HiddenSlides><MMClips>0</MMClips>"
        "<ScaleCrop>false</ScaleCrop>"
        "<HeadingPairs><vt:vector size=\"4\" baseType=\"variant\">"
        "<vt:variant><vt:lpstr>Theme</vt:lpstr></vt:variant><vt:variant><vt:i4>1</vt:i4></vt:variant>"
        "<vt:variant><vt:lpstr>Slide Titles</vt:lpstr></vt:variant>"
        f"<vt:variant><vt:i4>{len(titles)}</vt:i4></vt:variant>"
        "</vt:vector></HeadingPairs>"
        f"<TitlesOfParts><vt:vector size=\"{len(titles) + 1}\" baseType=\"lpstr\">"
        f"{title_nodes}</vt:vector></TitlesOfParts>"
        "<Manager></Manager><Company></Company><LinksUpToDate>false</LinksUpToDate>"
        "<SharedDoc>false</SharedDoc><HyperlinksChanged>false</HyperlinksChanged>"
        "<AppVersion>16.0000</AppVersion></Properties>"
    )


def build_core_xml() -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        "<dc:title>LaunchShield Swarm</dc:title><dc:creator>Codex</dc:creator>"
        "<cp:lastModifiedBy>Codex</cp:lastModifiedBy><cp:revision>2</cp:revision>"
        f"<dcterms:created xsi:type=\"dcterms:W3CDTF\">{now}</dcterms:created>"
        f"<dcterms:modified xsi:type=\"dcterms:W3CDTF\">{now}</dcterms:modified>"
        "</cp:coreProperties>"
    )


def rewrite_slides(extract_dir: Path) -> None:
    slides_dir = extract_dir / "ppt" / "slides"
    rels_dir = slides_dir / "_rels"
    for index, (_, renderer) in enumerate(SLIDES, start=1):
        (slides_dir / f"slide{index}.xml").write_text(renderer(), encoding="utf-8")
        (rels_dir / f"slide{index}.xml.rels").write_text(slide_rel_xml(), encoding="utf-8")


def pack_directory(source_dir: Path, output_path: Path) -> None:
    with ZipFile(output_path, "w", compression=ZIP_DEFLATED) as zf:
        for path in sorted(source_dir.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(source_dir).as_posix())


def generate() -> Path:
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"Template not found: {TEMPLATE_PATH}")
    build_root = DOCS_DIR / ".pptx-build"
    if build_root.exists():
        shutil.rmtree(build_root, ignore_errors=True)
    build_root.mkdir(parents=True, exist_ok=True)
    extract_dir = build_root / "deck"
    with ZipFile(TEMPLATE_PATH) as zf:
        zf.extractall(extract_dir)
    rewrite_slides(extract_dir)
    update_content_types(extract_dir / "[Content_Types].xml", len(SLIDES))
    update_presentation_rels(extract_dir / "ppt" / "_rels" / "presentation.xml.rels", len(SLIDES))
    update_presentation_xml(extract_dir / "ppt" / "presentation.xml", len(SLIDES))
    (extract_dir / "docProps" / "app.xml").write_text(build_app_xml([title for title, _ in SLIDES]), encoding="utf-8")
    (extract_dir / "docProps" / "core.xml").write_text(build_core_xml(), encoding="utf-8")
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    if OUTPUT_PATH.exists():
        OUTPUT_PATH.unlink()
    pack_directory(extract_dir, OUTPUT_PATH)
    return OUTPUT_PATH


if __name__ == "__main__":
    print(generate())
