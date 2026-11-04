# GPU Checker

Windows 多主机 NVIDIA GPU 监控工具。通过 SSH 实时查看显卡、用卡进程、用户和工作目录，支持日夜主题与机甲风界面。

## 下载与使用

到 [Releases](https://github.com/TheBlueBanisters/GPU-Checker/releases/latest) 下载 Windows x64 ZIP，解压后运行 `GPUChecker.exe`，无需安装 Python。

1. 添加主机，或导入／粘贴 SSH config。
2. 选择免密、私钥或密码登录；密码可保存到 Windows 凭据管理器。
3. 左侧主机并行监控，点击切换视图；暂停状态会记住。

- GPU 显示负载、显存、温度、功耗和趋势；进程可查看用户与目录。
- 彩色菱形区分空闲、可用、轻量占用、占用和不可用状态；可用性是资源提示，不预留资源。
- 离线保留最后快照；暂停时保留上次 GPU 状态标记，历史数据不计入当前可用数量。
- 无 GPU 主机也能保持 SSH 连接。采集只读，不控制服务器进程。
- 支持窗口与系统缩放适配、日夜渐变切换；连续点击 GPU 卡片可触发粉尘爆炸彩蛋，附带轻盈短音效，仅影响本地界面。

客户端面向 Windows 10/11 x64（已验证 Windows 11）；远端需要 Linux、Python 3.6+，GPU 监控另需 NVIDIA 驱动与 `nvidia-smi`。

配置、迁移、连接限制及构建方法见 [使用说明](docs/USAGE.md)。默认配置位于 `%USERPROFILE%\.gpu-checker`，更新程序会保留原有主机和快照。发行包不包含个人配置或凭据。

## 从源码构建

安装 Python 3.11+ x64，在 PowerShell 运行：

```powershell
.\build.ps1
```

成品位于 `delivery/releases/`。第三方声明及许可证见 [THIRD_PARTY_NOTICES](delivery/THIRD_PARTY_NOTICES.md)。
