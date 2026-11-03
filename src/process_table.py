"""Header and cells use identical text insets and column alignments."""
from PySide6.QtCore import Qt,QRect
from PySide6.QtGui import QColor,QFont
from PySide6.QtWidgets import QHeaderView,QStyledItemDelegate,QStyle

INSET=14
ALIGNMENTS=[Qt.AlignmentFlag.AlignCenter,Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,
    Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,Qt.AlignmentFlag.AlignCenter,
    Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter,Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,
    Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter]


def text_rect(rect):
    return rect.adjusted(INSET,0,-INSET,0)


class ProcessHeader(QHeaderView):
    def __init__(self,parent=None):
        super().__init__(Qt.Orientation.Horizontal,parent)
        self.setFixedHeight(42)
        self.setStretchLastSection(False)
        self.setHighlightSections(False)
        self.setSectionsClickable(False)
        self.setMinimumSectionSize(54)

    def paintSection(self,painter,rect,index):
        painter.save()
        painter.fillRect(rect,QColor('#16263a'))
        painter.setPen(QColor('#2b4056'))
        painter.drawLine(rect.bottomLeft(),rect.bottomRight())
        font=self.font()
        font.setWeight(QFont.Weight.Medium)
        painter.setFont(font)
        painter.setPen(QColor('#9ab4c9'))
        value=str(self.model().headerData(index,self.orientation()) or '')
        area=text_rect(rect)
        painter.drawText(area,ALIGNMENTS[index],painter.fontMetrics().elidedText(value,Qt.TextElideMode.ElideRight,area.width()))
        painter.restore()


class ProcessCells(QStyledItemDelegate):
    def paint(self,painter,option,index):
        painter.save()
        painter.fillRect(option.rect,QColor('#19485a') if option.state & QStyle.StateFlag.State_Selected else QColor('#0c192b'))
        painter.setPen(QColor('#203247'))
        painter.drawLine(option.rect.bottomLeft(),option.rect.bottomRight())
        painter.setFont(option.font)
        foreground=index.data(Qt.ItemDataRole.ForegroundRole)
        painter.setPen(foreground.color() if foreground else QColor('#d0dfec'))
        area=text_rect(option.rect)
        value=str(index.data() or '')
        painter.drawText(area,ALIGNMENTS[index.column()],painter.fontMetrics().elidedText(value,Qt.TextElideMode.ElideRight,max(0,area.width())))
        painter.restore()
