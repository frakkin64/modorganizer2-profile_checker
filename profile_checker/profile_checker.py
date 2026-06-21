import os
import mobase
from PyQt6.QtWidgets import (QMessageBox, QMainWindow, QDialog, QVBoxLayout, 
                             QLabel, QListWidget, QAbstractItemView, 
                             QDialogButtonBox, QTextBrowser, QPushButton, QHBoxLayout, QApplication)
from PyQt6.QtGui import QIcon

class MultiModSelectionDialog(QDialog):
    """Custom popup window that presents a scrollable, multi-selectable list of mods."""
    def __init__(self, mods, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Mods to Check")
        self.resize(450, 400)
        
        layout = QVBoxLayout(self)
        
        label = QLabel("Hold Ctrl (individual) or Shift (range) to select multiple mods:", self)
        layout.addWidget(label)
        
        self.list_widget = QListWidget(self)
        
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        
        self.list_widget.addItems(mods)
        layout.addWidget(self.list_widget)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_selected_mods(self):
        return [item.text() for item in self.list_widget.selectedItems()]


class ConflictReportDialog(QDialog):
    """Custom results window featuring rich text display and clipboard copying capabilities."""
    def __init__(self, html_text, plain_text, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Mod Conflict Review")
        self.resize(500, 450)
        self.plain_text_data = plain_text
        
        layout = QVBoxLayout(self)
        
        self.text_browser = QTextBrowser(self)
        self.text_browser.setHtml(html_text)
        layout.addWidget(self.text_browser)
        
        button_layout = QHBoxLayout()
        
        self.copy_btn = QPushButton("📋 Copy to Clipboard", self)
        self.copy_btn.clicked.connect(self.copy_to_clipboard)
        button_layout.addWidget(self.copy_btn)
        
        close_btn = QPushButton("Close", self)
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)

    def copy_to_clipboard(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.plain_text_data)
        
        self.copy_btn.setText("✓ Copied!")
        self.copy_btn.setEnabled(False)


class ProfileCheckerPlugin(mobase.IPluginTool):

    def __init__(self):
        super().__init__()
        self.__organizer: mobase.IOrganizer = None
        self.__parentWidget: QMainWindow = None

    def init(self, organizer: mobase.IOrganizer) -> bool:
        self.__organizer = organizer
        return True

    def name(self) -> str:
        return "CrossProfileModChecker"

    def author(self) -> str:
        return "frakkin64"

    def description(self) -> str:
        return "Checks if selected mods are active in other profiles before deletion."

    def version(self) -> mobase.VersionInfo:
        return mobase.VersionInfo(1, 0, 0, mobase.ReleaseType.FINAL)

    def isActive(self) -> bool:
        return True

    def settings(self) -> list[mobase.PluginSetting]:
        return []

    def displayName(self) -> str:
        return "Cross-Profile Mod Checker"

    def tooltip(self) -> str:
        return "Scans all other profiles to see if selected mods are enabled."

    def icon(self) -> QIcon:
        return QIcon() 

    def setParentWidget(self, widget: QMainWindow):
        self.__parentWidget = widget

    def display(self):
        # Fetch mod list, filter out separators
        try:
            raw_mods = self.__organizer.modList().allMods()
            filtered_mods = []
            
            for mod_name in raw_mods:
                if not mod_name or not mod_name.strip():
                    continue
                
                mod_object = self.__organizer.modList().getMod(mod_name)
                if mod_object:
                    ## skip separators
                    if hasattr(mod_object, "isSeparator") and mod_object.isSeparator():
                        continue

                    ## skip backups
                    if hasattr(mod_object, "isBackup") and mod_object.isBackup():
                        continue

                    ## skip overwrite
                    if hasattr(mod_object, "isOverwrite") and mod_object.isOverwrite():
                        continue
                    
                    ## skip unmanaged
                    if hasattr(mod_object, "isForeign") and mod_object.isForeign():
                       continue
                    
                filtered_mods.append(mod_name)
                
            all_mods = sorted(filtered_mods, key=str.casefold)
            
            if not all_mods:
                QMessageBox.information(self.__parentWidget, "No Mods Found", "No valid installed mods found in this instance.")
                return
        except Exception as e:
            QMessageBox.critical(self.__parentWidget, "API Error", f"Failed to fetch mod data: {str(e)}")
            return

        # Show mod list multi-select dialogue
        dialog = MultiModSelectionDialog(all_mods, self.__parentWidget)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_mods = dialog.get_selected_mods()
        else:
            return

        if not selected_mods:
            QMessageBox.information(self.__parentWidget, "No Selection", "No mods were selected.")
            return

        # Get profiles folder for current instance
        current_profile_name = self.__organizer.profile().name()
        base_instance_path = self.__organizer.basePath()
        profiles_path = os.path.join(base_instance_path, "profiles")

        if not os.path.exists(profiles_path):
            QMessageBox.critical(self.__parentWidget, "Directory Error", f"Profiles path not found at: {profiles_path}")
            return

        # Map to track conflicts
        conflicts = {mod: [] for mod in selected_mods}

        # Scan profiles
        try:
            for profile_name in os.listdir(profiles_path):
                modlist_file = os.path.join(profiles_path, profile_name, "modlist.txt")
                
                if os.path.exists(modlist_file):
                    with open(modlist_file, "r", encoding="utf-8") as f:
                        for line in f:
                            cleaned_line = line.strip()
                            for mod in selected_mods:
                                if cleaned_line == f"+{mod}":
                                    conflicts[mod].append(profile_name)
        except Exception as e:
            QMessageBox.critical(self.__parentWidget, "Error", f"Could not read profile configurations: {str(e)}")
            return

        # Generate report output in HTML & plain text
        unsafe_html = []
        safe_html = []
        
        unsafe_plain = []
        safe_plain = []

        for mod, profiles in conflicts.items():
            if profiles:
                profiles_list = ", ".join(profiles)
                unsafe_html.append(f"• <b>{mod}</b> is active in: <i>{profiles_list}</i>")
                unsafe_plain.append(f"- [CONFLICT] {mod} (Active in: {profiles_list})")
            else:
                safe_html.append(f"• {mod}")
                safe_plain.append(f"- [SAFE] {mod}")

        html_chunks = []
        plain_chunks = []

        if unsafe_html:
            html_chunks.append("<h3>⚠️ Conflicted Mods (Do Not Delete):</h3>")
            html_chunks.append("<br>".join(unsafe_html))
            
            plain_chunks.append("⚠️ Conflicted Mods (Do Not Delete):")
            plain_chunks.append("\n".join(unsafe_plain))
        
        if safe_html:
            if unsafe_html:
                html_chunks.append("<br><hr>")
                plain_chunks.append("\n" + "="*40 + "\n")
                
            html_chunks.append("<h3>✅ Safe to Delete:</h3>")
            html_chunks.append("<br>".join(safe_html))
            
            plain_chunks.append("✅ Safe to Delete:")
            plain_chunks.append("\n".join(safe_plain))

        final_html = "".join(html_chunks)
        final_plain = "\n".join(plain_chunks)

        # Show the report output
        report_window = ConflictReportDialog(final_html, final_plain, self.__parentWidget)
        report_window.exec()
