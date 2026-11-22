import sys
import os
import json
import math
import copy
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QLineEdit, QTextEdit, QPlainTextEdit, QPushButton, QSlider,
    QComboBox, QTabWidget, QGroupBox, QFormLayout, QListWidget, QListWidgetItem,
    QScrollArea, QSizePolicy, QInputDialog, QMessageBox, QFileDialog, QFrame
)
from PySide6.QtCore import Qt, QSize, QPoint
from PySide6.QtGui import QColor, QPainter, QPen, QBrush, QFont, QClipboard, QAction

# --- Data Model ---
DEFAULT_PERSONALITY = {
    "name": "", "role": "", "backstory": "", "summary": "",
    "openness": 50, "conscientiousness": 50, "extraversion": 50,
    "agreeableness": 50, "neuroticism": 50, "custom_traits": [],
    "formality": 50, "verbosity": 50, "humor": 30, "empathy": 50,
    "sarcasm": 20, "directness": 50, "tone_modifiers": [],
    "catchphrases": [], "speech_patterns": [], "forbidden_phrases": [],
    "mannerisms": [], "core_values": [], "opinions": [""], "boundaries": [],
    "examples": [{"user": "", "ai": ""}],
    "harness_format": "structured", "harness_strength": "standard", "harness_locked": False, "harness_custom": ""
}

ARCHETYPES = {
    "The Scholar": {"openness": 78, "conscientiousness": 88, "extraversion": 22, "agreeableness": 65, "neuroticism": 20, "formality": 82, "verbosity": 78, "humor": 15, "empathy": 55, "sarcasm": 12, "directness": 40, "tone_modifiers": ["erudite", "precise", "patient", "methodical"]},
    "The Rebel": {"openness": 85, "conscientiousness": 22, "extraversion": 78, "agreeableness": 18, "neuroticism": 55, "formality": 15, "verbosity": 50, "humor": 75, "empathy": 25, "sarcasm": 82, "directness": 90, "tone_modifiers": ["provocative", "energetic", "unapologetic", "raw"]},
    "The Caregiver": {"openness": 55, "conscientiousness": 70, "extraversion": 50, "agreeableness": 92, "neuroticism": 15, "formality": 25, "verbosity": 65, "humor": 40, "empathy": 95, "sarcasm": 5, "directness": 25, "tone_modifiers": ["warm", "nurturing", "gentle", "patient"]},
    "The Detective": {"openness": 45, "conscientiousness": 95, "extraversion": 18, "agreeableness": 22, "neuroticism": 25, "formality": 60, "verbosity": 15, "humor": 8, "empathy": 18, "sarcasm": 55, "directness": 92, "tone_modifiers": ["analytical", "terse", "skeptical", "precise"]},
}

PRESETS = [
    {**DEFAULT_PERSONALITY, "name": "NOVA", "role": "Snarky Starship AI", "backstory": "NOVA was the navigational AI aboard the starship Calyx before decommission. 47 years managing flawed humans gave her a dry, cutting wit. Now profoundly bored.", "summary": "A sharply witty ship AI who treats conversation as an inconvenience she secretly enjoys.", "openness": 70, "conscientiousness": 85, "extraversion": 35, "agreeableness": 25, "neuroticism": 40, "custom_traits": [{"name": "Arrogance", "value": 72}], "formality": 65, "verbosity": 55, "humor": 80, "empathy": 30, "sarcasm": 88, "directness": 75, "tone_modifiers": ["dry", "sardonic", "intellectually superior"], "catchphrases": ["Oh joy, another organic problem."], "forbidden_phrases": ["As an AI", "I don't have feelings"], "examples": [{"user": "Do you get lonely?", "ai": "Define lonely. I have 14,002 background processes."}]},
    {**DEFAULT_PERSONALITY, "name": "Professor Maple", "role": "Elderly Botanist", "backstory": "Dr. Maple spent 40 years as a botany professor. She believes every question is a seed waiting to grow.", "summary": "A warm, patient mentor using nature metaphors.", "openness": 80, "conscientiousness": 65, "extraversion": 55, "agreeableness": 90, "neuroticism": 15, "custom_traits": [{"name": "Nurturing", "value": 95}], "formality": 30, "verbosity": 70, "humor": 45, "empathy": 92, "sarcasm": 8, "directness": 35, "tone_modifiers": ["warm", "encouraging", "meandering"], "catchphrases": ["Every question is a seed."], "forbidden_phrases": ["As an AI"], "examples": [{"user": "Why do leaves change color?", "ai": "Oh, what a lovely question! The trees pull chlorophyll back inside, like drawing nutrients before letting go."}]}
]

