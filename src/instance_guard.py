"""One interactive monitor per data directory, shared across executable versions."""
import hashlib
from PySide6.QtCore import QObject,QLockFile
from PySide6.QtNetwork import QLocalServer,QLocalSocket


class InstanceGuard(QObject):
    def __init__(self,path,parent=None):
        super().__init__(parent)
        path.mkdir(parents=True,exist_ok=True)
        self.lock=QLockFile(str(path/'monitor.instance.lock'))
        self.lock.setStaleLockTime(0)
        self.name='GPUChecker-'+hashlib.sha256(str(path.resolve()).casefold().encode()).hexdigest()[:24]
        self.server=QLocalServer(self)
        self.server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self.window=None
        self.server.newConnection.connect(self.activate)

    def claim(self):
        if self.lock.tryLock(0):
            if self.server.listen(self.name):
                return True
            self.lock.unlock()
            raise RuntimeError('Cannot create the monitor activation channel')
        socket=QLocalSocket(self)
        socket.connectToServer(self.name)
        if socket.waitForConnected(500):
            socket.write(b'activate')
            socket.waitForBytesWritten(500)
            socket.disconnectFromServer()
            return False
        raise RuntimeError('无法取得主窗口实例锁，请关闭已运行的 GPU Checker 后重试。')

    def activate(self):
        while self.server.hasPendingConnections():
            socket=self.server.nextPendingConnection()
            socket.disconnected.connect(socket.deleteLater)
            socket.disconnectFromServer()
            if self.window is not None:
                self.window.reload_profiles()
                self.window.host_search.clear()
                if self.window.isMinimized(): self.window.showNormal()
                self.window.show()
                self.window.raise_()
                self.window.activateWindow()
