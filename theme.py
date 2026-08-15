"""
theme.py
ثيم داكن احترافي للتطبيق (QSS) + ألوان مساعدة للاستخدام في الكود (شارات الحالة، تنبيهات...).
"""

# لوحة الألوان
BG = "#12161c"          # خلفية النافذة
SURFACE = "#1a2029"     # خلفية البطاقات / الحقول
SURFACE_ALT = "#20283344"
BORDER = "#2a3340"
TEXT = "#e6eaf0"
TEXT_MUTED = "#8b97a8"
ACCENT = "#e8543a"      # أحمر/برتقالي ناري - يناسب مجال الحماية من الحريق
ACCENT_HOVER = "#ff6a4d"
ACCENT_DARK = "#b83f2a"
SUCCESS = "#3ecf8e"
WARNING = "#f2b94c"
DANGER = "#f0554a"
SIDEBAR_BG = "#0d1015"

STATUS_COLORS = {
    "Design": "#5b8def",
    "Supply": "#f2b94c",
    "Install": "#e8543a",
    "Testing": "#8a63f2",
    "Handover": "#3ecf8e",
}

ALERT_COLORS = {
    "overdue": DANGER,
    "soon": WARNING,
    "none": SUCCESS,
}

QSS = f"""
* {{
    outline: none;
}}

QMainWindow, QWidget {{
    background-color: {BG};
    color: {TEXT};
    font-family: "Segoe UI", "Tahoma", sans-serif;
    font-size: 13px;
}}

/* ---------- Sidebar ---------- */
#Sidebar {{
    background-color: {SIDEBAR_BG};
    border-right: 1px solid {BORDER};
}}

#SidebarTitle {{
    color: {TEXT};
    font-size: 16px;
    font-weight: 600;
    padding: 18px 16px 4px 16px;
}}

#SidebarSubtitle {{
    color: {TEXT_MUTED};
    font-size: 11px;
    padding: 0px 16px 16px 16px;
}}

QPushButton#NavButton {{
    text-align: left;
    padding: 10px 16px;
    border: none;
    border-radius: 8px;
    margin: 3px 10px;
    color: {TEXT_MUTED};
    background-color: transparent;
    font-size: 13px;
}}

QPushButton#NavButton:hover {{
    background-color: {SURFACE};
    color: {TEXT};
}}

QPushButton#NavButton:checked {{
    background-color: {ACCENT};
    color: white;
    font-weight: 600;
}}

/* ---------- Cards / surfaces ---------- */
QWidget#Card {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 10px;
}}

QLabel#PageTitle {{
    font-size: 20px;
    font-weight: 700;
    color: {TEXT};
}}

QLabel#PageSubtitle {{
    color: {TEXT_MUTED};
    font-size: 12px;
}}

QLabel#StatValue {{
    font-size: 26px;
    font-weight: 700;
    color: {TEXT};
}}

QLabel#StatLabel {{
    color: {TEXT_MUTED};
    font-size: 12px;
}}

/* ---------- Inputs ---------- */
QLineEdit, QTextEdit, QDateEdit, QComboBox, QDoubleSpinBox, QSpinBox {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 10px;
    color: {TEXT};
    selection-background-color: {ACCENT};
}}

QLineEdit:focus, QTextEdit:focus, QDateEdit:focus, QComboBox:focus {{
    border: 1px solid {ACCENT};
}}

QComboBox::drop-down {{
    border: none;
    width: 22px;
}}

QComboBox QAbstractItemView {{
    background-color: {SURFACE};
    color: {TEXT};
    selection-background-color: {ACCENT};
    border: 1px solid {BORDER};
}}

QLabel {{
    color: {TEXT};
}}

/* ---------- Buttons ---------- */
QPushButton {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 7px 16px;
    color: {TEXT};
}}

QPushButton:hover {{
    border-color: {ACCENT};
    color: {TEXT};
}}

QPushButton#PrimaryButton {{
    background-color: {ACCENT};
    border: none;
    color: white;
    font-weight: 600;
    padding: 9px 18px;
}}

QPushButton#PrimaryButton:hover {{
    background-color: {ACCENT_HOVER};
}}

QPushButton#DangerButton {{
    background-color: transparent;
    border: 1px solid {DANGER};
    color: {DANGER};
}}

QPushButton#DangerButton:hover {{
    background-color: {DANGER};
    color: white;
}}

/* ---------- Tables ---------- */
QTableWidget {{
    background-color: {SURFACE};
    alternate-background-color: #1e2530;
    border: 1px solid {BORDER};
    border-radius: 8px;
    gridline-color: {BORDER};
    selection-background-color: {ACCENT_DARK};
    selection-color: white;
}}

QHeaderView::section {{
    background-color: #161b22;
    color: {TEXT_MUTED};
    padding: 8px;
    border: none;
    border-bottom: 1px solid {BORDER};
    font-weight: 600;
}}

QTableWidget::item {{
    padding: 4px;
}}

/* ---------- Lists ---------- */
QListWidget {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 8px;
}}

QListWidget::item {{
    padding: 8px;
    border-bottom: 1px solid {BORDER};
}}

QListWidget::item:selected {{
    background-color: {ACCENT_DARK};
    color: white;
}}

/* ---------- Scrollbars ---------- */
QScrollBar:vertical {{
    background: {BG};
    width: 10px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 5px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {ACCENT};
}}

/* ---------- Status bar ---------- */
QStatusBar {{
    background-color: {SIDEBAR_BG};
    color: {TEXT_MUTED};
    border-top: 1px solid {BORDER};
}}

/* ---------- Tabs (if used) ---------- */
QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-radius: 8px;
}}
QTabBar::tab {{
    background: {SURFACE};
    padding: 8px 16px;
    color: {TEXT_MUTED};
    border: 1px solid {BORDER};
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}}
QTabBar::tab:selected {{
    color: {TEXT};
    background: {ACCENT};
}}
"""


def status_badge_style(status: str) -> str:
    color = STATUS_COLORS.get(status, TEXT_MUTED)
    return f"background-color:{color}22; color:{color}; border:1px solid {color}; border-radius:8px; padding:2px 10px; font-weight:600;"


def alert_badge_style(level: str) -> str:
    color = ALERT_COLORS.get(level, TEXT_MUTED)
    return f"background-color:{color}22; color:{color}; border:1px solid {color}; border-radius:8px; padding:2px 10px; font-weight:600;"
