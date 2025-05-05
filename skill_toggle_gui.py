import os, sys, re, random, json
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTabWidget, QScrollArea, QLineEdit,
    QFileDialog, QMessageBox, QGridLayout, QListWidget, QListWidgetItem,
    QStackedWidget, QSizePolicy, QGraphicsOpacityEffect
)
from PySide6.QtGui import QIcon, QPixmap, QAction, QActionGroup
from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve

PROFILE_DIR = "profiles"
ICON_DIR    = "skill_icons"
MAX_SKILLS  = 255
os.makedirs(PROFILE_DIR, exist_ok=True)

THEMES = {
    "Dark":  {"bg":"#1e1e1e","fg":"#ffffff","btn_on":"#61afef","btn_off":"#4b4b4b"},
    "Light": {"bg":"#ffffff","fg":"#000000","btn_on":"#6ab04c","btn_off":"#bbbbbb"}
}

def prettify(raw_name: str) -> str:
    tokens = re.split(r'[_\s]+', raw_name)
    words = []
    for tok in tokens:
        parts = re.findall(r'[A-Z](?:[a-z]+|[A-Z]*(?=[A-Z]|$))', tok)
        words.extend(parts or [tok])
    return ' '.join(words)

class SkillButton(QWidget):
    toggled = Signal(bool)
    def __init__(self, name, enabled, theme, icon=None):
        super().__init__()
        self.name, self.enabled, self.theme = name, enabled, theme
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(8)
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(32,32)
        self.icon_label.setScaledContents(True)
        if icon:
            self.icon_label.setPixmap(icon.pixmap(32,32))
        layout.addWidget(self.icon_label)
        self.button = QPushButton(name)
        self.button.setCheckable(True)
        self.button.setChecked(enabled)
        self.button.clicked.connect(self.toggle_state)
        layout.addWidget(self.button, stretch=1)
        self.update_style()

    def toggle_state(self):
        self.enabled = not self.enabled
        self.button.setChecked(self.enabled)
        self.update_style()
        self.toggled.emit(self.enabled)

    def update_style(self):
        color = self.theme['btn_on'] if self.enabled else self.theme['btn_off']
        fg = self.theme['fg']
        self.button.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: {fg};
                padding: 6px;
                border: none;
                text-align: left;
            }}
        """)

    def set_opacity(self, level: float):
        current_effect = self.graphicsEffect()
        if not current_effect or not isinstance(current_effect, QGraphicsOpacityEffect):
            effect = QGraphicsOpacityEffect(self)
            self.setGraphicsEffect(effect)
        else:
            effect = current_effect

        self.anim = QPropertyAnimation(effect, b"opacity")
        self.anim.setDuration(250)
        self.anim.setStartValue(effect.opacity())
        self.anim.setEndValue(level)
        self.anim.setEasingCurve(QEasingCurve.InOutQuad)
        self.anim.start()

class SkillGridTile(QWidget):
    toggled = Signal(bool)
    def __init__(self, name, enabled, theme, icon=None):
        super().__init__()
        self.name, self.enabled, self.theme = name, enabled, theme
        self.setFixedSize(128,128)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6,6,6,6)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignCenter)
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(64,64)
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setScaledContents(True)
        if icon:
            self.icon_label.setPixmap(icon.pixmap(64,64))
        self.label = QLabel(name)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setWordWrap(True)
        layout.addWidget(self.icon_label)
        layout.addWidget(self.label)
        self.setCursor(Qt.PointingHandCursor)
        self.mousePressEvent = self.toggle_state
        self.update_style()

    def toggle_state(self, event=None):
        self.enabled = not self.enabled
        self.update_style()
        self.toggled.emit(self.enabled)

    def update_style(self):
        color = self.theme['btn_on'] if self.enabled else self.theme['btn_off']
        fg = self.theme['fg']
        self.setStyleSheet(f"background-color: {color}; color: {fg}; border-radius: 8px;")
        self.label.setStyleSheet(f"color: {fg}; font-size: 11px;")

    def set_opacity(self, level: float):
        current_effect = self.graphicsEffect()
        if not current_effect or not isinstance(current_effect, QGraphicsOpacityEffect):
            effect = QGraphicsOpacityEffect(self)
            self.setGraphicsEffect(effect)
        else:
            effect = current_effect

        self.anim = QPropertyAnimation(effect, b"opacity")
        self.anim.setDuration(250)
        self.anim.setStartValue(effect.opacity())
        self.anim.setEndValue(level)
        self.anim.setEasingCurve(QEasingCurve.InOutQuad)
        self.anim.start()

class SkillToggleApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Skill Toggle Manager (Qt)')
        self.resize(1000, 720)

        # State
        self.file_path = None
        self.skill_data = {}
        self.skill_buttons = {}
        self.skill_icons = {}
        self.enabled_count = 0
        self.theme_name = 'Dark'
        self.theme = THEMES[self.theme_name]
        self.view_mode = 'List'      # 'List', 'Grid', 'Compact'
        self.sort_order = 'asc'      # 'asc', 'desc', or None
        self.layout_mode = 'Sidebar' # 'Tabs' or 'Sidebar'

        # Load and Build
        self.load_icons()
        self.setup_menus()
        self.build_ui()
        self.refresh_ui()
        self.apply_theme()

    def setup_menus(self):
        mb = self.menuBar()

        # File menu
        file_menu = mb.addMenu('File')
        open_act = QAction('Open…', self)
        open_act.triggered.connect(self.open_skill_file)
        file_menu.addAction(open_act)

        # Profile menu
        prof_menu = mb.addMenu('Profile')
        load_act = QAction('Load Profile…', self)
        load_act.triggered.connect(self.load_profile)
        save_act = QAction('Save Profile…', self)
        save_act.triggered.connect(self.save_profile)
        prof_menu.addAction(load_act)
        prof_menu.addAction(save_act)

        # Settings menu
        set_menu = mb.addMenu('Settings')

        theme_menu = set_menu.addMenu('Theme')
        tgroup = QActionGroup(self)
        for name in THEMES:
            act = QAction(name, self, checkable=True)
            act.setChecked(name == self.theme_name)
            act.triggered.connect(lambda _, n=name: self.set_theme(n))
            tgroup.addAction(act)
            theme_menu.addAction(act)

        view_menu = set_menu.addMenu('View Mode')
        vgroup = QActionGroup(self)
        for mode in ('List', 'Grid', 'Compact'):
            act = QAction(mode, self, checkable=True)
            act.setChecked(mode == self.view_mode)
            act.triggered.connect(lambda _, m=mode: self.change_view_mode(m))
            vgroup.addAction(act)
            view_menu.addAction(act)

        sort_menu = set_menu.addMenu('Sort')
        sort_az = QAction('Sort A → Z', self)
        sort_az.triggered.connect(lambda: self.set_sort_order('asc'))
        sort_za = QAction('Sort Z → A', self)
        sort_za.triggered.connect(lambda: self.set_sort_order('desc'))
        sort_reset = QAction('Reset Order', self)
        sort_reset.triggered.connect(lambda: self.set_sort_order(None))
        for act in (sort_az, sort_za, sort_reset):
            sort_menu.addAction(act)

        layout_menu = set_menu.addMenu('Category Layout')
        lg = QActionGroup(self)
        for layout in ('Tabs', 'Sidebar'):
            act = QAction(layout, self, checkable=True)
            act.setChecked(layout == self.layout_mode)
            act.triggered.connect(lambda _, l=layout: self.set_layout_mode(l))
            lg.addAction(act)
            layout_menu.addAction(act)

    def set_theme(self, name):
        self.theme_name = name
        self.theme = THEMES[name]
        self.apply_theme()

    def set_sort_order(self, order):
        self.sort_order = order
        self.refresh_ui()

    def set_layout_mode(self, mode):
        self.layout_mode = mode
        self.refresh_ui()

    def change_view_mode(self, mode):
        self.view_mode = mode
        self.refresh_ui()

    def build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        self.main_layout = QVBoxLayout(central)

        # Search
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText('Search skills…')
        self.search_input.textChanged.connect(self.filter_skills)
        self.main_layout.addWidget(self.search_input)

        # Content area (Tabs or Sidebar injected later)
        self.content_area = QWidget()
        self.content_layout = QVBoxLayout(self.content_area)
        self.main_layout.addWidget(self.content_area)

        # Status
        self.status_label = QLabel()
        self.main_layout.addWidget(self.status_label)

        # Actions
        actions = QHBoxLayout()
        self.random_btn = QPushButton('🎲 Randomize')
        self.random_btn.clicked.connect(self.randomize_skills)
        self.clear_btn = QPushButton('🗑️ Clear All')
        self.clear_btn.clicked.connect(self.clear_all_skills)
        self.save_btn = QPushButton('💾 Save Changes')
        self.save_btn.clicked.connect(self.save_to_file)
        for w in (self.random_btn, self.clear_btn, self.save_btn):
            actions.addWidget(w)
        self.main_layout.addLayout(actions)

    def apply_theme(self):
        self.setStyleSheet(f"background-color: {self.theme['bg']}; color: {self.theme['fg']};")
        for btn in self.skill_buttons.values():
            btn.theme = self.theme
            btn.update_style()

    def refresh_ui(self):
        # Reset previous content
        for i in reversed(range(self.content_layout.count())):
            widget = self.content_layout.itemAt(i).widget()
            if widget: widget.setParent(None)

        self.skill_buttons = {}
        has_data = bool(self.skill_data)
        self.search_input.setEnabled(has_data)
        for btn in (self.random_btn, self.clear_btn, self.save_btn):
            btn.setEnabled(has_data)

        if not has_data:
            msg = QLabel('No skills file loaded.\n\nUse File → Open… to select a .txt file.')
            msg.setAlignment(Qt.AlignCenter)
            self.content_layout.addWidget(msg)
            self.status_label.clear()
            return

        categories = list(self.skill_data.items())
        if self.layout_mode == 'Tabs':
            tab_widget = QTabWidget()
            self.content_layout.addWidget(tab_widget)
        elif self.layout_mode == 'Sidebar':
            container = QWidget()
            layout = QHBoxLayout(container)
            list_widget = QListWidget()
            stack = QStackedWidget()
            layout.addWidget(list_widget)
            layout.addWidget(stack, stretch=1)
            self.content_layout.addWidget(container)

        for cat, skills in categories:
            display_skills = skills.copy()
            if self.sort_order:
                display_skills.sort(
                    key=lambda tup: prettify(tup[1]).lower(),
                    reverse=(self.sort_order == 'desc')
                )

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            content = QWidget()
            layout = QGridLayout() if self.view_mode == 'Grid' else QVBoxLayout()
            if self.view_mode == 'Compact':
                layout.setSpacing(2)

            for idx, (ln, nm, en) in enumerate(display_skills):
                key = nm.lower().replace('_', '').replace(' ', '')
                icon = self.skill_icons.get(key)
                disp = prettify(nm)
                widget_cls = SkillGridTile if self.view_mode == 'Grid' else SkillButton
                widget = widget_cls(disp, en, self.theme, icon)
                widget.toggled.connect(lambda state, c=cat, name=nm: self._toggle_named_skill(c, name, state))
                self.skill_buttons[(cat, nm)] = widget
                if self.view_mode == 'Grid':
                    r, c = divmod(idx, 4)
                    layout.addWidget(widget, r, c)
                else:
                    layout.addWidget(widget)

            content.setLayout(layout)
            content.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
            scroll.setWidget(content)

            if self.layout_mode == 'Tabs':
                tab_widget.addTab(scroll, cat)
            elif self.layout_mode == 'Sidebar':
                item = QListWidgetItem(cat)
                list_widget.addItem(item)
                stack.addWidget(scroll)

        if self.layout_mode == 'Sidebar':
            def on_tab_change(index):
                stack.setCurrentIndex(index)
            list_widget.currentRowChanged.connect(on_tab_change)
            list_widget.setCurrentRow(0)

        self.update_counter()

    def update_counter(self):
        count = sum(1 for cat in self.skill_data for _, _, e in self.skill_data[cat] if e)
        self.status_label.setText(f'Enabled: {count} / {MAX_SKILLS}')

    def enforce_skill_limit(self):
        enabled_count = sum(1 for cat_skills in self.skill_data.values()
                            for _, _, en in cat_skills if en)
        at_limit = enabled_count >= MAX_SKILLS

        for (cat, name), widget in self.skill_buttons.items():
            is_enabled = any(nm == name and en for _, nm, en in self.skill_data[cat])
            should_be_active = not at_limit or is_enabled

            if hasattr(widget, 'button'):  # SkillButton
                widget.button.setEnabled(should_be_active)
            else:
                widget.setEnabled(should_be_active)

            # Apply visual dimming
            if hasattr(widget, 'set_opacity'):
                widget.set_opacity(1.0 if should_be_active else 0.4)

    def _toggle_named_skill(self, cat, name, state):
        for i, (ln, nm, _) in enumerate(self.skill_data[cat]):
            if nm == name:
                self.skill_data[cat][i] = (ln, nm, state)
                break
        self.update_counter()
        self.enforce_skill_limit()

    def filter_skills(self, q):
        q = q.lower()
        for (cat, name), widget in self.skill_buttons.items():
            _, nm, _ = next((s for s in self.skill_data[cat] if s[1] == name), (None, None, None))
            widget.setVisible(q in nm.lower())

    def open_skill_file(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Open Skills File', '.', 'Text Files (*.txt)')
        if not path:
            return
        self.file_path = path
        self.load_skills(path)
        self.refresh_ui()

    def load_icons(self):
        if not os.path.isdir(ICON_DIR): return
        for fn in os.listdir(ICON_DIR):
            if fn.lower().endswith(('.png', '.gif')):
                key = os.path.splitext(fn)[0].lower()
                px = QPixmap(os.path.join(ICON_DIR, fn))
                self.skill_icons[key] = QIcon(px)

    def load_skills(self, path):
        lines = open(path, 'r', encoding='utf-8').readlines()
        self.skill_data = {}
        cur = None
        pat = re.compile(r'^(\s*)(//\s*)?(SID_[A-Za-z0-9_]+)(.*)$')
        for i, raw in enumerate(lines):
            st = raw.strip()
            if st.startswith('////////'):
                cat = re.sub(r'(?i)skills', '', st.strip('/ ')).strip().title()
                self.skill_data[cat] = []
                cur = cat
                continue
            m = pat.match(raw)
            if m and cur:
                _, cm, tok, _ = m.groups()
                en = (cm is None)
                nm = tok[len('SID_'):]
                self.skill_data[cur].append((i, nm, en))

    def randomize_skills(self):
        all_keys = [(c, i) for c in self.skill_data for i in range(len(self.skill_data[c]))]
        random.shuffle(all_keys)
        for c, i in all_keys:
            ln, nm, _ = self.skill_data[c][i]
            self.skill_data[c][i] = (ln, nm, False)
        for c, i in all_keys[:MAX_SKILLS]:
            ln, nm, _ = self.skill_data[c][i]
            self.skill_data[c][i] = (ln, nm, True)
        
        self.refresh_ui()
        self.enforce_skill_limit()

    def clear_all_skills(self):
        for cat in self.skill_data:
            for idx in range(len(self.skill_data[cat])):
                ln, nm, _ = self.skill_data[cat][idx]
                self.skill_data[cat][idx] = (ln, nm, False)
        self.refresh_ui()

    def save_to_file(self):
        if not self.file_path:
            return
        try:
            lines = open(self.file_path, 'r', encoding='utf-8').readlines()
            for cat, skills in self.skill_data.items():
                for i, _, en in skills:
                    orig = lines[i]
                    if orig.lstrip().startswith('////////'):
                        continue
                    if en:
                        new = re.sub(r'^(\s*)//\s*', r'\1', orig, 1)
                    else:
                        if re.match(r'^\s*//', orig):
                            new = orig
                        else:
                            new = re.sub(r'^(\s*)', r'\1// ', orig, 1)
                    lines[i] = new
            with open(self.file_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            QMessageBox.information(self, 'Saved', 'Skill file updated.')
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to save:\n{e}')

    def save_profile(self):
        if not self.skill_data:
            return
        path, _ = QFileDialog.getSaveFileName(self, 'Save Profile As', PROFILE_DIR, 'JSON (*.json)')
        if not path:
            return
        data = {cat: [en for _, _, en in self.skill_data[cat]] for cat in self.skill_data}
        with open(path, 'w') as f:
            json.dump(data, f)
        QMessageBox.information(self, 'Saved', 'Profile saved.')

    def load_profile(self):
        if not self.skill_data:
            QMessageBox.warning(self, 'Warning', 'Load a skills file first.')
            return
        path, _ = QFileDialog.getOpenFileName(self, 'Load Profile', PROFILE_DIR, 'JSON (*.json)')
        if not path:
            return
        prof = json.load(open(path))
        for cat, vals in prof.items():
            if cat not in self.skill_data:
                continue
            for idx, val in enumerate(vals):
                if idx < len(self.skill_data[cat]):
                    ln, nm, _ = self.skill_data[cat][idx]
                    self.skill_data[cat][idx] = (ln, nm, val)
        self.refresh_ui()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = SkillToggleApp()
    win.show()
    sys.exit(app.exec())