from PyQt5.QtWidgets import (QTableWidget, QTableWidgetItem, QHeaderView, QMenu, QAction, QStyleFactory)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QColor

class ResultsTable(QTableWidget):
    def __init__(self):
        super().__init__()
        self.setColumnCount(7)
        self.setHorizontalHeaderLabels([
            "[ ]", "Original Name", "Type", "Category", 
            "Proposed Name", "Confidence", "Status"
        ])
        
        # Set column widths
        self.setColumnWidth(0, 40)  # Checkbox
        self.setColumnWidth(1, 250) # Original Name
        self.setColumnWidth(2, 80)  # Type
        self.setColumnWidth(3, 100) # Category
        self.setColumnWidth(4, 250) # Proposed Name
        self.setColumnWidth(5, 100) # Confidence
        self.setColumnWidth(6, 100) # Status
        
        # Enable sorting
        self.setSortingEnabled(True)
        
        # Set selection behavior
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setSelectionMode(QTableWidget.SingleSelection)
        
        # Set header properties
        header = self.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        
        # Context menu
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        
        # Store files
        self.files = []
        
    def set_files(self, files):
        """Set the list of files to display"""
        self.files = files
        self.setRowCount(len(files))
        
        for row, file_info in enumerate(files):
            self.update_file(row, file_info)
            
    def update_file(self, row, file_info):
        """Update a specific file row"""
        # Checkbox column
        checkbox_item = QTableWidgetItem()
        checkbox_item.setCheckState(Qt.Checked if file_info["status"] == "approved" else Qt.Unchecked)
        checkbox_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
        self.setItem(row, 0, checkbox_item)
        
        # Original Name
        self.setItem(row, 1, QTableWidgetItem(file_info["name"]))
        
        # Type
        self.setItem(row, 2, QTableWidgetItem(file_info["type"]))
        
        # Category
        self.setItem(row, 3, QTableWidgetItem(file_info["category"]))
        
        # Proposed Name
        self.setItem(row, 4, QTableWidgetItem(file_info["proposed_name"]))
        
        # Confidence
        confidence_item = QTableWidgetItem(f"{file_info['confidence']:.0%}")
        self.setItem(row, 5, confidence_item)
        
        # Status (with cache icon if cached)
        status_text = file_info["status"]
        if file_info.get("cached", False):
            status_text = f"⚡ {status_text}"
        status_item = QTableWidgetItem(status_text)
        self.setItem(row, 6, status_item)
        
        # Set row color based on status
        self.set_row_color(row, file_info["status"])
        
    def set_row_color(self, row, status):
        """Set row color based on status"""
        colors = {
            "approved": QColor(200, 255, 200),  # Light green
            "skipped": QColor(255, 200, 200),   # Light red
            "pending": QColor(240, 240, 240),   # Light gray
            "processing": QColor(200, 200, 255) # Light blue
        }
        
        color = colors.get(status, QColor(255, 255, 255))
        
        for col in range(self.columnCount()):
            item = self.item(row, col)
            if item:
                item.setBackground(color)
                
    def show_context_menu(self, position):
        """Show context menu for right-click"""
        row = self.rowAt(position.y())
        if row < 0:
            return
            
        menu = QMenu()
        
        # Approve action
        approve_action = QAction("Approve", self)
        approve_action.triggered.connect(lambda: self.set_status(row, "approved"))
        menu.addAction(approve_action)
        
        # Skip action
        skip_action = QAction("Skip", self)
        skip_action.triggered.connect(lambda: self.set_status(row, "skipped"))
        menu.addAction(skip_action)
        
        # Edit Proposed Name
        edit_action = QAction("Edit Proposed Name", self)
        edit_action.triggered.connect(lambda: self.edit_proposed_name(row))
        menu.addAction(edit_action)
        
        # Reanalyze
        reanalyze_action = QAction("Reanalyze", self)
        reanalyze_action.triggered.connect(lambda: self.reanalyze(row))
        menu.addAction(reanalyze_action)
        
        menu.exec_(self.mapToGlobal(position))
        
    def set_status(self, row, status):
        """Set status for a row"""
        if row < 0 or row >= len(self.files):
            return
            
        self.files[row]["status"] = status
        self.update_file(row, self.files[row])
        
    def edit_proposed_name(self, row):
        """Edit proposed name for a row"""
        if row < 0 or row >= len(self.files):
            return
            
        file_info = self.files[row]
        new_name, ok = QInputDialog.getText(self, "Edit Proposed Name", 
                                           "Enter new proposed name:",
                                           text=file_info["proposed_name"])
        if ok and new_name:
            file_info["proposed_name"] = new_name
            self.update_file(row, file_info)
            
    def reanalyze(self, row):
        """Reanalyze a file"""
        if row < 0 or row >= len(self.files):
            return
            
        file_info = self.files[row]
        file_info["status"] = "processing"
        self.update_file(row, file_info)
        
        # Simulate re-analysis
        file_info["proposed_name"] = f"reanalyzed_{file_info['name']}"
        file_info["confidence"] = 0.92
        file_info["status"] = "approved"
        file_info["reasoning"] = "Re-analyzed with updated parameters"
        
        self.update_file(row, file_info)
        
    def get_selected_files(self):
        """Get list of approved files"""
        approved_files = []
        for row in range(self.rowCount()):
            checkbox = self.item(row, 0)
            if checkbox and checkbox.checkState() == Qt.Checked:
                approved_files.append(self.files[row])
                
        return approved_files