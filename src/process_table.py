"""Header and cells use identical text insets and column alignments."""
from PySide6.QtCore import Qt,QRect,QEvent
from PySide6.QtGui import QColor,QFont
from PySide6.QtWidgets import QHeaderView,QStyledItemDelegate,QStyle,QTableWidget

INSET=20
ALIGNMENTS=[Qt.AlignmentFlag.AlignCenter,Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,
    Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,Qt.AlignmentFlag.AlignCenter,
    Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter,Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,
    Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter]


def text_rect(rect):
    return rect.adjusted(INSET,0,-INSET,0)


class ProcessTable(QTableWidget):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.hovered_row=-1
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)

    def _hover_row(self,row):
        if row==self.hovered_row:
            return
        previous=self.hovered_row
        self.hovered_row=row
        for r in (previous,row):
            if 0<=r<self.rowCount():
                self.viewport().update(QRect(0,self.rowViewportPosition(r),self.viewport().width(),self.rowHeight(r)))

    def mouseMoveEvent(self,event):
        self._hover_row(self.rowAt(int(event.position().y())))
        super().mouseMoveEvent(event)

    def viewportEvent(self,event):
        if event.type()==QEvent.Type.Leave:
            self._hover_row(-1)
        return super().viewportEvent(event)


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
        painter.drawLine(rect.topRight(),rect.bottomRight())
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
        hovered=getattr(self.parent(),'hovered_row',-1)==index.row()
        selected=bool(option.state & QStyle.StateFlag.State_Selected)
        color='#205568' if selected and hovered else '#19485a' if selected else '#143449' if hovered else '#0c192b'
        painter.fillRect(option.rect,QColor(color))
        if hovered and index.column()==0:
            painter.fillRect(QRect(option.rect.x(),option.rect.y(),3,option.rect.height()),QColor('#61c9cf'))
        painter.setPen(QColor('#203247'))
        painter.drawLine(option.rect.bottomLeft(),option.rect.bottomRight())
        painter.drawLine(option.rect.topRight(),option.rect.bottomRight())
        painter.setFont(option.font)
        foreground=index.data(Qt.ItemDataRole.ForegroundRole)
        painter.setPen(foreground.color() if foreground else QColor('#d0dfec'))
        area=text_rect(option.rect)
        value=str(index.data() or '')
        painter.drawText(area,ALIGNMENTS[index.column()],painter.fontMetrics().elidedText(value,Qt.TextElideMode.ElideRight,max(0,area.width())))
        painter.restore()