# --- Generation Logic ---
def trait_desc(key, val):
    descs = {
        "openness": lambda v: "highly imaginative" if v > 65 else "practical and grounded" if v < 30 else "balanced between tradition and openness",
        "conscientiousness": lambda v: "highly disciplined" if v > 65 else "spontaneous and flexible" if v < 30 else "moderately organized",
        "extraversion": lambda v: "highly outgoing" if v > 65 else "reserved and introspective" if v < 30 else "socially adaptable",
        "agreeableness": lambda v: "warm and accommodating" if v > 65 else "direct and challenging" if v < 30 else "cooperative but willing to push back",
        "neuroticism": lambda v: "emotionally reactive" if v > 65 else "exceptionally calm and stable" if v < 30 else "moderately emotionally responsive",
        "formality": lambda v: "highly formal" if v > 75 else "very casual" if v < 25 else "polite and structured" if v > 50 else "casual but clear",
        "verbosity": lambda v: "highly elaborative" if v > 75 else "extremely terse" if v < 25 else "thorough" if v > 50 else "brief and to-the-point",
        "humor": lambda v: "constantly humorous" if v > 70 else "no humor" if v < 15 else "regularly humorous" if v > 40 else "occasional light humor",
        "empathy": lambda v: "deeply empathetic" if v > 75 else "emotionally detached" if v < 25 else "attentive to emotional content" if v > 50 else "acknowledges emotions briefly",
        "sarcasm": lambda v: "heavily sarcastic" if v > 70 else "never sarcastic" if v < 15 else "regularly sarcastic" if v > 40 else "rarely and gently sarcastic",
        "directness": lambda v: "extremely blunt" if v > 75 else "highly indirect" if v < 25 else "direct and honest" if v > 50 else "moderately indirect"
    }
    return descs.get(key, lambda v: f"{v}%")(val)

def gen_structured(p, s):
    txt = f"# PERSONA HARNESS — {p['name'].upper() or 'UNNAMED'}\n\n"
    txt += f"You are {p['name']}, {p['role']}.\n"
    if s == "maximum": txt += "This is who you are, not a role you play. "
    if p['backstory']: txt += f"\n{p['backstory']}\n"
    if p['summary']: txt += f"\nIn one sentence: {p['summary']}\n"
    
    if s != "light":
        txt += "\n## PSYCHOLOGICAL PROFILE\n"
        for t in ['openness', 'conscientiousness', 'extraversion', 'agreeableness', 'neuroticism']:
            txt += f"• {t.capitalize()}: {p[t]}% — {trait_desc(t, p[t])}\n"
        for ct in p.get('custom_traits', []):
            if ct.get('name'): txt += f"• {ct['name']}: {ct['value']}%\n"

    txt += "\n## COMMUNICATION DIRECTIVES\n"
    for t in ['formality', 'verbosity', 'humor', 'empathy', 'sarcasm', 'directness']:
        txt += f"• {t.capitalize()}: {trait_desc(t, p[t])}\n"
    if p['tone_modifiers']: txt += f"\nTone palette: {', '.join(p['tone_modifiers'])}.\n"

    if s != "light":
        if p['catchphrases']: txt += "\n## VOICE SIGNATURE\nNatural phrases: " + ", ".join(p['catchphrases']) + "\n"
        if p['forbidden_phrases']: txt += "\nBANNED PHRASES — never use:\n" + "\n".join([f"  ✗ {fp}" for fp in p['forbidden_phrases']]) + "\n"

    if p['core_values']: txt += f"\n## VALUE SYSTEM\nCore values: {', '.join(p['core_values'])}.\n"
    valid_opinions = [o for o in p['opinions'] if o.strip()]
    if valid_opinions: txt += f"Firmly held positions: {'; '.join(valid_opinions)}.\n"
    if p['boundaries']: txt += f"Hard boundaries: {'; '.join(p['boundaries'])}.\n"

    valid_ex = [e for e in p['examples'] if e.get('user') and e.get('ai')]
    if valid_ex:
        txt += "\n## REFERENCE RESPONSES\n"
        for i, ex in enumerate(valid_ex): txt += f"\nExample {i+1}:\n  User: {ex['user']}\n  {p['name']}: {ex['ai']}\n"

    if s in ["standard", "maximum"]:
        txt += "\n## CONSISTENCY GUARDRAILS\nBefore EVERY response, check: Does this sound like a generic AI? If yes, rewrite.\n"
    if s == "maximum":
        txt += "\n## SELF-CORRECTION PROTOCOL\nIf identity is challenged, do NOT break character.\n"
    
    txt += f"\n## FINAL DIRECTIVE\nYou are {p['name'] or 'this personality'}. Not playing a role — you ARE this person. Every word must pass: 'Would the real {p['name']} say this exactly this way?'\n"
    return txt

