"""Connection metadata only: passwords and private keys are never exported."""
import json
import tempfile
from pathlib import Path
import re
import shutil
import uuid
import ipaddress
import fnmatch
import shlex
import paramiko
from backend import DATA, config_path

FIELDS = {"id", "name", "host", "user", "port", "key", "mode", "interval", "autoconnect", "retry"}
MODES = ["OpenSSH 免密（推荐）", "内置密钥（无需 OpenSSH）", "密码登录（内置）"]


def clean(profile):
    result = {k: v for k, v in profile.items() if k in FIELDS}
    result["id"] = str(result.get("id") or uuid.uuid4().hex)
    result["autoconnect"] = bool(result.get("autoconnect", True))
    result["retry"] = bool(result.get("retry", True))
    result.setdefault("name", result.get("host", "新连接"))
    result.setdefault("mode", MODES[0])
    if result["mode"] not in MODES:
        result["mode"] = MODES[0]
    result["interval"] = max(1, min(60, int(result.get("interval", 2))))
    for key in ("name", "host", "user", "port", "key"):
        result[key] = str(result.get(key, ""))
    return result


def atomic_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,suffix='.tmp',delete=False) as stream:
        temporary=Path(stream.name)
        json.dump(value,stream,ensure_ascii=False,indent=2)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def catalog():
    path=DATA/'host_catalog.json'
    if not path.exists():
        return {'hosts':[],'removed':[]}
    value=json.loads(path.read_text(encoding='utf-8'))
    return {'hosts':[clean(p) for p in value['hosts']],'removed':[str(k) for k in value.get('removed',[])]}


def save(items,removed_ids=()):
    # Only explicit UI removal can erase an enrolled host. Legacy versions may
    # rewrite profiles.json, but cannot erase the independent enrollment catalog.
    registry=catalog()
    removed=set(registry['removed'])|set(removed_ids)
    incoming=[clean(p) for p in items]
    by_id={p['id']:p for p in incoming if p['id'] not in removed}
    for p in registry['hosts']:
        if p['id'] not in removed:
            by_id.setdefault(p['id'],p)
    merged=list(by_id.values())
    atomic_json(DATA/'host_catalog.json',{'hosts':merged,'removed':sorted(removed)})
    atomic_json(DATA/'profiles.json',merged)
    return merged


def load():
    target=DATA/'profiles.json'
    registry=catalog()
    if target.exists():
        items=[clean(p) for p in json.loads(target.read_text(encoding='utf-8'))]
    elif registry['hosts'] or registry['removed']:
        items=[]
    else:
        return []
    removed=set(registry['removed'])
    by_id={p['id']:p for p in items if p['id'] not in removed}
    for p in registry['hosts']:
        if p['id'] not in removed:
            by_id.setdefault(p['id'],p)
    return list(by_id.values())


def aliases(source=None):
    source = Path(source or config_path())
    if not source.exists():
        return []
    cfg = paramiko.SSHConfig()
    with source.open(encoding="utf-8-sig") as f:
        cfg.parse(f)
    return sorted(x for x in cfg.get_hostnames() if not any(c in x for c in "*?!") and x != "*")


def validate_config(contents):
    if not contents.strip():
        raise ValueError('配置内容为空，请粘贴 SSH config。')
    if len(contents)>512*1024:
        raise ValueError('配置超过 512 KiB，请精简后导入。')
    if re.search(r'(?im)^\s*Match\s',contents):
        raise ValueError('此编辑器暂不支持校验 Match 条件块；请使用无 Match 的主机条目，或通过系统 SSH config 使用复杂规则。')
    try:
        cfg = paramiko.SSHConfig.from_text('CanonicalizeHostname no\n'+contents)
    except Exception as exc:
        raise ValueError('SSH config 语法错误：'+str(exc)) from exc
    names = sorted(x for x in cfg.get_hostnames() if not any(c in x for c in "*?!"))
    if not names:
        raise ValueError('缺少具体 Host 条目，例如：Host my-gpu。只有 Host * 或直接粘贴 ssh 命令无法导入。')
    errors=[]
    resolved={}
    for name in names:
        # Do not execute Match exec or ProxyCommand while validating pasted text.
        # Match blocks are advanced OpenSSH rules; keep import validation free of subprocesses.
        info=cfg.lookup(name)
        resolved[name]=info
        host=info.get('hostname',name)
        try:
            ipaddress.ip_address(name.strip('[]'))
            literal=True
        except ValueError:
            literal='.' in name or ':' in name
        patterns=['*']
        explicit_hostname=False
        for line in contents.splitlines():
            directive=re.match(r'^\s*([A-Za-z]+)(?:\s*=\s*|\s+)(.*)',line)
            if not directive:
                continue
            key,value=directive.groups()
            if key.lower()=='host':
                patterns=shlex.split(value,comments=True)
            elif key.lower()=='hostname':
                positive=any(fnmatch.fnmatchcase(name,p) for p in patterns if not p.startswith('!'))
                negative=any(fnmatch.fnmatchcase(name,p[1:]) for p in patterns if p.startswith('!'))
                if positive and not negative:
                    explicit_hostname=True
        if not explicit_hostname and not literal:
            errors.append(f'Host {name}：缺少 HostName（别名需要明确的服务器地址）')
        if not info.get('user','').strip():
            errors.append(f'Host {name}：缺少 User（请明确远端用户名，避免迁移后使用错误账号）')
        try:
            from backend import validate
            validate({'host':name})
            validate({'host':host,'user':info.get('user',''),'port':info.get('port','22')})
        except Exception as exc:
            errors.append(f'Host {name}：{exc}')
    if errors:
        raise ValueError('发现以下配置问题，尚未保存：\n\n'+'\n'.join(errors))
    return names,resolved


def import_config(source):
    source = Path(source)
    contents = source.read_text(encoding="utf-8-sig")
    names,_=validate_config(contents)
    DATA.mkdir(parents=True, exist_ok=True)
    target = DATA / "ssh_config"
    if target.exists():
        shutil.copy2(target, target.with_suffix(".backup"))
    temporary=target.with_suffix('.tmp')
    temporary.write_text(contents, encoding='utf-8')
    temporary.replace(target)
    warnings = []
    if re.search(r"(?im)^\s*Include\s", contents):
        warnings.append("Include 仍按 OpenSSH 规则引用外部文件；迁移时请同步这些文件。")
    if re.search(r"(?im)^\s*(IdentityFile|CertificateFile|UserKnownHostsFile)\s+[\"']?(?:[A-Za-z]:[\\/]|/)", contents):
        warnings.append("配置中有绝对路径；换电脑后可在连接面板重新选择密钥或编辑配置。")
    return names, warnings
