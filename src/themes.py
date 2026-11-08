"""Shared day/night tokens for stylesheets and custom-painted components."""
import re
from shiboken6 import isValid
from PySide6.QtGui import QColor,QPalette
from PySide6.QtWidgets import QApplication,QWidget

DAY={
    '#e8ca67':'#987516','#ed8948':'#b65b25',
    '#b6a0ef':'#7755b5',
    '#17263a':'#e2edf3','#2c425a':'#c9dfe9','#56677c':'#899ba7','#41576c':'#94aebe',
    '#080f1e':'#e7eff4','#0e1b2d':'#f7fbfd','#0c1729':'#f7fbfd','#101b2d':'#edf4f8',
    '#0b1728':'#f7fbfd','#0b192a':'#f7fbfd','#0c192b':'#f7fbfd','#0b1424':'#e1ecf2',
    '#0d1d30':'#e0edf3','#0b1727':'#eaf3f7','#101d30':'#e3eef4','#122638':'#dceaf1',
    '#16263a':'#dce9f0','#15263c':'#dce9f0','#143449':'#d6eaf1','#19485a':'#bbdce8','#205568':'#aad2e1',
    '#203247':'#a6bdcc','#2b4056':'#a6bdcc','#2b4b60':'#9eb8c9','#203249':'#a6bdcc',
    '#263a50':'#a0bacb','#243b50':'#a8c1cf','#31576b':'#8aafc1','#315267':'#97b4c4',
    '#182b43':'#f4f9fc','#183547':'#c5d9e3','#102b39':'#deedf3',
    '#64e5c7':'#137f78','#62ddc1':'#137f78','#99f4df':'#249c91','#8df2d9':'#249c91',
    '#072a29':'#f3fffd','#092f2b':'#f3fffd','#63dec1':'#177b61','#65bde9':'#206fa2',
    '#d9a86c':'#95611e','#d77f8c':'#b14a60','#78909f':'#647988','#859faf':'#647988',
    '#68f6cf':'#177b61','#6edac2':'#177b61','#5bdac4':'#177b61',
    '#8b9ca6':'#6c7b86','#7a8c97':'#6c7b86','#61c9cf':'#147e94','#69cddd':'#166d88',
    '#75e6e1':'#167c89','#6bf8e0':'#137f78','#a0dfea':'#1d647d','#88d5e2':'#1d647d',
    '#95cfe0':'#2a637b','#8fc8de':'#245d77','#78a9bd':'#426c82','#91b8cc':'#355f76',
    '#bdd5e9':'#285a72','#a9cbdc':'#315b71','#d0dfec':'#284c64','#ceddea':'#31576c',
    '#7f96b1':'#54758a','#7498b1':'#54758a','#7aa5b6':'#507489','#79a6ba':'#507489',
    '#527d94':'#55798e','#557b96':'#55798e','#5d9aaf':'#466f85','#9ab4c9':'#3f6680',
    '#83a5bb':'#426f89','#b7e1eb':'#215e77','#7eece6':'#097e8d','#b1f6e5':'#136f74',
}


def is_day():
    app=QApplication.instance()
    return bool(app and app.property('colorMode')=='day')


def color(night,*args,day=None):
    original=QColor(night,*args)
    if not is_day():
        return original
    if day:
        return QColor(day)
    key=original.name().lower()
    if key in DAY:
        mapped=QColor(DAY[key])
    elif original.lightnessF()<.22:
        mapped=QColor('#eaf2f6')
    elif original.lightnessF()<.45:
        mapped=QColor('#7098ae')
    elif original.saturationF()<.25:
        mapped=QColor('#4d6679')
    else:
        mapped=QColor.fromHsvF(max(0,original.hueF()),min(.85,max(.45,original.saturationF())),.55)
    mapped.setAlpha(original.alpha())
    return mapped


def style_for(css,scale=1.):
    from ui_density import css as sized_css
    css=sized_css(css,scale)
    if not is_day():
        return css
    css=re.sub(r'rgba\((\d+),(\d+),(\d+),(\d+)\)',
               lambda m:'rgba('+','.join(str(v) for v in (*color(*[int(m[i]) for i in (1,2,3)]).getRgb()[:3],int(m[4])))+')',css)
    return re.sub(r'#[0-9A-Fa-f]{6}\b',lambda m:color(m.group()).name(),css)


def set_style(widget,css):
    widget.setProperty('_nightStyle',css)
    from ui_density import current
    widget.setStyleSheet(style_for(css,current(widget)))


def apply(app,mode,base_style):
    mode='day' if mode=='day' else 'night'
    if app.property('colorMode')==mode and app.styleSheet()==style_for(base_style):
        return
    app.setProperty('colorMode',mode)
    palette=QPalette()
    for role,value in ((QPalette.ColorRole.Window,'#080f1e'),(QPalette.ColorRole.Base,'#0e1b2d'),
                       (QPalette.ColorRole.WindowText,'#a9cbdc'),(QPalette.ColorRole.Text,'#a9cbdc'),
                       (QPalette.ColorRole.Button,'#122638'),(QPalette.ColorRole.ButtonText,'#ceddea'),
                       (QPalette.ColorRole.Highlight,'#19485a'),(QPalette.ColorRole.HighlightedText,'#a9cbdc')):
        palette.setColor(role,color(value))
    app.setPalette(palette)
    app.setStyleSheet(style_for(base_style))
    for widget in app.allWidgets():
        if not isValid(widget): continue
        css=widget.property('_nightStyle')
        if isinstance(css,str):
            from ui_density import current
            widget.setStyleSheet(style_for(css,current(widget)))
        if not isValid(widget): continue
        if getattr(widget,'kind',None)=='theme':
            widget.sync_theme_label()
        if isValid(widget): QWidget.update(widget)
