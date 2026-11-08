"""Logical-pixel UI density; respects OS DPI without disabling accessibility scaling."""
import re
from PySide6.QtWidgets import QWidget,QLayout,QLabel

def factor(width,height):
    return round(max(.78,min(1.,width/1440,height/900))*20)/20

def css(text,scale):
    if scale==1.:return text
    def replace(match):
        value=float(match.group(1))
        return str(max(1,round(value*scale)))+'px'
    return re.sub(r'(?<![\w#])([0-9]+(?:\.[0-9]+)?)px',replace,text)

def current(widget):
    return float(widget.window().property('uiDensity') or 1.)

def apply(window,scale,base_style):
    import themes
    changed=window.property('uiDensity')!=scale
    window.setProperty('uiDensity',scale)
    for widget in [window]+window.findChildren(QWidget):
        managed=widget.__class__.__name__=='GPUCard'
        height=None if managed else widget.property('_densityHeight')
        if not managed and height is None and widget.minimumHeight()==widget.maximumHeight():
            height=widget.height();widget.setProperty('_densityHeight',height)
        if height is not None:widget.setFixedHeight(max(1,round(height*scale)))
        if widget.__class__.__name__=='WindowControl':widget.setFixedWidth(round(38*scale))
        for layout in ([widget.layout()] if widget.layout() else []):
            scale_layout(layout,scale)
        source=widget.property('_nightStyle')
        if isinstance(source,str) and (changed or widget.property('_densityStyled')!=scale):
            widget.setStyleSheet(themes.style_for(source,scale))
            widget.setProperty('_densityStyled',scale)
        if widget.__class__.__name__=='StatusIndicator':widget.setText(widget.text())
    if changed:themes.set_style(window,base_style)

def scale_layout(layout,scale):
    base=layout.property('_densityMargins')
    if base is None:
        m=layout.contentsMargins();base=(m.left(),m.top(),m.right(),m.bottom())
        layout.setProperty('_densityMargins',base);layout.setProperty('_densitySpacing',layout.spacing())
    layout.setContentsMargins(*(round(value*scale) for value in base))
    spacing=layout.property('_densitySpacing')
    if spacing is not None and spacing>=0:layout.setSpacing(round(spacing*scale))
    for i in range(layout.count()):
        child=layout.itemAt(i).layout()
        if child:scale_layout(child,scale)
