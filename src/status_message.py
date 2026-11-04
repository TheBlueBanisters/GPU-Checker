"""Fixed-height, scrollable status text that cannot push the telemetry layout."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPlainTextEdit,QSizePolicy
from themes import set_style


class StatusMessage(QPlainTextEdit):
    def __init__(self,text=''):
        super().__init__()
        self.setReadOnly(True)
        self.setFixedHeight(58)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Fixed)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.document().setDocumentMargin(0)
        set_style(self,'QPlainTextEdit {background:transparent;border:0;padding:0;color:#7498b1;font-size:14px;}')
        self.setText(text)

    def setText(self,text):
        if text!=self.toPlainText():self.setPlainText(text)

    def text(self):
        return self.toPlainText()
