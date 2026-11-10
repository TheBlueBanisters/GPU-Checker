"""Exercise real Qt input, not only the credential transport underneath it."""
import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QDialog,QScrollArea
from test_multihost import window
from dialogs import HostDialog
import profiles,vault


@pytest.mark.parametrize('mode',[0,1,2])
@pytest.mark.parametrize('credentials_only',[False,True])
def test_all_authentication_forms_accept_input_and_route_it_correctly(window,monkeypatch,mode,credentials_only):
    monkeypatch.setattr(vault,'get_password',lambda p:'')
    profile=profiles.clean(dict(host='test.invalid',user='test',mode=profiles.MODES[mode]))
    dialog=HostDialog(window,profile,credentials_only);dialog.show();QApplication.processEvents()
    try:
        assert dialog.secret.isEnabled() and not dialog.secret.isReadOnly()
        dialog.findChild(QScrollArea).ensureWidgetVisible(dialog.secret)
        QTest.mouseClick(dialog.secret,Qt.MouseButton.LeftButton)
        assert dialog.secret.hasFocus()
        QTest.keyClicks(dialog.secret,'first-then-rest')
        assert dialog.secret.text()=='first-then-rest'
        if mode==1:
            assert dialog.credentials()==('','first-then-rest')
            assert not dialog.remember.isEnabled()
        else:
            assert dialog.mode.currentIndex()==2 and dialog.remember.isEnabled()
            assert dialog.credentials()==('first-then-rest','')
        dialog.check();assert dialog.result()==QDialog.DialogCode.Accepted
    finally:dialog.close()


def test_new_host_paste_preserves_every_character_and_switches_from_native(window,monkeypatch):
    monkeypatch.setattr(vault,'get_password',lambda p:'')
    dialog=HostDialog(window);dialog.show();QApplication.processEvents()
    clipboard=QApplication.clipboard();previous=clipboard.text()
    try:
        dialog.host.setText('paste.invalid');dialog.user.setText('test')
        clipboard.setText('paste-only-密碼-!@# 42')
        dialog.secret.setFocus();QTest.keyClick(dialog.secret,Qt.Key.Key_V,Qt.KeyboardModifier.ControlModifier)
        assert dialog.mode.currentIndex()==2
        assert dialog.credentials()==('paste-only-密碼-!@# 42','')
        dialog.check();assert dialog.result()==QDialog.DialogCode.Accepted
    finally:clipboard.setText(previous);dialog.close()


def test_manual_switch_does_not_reuse_private_key_passphrase_as_server_password(window,monkeypatch):
    monkeypatch.setattr(vault,'get_password',lambda p:'')
    dialog=HostDialog(window,profiles.clean({'host':'key.invalid','mode':profiles.MODES[1]}))
    try:
        QTest.keyClicks(dialog.secret,'private-key-passphrase')
        dialog.password_button.click()
        assert dialog.mode.currentIndex()==2 and dialog.secret.isEnabled() and not dialog.secret.text()
        QTest.keyClicks(dialog.secret,'server-password')
        assert dialog.credentials()==('server-password','')
        dialog.mode.setCurrentIndex(0)
        assert dialog.secret.isEnabled() and not dialog.secret.text() and dialog.credentials()==('','')
    finally:dialog.close()


def test_saved_password_never_disables_input_and_endpoint_hint_refreshes(window,monkeypatch):
    profile=profiles.clean({'host':'saved.invalid','user':'one','port':'22','mode':profiles.MODES[2]})
    monkeypatch.setattr(vault,'get_password',lambda p:'stored' if (p['host'],p['user'],p['port'])==('saved.invalid','one','22') else '')
    dialog=HostDialog(window,profile)
    try:
        assert dialog.secret.isEnabled() and '已记住' in dialog.secret.placeholderText()
        assert not dialog.secret.text()
        dialog.user.setText('two');assert '已记住' not in dialog.secret.placeholderText()
        dialog.user.setText('one');assert '已记住' in dialog.secret.placeholderText()
        dialog.remember.setChecked(False);assert '忘记原密码' in dialog.secret.placeholderText()
        assert dialog.secret.isEnabled()
        dialog.remember.setChecked(True);dialog.check()
        assert dialog.result()==QDialog.DialogCode.Accepted
    finally:dialog.close()


def test_failed_native_import_can_be_corrected_and_saved_without_disabling_field(window,monkeypatch):
    saved={}
    monkeypatch.setattr(vault,'get_password',lambda p:saved.get(p['id'],''))
    monkeypatch.setattr(vault,'save_password',lambda p,secret:saved.update({p['id']:secret}))
    original=window.selected;original.state='连接异常';original.message='Permission denied (publickey,password)'
    dialog=HostDialog(window,original.profile,credentials_only=True)
    try:
        assert dialog.mode.currentIndex()==0 and dialog.secret.isEnabled()
        QTest.keyClicks(dialog.secret,'new-server-password');dialog.check()
        window.apply_profile(dialog.profile(),*dialog.credentials(),remember=True)
        session=window.selected
        assert session.profile['mode']==profiles.MODES[2] and saved[session.id]=='new-server-password'
        session.pause();session.start()
        assert session.password=='new-server-password' and session.running
    finally:dialog.close()


def test_empty_unsaved_password_validation_keeps_field_editable(window,monkeypatch):
    import dialogs
    monkeypatch.setattr(vault,'get_password',lambda p:'')
    messages=[];monkeypatch.setattr(dialogs.QMessageBox,'information',lambda *args:messages.append(args[2]))
    dialog=HostDialog(window,profiles.clean({'host':'empty.invalid','mode':profiles.MODES[2]}))
    try:
        dialog.check();assert dialog.result()!=QDialog.DialogCode.Accepted and messages
        assert dialog.secret.isEnabled()
        QTest.keyClicks(dialog.secret,'corrected');dialog.check()
        assert dialog.result()==QDialog.DialogCode.Accepted
    finally:dialog.close()


def test_vault_read_error_still_opens_editable_credentials_dialog(window,monkeypatch):
    session=window.selected;session.profile['mode']=profiles.MODES[2];session.state='已暂停'
    def broken(profile):raise OSError('simulated credential read failure')
    monkeypatch.setattr(vault,'get_password',broken)
    opened=[];monkeypatch.setattr(window,'edit_host',lambda credentials_only=False:opened.append(credentials_only))
    window.toggle_selected();assert opened==[True]
    dialog=HostDialog(window,session.profile,credentials_only=True)
    try:
        assert dialog.secret.isEnabled()
        QTest.keyClicks(dialog.secret,'replacement')
        dialog.check();assert dialog.result()==QDialog.DialogCode.Accepted
    finally:dialog.close()