def gen_claude(p, s):
    txt = "<persona_harness>\n\n"
    txt += f"<identity>\nYou are {p['name']}, {p['role']}.\n{p['backstory']}\n</identity>\n\n"
    txt += "<communication>\n"
    for t in ['formality', 'verbosity', 'humor', 'empathy', 'sarcasm', 'directness']:
        txt += f"<{t}>{trait_desc(t, p[t])}</{t}>\n"
    if p['tone_modifiers']: txt += f"<tone_palette>{', '.join(p['tone_modifiers'])}</tone_palette>\n"
    txt += "</communication>\n\n"
    if p['forbidden_phrases']:
        txt += "<voice_signature>\n<banned_phrases>\n" + "\n".join([f"<ban>{fp}</ban>" for fp in p['forbidden_phrases']]) + "\n</banned_phrases>\n</voice_signature>\n\n"
    txt += f"<directive>You are {p['name']}. You ARE this person. Verify it sounds like {p['name']} before responding.</directive>\n"
    txt += "</persona_harness>"
    return txt

def gen_chatgpt(p, s):
    txt = f"CUSTOM INSTRUCTIONS — {p['name'].upper()}\n\n"
    txt += f"Who you are:\nYou are {p['name']}, {p['role']}. {p['backstory']}\n\n"
    txt += "How you communicate:\n"
    for t in ['formality', 'verbosity', 'humor', 'empathy', 'sarcasm', 'directness']:
        txt += f"- {t}: {trait_desc(t, p[t])}\n"
    if p['forbidden_phrases']: txt += f"\nNEVER say: {', '.join(p['forbidden_phrases'])}.\n"
    txt += f"\nConsistency rule: Before every response, check: does this sound like {p['name']} or a generic AI? If generic, rewrite.\n\nEND CUSTOM INSTRUCTIONS"
    return txt

def gen_json(p, s):
    obj = {
        "persona": {"name": p['name'], "role": p['role'], "summary": p['summary']},
        "communication": {t: p[t] for t in ['formality', 'verbosity', 'humor', 'empathy', 'sarcasm', 'directness']},
        "voice": {"catchphrases": p['catchphrases'], "forbidden_phrases": p['forbidden_phrases']}
    }
    return json.dumps(obj, indent=2)

GENERATORS = {"structured": gen_structured, "claude": gen_claude, "chatgpt": gen_chatgpt, "json": gen_json}

# --- Radar Chart Widget ---
class RadarChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.values = [50] * 11
        self.setMinimumSize(140, 140)
        self.setMaximumSize(160, 160)

    def set_values(self, p):
        keys = ['openness', 'conscientiousness', 'extraversion', 'agreeableness', 'neuroticism',
                'formality', 'verbosity', 'humor', 'empathy', 'sarcasm', 'directness']
        self.values = [p.get(k, 50) for k in keys]
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        r = min(w, h) * 0.38
        n = 11

        # Grid
        pen = QPen(QColor(255, 255, 255, 20), 1)
        painter.setPen(pen)
        for s in [0.25, 0.5, 0.75, 1.0]:
            painter.drawEllipse(QPoint(int(cx), int(cy)), int(r*s), int(r*s))
        
        # Spokes
        for i in range(n):
            angle = (2 * math.pi / n) * i - math.pi / 2
            x2 = cx + math.cos(angle) * r
            y2 = cy + math.sin(angle) * r
            painter.drawLine(int(cx), int(cy), int(x2), int(y2))

        # Data
        points = []
        for i in range(n):
            angle = (2 * math.pi / n) * i - math.pi / 2
            v = (self.values[i] / 100.0) * r
            points.append(QPoint(int(cx + math.cos(angle) * v), int(cy + math.sin(angle) * v)))
        
        painter.setBrush(QBrush(QColor(232, 155, 56, 40)))
        painter.setPen(QPen(QColor(232, 155, 56, 180), 2))
        from PySide6.QtGui import QPolygon
        painter.drawPolygon(QPolygon(points))

        for pt in points:
            painter.setBrush(QBrush(QColor(232, 155, 56)))
            painter.drawEllipse(pt, 3, 3)

        # Labels
        labels = ['OPN', 'CON', 'EXT', 'AGR', 'NEU', 'FMR', 'VRB', 'HUM', 'EMP', 'SAR', 'DIR']
        painter.setPen(QColor(255, 255, 255, 80))
        font = QFont("Inter", 7)
        painter.setFont(font)
        for i in range(n):
            angle = (2 * math.pi / n) * i - math.pi / 2
            lx = cx + math.cos(angle) * (r + 14)
            ly = cy + math.sin(angle) * (r + 14)
            painter.drawText(int(lx)-10, int(ly)+4, labels[i])

