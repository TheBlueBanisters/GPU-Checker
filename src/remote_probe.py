"""Read-only Linux probe, sent in memory through SSH. Python 3.6+; no installation."""
import json
import csv
import os
import pwd
import shutil
import glob
import subprocess
import sys
import time
import xml.etree.ElementTree as ET


def number(value):
    try:
        return float(value.split()[0])
    except (ValueError, AttributeError, IndexError):
        return None


def text(node, path):
    return node.findtext(path, default="N/A")


def process_details(pid):
    """Never read environ/cmdline, attach, signal, or escalate privileges."""
    base = "/proc/" + str(int(pid))
    try:
        def stat():
            with open(base + "/stat") as f:
                return f.read().rsplit(")", 1)[1].split()
        before = stat()
        uid = os.stat(base).st_uid
        try:
            user = pwd.getpwuid(uid).pw_name
        except KeyError:
            user = str(uid)
        result = {"user": user, "uid": uid, "ppid": before[1], "start": before[19]}
        for field in ("cwd", "exe"):
            try:
                result[field] = os.readlink(base + "/" + field)
            except PermissionError:
                result[field] = "无权限（系统保护）"
            except FileNotFoundError:
                result[field] = "已退出或不可用"
            except OSError:
                result[field] = "不可用"
        if stat()[19] != before[19]:
            return {"user": "进程已变化", "cwd": "等待下次采样", "exe": "—"}
        return result
    except PermissionError:
        return {"user": "无权限", "cwd": "无权限（系统保护）", "exe": "—"}
    except (OSError, IndexError):
        return {"user": "已退出", "cwd": "进程已退出或 PID 不在当前命名空间", "exe": "—"}


def parse_gpu_indices(output):
    indices={}
    for row in csv.reader(output.decode('utf-8','replace').splitlines()):
        if len(row)!=2: continue
        index,uuid=(value.strip() for value in row)
        if index.isdigit() and uuid and uuid!='N/A':
            value=int(index)
            indices[uuid]=value if uuid not in indices or indices[uuid]==value else None
    return indices


def parse_xml(xml, details=process_details, indices=None):
    root = ET.fromstring(xml)
    gpus, processes, cache = [], [], {}
    for gpu in root.findall("gpu"):
        uuid=text(gpu,'uuid')
        native=text(gpu,'index')
        index=indices.get(uuid) if indices is not None else int(native) if native.isdigit() else None
        g = {"index": index, "uuid": text(gpu, "uuid"), "name": text(gpu, "product_name"),
             "util": number(text(gpu, "utilization/gpu_util")),
             "used": number(text(gpu, "fb_memory_usage/used")),
             "total": number(text(gpu, "fb_memory_usage/total")),
             'free':number(text(gpu,'fb_memory_usage/free')),
             "temp": number(text(gpu, "temperature/gpu_temp")),
             "power": number(text(gpu, "gpu_power_readings/power_draw")),
             "fan": text(gpu, "fan_speed"), "state": text(gpu, "performance_state")}
        process_node=gpu.find('processes')
        process_text=(process_node.text or '').lower() if process_node is not None else ''
        g.update(compute_mode=text(gpu,'compute_mode'),mig_mode=text(gpu,'mig_mode/current_mig'),
                 recovery_action=text(gpu,'gpu_recovery_action'),
                 slowdown_temp=number(text(gpu,'temperature/gpu_temp_slow_threshold')),
                 remap_failure=text(gpu,'remapped_rows/remapping_failure'),
                 minor_number=text(gpu,'minor_number'),
                 process_query_ok=process_node is not None and not any(s in process_text for s in ('not supported','insufficient','permission','error','n/a')))
        ecc=[number(text(gpu,p)) for p in ('ecc_errors/volatile/dram_uncorrectable',
             'ecc_errors/volatile/double_bit/device_memory','ecc_errors/volatile/device_memory/uncorrectable')]
        g['ecc_uncorrectable']=max((n for n in ecc if n is not None),default=None)
        for path in ("gpu_power_readings/instant_power_draw", "gpu_power_readings/average_power_draw",
                     "power_readings/power_draw", "power_readings/instant_power_draw"):
            if g["power"] is None:
                g["power"] = number(text(gpu, path))
        gpus.append(g)
        for p in gpu.findall("processes/process_info"):
            pid = text(p, "pid")
            if not pid.isdigit():
                g['process_query_ok']=False
                continue
            if pid not in cache:
                cache[pid] = details(pid)
            processes.append(dict(cache[pid], gpu=index, uuid=g["uuid"], pid=pid,
                                  kind=text(p, "type"), name=text(p, "process_name"),
                                  memory=number(text(p, "used_memory")),
                                  instance=text(p, "gpu_instance_id")))
    return {"gpus": gpus, "processes": processes, "driver": text(root, "driver_version"),
            "cuda": text(root, "cuda_version"), "timestamp": time.time(),
            'gpu_status':'available' if gpus else 'no_gpu'}


