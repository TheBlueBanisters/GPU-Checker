"""Passwords live only in the current Windows user's Credential Manager."""
import ctypes
from ctypes import wintypes
import hashlib
import json
import os


def target(profile):
    from backend import config_path
    import paramiko
    cfg=paramiko.SSHConfig()
    path=config_path()
    if path.exists():
        cfg=paramiko.SSHConfig.from_text(path.read_text(encoding='utf-8-sig'))
    info=cfg.lookup(profile['host'])
    endpoint=[profile['host'],info.get('hostname',profile['host']),
              profile.get('user') or info.get('user',''),str(profile.get('port') or info.get('port',22))]
    digest=hashlib.sha256(json.dumps(endpoint,ensure_ascii=True).encode()).hexdigest()[:24]
    return 'GPUChecker/SSH/'+profile['id']+'/'+digest


class Credential(ctypes.Structure):
    _fields_=[('Flags',wintypes.DWORD),('Type',wintypes.DWORD),('TargetName',wintypes.LPWSTR),
        ('Comment',wintypes.LPWSTR),('LastWritten',wintypes.FILETIME),('CredentialBlobSize',wintypes.DWORD),
        ('CredentialBlob',ctypes.POINTER(ctypes.c_ubyte)),('Persist',wintypes.DWORD),
        ('AttributeCount',wintypes.DWORD),('Attributes',ctypes.c_void_p),
        ('TargetAlias',wintypes.LPWSTR),('UserName',wintypes.LPWSTR)]


def api():
    if os.name!='nt':
        raise RuntimeError('记住密码需要 Windows 凭据管理器')
    dll=ctypes.WinDLL('Advapi32.dll',use_last_error=True)
    dll.CredWriteW.argtypes=[ctypes.POINTER(Credential),wintypes.DWORD]
    dll.CredReadW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.POINTER(ctypes.POINTER(Credential))]
    dll.CredDeleteW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD]
    dll.CredFree.argtypes=[ctypes.c_void_p]
    return dll


def get_password(profile):
    if os.name!='nt':
        return ''
    dll=api()
    pointer=ctypes.POINTER(Credential)()
    if not dll.CredReadW(target(profile),1,0,ctypes.byref(pointer)):
        error=ctypes.get_last_error()
        if error==1168:
            return ''
        raise ctypes.WinError(error)
    try:
        credential=pointer.contents
        return ctypes.string_at(credential.CredentialBlob,credential.CredentialBlobSize).decode('utf-16-le')
    finally:
        dll.CredFree(pointer)


def save_password(profile,password):
    encoded=password.encode('utf-16-le')
    if not encoded or len(encoded)>2500:
        raise ValueError('密码为空或超出 Windows 凭据长度限制')
    blob=(ctypes.c_ubyte*len(encoded)).from_buffer_copy(encoded)
    credential=Credential()
    credential.Type=1
    credential.TargetName=target(profile)
    credential.Comment='GPU Checker SSH password; current Windows user only'
    credential.CredentialBlobSize=len(encoded)
    credential.CredentialBlob=ctypes.cast(blob,ctypes.POINTER(ctypes.c_ubyte))
    credential.Persist=2
    credential.UserName=profile.get('user','')
    if not api().CredWriteW(ctypes.byref(credential),0):
        raise ctypes.WinError(ctypes.get_last_error())


def forget_password(profile):
    if os.name=='nt' and not api().CredDeleteW(target(profile),1,0):
        error=ctypes.get_last_error()
        if error!=1168:
            raise ctypes.WinError(error)
