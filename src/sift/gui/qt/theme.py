"""Design tokens and the one QSS string that styles the whole window.

Every color of the window is a field of ``Tokens``. ``generate_qss``
turns a ``Tokens`` into the style sheet, ``apply_theme`` installs the
Fusion style, a palette and that sheet on the application. The
delegate and the preview read the same tokens, so a theme switch is
one call and nothing keeps a stale color.

The palette matters as much as the sheet: a style sheet colors the
widgets it names, while ``QPalette.Window`` is what ``window()``,
tooltips and the parts of a widget without a rule use.
"""

from dataclasses import dataclass
from typing import Literal

import qtawesome
from PySide6.QtGui import QColor, QFont, QIcon, QPalette
from PySide6.QtWidgets import QApplication

type Scheme = Literal["light", "dark"]

FAMILIES = ["Inter", "Noto Sans CJK SC"]
MONO_FAMILIES = ["JetBrains Mono", "DejaVu Sans Mono"]

# type scale, in pixels
SIZE_BODY = 13
SIZE_META = 12
SIZE_TITLE = 15
SIZE_HEADER = 22

# spacing scale and radii, in pixels
SPACE_1, SPACE_2, SPACE_3, SPACE_4, SPACE_5 = 4, 8, 12, 16, 24
RADIUS_CARD = 10
RADIUS_INPUT = 8
RADIUS_CHIP = 999


@dataclass(frozen=True, slots=True)
class Tokens:
    """The colors of one theme, as ``#RRGGBB`` strings."""

    name: Scheme
    bg: str
    surface: str
    surface_alt: str
    border: str
    text: str
    muted: str
    accent: str
    accent_hover: str
    accent_soft: str
    mark_bg: str
    mark_text: str
    error: str
    error_soft: str


LIGHT = Tokens(
    name="light",
    bg="#F7F8FA",
    surface="#FFFFFF",
    surface_alt="#F1F3F7",
    border="#E4E7EC",
    text="#1D2433",
    muted="#667085",
    accent="#4F46E5",
    accent_hover="#4338CA",
    accent_soft="#EEF2FF",
    mark_bg="#FDE68A",
    mark_text="#1D2433",
    error="#DC2626",
    error_soft="#FEF2F2",
)

DARK = Tokens(
    name="dark",
    bg="#0F1117",
    surface="#171A21",
    surface_alt="#1E222B",
    border="#2A2F3A",
    text="#E6E8EE",
    muted="#98A2B3",
    accent="#818CF8",
    accent_hover="#A5B4FC",
    accent_soft="#1E1B4B",
    mark_bg="#854D0E",
    mark_text="#FEF3C7",
    error="#F87171",
    error_soft="#3B1212",
)

TOKENS: dict[Scheme, Tokens] = {"light": LIGHT, "dark": DARK}


def make_font(
    size: int, *, semibold: bool = False, mono: bool = False
) -> QFont:
    """Return a font of size pixels in the Sift families.

    The first family is Inter (or JetBrains Mono); Qt falls back to
    the next family, and then to fontconfig, for a glyph that the
    first one lacks, which is how Chinese text reaches Noto Sans CJK.
    """
    font = QFont()
    font.setFamilies(MONO_FAMILIES if mono else FAMILIES)
    font.setPixelSize(size)
    font.setWeight(QFont.Weight.DemiBold if semibold else QFont.Weight.Normal)
    return font


def icon(name: str, color: str) -> QIcon:
    """Return the qtawesome icon name drawn in color.

    qtawesome has no type information (``typings/qtawesome`` is a
    stub of the one function), and this is the one place that calls
    it. A name is ``<set>.<icon>``, e.g. ``mdi6.magnify``.
    Needs a running QApplication.
    """
    return qtawesome.icon(name, color=color)


def _families(names: list[str]) -> str:
    """Return names as a QSS ``font-family`` value."""
    return ", ".join(f'"{name}"' for name in names)