def sample():
    smi = shutil.which("nvidia-smi")
    if not smi:
        present=bool(glob.glob('/dev/nvidia[0-9]*'))
        for device in glob.glob('/sys/bus/pci/devices/*/vendor'):
            try:
                with open(device) as f:
                    vendor=f.read().strip()
                with open(device.rsplit('/',1)[0]+'/class') as f:
                    category=f.read().strip()
                present=present or (vendor=='0x10de' and category.startswith('0x03'))
            except OSError:
                pass
        return {'gpus':[],'processes':[],'driver':'N/A','cuda':'N/A','timestamp':time.time(),
                'gpu_status':'unavailable' if present else 'no_gpu',
                'notice':'SSH 已连接；检测到 NVIDIA 设备，但 nvidia-smi 不可用' if present else 'SSH 已连接；当前环境未检测到 NVIDIA GPU，连接仍持续保活'}
    env = dict(os.environ, LC_ALL="C")
    run = subprocess.run([smi, "-q", "-x"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         timeout=8, env=env)
    if run.returncode:
        message=(run.stderr+run.stdout).decode('utf-8','replace')[:1200]
        if 'no devices were found' in message.lower():
            return {'gpus':[],'processes':[],'driver':'N/A','cuda':'N/A','timestamp':time.time(),
                    'gpu_status':'no_gpu','notice':'SSH 已连接；nvidia-smi 未发现 NVIDIA GPU'}
        return {'gpus':[],'processes':[],'driver':'N/A','cuda':'N/A','timestamp':time.time(),
                'gpu_status':'unavailable','notice':'SSH 已连接，GPU 查询不可用：'+message}
    try:
        index_run=subprocess.run([smi,'--query-gpu=index,uuid','--format=csv,noheader,nounits'],
                                 stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=8,env=env)
        indices=parse_gpu_indices(index_run.stdout) if index_run.returncode==0 else {}
    except (OSError,subprocess.TimeoutExpired):
        indices={}
    data=parse_xml(run.stdout,indices=indices)
    if any(g['index'] is None for g in data['gpus']):
        data['notice']='部分 GPU 原生编号暂不可读，显示 —；不会按返回顺序重新编号'
    for g in data['gpus']:
        minor=g.get('minor_number','')
        paths=['/dev/nvidia'+minor,'/dev/nvidiactl'] if minor.isdigit() else []
        g['device_access']=(all(os.access(p,os.R_OK|os.W_OK) for p in paths)
                            if paths and all(os.path.exists(p) for p in paths) else None)
    return data


def main(interval=2):
    while True:
        start = time.monotonic()
        try:
            payload = sample()
        except Exception as exc:
            payload = {"error": str(exc), "timestamp": time.time()}
        try:
            print("GPUCHECK:" + json.dumps(payload, ensure_ascii=True), flush=True)
        except (BrokenPipeError, OSError):
            break
        time.sleep(max(0.2, interval - (time.monotonic() - start)))


if __name__ == "__main__":
    main(float(sys.argv[1]) if len(sys.argv) > 1 else 2)
