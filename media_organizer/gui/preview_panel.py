from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QTextEdit, QLineEdit, QPushButton, QFrame, QSizePolicy, QScrollArea)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QPixmap, QFont, QColor, QPainter, QImage
from PyQt5.QtCore import pyqtSignal

class PreviewPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.file_info = None
        
        # Create layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Title
        title = QLabel("Preview Panel")
        title.setStyleSheet("QLabel { font-size: 16px; font-weight: bold; }")
        layout.addWidget(title)
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator)
        
        # Thumbnail area
        self.thumbnail_area = QLabel()
        self.thumbnail_area.setMinimumSize(400, 300)
        self.thumbnail_area.setAlignment(Qt.AlignCenter)
        self.thumbnail_area.setStyleSheet("QLabel { background: #f0f0f0; border: 1px solid #ccc; }")
        layout.addWidget(self.thumbnail_area)
        
        # Proposed path section
        proposed_layout = QHBoxLayout()
        proposed_label = QLabel("Proposed Path:")
        proposed_layout.addWidget(proposed_label)
        
        self.proposed_path_edit = QLineEdit()
        self.proposed_path_edit.setReadOnly(True)
        self.proposed_path_edit.setStyleSheet("QLineEdit { background: #fff; border: 1px solid #ccc; padding: 2px; }")
        proposed_layout.addWidget(self.proposed_path_edit)
        
        layout.addLayout(proposed_layout)
        
        # Tags section
        self.tags_layout = QHBoxLayout()
        tags_label = QLabel("Tags:")
        self.tags_layout.addWidget(tags_label)
        layout.addLayout(self.tags_layout)
        
        # Confidence meter
        confidence_layout = QHBoxLayout()
        confidence_label = QLabel("Confidence:")
        confidence_layout.addWidget(confidence_label)
        
        self.confidence_bar = QProgressBar()
        self.confidence_bar.setMaximum(100)
        self.confidence_bar.setTextVisible(True)
        confidence_layout.addWidget(self.confidence_bar)
        
        layout.addLayout(confidence_layout)
        
        # Reasoning text
        reasoning_label = QLabel("Reasoning:")
        layout.addWidget(reasoning_label)
        
        self.reasoning_text = QTextEdit()
        self.reasoning_text.setReadOnly(True)
        self.reasoning_text.setMinimumHeight(100)
        self.reasoning_text.setStyleSheet("QTextEdit { background: #fafafa; border: 1px solid #ccc; padding: 5px; font-family: monospace; }")
        layout.addWidget(self.reasoning_text)
        
        # Editable proposed name
        editable_layout = QHBoxLayout()
        editable_label = QLabel("Edit Proposed Name:")
        editable_layout.addWidget(editable_label)
        
        self.editable_name = QLineEdit()
        editable_layout.addWidget(self.editable_name)
        
        self.update_button = QPushButton("Update")
        self.update_button.clicked.connect(self.update_proposed_name)
        editable_layout.addWidget(self.update_button)
        
        layout.addLayout(editable_layout)
        
        # Spacer
        layout.addStretch()
        
    def update_preview(self, file_info):
        """Update the preview panel with file information"""
        self.file_info = file_info
        
        # Update thumbnail
        self.update_thumbnail(file_info)
        
        # Update proposed path
        proposed_path = f"{file_info.get('category', 'unknown')}/{file_info.get('proposed_name', 'unknown')}"
        self.proposed_path_edit.setText(proposed_path)
        
        # Update tags
        self.update_tags(file_info.get('tags', []))
        
        # Update confidence
        confidence = file_info.get('confidence', 0) * 100
        self.confidence_bar.setValue(confidence)
        
        # Update reasoning
        self.reasoning_text.setText(file_info.get('reasoning', ''))
        
        # Update editable name
        self.editable_name.setText(file_info.get('proposed_name', ''))
        
    def update_thumbnail(self, file_info):
        """Update the thumbnail based on file type"""
        file_path = file_info.get('path', '')
        
        if not file_path:
            self.thumbnail_area.setText("No file selected")
            return
            
        # Check if file exists
        from pathlib import Path
        if not Path(file_path).exists():
            self.thumbnail_area.setText("File not found")
            return
            
        # Handle different file types
        if file_info.get('type', '').lower() in ['.jpg', '.jpeg', '.png', '.gif']:
            self.show_image_thumbnail(file_path)
        elif file_info.get('type', '').lower() in ['.mp4', '.mov', '.avi']:
            self.show_video_thumbnail(file_path)
        else:
            self.thumbnail_area.setText(f"Unsupported file type: {file_info.get('type', '')}")
            
    def show_image_thumbnail(self, file_path):
        """Show image thumbnail"""
        try:
            pixmap = QPixmap(file_path)
            if pixmap.isNull():
                self.thumbnail_area.setText("Cannot load image")
                return
                
            # Scale to fit while maintaining aspect ratio
            scaled_pixmap = pixmap.scaled(
                400, 300, 
                Qt.KeepAspectRatio, 
                Qt.SmoothTransformation
            )
            self.thumbnail_area.setPixmap(scaled_pixmap)
            
        except Exception as e:
            self.thumbnail_area.setText(f"Error loading image: {str(e)}")
            
    def show_video_thumbnail(self, file_path):
        """Show video thumbnail (first frame)"""
        # For simplicity, we'll just show a video icon
        # In a real implementation, you might extract the first frame
        self.thumbnail_area.setText("🎥 Video File")
        
    def update_tags(self, tags):
        """Update the tags display"""
        # Clear existing tags
        for i in reversed(range(self.tags_layout.count())):
            widget = self.tags_layout.takeAt(i).widget()
            if widget:
                widget.deleteLater()
                
        # Add new tags
        for tag in tags:
            tag_label = QLabel(tag)
            tag_label.setStyleSheet("QLabel { background: #e0e0e0; padding: 2px 8px; border-radius: 10px; margin-right: 5px; }")
            self.tags_layout.addWidget(tag_label)
            
    def update_proposed_name(self):
        """Update the proposed name"""
        if self.file_info:
            new_name = self.editable_name.text()
            if new_name:
                self.file_info["proposed_name"] = new_name
                proposed_path = f"{self.file_info.get('category', 'unknown')}/{new_name}"
                self.proposed_path_edit.setText(proposed_path)
                
                # Update the results table
                from .main_window import MainWindow
                if hasattr(MainWindow, 'instance'):
                    MainWindow.instance.results_table.update_file(
                        MainWindow.instance.files.index(self.file_info),
                        self.file_info
                    )