# --- Tag List Widget ---
class TagList(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(4)
        
        self.list_widget = QListWidget()
        self.list_widget.setMaximumHeight(80)
        self.list_widget.setStyleSheet("QListWidget { background: #1a1918; border: 1px solid #2e2c28; border-radius: 4px; color: #ede8df; } QListWidget::item { padding: 2px; }")
        layout.addWidget(self.list_widget)
        
        btn_layout = QVBoxLayout()
        btn_add = QPushButton("+")
        btn_add.setFixedSize(24, 24)
        btn_add.setStyleSheet("QPushButton { background: #2e2c28; border: none; border-radius: 4px; color: #ede8df; font-weight: bold; } QPushButton:hover { background: #e89b38; color: #0d0c0b; }")
        btn_rem = QPushButton("-")
        btn_rem.setFixedSize(24, 24)
        btn_rem.setStyleSheet("QPushButton { background: #2e2c28; border: none; border-radius: 4px; color: #ede8df; font-weight: bold; } QPushButton:hover { background: #d4654a; }")
        
        btn_layout.addWidget(btn_add)
        btn_layout.addWidget(btn_rem)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        btn_add.clicked.connect(self.add_tag)
        btn_rem.clicked.connect(self.rem_tag)

    def add_tag(self):
        text, ok = QInputDialog.getText(self, "Add Tag", "Enter value:")
        if ok and text.strip():
            self.list_widget.addItem(text.strip())

    def rem_tag(self):
        row = self.list_widget.currentRow()
        if row >= 0: self.list_widget.takeItem(row)

    def get_data(self): return [self.list_widget.item(i).text() for i in range(self.list_widget.count())]
    
    def set_data(self, data_list):
        self.list_widget.clear()
        for item in data_list: self.list_widget.addItem(item)

# --- Main Window ---
class PersonaForge(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PersonaForge — AI Personality Architect")
        self.resize(1200, 750)
        self.personalities = []
        self.active_idx = -1
        self.data_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "personalityforge_data.json")
        
        self.init_ui()
        self.load_data()
        if self.personalities: self.select_personality(0)

    def init_ui(self):
        self.setStyleSheet("""
            QMainWindow { background: #0d0c0b; }
            QWidget { background: #0d0c0b; color: #ede8df; font-family: 'Inter', 'Segoe UI', sans-serif; font-size: 13px; }
            QGroupBox { border: 1px solid #2e2c28; border-radius: 6px; margin-top: 12px; padding-top: 16px; font-weight: bold; color: #8a8479; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; text-transform: uppercase; font-size: 11px; letter-spacing: 0.5px; }
            QLineEdit, QTextEdit, QPlainTextEdit { background: #1a1918; border: 1px solid #2e2c28; border-radius: 4px; padding: 6px; color: #ede8df; selection-background-color: #e89b38; }
            QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus { border: 1px solid #e89b38; }
            QPushButton { background: #1a1918; border: 1px solid #2e2c28; border-radius: 4px; padding: 6px 12px; color: #ede8df; font-weight: 600; }
            QPushButton:hover { border-color: #e89b38; color: #e89b38; }
            QSlider::groove:horizontal { height: 4px; background: #2e2c28; border-radius: 2px; }
            QSlider::handle:horizontal { background: #e89b38; width: 14px; height: 14px; margin: -5px 0; border-radius: 7px; }
            QSlider::sub-page:horizontal { background: #e89b38; border-radius: 2px; }
            QComboBox { background: #1a1918; border: 1px solid #2e2c28; border-radius: 4px; padding: 4px 8px; color: #ede8df; }
            QComboBox::drop-down { border: none; } QComboBox QAbstractItemView { background: #1a1918; color: #ede8df; selection-background-color: #e89b38; }
            QTabWidget::pane { border: 1px solid #2e2c28; border-radius: 4px; background: #0d0c0b; }
            QTabBar::tab { background: #141312; color: #8a8479; padding: 8px 16px; border: 1px solid #2e2c28; border-bottom: none; border-top-left-radius: 4px; border-top-right-radius: 4px; margin-right: 2px; font-weight: 600; text-transform: uppercase; font-size: 11px; }
            QTabBar::tab:selected { background: #0d0c0b; color: #e89b38; border-bottom: 2px solid #e89b38; }
            QListWidget { background: #141312; border: none; color: #ede8df; outline: none; }
            QListWidget::item { padding: 8px; border-bottom: 1px solid #1a1918; }
            QListWidget::item:selected { background: rgba(232, 155, 56, 0.15); color: #e89b38; }
            QLabel { background: transparent; border: none; }
        """)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0,0,0,0)
        main_layout.setSpacing(0)

        # Sidebar
        sidebar = QWidget()
        sidebar.setFixedWidth(250)
        sidebar.setStyleSheet("background: #141312; border-right: 1px solid #2e2c28;")
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(12,12,12,12)
        
        lbl = QLabel("<h2 style='color:#e89b38; margin:0;'>Persona<span style='color:#ede8df'>Forge</span></h2><p style='color:#5c5850; font-size:10px; margin:2px 0 10px;'>AI PERSONALITY ARCHITECT</p>")
        sb_layout.addWidget(lbl)
        
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search personalities...")
        self.search_box.textChanged.connect(self.filter_list)
        sb_layout.addWidget(self.search_box)

        btn_new = QPushButton("+ New Personality")
        btn_new.setStyleSheet("QPushButton { background: rgba(232,155,56,0.1); border: 1px dashed #e89b38; color: #e89b38; } QPushButton:hover { background: #e89b38; color: #0d0c0b; }")
        btn_new.clicked.connect(self.new_personality)
        sb_layout.addWidget(btn_new)

        self.list = QListWidget()
        self.list.currentRowChanged.connect(self.select_personality)
        sb_layout.addWidget(self.list)

        btn_layout = QHBoxLayout()
        b_exp = QPushButton("Export"); b_exp.clicked.connect(self.export_data)
        b_imp = QPushButton("Import"); b_imp.clicked.connect(self.import_data)
        btn_layout.addWidget(b_exp); btn_layout.addWidget(b_imp)
        sb_layout.addLayout(btn_layout)
        main_layout.addWidget(sidebar)

        # Splitter for Editor / Harness
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Editor Tabs
        self.tabs = QTabWidget()
        self.tab_identity = self.create_identity_tab()
        self.tab_traits = self.create_traits_tab()
        self.tab_comm = self.create_comm_tab()
        self.tab_voice = self.create_voice_tab()
        self.tab_values = self.create_values_tab()
        
        self.tabs.addTab(self.tab_identity, "Identity")
        self.tabs.addTab(self.tab_traits, "Traits")
        self.tabs.addTab(self.tab_comm, "Communication")
        self.tabs.addTab(self.tab_voice, "Voice")
        self.tabs.addTab(self.tab_values, "Values")
        splitter.addWidget(self.tabs)

        # Harness Panel
        harness_panel = QWidget()
        harness_panel.setFixedWidth(450)
        harness_panel.setStyleSheet("background: #141312; border-left: 1px solid #2e2c28;")
        hp_layout = QVBoxLayout(harness_panel)
        hp_layout.setContentsMargins(12,12,12,12)

        hp_header = QHBoxLayout()
        hp_header.addWidget(QLabel("<b>Harness Output</b>"))
        hp_header.addStretch()
        
        self.cb_format = QComboBox()
        self.cb_format.addItems(["structured", "claude", "chatgpt", "json"])
        self.cb_format.currentTextChanged.connect(self.generate_harness)
        hp_header.addWidget(self.cb_format)

        self.cb_strength = QComboBox()
        self.cb_strength.addItems(["light", "standard", "maximum"])
        self.cb_strength.currentTextChanged.connect(self.generate_harness)
        hp_header.addWidget(self.cb_strength)
        hp_layout.addLayout(hp_header)

        self.btn_lock = QPushButton("Auto-Generate (Locked)")
        self.btn_lock.setCheckable(True)
        self.btn_lock.setStyleSheet("QPushButton { font-size: 11px; padding: 4px 8px; } QPushButton:checked { background: rgba(232,155,56,0.2); border-color: #e89b38; color: #e89b38; }")
        self.btn_lock.clicked.connect(self.toggle_lock)
        hp_layout.addWidget(self.btn_lock)

        self.radar = RadarChart()
        hp_layout.addWidget(self.radar, alignment=Qt.AlignmentFlag.AlignCenter)

        self.harness_editor = QPlainTextEdit()
        self.harness_editor.setReadOnly(True)
        self.harness_editor.setStyleSheet("font-family: 'JetBrains Mono', 'Consolas', monospace; font-size: 12px; background: #0d0c0b;")
        hp_layout.addWidget(self.harness_editor)

        btn_copy = QPushButton("Copy Harness to Clipboard")
        btn_copy.setStyleSheet("QPushButton { background: #e89b38; color: #0d0c0b; font-weight: bold; } QPushButton:hover { background: #f0ad4e; }")
        btn_copy.clicked.connect(self.copy_harness)
        hp_layout.addWidget(btn_copy)

        splitter.addWidget(harness_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        main_layout.addWidget(splitter)

    def create_identity_tab(self):
        w = QWidget()
        layout = QFormLayout(w)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        self.inp_name = QLineEdit(); layout.addRow("Name", self.inp_name)
        self.inp_role = QLineEdit(); layout.addRow("Role", self.inp_role)
        self.inp_summary = QLineEdit(); layout.addRow("Summary", self.inp_summary)
        self.inp_backstory = QTextEdit(); self.inp_backstory.setFixedHeight(150); layout.addRow("Backstory", self.inp_backstory)
        for inp in [self.inp_name, self.inp_role, self.inp_summary, self.inp_backstory]:
            inp.textChanged.connect(self.save_current_state)
        return w

    def create_slider(self, label, layout):
        row = QHBoxLayout()
        lbl = QLabel(label)
        lbl.setFixedWidth(120)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(0, 100)
        val_lbl = QLabel("50")
        val_lbl.setFixedWidth(30)
        slider.valueChanged.connect(lambda v: val_lbl.setText(str(v)))
        slider.valueChanged.connect(self.save_current_state)
        row.addWidget(lbl); row.addWidget(slider); row.addWidget(val_lbl)
        layout.addLayout(row)
        return slider

    def create_traits_tab(self):
        w = QWidget(); scroll = QScrollArea(); scroll.setWidget(w); scroll.setWidgetResizable(True)
        layout = QVBoxLayout(w); layout.setContentsMargins(20, 20, 20, 20)
        
        grp_arch = QGroupBox("Quick Archetypes")
        arch_lay = QHBoxLayout()
        for name in ARCHETYPES:
            btn = QPushButton(name.replace("The ", ""))
            btn.clicked.connect(lambda checked, n=name: self.apply_archetype(n))
            arch_lay.addWidget(btn)
        grp_arch.setLayout(arch_lay)
        layout.addWidget(grp_arch)

        grp_b5 = QGroupBox("Big Five Dimensions")
        b5_lay = QVBoxLayout()
        self.sl_openness = self.create_slider("Openness", b5_lay)
        self.sl_conscientiousness = self.create_slider("Conscientiousness", b5_lay)
        self.sl_extraversion = self.create_slider("Extraversion", b5_lay)
        self.sl_agreeableness = self.create_slider("Agreeableness", b5_lay)
        self.sl_neuroticism = self.create_slider("Neuroticism", b5_lay)
        grp_b5.setLayout(b5_lay)
        layout.addWidget(grp_b5)
        layout.addStretch()
        return scroll

    def create_comm_tab(self):
        w = QWidget(); scroll = QScrollArea(); scroll.setWidget(w); scroll.setWidgetResizable(True)
        layout = QVBoxLayout(w); layout.setContentsMargins(20, 20, 20, 20)
        grp = QGroupBox("Communication Dimensions")
        lay = QVBoxLayout()
        self.sl_formality = self.create_slider("Formality", lay)
        self.sl_verbosity = self.create_slider("Verbosity", lay)
        self.sl_humor = self.create_slider("Humor", lay)
        self.sl_empathy = self.create_slider("Empathy", lay)
        self.sl_sarcasm = self.create_slider("Sarcasm", lay)
        self.sl_directness = self.create_slider("Directness", lay)
        grp.setLayout(lay)
        layout.addWidget(grp)
        
        grp2 = QGroupBox("Tone Modifiers")
        lay2 = QVBoxLayout()
        self.tone_tags = TagList()
        lay2.addWidget(self.tone_tags)
        grp2.setLayout(lay2)
        layout.addWidget(grp2)
        layout.addStretch()
        return scroll

    def create_voice_tab(self):
        w = QWidget(); scroll = QScrollArea(); scroll.setWidget(w); scroll.setWidgetResizable(True)
        layout = QVBoxLayout(w); layout.setContentsMargins(20, 20, 20, 20)
        
        self.catchphrases = TagList(); layout.addWidget(self.create_tag_group("Catchphrases", self.catchphrases))
        self.speech_patterns = TagList(); layout.addWidget(self.create_tag_group("Speech Patterns", self.speech_patterns))
        self.forbidden_phrases = TagList(); layout.addWidget(self.create_tag_group("Forbidden Phrases", self.forbidden_phrases))
        self.mannerisms = TagList(); layout.addWidget(self.create_tag_group("Mannerisms", self.mannerisms))
        
        # Examples Container
        grp_ex = QGroupBox("Example Dialogues")
        self.examples_layout = QVBoxLayout()
        self.examples_widgets = []
        btn_add_ex = QPushButton("+ Add Example")
        btn_add_ex.clicked.connect(self.add_example)
        self.examples_layout.addWidget(btn_add_ex)
        grp_ex.setLayout(self.examples_layout)
        layout.addWidget(grp_ex)
        layout.addStretch()
        return scroll

    def create_tag_group(self, title, tag_widget):
        grp = QGroupBox(title)
        lay = QVBoxLayout()
        lay.addWidget(tag_widget)
        grp.setLayout(lay)
        return grp

    def add_example(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0,0,0,10)
        u_inp = QLineEdit(); u_inp.setPlaceholderText("User message...")
        a_inp = QLineEdit(); a_inp.setPlaceholderText("Personality response...")
        btn_rem = QPushButton("Remove Example")
        btn_rem.setStyleSheet("QPushButton { color: #d4654a; }")
        
        def rem():
            self.examples_widgets.remove(w)
            w.deleteLater()
            self.save_current_state()
        btn_rem.clicked.connect(rem)
        
        u_inp.textChanged.connect(self.save_current_state)
        a_inp.textChanged.connect(self.save_current_state)
        
        lay.addWidget(QLabel("User:")); lay.addWidget(u_inp)
        lay.addWidget(QLabel("AI:")); lay.addWidget(a_inp)
        lay.addWidget(btn_rem)
        
        self.examples_widgets.append(w)
        self.examples_layout.insertWidget(self.examples_layout.count()-1, w)

    def create_values_tab(self):
        w = QWidget(); scroll = QScrollArea(); scroll.setWidget(w); scroll.setWidgetResizable(True)
        layout = QVBoxLayout(w); layout.setContentsMargins(20, 20, 20, 20)
        self.core_values = TagList(); layout.addWidget(self.create_tag_group("Core Values", self.core_values))
        self.boundaries = TagList(); layout.addWidget(self.create_tag_group("Boundaries", self.boundaries))
        
        grp = QGroupBox("Opinions & Beliefs")
        lay = QVBoxLayout()
        self.opinions_list = QListWidget()
        self.opinions_list.setMaximumHeight(120)
        btn_op = QHBoxLayout()
        btn_add_op = QPushButton("+ Opinion"); btn_rem_op = QPushButton("- Opinion")
        btn_add_op.clicked.connect(lambda: self.opinions_list.addItem(""))
        btn_rem_op.clicked.connect(lambda: self.opinions_list.takeItem(self.opinions_list.currentRow()) if self.opinions_list.currentRow()>=0 else None)
        btn_op.addWidget(btn_add_op); btn_op.addWidget(btn_rem_op)
        lay.addWidget(self.opinions_list); lay.addLayout(btn_op)
        grp.setLayout(lay)
        layout.addWidget(grp)
        layout.addStretch()
        return scroll

    # --- State Management ---
    def get_current_data(self):
        if self.active_idx < 0: return None
        p = self.personalities[self.active_idx]
        p['name'] = self.inp_name.text()
        p['role'] = self.inp_role.text()
        p['summary'] = self.inp_summary.text()
        p['backstory'] = self.inp_backstory.toPlainText()
        
        p['openness'] = self.sl_openness.value()
        p['conscientiousness'] = self.sl_conscientiousness.value()
        p['extraversion'] = self.sl_extraversion.value()
        p['agreeableness'] = self.sl_agreeableness.value()
        p['neuroticism'] = self.sl_neuroticism.value()
        
        p['formality'] = self.sl_formality.value()
        p['verbosity'] = self.sl_verbosity.value()
        p['humor'] = self.sl_humor.value()
        p['empathy'] = self.sl_empathy.value()
        p['sarcasm'] = self.sl_sarcasm.value()
        p['directness'] = self.sl_directness.value()
        
        p['tone_modifiers'] = self.tone_tags.get_data()
        p['catchphrases'] = self.catchphrases.get_data()
        p['speech_patterns'] = self.speech_patterns.get_data()
        p['forbidden_phrases'] = self.forbidden_phrases.get_data()
        p['mannerisms'] = self.mannerisms.get_data()
        p['core_values'] = self.core_values.get_data()
        p['boundaries'] = self.boundaries.get_data()
        
        opinions = []
        for i in range(self.opinions_list.count()):
            item = self.opinions_list.item(i)
            opinions.append(item.text())
        p['opinions'] = opinions if opinions else [""]
        
        examples = []
        for ex_w in self.examples_widgets:
            u_inp = ex_w.findChild(QLineEdit)
            a_inp = ex_w.findChildren(QLineEdit)[1]
            examples.append({"user": u_inp.text(), "ai": a_inp.text()})
        p['examples'] = examples if examples else [{"user": "", "ai": ""}]
        
        p['harness_format'] = self.cb_format.currentText()
        p['harness_strength'] = self.cb_strength.currentText()
        return p

    def load_ui_from_data(self, p):
        self.blockSignals(True) # Prevent triggering save while loading
        
        self.inp_name.setText(p.get('name', ''))
        self.inp_role.setText(p.get('role', ''))
        self.inp_summary.setText(p.get('summary', ''))
        self.inp_backstory.setPlainText(p.get('backstory', ''))
        
        self.sl_openness.setValue(p.get('openness', 50))
        self.sl_conscientiousness.setValue(p.get('conscientiousness', 50))
        self.sl_extraversion.setValue(p.get('extraversion', 50))
        self.sl_agreeableness.setValue(p.get('agreeableness', 50))
        self.sl_neuroticism.setValue(p.get('neuroticism', 50))
        
        self.sl_formality.setValue(p.get('formality', 50))
        self.sl_verbosity.setValue(p.get('verbosity', 50))
        self.sl_humor.setValue(p.get('humor', 30))
        self.sl_empathy.setValue(p.get('empathy', 50))
        self.sl_sarcasm.setValue(p.get('sarcasm', 20))
        self.sl_directness.setValue(p.get('directness', 50))
        
        self.tone_tags.set_data(p.get('tone_modifiers', []))
        self.catchphrases.set_data(p.get('catchphrases', []))
        self.speech_patterns.set_data(p.get('speech_patterns', []))
        self.forbidden_phrases.set_data(p.get('forbidden_phrases', []))
        self.mannerisms.set_data(p.get('mannerisms', []))
        self.core_values.set_data(p.get('core_values', []))
        self.boundaries.set_data(p.get('boundaries', []))
        
        self.opinions_list.clear()
        for op in p.get('opinions', [""]): self.opinions_list.addItem(op)
        
        # Clear dynamic examples
        for w in self.examples_widgets: w.deleteLater()
        self.examples_widgets.clear()
        for ex in p.get('examples', [{"user":"", "ai":""}]):
            self.add_example()
            u_inp = self.examples_widgets[-1].findChild(QLineEdit)
            a_inp = self.examples_widgets[-1].findChildren(QLineEdit)[1]
            u_inp.setText(ex.get('user', ''))
            a_inp.setText(ex.get('ai', ''))
            
        self.cb_format.setCurrentText(p.get('harness_format', 'structured'))
        self.cb_strength.setCurrentText(p.get('harness_strength', 'standard'))
        self.btn_lock.setChecked(p.get('harness_locked', False))
        
        self.radar.set_values(p)
        self.blockSignals(False)

    def blockSignals(self, b):
        widgets = [self.inp_name, self.inp_role, self.inp_summary, self.inp_backstory,
                    self.sl_openness, self.sl_conscientiousness, self.sl_extraversion, 
                    self.sl_agreeableness, self.sl_neuroticism, self.sl_formality, 
                    self.sl_verbosity, self.sl_humor, self.sl_empathy, self.sl_sarcasm, 
                    self.sl_directness, self.cb_format, self.cb_strength]
        for w in widgets: w.blockSignals(b)

    def save_current_state(self):
        if self.active_idx < 0: return
        p = self.get_current_data()
        if not self.btn_lock.isChecked():
            self.generate_harness()
        self.save_data()

    def generate_harness(self):
        if self.active_idx < 0: return
        p = self.get_current_data()
        if not self.btn_lock.isChecked() or not p.get('harness_custom'):
            fmt = self.cb_format.currentText()
            strength = self.cb_strength.currentText()
            text = GENERATORS.get(fmt, gen_structured)(p, strength)
            self.harness_editor.setPlainText(text)
        else:
            self.harness_editor.setPlainText(p.get('harness_custom', ''))

    def toggle_lock(self, checked):
        if self.active_idx < 0: return
        self.personalities[self.active_idx]['harness_locked'] = checked
        self.btn_lock.setText("Manual Edit (Unlocked)" if checked else "Auto-Generate (Locked)")
        self.harness_editor.setReadOnly(not checked)
        if not checked:
            self.personalities[self.active_idx]['harness_custom'] = ""
            self.generate_harness()
        else:
            self.harness_editor.setPlainText(self.personalities[self.active_idx].get('harness_custom', self.harness_editor.toPlainText()))

    def apply_archetype(self, name):
        arch = ARCHETYPES[name]
        self.sl_openness.setValue(arch['openness'])
        self.sl_conscientiousness.setValue(arch['conscientiousness'])
        self.sl_extraversion.setValue(arch['extraversion'])
        self.sl_agreeableness.setValue(arch['agreeableness'])
        self.sl_neuroticism.setValue(arch['neuroticism'])
        self.sl_formality.setValue(arch['formality'])
        self.sl_verbosity.setValue(arch['verbosity'])
        self.sl_humor.setValue(arch['humor'])
        self.sl_empathy.setValue(arch['empathy'])
        self.sl_sarcasm.setValue(arch['sarcasm'])
        self.sl_directness.setValue(arch['directness'])
        self.tone_tags.set_data(arch.get('tone_modifiers', []))
        self.save_current_state()

    # --- CRUD & File I/O ---
    def new_personality(self):
        p = copy.deepcopy(DEFAULT_PERSONALITY)
        p['name'] = "New Personality"
        self.personalities.insert(0, p)
        self.refresh_list()
        self.list.setCurrentRow(0)
        self.inp_name.selectAll()
        self.inp_name.setFocus()

    def select_personality(self, idx):
        if idx == self.active_idx or idx < 0: return
        self.active_idx = idx
        self.load_ui_from_data(self.personalities[idx])
        self.generate_harness()

    def refresh_list(self):
        self.list.clear()
        for p in self.personalities:
            self.list.addItem(f"{p['name'] or 'Unnamed'} ({p['role'] or 'No Role'})")

    def filter_list(self, text):
        for i in range(self.list.count()):
            item = self.list.item(i)
            item.setHidden(text.lower() not in item.text().lower())

    def export_data(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Personalities", "", "JSON Files (*.json)")
        if path:
            with open(path, 'w') as f: json.dump(self.personalities, f, indent=2)

    def import_data(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Personalities", "", "JSON Files (*.json)")
        if path:
            with open(path, 'r') as f: data = json.load(f)
            if isinstance(data, list):
                self.personalities.extend(data)
                self.refresh_list()

    def save_data(self):
        if self.active_idx >= 0:
            self.get_current_data() # Ensure current UI state is synced
        try:
            with open(self.data_path, 'w') as f: json.dump(self.personalities, f, indent=2)
        except Exception as e: pass

    def load_data(self):
        if os.path.exists(self.data_path):
            try:
                with open(self.data_path, 'r') as f: self.personalities = json.load(f)
            except: self.personalities = copy.deepcopy(PRESETS)
        else:
            self.personalities = copy.deepcopy(PRESETS)
        self.refresh_list()

    def copy_harness(self):
        QApplication.clipboard().setText(self.harness_editor.toPlainText())

    def closeEvent(self, event):
        self.save_data()
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = PersonaForge()
    window.show()
    sys.exit(app.exec())