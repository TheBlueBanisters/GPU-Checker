"""Read-only Linux probe, sent in memory through SSH. Python 3.6+; no installation."""
import json
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


def parse_xml(xml, details=process_details):
    root = ET.fromstring(xml)
    gpus, processes, cache = [], [], {}
    for index, gpu in enumerate(root.findall("gpu")):
        g = {"index": index, "uuid": text(gpu, "uuid"), "name": text(gpu, "product_name"),
             "util": number(text(gpu, "utilization/gpu_util")),
             "used": number(text(gpu, "fb_memory_usage/used")),
             "total": number(text(gpu, "fb_memory_usage/total")),
             "temp": number(text(gpu, "temperature/gpu_temp")),
             "power": number(text(gpu, "gpu_power_readings/power_draw")),
             "fan": text(gpu, "fan_speed"), "state": text(gpu, "performance_state")}
        for path in ("gpu_power_readings/instant_power_draw", "gpu_power_readings/average_power_draw",
                     "power_readings/power_draw", "power_readings/instant_power_draw"):
            if g["power"] is None:
                g["power"] = number(text(gpu, path))
        gpus.append(g)
        for p in gpu.findall("processes/process_info"):
            pid = text(p, "pid")
            if not pid.isdigit():
                continue
            if pid not in cache:
                cache[pid] = details(pid)
            processes.append(dict(cache[pid], gpu=index, uuid=g["uuid"], pid=pid,
                                  kind=text(p, "type"), name=text(p, "process_name"),
                                  memory=number(text(p, "used_memory")),
                                  instance=text(p, "gpu_instance_id")))
    return {"gpus": gpus, "processes": processes, "driver": text(root, "driver_version"),
            "cuda": text(root, "cuda_version"), "timestamp": time.time()}


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
    return parse_xml(run.stdout)


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
