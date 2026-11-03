"""Build clean end-user and rebuildable source assets for a GitHub Release."""
import hashlib
import argparse
from pathlib import Path
import shutil
import subprocess
import zipfile
import runpy

ROOT=Path(__file__).resolve().parent
VERSION=runpy.run_path(str(ROOT/'src/version.py'))['APP_VERSION']
OUT=ROOT/'delivery/releases'/('v'+VERSION)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--exe',type=Path,default=ROOT/'build/release-runtime/GPUChecker.exe')
    args=parser.parse_args()
    from PyInstaller.archive.readers import CArchiveReader
    version_code=CArchiveReader(args.exe).open_embedded_archive('PYZ.pyz').extract('version')
    if VERSION not in version_code.co_consts or 'APP_VERSION' not in version_code.co_names:
        raise ValueError('Executable version does not match release version')
    OUT.mkdir(parents=True,exist_ok=True)
    executable=OUT/'GPUChecker.exe'
    shutil.copy2(args.exe,executable)
    runtime=OUT/f'GPUChecker-v{VERSION}-Windows-x64.zip'
    with zipfile.ZipFile(runtime,'w',zipfile.ZIP_DEFLATED) as archive:
        archive.write(executable,'GPUChecker/GPUChecker.exe')
        archive.write(ROOT/'docs/USAGE.md','GPUChecker/使用说明.md')
        archive.write(ROOT/'delivery/portable.flag.example','GPUChecker/portable.flag.example')
        archive.write(ROOT/'delivery/THIRD_PARTY_NOTICES.md','GPUChecker/THIRD_PARTY_NOTICES.md')
        for path in sorted((ROOT/'delivery/licenses').rglob('*')):
            if path.is_file(): archive.write(path,'GPUChecker/'+path.relative_to(ROOT/'delivery').as_posix())
    source=OUT/f'GPUChecker-v{VERSION}-source.zip'
    names=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
    with zipfile.ZipFile(source,'w',zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(filter(None,names)):
            if (ROOT/name).is_file():
                archive.write(ROOT/name,name)
    checksums=[]
    for path in (executable,runtime,source):
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        checksums.append(f'{digest}  {path.name}\n')
    (OUT/'SHA256SUMS.txt').write_text(''.join(checksums),encoding='utf-8')
    for path in (runtime,source):
        with zipfile.ZipFile(path) as archive:
            assert archive.testzip() is None
    print('Release assets:',OUT)
    for path in (executable,runtime,source,OUT/'SHA256SUMS.txt'):
        print(path.name,path.stat().st_size)


if __name__=='__main__':main()
