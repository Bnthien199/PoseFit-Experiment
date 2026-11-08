"""Load the installed Windows fonts explicitly; no third-party font redistribution."""
from pathlib import Path
import os
from PySide6 import QtGui


def configure_font(app):
    folder=Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'
    for name in ['segoeui.ttf','segoeuib.ttf','seguisb.ttf','seguisym.ttf']:
        path=folder/name
        if path.is_file():QtGui.QFontDatabase.addApplicationFont(str(path))
    font=QtGui.QFont('Segoe UI',10);app.setFont(font)
    raw=QtGui.QRawFont.fromFont(font)
    if not raw.isValid() or not all(raw.supportsCharacter(ord(c)) for c in 'Đứơệ°'):
        raise RuntimeError('Không nạp được phông chữ tiếng Việt của Windows. Hãy kiểm tra phông Segoe UI trước khi sử dụng.')
