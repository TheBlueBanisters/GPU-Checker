"""Actual local SSH transport with a synthetic sample. No production password needed."""
import json
import socket
import threading
import time
import paramiko
import pytest
import backend
import profiles


@pytest.mark.parametrize("scenario", ["accept", "reject", "changed", "badpassword"])
def test_password_login_unknown_host_and_stream(tmp_path, monkeypatch, scenario):
    monkeypatch.setattr(backend, "DATA", tmp_path)
    monkeypatch.setattr(backend, "config_path", lambda: tmp_path / "absent")
    server_key = paramiko.RSAKey.generate(2048)
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    port = listener.getsockname()[1]
    if scenario == "changed":
        known = paramiko.HostKeys()
        known.add(f"[127.0.0.1]:{port}", "ssh-rsa", paramiko.RSAKey.generate(2048))
        known.save(str(tmp_path / "known_hosts"))
    authenticated = []
    class Server(paramiko.ServerInterface):
        def check_auth_password(self, username, password):
            authenticated.append((username, password))
            return paramiko.AUTH_SUCCESSFUL if (username, password) == ("test", "test-only-secret") else paramiko.AUTH_FAILED
        def get_allowed_auths(self, username):
            return "password"
        def check_channel_request(self, kind, chanid):
            return paramiko.OPEN_SUCCEEDED
        def check_channel_exec_request(self, channel, command):
            def send():
                for i in range(2):
                    channel.sendall(("GPUCHECK:" + json.dumps({"gpus": [], "processes": [], "timestamp": time.time()}) + "\n").encode())
                    time.sleep(0.1)
            threading.Thread(target=send, daemon=True).start()
            return True
    def serve():
        connection, _ = listener.accept()
        transport = paramiko.Transport(connection)
        transport.add_server_key(server_key)
        try:
            transport.start_server(server=Server())
            channel = transport.accept(5)
        except (EOFError, OSError, paramiko.SSHException):
            channel = None
        if channel:
            for _ in range(100):
                if channel.closed:
                    break
                time.sleep(0.05)
        transport.close()
        listener.close()
    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    worker = backend.Monitor(profiles.clean({"host": "127.0.0.1", "user": "test", "port": str(port), "mode": profiles.MODES[2]}), "wrong" if scenario == "badpassword" else "test-only-secret")
    received = []
    # Run synchronously in this test; direct signal connection needs no GUI event loop.
    from PySide6.QtCore import Qt
    worker.trust.connect(lambda host, fingerprint: worker.accept_key(scenario != "reject"), Qt.ConnectionType.DirectConnection)
    failures = []
    worker.failed.connect(failures.append, Qt.ConnectionType.DirectConnection)
    def accept_sample(data):
        received.append(data)
        if len(received) == 2:
            worker.stop()
    worker.data.connect(accept_sample, Qt.ConnectionType.DirectConnection)
    worker.run()
    thread.join(timeout=3)
    if scenario == "accept":
        assert len(received) == 2
        assert authenticated == [("test", "test-only-secret")]
        assert "127.0.0.1" in (tmp_path / "known_hosts").read_text()
    else:
        assert not received
        assert failures
        if scenario in ("reject", "changed"):
            assert not authenticated  # Authentication must never follow untrusted host keys.
    assert worker.password == ""
