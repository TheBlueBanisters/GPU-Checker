import pytest
import profiles


@pytest.mark.parametrize('text,field',[
    ('','为空'),('HostName x.test\n User bob','Host'),
    ('Host test\n User alice','HostName'),
    ('Host test\n HostName x.test','User'),
    ('Host test\n HostName x.test\n User alice\n Port nope','Host test'),
    ('Host test\n HostName x.test\n User alice\n Port 70000','端口'),
    ('Host','语法'),
    ('Host a\n HostName a.test\n User alice\nHost b\n HostName b.test','Host b'),
])
def test_incomplete_pasted_config_is_rejected(text,field):
    with pytest.raises(ValueError,match=field):
        profiles.validate_config(text)


def test_optional_port_and_key_defaults_and_global_user():
    names,info=profiles.validate_config('Host *\n User alice\nHost one\n HostName one.test\nHost two.test\n')
    assert names==['one','two.test']
    assert info['one']['user']=='alice'
    assert info['one'].get('port','22')=='22'


def test_invalid_import_cannot_replace_saved_config(tmp_path,monkeypatch):
    monkeypatch.setattr(profiles,'DATA',tmp_path)
    old='Host good\n HostName good.test\n User alice\n'
    (tmp_path/'ssh_config').write_text(old)
    f=tmp_path/'bad'
    f.write_text('Host bad\n HostName bad.test')
    with pytest.raises(ValueError):
        profiles.import_config(f)
    assert (tmp_path/'ssh_config').read_text()==old


def test_validation_never_executes_match_exec(tmp_path):
    marker=tmp_path/'should-not-exist'
    text=f'Host a\n HostName a.test\n User alice\nMatch exec "echo bad > {marker}"\n User bob\n'
    with pytest.raises(ValueError,match='Match'):
        profiles.validate_config(text)
    assert not marker.exists()
