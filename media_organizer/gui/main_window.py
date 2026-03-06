import sys
from pathlib import Path
from datetime import datetime
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QToolBar, QAction, QFileDialog, QCheckBox, QProgressBar, QPushButton, QLabel, QTableWidget, QTableWidgetItem, QHeaderView, QMenu, QInputDialog, QMessageBox, QStyleFactory, QTextEdit, QGroupBox, QScrollArea, QFrame)
from PyQt5.QtCore import Qt, QTimer, QSize
from PyQt5.QtGui import QIcon, QPixmap, QFont, QColor, QTextCharFormat

from .results_table import ResultsTable
from .preview_panel import PreviewPanel
from .settings_dialog import SettingsDialog
from .worker import AnalysisWorker, MediaAnalyzer
from ..core.llm_client import Settings, APIKeyError, APICallError
from ..core.extractor import ExtractionError
from ..core.organizer import OrganizerError
from ..core.local_processor import LocalProcessor

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Media Organizer")
        self.setMinimumSize(1200, 800)
        
        # Initialize settings
        self.settings = Settings()
        
        # Initialize state
        self.source_dir = None
        self.output_dir = None
        self.testing_mode = self.settings.testing_mode
        self.files = []
        self.current_file_index = 0
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        
        # Create error banner (hidden by default)
        self.error_banner = QLabel()
        self.error_banner.setStyleSheet("""
            QLabel {
                background-color: #ff4444;
                color: white;
                padding: 10px;
                font-weight: bold;
                border-radius: 4px;
            }
        """)
        self.error_banner.setAlignment(Qt.AlignCenter)
        self.error_banner.setVisible(False)
        main_layout.addWidget(self.error_banner)
        
        # Create toolbar
        self.create_toolbar()
        
        # Create main splitter
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)
        
        # Create results table
        self.results_table = ResultsTable()
        splitter.addWidget(self.results_table)
        
        # Create preview panel
        self.preview_panel = PreviewPanel()
        splitter.addWidget(self.preview_panel)
        
        # Create status bar
        self.create_status_bar()
        
        # Create action buttons
        self.create_action_buttons()
        
        # Connect signals
        self.results_table.cellClicked.connect(self.on_row_clicked)
        
        # Initialize timer for progress updates
        self.progress_timer = QTimer()
        self.progress_timer.timeout.connect(self.update_progress)
        
        # Initialize token counter
        self.token_counter = 0
        
        # Store worker reference
        self.worker = None
        self.analysis_results = []
        
        # Store instance reference for cross-component communication
        MainWindow.instance = self
        
        # Create log panel
        self.create_log_panel()
        
    def create_toolbar(self):
        """Create the toolbar with directory pickers and settings"""
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)
        
        # Source directory button
        self.source_action = QAction(QIcon.fromTheme("folder"), "Source Directory", self)
        self.source_action.triggered.connect(self.select_source_directory)
        toolbar.addAction(self.source_action)
        
        # Output directory button
        self.output_action = QAction(QIcon.fromTheme("folder"), "Output Directory", self)
        self.output_action.triggered.connect(self.select_output_directory)
        toolbar.addAction(self.output_action)
        
        # Settings button
        self.settings_action = QAction(QIcon.fromTheme("preferences-system"), "Settings", self)
        self.settings_action.triggered.connect(self.open_settings)
        toolbar.addAction(self.settings_action)
        
        # Help button
        self.help_action = QAction(QIcon.fromTheme("help"), "Help", self)
        self.help_action.triggered.connect(self.show_help)
        toolbar.addAction(self.help_action)
        
        # Testing mode checkbox
        self.testing_mode_checkbox = QCheckBox("Test Mode ON")
        self.testing_mode_checkbox.setStyleSheet("QCheckBox { color: yellow; font-weight: bold; }")
        self.testing_mode_checkbox.stateChanged.connect(self.on_testing_mode_changed)
        toolbar.addWidget(self.testing_mode_checkbox)
        
    def create_status_bar(self):
        """Create the status bar with progress information"""
        self.status_bar = self.statusBar()
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setTextVisible(True)
        
        # Progress labels
        self.progress_label = QLabel("Progress: 0%")
        self.files_label = QLabel("0/0 files")
        self.time_label = QLabel("⏱️ 0s")
        self.tokens_label = QLabel("🔑 0 tokens")
        
        # Cancel button
        self.cancel_button = QPushButton("❌ Cancel")
        self.cancel_button.clicked.connect(self.cancel_processing)
        self.cancel_button.setEnabled(False)
        
        # Add to status bar
        self.status_bar.addPermanentWidget(self.progress_label)
        self.status_bar.addPermanentWidget(self.progress_bar)
        self.status_bar.addPermanentWidget(self.files_label)
        self.status_bar.addPermanentWidget(self.time_label)
        self.status_bar.addPermanentWidget(self.tokens_label)
        self.status_bar.addPermanentWidget(self.cancel_button)
        
    def create_action_buttons(self):
        """Create the action buttons at the bottom"""
        button_layout = QHBoxLayout()
        
        # Test mode indicator
        self.test_mode_indicator = QLabel("🧪 Test Mode ON")
        self.test_mode_indicator.setStyleSheet("QLabel { color: yellow; font-weight: bold; }")
        self.test_mode_indicator.setVisible(False)
        button_layout.addWidget(self.test_mode_indicator)
        
        # Analyze button
        self.analyze_button = QPushButton("▶ Analyze")
        self.analyze_button.clicked.connect(self.analyze_files)
        self.analyze_button.setEnabled(False)
        button_layout.addWidget(self.analyze_button)
        
        # Approve All button
        self.approve_all_button = QPushButton("✅ Approve All")
        self.approve_all_button.clicked.connect(self.approve_all_files)
        button_layout.addWidget(self.approve_all_button)
        
        # Preview Plan button
        self.preview_plan_button = QPushButton("👁 Preview Plan")
        self.preview_plan_button.clicked.connect(self.preview_plan)
        button_layout.addWidget(self.preview_plan_button)
        
        # Execute buttons
        self.execute_dry_run_button = QPushButton("🚀 Execute (Dry Run)")
        self.execute_dry_run_button.clicked.connect(self.execute_dry_run)
        button_layout.addWidget(self.execute_dry_run_button)
        
        self.execute_real_button = QPushButton("🚀 Execute (For Real)")
        self.execute_real_button.clicked.connect(self.execute_real)
        self.execute_real_button.setEnabled(False)
        button_layout.addWidget(self.execute_real_button)
        
        # Add to main layout
        main_layout = self.centralWidget().layout()
        main_layout.addLayout(button_layout)
        
        # Create log panel
        self.create_log_panel()
        
    def create_log_panel(self):
        """Create a collapsible log panel at the bottom."""
        # Log group box
        self.log_group = QGroupBox("📋 Log")
        self.log_group.setCheckable(True)
        self.log_group.setChecked(False)  # Collapsed by default
        self.log_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #666;
                border-radius: 4px;
                margin-top: 4px;
                padding-top: 4px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        
        # Log text area
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 11px;
                border: none;
            }
        """)
        
        # Layout for log panel
        log_layout = QVBoxLayout()
        log_layout.addWidget(self.log_text)
        self.log_group.setLayout(log_layout)
        
        # Add to main layout
        main_layout = self.centralWidget().layout()
        main_layout.addWidget(self.log_group)
        
        # Connect collapse/expand to update layout
        self.log_group.toggled.connect(self.on_log_panel_toggled)
    
    def on_log_panel_toggled(self, checked):
        """Handle log panel toggle."""
        if checked:
            self.log_group.setTitle("📋 Log ▼")
        else:
            self.log_group.setTitle("📋 Log ▶")
    
    def log_message(self, message: str, level: str = "info"):
        """
        Add a timestamped message to the log panel.
        
        Args:
            message: The message to log
            level: Log level - "info", "warning", "error", "success"
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Create text format based on level
        fmt = QTextCharFormat()
        colors = {
            "info": "#d4d4d4",
            "warning": "#ff9800",
            "error": "#ff4444",
            "success": "#4caf50",
            "step": "#64b5f6"
        }
        fmt.setForeground(QColor(colors.get(level, "#d4d4d4")))
        
        # Append to log
        cursor = self.log_text.textCursor()
        cursor.movePosition(cursor.End)
        
        # Add timestamp
        cursor.insertText(f"[{timestamp}] ", fmt)
        
        # Add message with appropriate color
        cursor.insertText(f"{message}\n", fmt)
        
        # Auto-scroll to bottom
        self.log_text.setTextCursor(cursor)
        self.log_text.ensureCursorVisible()
    
    def log_step(self, step_name: str):
        """Log a processing step."""
        self.log_message(f"→ {step_name}", "step")
    
    def log_error(self, error_msg: str):
        """Log an error message."""
        self.log_message(f"❌ {error_msg}", "error")
    
    def log_success(self, message: str):
        """Log a success message."""
        self.log_message(f"✓ {message}", "success")
    
    def log_tokens(self, prompt_tokens: int, completion_tokens: int):
        """Log token usage for a file."""
        total = prompt_tokens + completion_tokens
        self.log_message(f"📊 Tokens: prompt={prompt_tokens}, completion={completion_tokens}, total={total}", "info")
        
    def select_source_directory(self):
        """Select source directory"""
        dir_path = QFileDialog.getExistingDirectory(self, "Select Source Directory")
        if dir_path:
            self.source_dir = Path(dir_path)
            self.source_action.setText(f"📁 {self.source_dir.name}")
            self.check_analyze_enabled()
            
    def select_output_directory(self):
        """Select output directory"""
        dir_path = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if dir_path:
            self.output_dir = Path(dir_path)
            self.output_action.setText(f"📂 {self.output_dir.name}")
            
    def open_settings(self):
        """Open settings dialog"""
        self.hide_error_banner()
        dialog = SettingsDialog(self.settings)
        if dialog.exec_():
            # Re-check API key after settings are saved
            self.check_api_key()
        
    def show_help(self):
        """Show help information"""
        QMessageBox.information(self, "Help", "Help information would be displayed here")
        
    def show_error_banner(self, message: str, is_warning: bool = False):
        """Show error banner with given message."""
        if is_warning:
            self.error_banner.setStyleSheet("""
                QLabel {
                    background-color: #ff9800;
                    color: white;
                    padding: 10px;
                    font-weight: bold;
                    border-radius: 4px;
                }
            """)
        else:
            self.error_banner.setStyleSheet("""
                QLabel {
                    background-color: #ff4444;
                    color: white;
                    padding: 10px;
                    font-weight: bold;
                    border-radius: 4px;
                }
            """)
        self.error_banner.setText(message)
        self.error_banner.setVisible(True)
        
    def hide_error_banner(self):
        """Hide the error banner."""
        self.error_banner.setVisible(False)
        
    def check_api_key(self) -> bool:
        """Check if API key is configured. Show banner if not."""
        if not self.settings.api_key or self.settings.api_key.strip() == "":
            self.show_error_banner("⚠️ API key not set. Go to Settings.", is_warning=True)
            return False
        self.hide_error_banner()
        return True
        
    def on_testing_mode_changed(self, state):
        """Handle testing mode toggle"""
        self.testing_mode = state == Qt.Checked
        self.test_mode_indicator.setVisible(self.testing_mode)
        
    def check_analyze_enabled(self):
        """Enable analyze button if source directory is selected"""
        self.analyze_button.setEnabled(self.source_dir is not None)
        
    def on_row_clicked(self, row):
        """Handle row click in results table"""
        if row >= 0 and row < len(self.files):
            file_info = self.files[row]
            self.preview_panel.update_preview(file_info)
            
    def analyze_files(self):
        """Start file analysis using worker thread"""
        if not self.source_dir:
            return
        
        # Check API key first
        if not self.check_api_key():
            return
        
        # Clear log at start of new analysis
        self.log_text.clear()
        self.log_message("Starting analysis...", "info")
        self.log_message(f"Source: {self.source_dir}", "info")
        self.log_message(f"Testing mode: {self.testing_mode}", "info")
        
        # Reset state
        self.analysis_results = []
        self.files = []
        self.token_counter = 0
        self.start_time = QTimer().elapsed()
        
        # Clear results table
        self.results_table.set_files([])
        
        # Create analyzer and worker
        analyzer = MediaAnalyzer(self.settings)
        self.worker = AnalysisWorker(analyzer, self.source_dir)
        
        # Connect worker signals
        self.worker.progress.connect(self.on_analysis_progress)
        self.worker.file_done.connect(self.on_file_done)
        self.worker.all_done.connect(self.on_analysis_complete)
        self.worker.error.connect(self.on_analysis_error)
        self.worker.token_update.connect(self.on_token_update)
        self.worker.gpu_fallback.connect(self.on_gpu_fallback)
        
        # Start progress timer for elapsed time
        self.progress_timer.start(100)
        self.cancel_button.setEnabled(True)
        self.analyze_button.setEnabled(False)
        
        # Start worker thread
        self.worker.start()
        
    def on_analysis_progress(self, current: int, total: int, result: dict):
        """Handle progress updates from worker thread"""
        progress = (current / total * 100) if total > 0 else 0
        self.progress_bar.setValue(int(progress))
        self.progress_label.setText(f"Progress: {progress:.0f}%")
        self.files_label.setText(f"{current}/{total} files")
        self.log_step(f"Processing file {current}/{total}")
        
    def on_file_done(self, result: dict):
        """Handle file completion from worker thread"""
        self.analysis_results.append(result)
        
        # Log file completion
        file_name = Path(result["source"]).name
        category = result.get("category", "unknown")
        name = result.get("descriptive_name", "unknown")
        status = result.get("status", "pending")
        
        if status == "error":
            error_type = result.get("error_type", "unknown")
            error_msg = result.get("error_message", "Unknown error")
            self.log_error(f"{file_name}: [{error_type}] {error_msg}")
        else:
            self.log_message(f"✓ {file_name} → {category}/{name}", "success")
        
        # Convert result to file_info format for the table
        file_info = {
            "path": result["source"],
            "name": Path(result["source"]).name,
            "type": Path(result["source"]).suffix.lower(),
            "category": result.get("category", ""),
            "proposed_name": result.get("descriptive_name", ""),
            "confidence": result.get("confidence", 0.0),
            "status": result.get("status", "pending"),
            "tags": result.get("tags", []),
            "reasoning": result.get("reasoning", ""),
            "error_type": result.get("error_type"),
            "retryable": result.get("retryable", False)
        }
        self.files.append(file_info)
        
        # Update or add row in results table
        row_index = len(self.files) - 1
        if row_index < self.results_table.rowCount():
            self.results_table.update_file(row_index, file_info)
        else:
            self.results_table.set_files(self.files)
        
        # Show status-specific messages
        status = result.get("status", "")
        error_type = result.get("error_type", "")
        
        if error_type == "unreadable":
            self.status_bar.showMessage(f"⚠️ Skipped unreadable file: {file_info['name']}", 3000)
        elif error_type == "api_error":
            self.show_error_banner(f"⚠️ API Error for {file_info['name']}. Marked for retry.", is_warning=True)
        elif error_type == "gpu_fallback":
            self.status_bar.showMessage(f"ℹ️ GPU not available, using CPU for Whisper", 5000)
        
        # Update preview for first file
        if len(self.files) == 1:
            self.preview_panel.update_preview(file_info)
            
    def on_analysis_complete(self, results: list):
        """Handle analysis completion"""
        self.progress_timer.stop()
        self.cancel_button.setEnabled(False)
        self.analyze_button.setEnabled(True)
        
        # Final progress update
        self.progress_bar.setValue(100)
        self.progress_label.setText("Progress: 100%")
        self.status_bar.showMessage(f"Analysis complete: {len(results)} files processed", 5000)
        
        # Log completion
        self.log_message(f"Analysis complete: {len(results)} files processed", "success")
        
    def on_gpu_fallback(self, message: str):
        """Handle GPU fallback notification"""
        self.status_bar.showMessage(f"ℹ️ {message}", 10000)
        
    def on_analysis_error(self, error_msg: str, error_type: str = "error"):
        """Handle analysis error with context-aware messaging"""
        self.progress_timer.stop()
        self.cancel_button.setEnabled(False)
        self.analyze_button.setEnabled(True)
        
        # Log the error
        self.log_error(f"{error_type}: {error_msg}")
        
        # Show appropriate banner based on error type
        if error_type == "api_key":
            self.show_error_banner("⚠️ API key not set. Go to Settings.", is_warning=True)
        elif error_type == "api_error":
            self.show_error_banner(f"⚠️ API Error: {error_msg}. Click retry button to retry.", is_warning=True)
        elif error_type == "unreadable":
            self.status_bar.showMessage(f"Skipped unreadable file: {error_msg}", 5000)
        elif error_type == "gpu_fallback":
            self.status_bar.showMessage(f"ℹ️ {error_msg}", 5000)
        else:
            self.show_error_banner(f"Error: {error_msg}")
            
        self.status_bar.showMessage(f"Error: {error_msg}", 5000)
        
    def on_token_update(self, prompt_tokens: int, completion_tokens: int):
        """Handle token usage update"""
        self.token_counter = prompt_tokens + completion_tokens
        self.tokens_label.setText(f"🔑 {self.token_counter} tokens")
        self.log_tokens(prompt_tokens, completion_tokens)
        
    def update_progress(self):
        """Update elapsed time display"""
        elapsed_time = (QTimer().elapsed() - self.start_time) // 1000
        self.time_label.setText(f"⏱️ {elapsed_time}s")
        
    def cancel_processing(self):
        """Cancel file processing"""
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait(2000)  # Wait up to 2 seconds for thread to finish
        self.progress_timer.stop()
        self.cancel_button.setEnabled(False)
        self.analyze_button.setEnabled(True)
        self.status_bar.showMessage("Analysis cancelled", 3000)
        
    def approve_all_files(self):
        """Approve all files in the table"""
        for i, file_info in enumerate(self.files):
            file_info["status"] = "approved"
            self.results_table.update_file(i, file_info)
            
    def preview_plan(self):
        """Show preview of what will happen"""
        plan_text = "Preview plan would be shown here"
        QMessageBox.information(self, "Preview Plan", plan_text)
        
    def execute_dry_run(self):
        """Execute dry run"""
        QMessageBox.information(self, "Dry Run", "Dry run would be executed here")
        self.execute_real_button.setEnabled(True)
        
    def execute_real(self):
        """Execute real operation"""
        if not self.output_dir:
            QMessageBox.warning(self, "Error", "Please select an output directory first")
            return
            
        # Show confirmation dialog
        confirm = QMessageBox.question(
            self, "Confirm Execution", 
            "Are you sure you want to execute the real operation?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            QMessageBox.information(self, "Success", "Real execution would be performed here")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create("Fusion"))
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())