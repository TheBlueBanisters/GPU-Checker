"""Stable per-user storage outside MSIX's context-dependent AppData overlay."""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import time


def default_dir():
    return Path.home()/'.gpu-checker'


def data_dir(base):
    override=os.environ.get('GPUCHECKER_DATA_DIR')
    if override:
        path=Path(os.path.expandvars(override)).expanduser()
        return path if path.is_absolute() else base/path
    return base/'data' if (base/'portable.flag').exists() else default_dir()


def physical_path(path):
    path=Path(path)
    if os.name!='nt' or not path.is_file(): return path.resolve()
    import msvcrt
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    function=kernel.GetFinalPathNameByHandleW
    function.argtypes=[ctypes.c_void_p,ctypes.c_wchar_p,ctypes.c_uint32,ctypes.c_uint32]
    with path.open('rb') as stream:
        buffer=ctypes.create_unicode_buffer(32768)
        size=function(msvcrt.get_osfhandle(stream.fileno()),buffer,len(buffer),0)
        if not size or size>=len(buffer): raise ctypes.WinError(ctypes.get_last_error())
    value=buffer.value
    if value.startswith('\\\\?\\UNC\\'): value='\\\\'+value[8:]
    elif value.startswith('\\\\?\\'): value=value[4:]
    return Path(value)


def legacy_roots():
    bases=[Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'AppData/Local'))),Path.home()/'AppData/Local']
    candidates=[]
    for base in bases:
        candidates.append(base/'GPUChecker')
        try: candidates.extend((base/'Packages').glob('*/LocalCache/Local/GPUChecker'))
        except OSError: pass
    found={}
    for root in candidates:
        try:
            file=next((root/name for name in ('profiles.json','host_catalog.json') if (root/name).is_file()),None)
            if file:
                actual=physical_path(file).parent
                found.setdefault(str(actual).casefold(),actual)
        except OSError: pass
    return list(found.values())


def read_source(root):
    import profiles
    records={}
    removed=set()
    for name in ('host_catalog.json','profiles.json'):
        file=root/name
        if not file.exists(): continue
        value=json.loads(file.read_text(encoding='utf-8-sig'))
        if name=='host_catalog.json':
            removed.update(str(key) for key in value.get('removed',[]))
            value=value['hosts']
        if not isinstance(value,list): raise ValueError('Invalid legacy host list')
        for entry in value:
            profile=profiles.clean(entry)
            records[profile['id']]=profile
    return [p for key,p in records.items() if key not in removed],removed


def legacy_summary():
    result=[]
    for root in legacy_roots():
        try:
            records,_=read_source(root)
            result.append({'physical_dir':str(root),'host_count':len(records)})
        except (OSError,ValueError,TypeError,KeyError): pass
    return result


def migrate_once(destination):
    """Merge only on the first canonical start; retain originals and backup copies."""
    import profiles
    destination=Path(destination)
    if os.environ.get('GPUCHECKER_DATA_DIR') or destination!=default_dir(): return
    if any((destination/name).exists() for name in ('profiles.json','host_catalog.json','storage_migration.json')): return
    sources=[]
    for root in legacy_roots():
        try:
            records,removed=read_source(root)
            sources.append((root,records,removed))
        except (OSError,ValueError,TypeError,KeyError): continue
    sources.sort(key=lambda entry:len(entry[1]),reverse=True)
    records={}
    endpoints=set()
    removed=set().union(*(entry[2] for entry in sources)) if sources else set()
    files=('profiles.json','host_catalog.json','ssh_config','known_hosts','availability_rules.json','inventory_hints.json','ui_preferences.json')
    backup=destination/'backups'/('storage-migration-'+time.strftime('%Y%m%d-%H%M%S'))
    for root,entries,_ in sources:
        stamp=hashlib.sha256(str(root).encode()).hexdigest()[:12]
        for name in files:
            source=root/name
            if not source.is_file(): continue
            target=backup/stamp/name;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(source,target)
            if name not in ('profiles.json','host_catalog.json') and not (destination/name).exists():
                shutil.copy2(source,destination/name)
        for profile in entries:
            key=(profile['host'].casefold(),profile.get('user',''),profile.get('port') or '22')
            if profile['id'] in removed or profile['id'] in records or key in endpoints: continue
            records[profile['id']]=profile;endpoints.add(key)
        for source in (root/'snapshots').glob('*.json'):
            target=destination/'snapshots'/source.name
            if not target.exists():
                target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
    # All data is copied before publishing the new authoritative host registry.
    destination.mkdir(parents=True,exist_ok=True)
    profiles.atomic_json(destination/'host_catalog.json',{'hosts':list(records.values()),'removed':sorted(removed)})
    profiles.atomic_json(destination/'profiles.json',list(records.values()))
    profiles.atomic_json(destination/'storage_migration.json',{
        'version':1,'at':time.time(),'host_count':len(records),
        'sources':[{'physical_dir':str(root),'host_count':len(entries)} for root,entries,_ in sources],
        'destination':str(destination),'legacy_files_untouched':True,
    })