def generate_qss(t: Tokens) -> str:
    """Return the style sheet of the whole window for tokens t."""
    sans = _families(FAMILIES)
    mono = _families(MONO_FAMILIES)
    return f"""
QWidget {{
    background: {t.bg};
    color: {t.text};
    font-family: {sans};
    font-size: {SIZE_BODY}px;
    selection-background-color: {t.accent_soft};
    selection-color: {t.text};
}}
QLabel {{ background: transparent; }}
QMainWindow, QStackedWidget, QSplitter {{ background: {t.bg}; }}

/* header */
#header {{
    background: {t.surface};
    border: 0;
    border-bottom: 1px solid {t.border};
}}
#brand, #fieldBox {{ background: transparent; }}
#appName {{
    font-size: {SIZE_HEADER}px;
    font-weight: 600;
    color: {t.text};
}}
#chip {{
    background: {t.accent_soft};
    color: {t.accent};
    border-radius: 11px;
    padding: 2px 10px;
    font-size: {SIZE_META}px;
    font-weight: 600;
}}
QLineEdit {{
    background: {t.surface_alt};
    color: {t.text};
    border: 1px solid {t.border};
    border-radius: {RADIUS_INPUT}px;
    padding: 0 {SPACE_3}px;
    min-height: 44px;
    max-height: 44px;
    font-size: 14px;
    selection-background-color: {t.accent};
    selection-color: {t.surface};
}}
QLineEdit:hover {{ border-color: {t.muted}; }}
QLineEdit:focus {{
    border: 2px solid {t.accent};
    background: {t.surface};
}}
#banner {{
    background: {t.error_soft};
    color: {t.error};
    border: 1px solid {t.error};
    border-radius: {RADIUS_INPUT}px;
    padding: {SPACE_2}px {SPACE_3}px;
    font-family: {mono};
    font-size: {SIZE_META}px;
}}
QProgressBar#busy {{
    background: transparent;
    border: 0;
    min-height: 2px;
    max-height: 2px;
}}
QProgressBar#busy::chunk {{ background: {t.accent}; }}

/* buttons */
QPushButton {{
    background: {t.surface_alt};
    color: {t.text};
    border: 1px solid {t.border};
    border-radius: {RADIUS_INPUT}px;
    padding: {SPACE_2}px {SPACE_4}px;
}}
QPushButton:hover {{
    background: {t.accent_soft};
    border-color: {t.accent};
    color: {t.accent_hover};
}}
QPushButton:pressed {{ background: {t.accent_soft}; }}
QPushButton:focus {{ border: 1px solid {t.accent}; }}
QPushButton#themeButton {{
    min-width: 44px;
    max-width: 44px;
    min-height: 44px;
    max-height: 44px;
    padding: 0;
}}
QPushButton#exampleChip {{
    background: {t.surface};
    color: {t.text};
    border: 1px solid {t.border};
    border-radius: 15px;
    padding: {SPACE_2 - 1}px {SPACE_4}px;
    font-size: {SIZE_BODY}px;
    font-weight: 400;
}}
QPushButton#exampleChip:hover {{
    background: {t.accent_soft};
    border-color: {t.accent};
    color: {t.accent};
}}

/* results and preview */
QListView {{
    background: transparent;
    border: 0;
    outline: 0;
}}
#panel {{
    background: {t.surface};
    border: 1px solid {t.border};
    border-radius: {RADIUS_CARD}px;
}}
QTextBrowser {{
    background: {t.surface};
    color: {t.text};
    border: 0;
    selection-background-color: {t.accent};
    selection-color: {t.surface};
}}
#stateTitle {{
    font-size: {SIZE_TITLE}px;
    font-weight: 600;
    color: {t.text};
}}
#stateHint {{ color: {t.muted}; font-size: {SIZE_META}px; }}

/* scroll bars */
QScrollBar:vertical {{
    background: transparent;
    width: 12px;
    margin: 2px;
    border: 0;
}}
QScrollBar::handle:vertical {{
    background: {t.border};
    min-height: 32px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical:hover {{ background: {t.muted}; }}
QScrollBar:horizontal {{
    background: transparent;
    height: 12px;
    margin: 2px;
    border: 0;
}}
QScrollBar::handle:horizontal {{
    background: {t.border};
    min-width: 32px;
    border-radius: 4px;
}}
QScrollBar::handle:horizontal:hover {{ background: {t.muted}; }}
QScrollBar::add-line, QScrollBar::sub-line {{
    width: 0; height: 0; background: transparent; border: 0;
}}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* splitter, status bar, tooltip, menu */
QSplitter::handle {{ background: transparent; }}
QSplitter::handle:horizontal {{ width: {SPACE_3}px; }}
QStatusBar {{
    background: {t.surface};
    color: {t.muted};
    border-top: 1px solid {t.border};
    font-size: {SIZE_META}px;
}}
QStatusBar::item {{ border: 0; }}
QStatusBar QLabel {{ color: {t.muted}; }}
QToolTip {{
    background: {t.surface};
    color: {t.text};
    border: 1px solid {t.border};
    border-radius: {SPACE_1}px;
    padding: {SPACE_1}px {SPACE_2}px;
}}
QMenu {{
    background: {t.surface};
    color: {t.text};
    border: 1px solid {t.border};
    border-radius: {RADIUS_INPUT}px;
    padding: {SPACE_1}px;
}}
QMenu::item {{
    padding: 6px 20px;
    border-radius: {SPACE_1}px;
}}
QMenu::item:selected {{
    background: {t.accent_soft};
    color: {t.accent};
}}
QMenu::separator {{
    height: 1px;
    background: {t.border};
    margin: {SPACE_1}px {SPACE_2}px;
}}
"""


def make_palette(t: Tokens) -> QPalette:
    """Return the QPalette that matches tokens t."""
    palette = QPalette()
    roles = {
        QPalette.ColorRole.Window: t.bg,
        QPalette.ColorRole.WindowText: t.text,
        QPalette.ColorRole.Base: t.surface,
        QPalette.ColorRole.AlternateBase: t.surface_alt,
        QPalette.ColorRole.Text: t.text,
        QPalette.ColorRole.Button: t.surface_alt,
        QPalette.ColorRole.ButtonText: t.text,
        QPalette.ColorRole.ToolTipBase: t.surface,
        QPalette.ColorRole.ToolTipText: t.text,
        QPalette.ColorRole.PlaceholderText: t.muted,
        QPalette.ColorRole.Highlight: t.accent,
        QPalette.ColorRole.HighlightedText: t.surface,
        QPalette.ColorRole.Link: t.accent,
        QPalette.ColorRole.LinkVisited: t.accent_hover,
    }
    for role, value in roles.items():
        palette.setColor(role, QColor(value))
    for role in (
        QPalette.ColorRole.Text,
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.ButtonText,
    ):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(t.muted))
    return palette


def apply_theme(app: QApplication, scheme: Scheme) -> Tokens:
    """Install Fusion, the palette and the style sheet of scheme.

    Return the tokens, which the delegate and the preview need. The
    style is set only once: ``setStyle`` builds a new style object
    and repolishes every widget, which a theme switch does not need.
    """
    if app.style().objectName().lower() != "fusion":
        app.setStyle("Fusion")
    tokens = TOKENS[scheme]
    app.setFont(make_font(SIZE_BODY))
    app.setPalette(make_palette(tokens))
    app.setStyleSheet(generate_qss(tokens))
    return tokens
