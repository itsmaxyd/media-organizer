import sys
from pathlib import Path
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QGroupBox, QLineEdit, QPushButton, QCheckBox, QSpinBox, QComboBox, QTextEdit, QLabel, QGridLayout, QFrame, QSizePolicy, QStyleFactory, QMessageBox, QHBoxLayout)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon, QFont

from ..core.llm_client import Settings

class SettingsDialog(QDialog):
    def __init__(self, current_settings: Settings):
        super().__init__()
        self.current_settings = current_settings
        self.new_settings = Settings(**current_settings.__dict__)
        
        self.setWindowTitle("Settings")
        self.setMinimumSize(600, 600)
        
        # Main layout
        main_layout = QVBoxLayout(self)
        
        # Create sections
        self.create_api_section(main_layout)
        self.create_processing_section(main_layout)
        self.create_output_section(main_layout)
        self.create_testing_section(main_layout)
        self.create_buttons_section(main_layout)
        
        # Apply current settings
        self.apply_current_settings()
        
    def create_api_section(self, parent_layout):
        """Create API Configuration section"""
        group = QGroupBox("API Configuration")
        parent_layout.addWidget(group)
        
        layout = QFormLayout(group)
        
        # API Key field with show/hide toggle
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        self.api_key_edit.setPlaceholderText("Enter your API key")
        
        # Show/hide toggle
        self.show_hide_btn = QPushButton("Show")
        self.show_hide_btn.setFixedWidth(60)
        self.show_hide_btn.clicked.connect(self.toggle_api_key_visibility)
        
        # Combine API key and toggle in a horizontal layout
        api_key_layout = QHBoxLayout()
        api_key_layout.addWidget(self.api_key_edit)
        api_key_layout.addWidget(self.show_hide_btn)
        
        layout.addRow("API Key:", api_key_layout)
        
        # Base URL field
        self.base_url_edit = QLineEdit("https://frogapi.app/v1")
        layout.addRow("Base URL:", self.base_url_edit)
        
        # Model name field
        self.model_name_edit = QLineEdit()
        layout.addRow("Model Name:", self.model_name_edit)
        
        # Test Connection button
        self.test_btn = QPushButton("[Test Connection]")
        self.test_btn.clicked.connect(self.test_connection)
        self.test_btn.setFixedHeight(30)
        
        layout.addRow(self.test_btn)
    
    def create_processing_section(self, parent_layout):
        """Create Processing section"""
        group = QGroupBox("Processing")
        parent_layout.addWidget(group)
        
        layout = QFormLayout(group)
        
        # Keyframes per video
        self.keyframes_spin = QSpinBox()
        self.keyframes_spin.setRange(6, 12)
        self.keyframes_spin.setSingleStep(1)
        self.keyframes_spin.setSuffix(" keyframes")
        layout.addRow("Keyframes per video:", self.keyframes_spin)
        
        # Max image size px dropdown
        self.image_size_combo = QComboBox()
        self.image_size_combo.addItems(["256 px", "512 px", "768 px"])
        layout.addRow("Max image size:", self.image_size_combo)
        
        # Use local Whisper transcription
        self.whisper_checkbox = QCheckBox("Use local Whisper transcription")
        layout.addRow(self.whisper_checkbox)
        
        # Whisper model size
        self.whisper_model_combo = QComboBox()
        self.whisper_model_combo.addItems(["tiny", "base", "small"])
        self.whisper_model_combo.setEnabled(False)  # Disabled until checkbox is checked
        layout.addRow("Whisper model:", self.whisper_model_combo)
        
        # Connect checkbox to enable/disable whisper model combo
        self.whisper_checkbox.stateChanged.connect(self.on_whisper_toggled)
    
    def create_output_section(self, parent_layout):
        """Create Output section"""
        group = QGroupBox("Output")
        parent_layout.addWidget(group)
        
        layout = QFormLayout(group)
        
        # Naming template
        self.naming_template_edit = QLineEdit()
        self.naming_template_edit.setPlaceholderText("{category}/{descriptive_name}{ext}")
        layout.addRow("Naming template:", self.naming_template_edit)
        
        # Live preview label
        self.preview_label = QLabel("Preview: ")
        layout.addRow("Live preview:", self.preview_label)
        
        # Conflict resolution
        self.conflict_combo = QComboBox()
        self.conflict_combo.addItems(["skip", "rename with suffix"])
        layout.addRow("Conflict resolution:", self.conflict_combo)
    
    def create_testing_section(self, parent_layout):
        """Create Testing Mode section"""
        group = QGroupBox("Testing Mode")
        parent_layout.addWidget(group)
        
        layout = QFormLayout(group)
        
        # Testing mode toggle
        self.testing_mode_checkbox = QCheckBox("Testing mode ON")
        layout.addRow(self.testing_mode_checkbox)
        
        # File limit spinner
        self.file_limit_spin = QSpinBox()
        self.file_limit_spin.setRange(1, 10)
        self.file_limit_spin.setSuffix(" files")
        layout.addRow("File limit:", self.file_limit_spin)
        
        # Warning label
        self.warning_label = QLabel("⚠️ Testing mode limits processing to N files to save tokens")
        self.warning_label.setStyleSheet("color: red;")
        layout.addRow(self.warning_label)
    
    def create_buttons_section(self, parent_layout):
        """Create Save/Cancel buttons"""
        button_layout = QHBoxLayout()
        
        # Clear Cache button
        self.clear_cache_btn = QPushButton("🗑️ Clear Cache")
        self.clear_cache_btn.clicked.connect(self.clear_cache)
        self.clear_cache_btn.setToolTip("Clear all cached analysis results")
        button_layout.addWidget(self.clear_cache_btn)
        
        button_layout.addStretch()
        
        # Save button
        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self.save_settings)
        self.save_btn.setDefault(True)
        button_layout.addWidget(self.save_btn)
        
        # Cancel button
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)
        
        parent_layout.addLayout(button_layout)
        
    def apply_current_settings(self):
        """Apply current settings to UI"""
        self.api_key_edit.setText(self.current_settings.api_key)
        self.base_url_edit.setText(self.current_settings.api_base_url)
        self.model_name_edit.setText(self.current_settings.model_name)
        self.keyframes_spin.setValue(self.current_settings.keyframes_per_video)
        
        # Set image size combo based on value
        if self.current_settings.max_image_size_px == 256:
            self.image_size_combo.setCurrentIndex(0)
        elif self.current_settings.max_image_size_px == 512:
            self.image_size_combo.setCurrentIndex(1)
        elif self.current_settings.max_image_size_px == 768:
            self.image_size_combo.setCurrentIndex(2)
        
        self.whisper_checkbox.setChecked(self.current_settings.use_local_whisper)
        self.on_whisper_toggled(self.current_settings.use_local_whisper)
        
        if self.current_settings.whisper_model == "tiny":
            self.whisper_model_combo.setCurrentIndex(0)
        elif self.current_settings.whisper_model == "base":
            self.whisper_model_combo.setCurrentIndex(1)
        elif self.current_settings.whisper_model == "small":
            self.whisper_model_combo.setCurrentIndex(2)
        
        self.naming_template_edit.setText(self.current_settings.naming_template)
        self.conflict_combo.setCurrentText("skip" if self.current_settings.dry_run else "rename with suffix")
        self.testing_mode_checkbox.setChecked(self.current_settings.testing_mode)
        self.file_limit_spin.setValue(self.current_settings.testing_limit)
        
    def toggle_api_key_visibility(self):
        """Toggle API key visibility"""
        if self.api_key_edit.echoMode() == QLineEdit.Password:
            self.api_key_edit.setEchoMode(QLineEdit.Normal)
            self.show_hide_btn.setText("Hide")
        else:
            self.api_key_edit.setEchoMode(QLineEdit.Password)
            self.show_hide_btn.setText("Show")
    
    def on_whisper_toggled(self, state):
        """Enable/disable whisper model combo based on checkbox"""
        self.whisper_model_combo.setEnabled(state)
    
    def test_connection(self):
        """Test API connection"""
        from ..core.llm_client import LLMClient
        from ..core.llm_client import Settings
        
        # Create temporary settings
        test_settings = Settings(
            api_key=self.api_key_edit.text(),
            api_base_url=self.base_url_edit.text(),
            model_name=self.model_name_edit.text()
        )
        
        try:
            client = LLMClient(test_settings)
            # Make a simple test call
            response = client.client.chat.completions.create(
                model=test_settings.model_name,
                messages=[{"role": "system", "content": "Test"}],
                max_tokens=1
            )
            QMessageBox.information(self, "Connection Test", "Connection successful!")
        except Exception as e:
            QMessageBox.critical(self, "Connection Test", f"Connection failed: {str(e)}")
    
    def save_settings(self):
        """Save settings and apply immediately"""
        # Update settings from UI
        self.new_settings.api_key = self.api_key_edit.text()
        self.new_settings.api_base_url = self.base_url_edit.text()
        self.new_settings.model_name = self.model_name_edit.text()
        self.new_settings.keyframes_per_video = self.keyframes_spin.value()
        
        # Map image size combo to value
        if self.image_size_combo.currentIndex() == 0:
            self.new_settings.max_image_size_px = 256
        elif self.image_size_combo.currentIndex() == 1:
            self.new_settings.max_image_size_px = 512
        elif self.image_size_combo.currentIndex() == 2:
            self.new_settings.max_image_size_px = 768
        
        self.new_settings.use_local_whisper = self.whisper_checkbox.isChecked()
        self.new_settings.whisper_model = self.whisper_model_combo.currentText()
        self.new_settings.naming_template = self.naming_template_edit.text()
        self.new_settings.dry_run = self.conflict_combo.currentText() == "skip"
        self.new_settings.testing_mode = self.testing_mode_checkbox.isChecked()
        self.new_settings.testing_limit = self.file_limit_spin.value()
        
        # Apply settings immediately
        self.apply_settings()
        
        # Accept dialog
        self.accept()
    
    def apply_settings(self):
        """Apply settings to the application"""
        # Update the current settings instance
        self.current_settings.__dict__.update(self.new_settings.__dict__)
        
        # Update main window if it exists
        from .main_window import MainWindow
        if hasattr(MainWindow, 'instance'):
            main_window = MainWindow.instance
            main_window.testing_mode_checkbox.setChecked(self.new_settings.testing_mode)
            main_window.test_mode_indicator.setVisible(self.new_settings.testing_mode)
    
    def clear_cache(self):
        """Clear all cached analysis results"""
        from ..core.cache_manager import CacheManager
        
        reply = QMessageBox.question(
            self,
            "Clear Cache",
            "Are you sure you want to clear all cached analysis results?\n\n"
            "This will require re-analyzing all files on the next run.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            cache_manager = CacheManager()
            cache_manager.clear()
            QMessageBox.information(self, "Cache Cleared", "All cached results have been cleared.")