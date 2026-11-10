"""Release gates run real Windows signature verification without creating keys."""
import importlib.util,json,os,shutil,subprocess
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('release_packager',ROOT/'package_github_release.py')
packager=importlib.util.module_from_spec(spec);spec.loader.exec_module(packager)
SHELL=shutil.which('pwsh') or shutil.which('powershell.exe')


@pytest.mark.skipif(os.name!='nt' or not SHELL,reason='Windows Authenticode required')
def test_release_rejects_unsigned_binary_and_development_report_is_explicit(tmp_path):
    executable=tmp_path/'GPUChecker.exe';executable.write_bytes(b'MZ-not-a-trusted-program')
    command=[SHELL,'-NoProfile','-NonInteractive','-File',str(ROOT/'sign_windows.ps1'),'-RuntimeDirectory',str(tmp_path),'-VerifyOnly']
    rejected=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=30)
    assert rejected.returncode!=0 and not (tmp_path/'SIGNATURES.json').exists()
    allowed=subprocess.run(command+['-DevelopmentUnsigned'],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=30)
    assert allowed.returncode==0,allowed.stderr
    report=json.loads((tmp_path/'SIGNATURES.json').read_text(encoding='utf-8-sig'))
    assert report['distribution']=='unsigned-development'
    assert report['binaries'][0]['status']!='Valid'
    # A forged success report must not bypass actual verification.
    (tmp_path/'SIGNATURES.json').write_text('{"distribution":"signed-release"}')
    assert subprocess.run(command,capture_output=True,timeout=30).returncode!=0


@pytest.mark.skipif(os.name!='nt' or not SHELL,reason='Windows release build required')
def test_missing_certificate_stops_default_build_before_installing_or_building(tmp_path):
    env=os.environ.copy();env.pop('GPUCHECKER_SIGNING_THUMBPRINT',None)
    result=subprocess.run([SHELL,'-NoProfile','-NonInteractive','-File',str(ROOT/'build.ps1')],env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=30)
    assert result.returncode!=0 and 'certificate is required' in result.stderr


def test_directory_zip_preserves_loadable_runtime_and_excludes_data_outside_it(tmp_path):
    import zipfile
    runtime=tmp_path/'runtime';runtime.mkdir();(runtime/'GPUChecker.exe').write_bytes(b'MZ')
    internal=runtime/'_internal';internal.mkdir();(internal/'python311.dll').write_bytes(b'dll')
    (tmp_path/'profiles.json').write_text('private profile outside runtime')
    output=tmp_path/'app.zip';packager.write_runtime_zip(runtime,output)
    with zipfile.ZipFile(output) as archive:
        assert 'GPUChecker/_internal/python311.dll' in archive.namelist()
        assert not any(p.endswith('profiles.json') for p in archive.namelist())
