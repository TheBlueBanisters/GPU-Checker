"""Package a complete runtime after checking every loadable binary's signature."""
import argparse,hashlib,runpy,shutil,subprocess,zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent
VERSION=runpy.run_path(str(ROOT/'src/version.py'))['APP_VERSION']


def runtime_files(runtime):
    runtime=Path(runtime).resolve()
    files=[]
    for path in sorted(runtime.rglob('*')):
        if path.is_symlink():raise ValueError('Runtime links are not allowed')
        if path.is_file():
            if not path.resolve().is_relative_to(runtime):raise ValueError('Runtime path escapes its root')
            files.append(path)
    if not (runtime/'GPUChecker.exe').is_file():raise ValueError('GPUChecker.exe is missing')
    return files


def verify_runtime(runtime,development=False):
    shell=shutil.which('pwsh') or shutil.which('powershell.exe')
    if not shell:raise RuntimeError('Windows PowerShell is required to verify Authenticode signatures')
    command=[shell,'-NoProfile','-NonInteractive','-File',str(ROOT/'sign_windows.ps1'),'-RuntimeDirectory',str(runtime),'-VerifyOnly']
    if development:command.append('-DevelopmentUnsigned')
    subprocess.run(command,check=True)


def write_runtime_zip(runtime,destination):
    runtime=Path(runtime).resolve()
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as archive:
        for path in runtime_files(runtime):archive.write(path,'GPUChecker/'+path.relative_to(runtime).as_posix())
        archive.write(ROOT/'docs/USAGE.md','GPUChecker/使用说明.md')
        archive.write(ROOT/'delivery/portable.flag.example','GPUChecker/portable.flag.example')
        archive.write(ROOT/'delivery/THIRD_PARTY_NOTICES.md','GPUChecker/THIRD_PARTY_NOTICES.md')
        for path in sorted((ROOT/'delivery/licenses').rglob('*')):
            if path.is_file():archive.write(path,'GPUChecker/'+path.relative_to(ROOT/'delivery').as_posix())


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--runtime',type=Path,default=ROOT/'build/release-runtime/GPUChecker')
    parser.add_argument('--allow-unsigned-development',action='store_true')
    args=parser.parse_args();runtime=args.runtime.resolve()
    runtime_files(runtime)
    from PyInstaller.archive.readers import CArchiveReader
    version_code=CArchiveReader(runtime/'GPUChecker.exe').open_embedded_archive('PYZ.pyz').extract('version')
    if VERSION not in version_code.co_consts or 'APP_VERSION' not in version_code.co_names:
        raise ValueError('Executable version does not match source version')
    # Never trust a pre-existing report: recheck the actual bytes before packaging.
    verify_runtime(runtime,args.allow_unsigned_development)
    out=ROOT/('delivery/development' if args.allow_unsigned_development else 'delivery/releases')/('v'+VERSION)
    out.mkdir(parents=True,exist_ok=True)
    suffix='-UNSIGNED-DEVELOPMENT' if args.allow_unsigned_development else ''
    binary=out/f'GPUChecker-v{VERSION}-Windows-x64{suffix}.zip'
    write_runtime_zip(runtime,binary)
    source=out/f'GPUChecker-v{VERSION}-source.zip'
    names=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
    with zipfile.ZipFile(source,'w',zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(filter(None,names)):
            if (ROOT/name).is_file():archive.write(ROOT/name,name)
    files=(binary,source)
    (out/'SHA256SUMS.txt').write_text(''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n' for p in files),encoding='utf-8')
    for path in files:
        with zipfile.ZipFile(path) as archive:assert archive.testzip() is None
    print('Development assets (not SAC-approved):' if args.allow_unsigned_development else 'Signed release assets:',out)
    for path in files:print(path.name,path.stat().st_size)


if __name__=='__main__':main()
