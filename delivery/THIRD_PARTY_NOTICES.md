# Third-party components

GPU Checker bundles Python, PySide6/Qt 6.8.3, Shiboken6, Paramiko 4.0.0, cryptography/OpenSSL, bcrypt, PyNaCl/libsodium, cffi and their runtime dependencies. PyInstaller is used to package the executable.

The matching license files and installed distribution metadata are included in `licenses/`. Qt/PySide6/Shiboken are used under their applicable open-source LGPL terms. The application source and a reproducible build script accompany this delivery, so the runtime can be rebuilt/replaced. The one-file runtime unpacks its shared libraries at launch; there are no application checks preventing replacement or debugging of those libraries.

Sources and project notices:

- Python: https://www.python.org/downloads/source/
- Qt 6.8.3 source: https://download.qt.io/archive/qt/6.8/6.8.3/single/
- PySide6/Shiboken 6.8.3 source: https://code.qt.io/cgit/pyside/pyside-setup.git/tag/?h=v6.8.3
- Paramiko: https://github.com/paramiko/paramiko/tree/4.0.0
- Cryptography: https://github.com/pyca/cryptography
- OpenSSL: https://www.openssl.org/source/
- PyNaCl: https://github.com/pyca/pynacl
- libsodium: https://github.com/jedisct1/libsodium
- bcrypt: https://github.com/pyca/bcrypt
- cffi: https://foss.heptapod.net/pypy/cffi
- PyInstaller exception and license: https://pyinstaller.org/en/stable/license.html

No private SSH keys, passwords or user SSH config are bundled with the application.
