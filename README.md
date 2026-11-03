# GPU Checker v3 · 多主机算力监控

Windows 上的轻量远程 NVIDIA GPU 查看器。新版程序在 `delivery/GPUChecker-v3.exe`，双击即可运行，不需要安装 Python、Qt 或 AI 服务。深色科幻界面包含荧光曲线、选中高亮、网格背景和半透明面板。

## 快速开始

1. 左侧直接显示主机列表及每台主机的在线状态、GPU 数量和平均负载。点击条目只切换右侧视图，**不会断开其他主机**。每台主机的连接、数据、最近 60 次趋势和重连计时独立保存于当前会话。
2. 点击“添加主机”或右侧“编辑”，在弹窗中填写名称、地址、用户名、端口和认证方式。“保存并监控”只重新连接被编辑的这一台主机。
3. 已能免密 SSH：保持“OpenSSH 免密”，用户名和端口留空以复用 config。自定义私钥可通过 `…` 选择。没有 OpenSSH 时可使用“内置密钥”。密码登录则选择内置密码模式，在弹窗中输入密码。
4. 导入主机后可点“全部连接”，或逐台点“连接主机”。默认每 2 秒采样，可在编辑弹窗改成 1–60 秒。“全部停止”停止所有监控；关闭窗口也会清理全部会话。
5. 点击进程行查看完整工作目录、可执行文件路径、UID、父 PID 和身份标记；这些文本可以选择复制。搜索框可筛选用户、PID、进程和目录。

每张 GPU 显示利用率、显存、温度、功耗、风扇、性能状态和最近 60 次利用率趋势。驱动不提供的字段显示 N/A。进程包括驱动报告的计算、图形进程；同一 PID 在不同 GPU 上分别列出。

首次新主机可使用内置模式核对并保存 SSH 指纹；OpenSSH 模式也可复用系统已有 known_hosts。多台主机的指纹确认会排队显示。**已经记录的主机密钥发生变化时会拒绝连接，不会自动覆盖。** 请向服务器管理员核实原因。

## 导入 SSH config 与迁移

“粘贴 / 编辑 config”打开多行文本编辑器，可以直接粘贴一份或多份 Host 配置，也可以读取文件或载入当前配置。点击“检查内容”会列出识别到的主机；保存时再次校验。校验失败不会覆盖原配置，也不会中断运行中的连接。

本程序要求具体条目有 Host 和可继承的 User；只有别名时还需 HostName。直接使用域名或 IP 作为 Host 可以省略 HostName。明确 User 的要求用于避免换电脑后误用本机账号，并不是声称 OpenSSH 语法本身必须写 User。Port 缺省为 22，IdentityFile 可省略以使用 Agent／默认密钥。错误报告会指出有问题的 Host 及缺失字段；非法端口和不完整的语法也会阻止保存。

```sshconfig
Host lab-gpu
    HostName gpu.example.com
    User yourname
    # Port 22 和 IdentityFile 都是可选项

Host another-gpu
    HostName another.example.com
    User yourname
    Port 8848
```

文本校验不会连接服务器或执行 Match exec。编辑器不支持校验 Match 条件块，会明确报告；复杂 Match 规则可以继续放在系统 OpenSSH config 中，通过免密模式使用已有别名。外部 Include 不自动展开校验，必要字段应在当前文本中给出。

“导入 SSH config”支持标准 OpenSSH config 文本以及本程序导出的 JSON。导入的具体 Host 别名会出现在连接列表中；通配符 Host 不作为独立条目。导入的 SSH config 被复制到本程序的数据目录，不修改系统 `~/.ssh/config`。再次导入时替换本程序副本，并保留上一份 `ssh_config.backup`。

OpenSSH 模式用原生 `ssh -F` 读取导入副本，支持 OpenSSH 自身的 Include、ProxyJump、ProxyCommand、Agent 和证书规则。Include 引用的文件不会自动打包；其路径继续遵循 OpenSSH 的规则。内置模式支持常用的 HostName、User、Port、IdentityFile，**仅支持直连，不完整实现 Include、Match、跳板机和证书等 OpenSSH 功能**；复杂配置请选 OpenSSH。

“保存并监控”保存连接参数；“迁移配置”导出连接条目与当前 SSH config 文本。程序输入的密码、私钥口令、私钥文件内容和主机信任记录不导出。SSH config 的自定义指令原样保留，如果你曾在 ProxyCommand 等自定义指令中自行写入秘密，导出前请自行删除。

换电脑后双击 exe，导入 JSON，重新选择该电脑上的私钥即可。主机密钥需要在新环境重新核对。程序没有绑定开发电脑的账号、Python 安装位置或项目目录。

## 配置与路径

- 默认配置目录：当前用户的 `%LOCALAPPDATA%/GPUChecker`，由系统环境动态定位。exe 放在只读目录也能使用。
- 便携模式：退出程序，在 exe 旁创建空文件 `portable.flag`，下次启动会使用旁边的 `data/`。随 exe 移动 data 文件夹即可。也可把本目录的 `portable.flag.example` 复制并改名为 `portable.flag`。默认配置不会自动搬过去；可以先导出再导入。
- 连接面板里的私钥支持 `~/.ssh/id_ed25519`、环境变量、绝对路径或相对于 exe 的路径，例如 `keys/id_ed25519`。程序选中当前用户目录内的私钥时优先保存为 `~/...`。
- SSH config 文件内的相对路径由 OpenSSH 解释，**不等同于相对于 exe**。跨电脑优先使用 `~/.ssh/...`。外部 Include、ProxyCommand 依赖和自定义绝对路径需要一并迁移或改写。
- OpenSSH 来自 PATH 或系统 Windows 目录的 OpenSSH，不假设安装盘符。也可自行在 exe 旁提供完整可用的 `tools/ssh.exe` 及其依赖；程序不附带 OpenSSH。
- 程序不需要用户填写绝对路径。对于系统 SSH 可执行文件、当前实际选中的外部密钥和配置文件，程序执行时会解析为绝对路径，以避免受工作目录影响。

## 自动化与连接行为

每台已连接主机使用一个持续的 SSH 会话和一个只读 Python 采集循环，不会每次刷新重新登录。所有主机并行采集，未选中的主机也继续积累趋势和更新左侧状态。不依赖 AI，也不要求打开终端或运行 `watch`。可以在编辑弹窗关闭某台主机的自动重连或下次启动自动监控。

网络异常会按 3、6、12、24、48、60 秒退避自动重连，直到恢复或点击“停止监控”。认证或主机密钥错误会停止重试，等待用户修正。每台主机独立重连，不影响其他会话。超过采样期限会标记数据已过期；停止后保留的是历史数据。远端 nvidia-smi 查询失败时显示原因，并继续尝试下次采样。选择 60 秒间隔时，连接超时也会相应延长。

服务器密码可选择保存在当前 Windows 用户的凭据管理器中，按主机 ID 和实际连接地址、用户名、端口绑定；不会写入 JSON、SSH config、源码或迁移包。程序启动会自动读取已保存密码进行连接。停止监控清空会话内存，但保留用户要求记住的凭据。取消“记住密码”并保存可删除已保存密码。私钥口令仍仅留在会话内存中。没有保存密码的主机会标记“待认证”。程序没有系统开机自启功能，不修改服务器或操作系统的 SSH 配置。旧版连接列表会自动迁移为具有独立 ID 的主机条目。

## 支持范围

- 客户端目标：Windows 10/11 x64；本次在 Windows 11 x64 验证。ARM 原生、Windows 7/8、Linux/macOS 客户端未验证。
- 远端目标：Linux + Python 3.6 及以上；GPU 遥测还需要可在非交互 SSH PATH 中运行的 `nvidia-smi`，只依赖 Python 标准库，无须 pip、root 或常驻代理。
- 支持多张 NVIDIA GPU；AMD/Intel GPU、远端 Windows 不在此版范围。MIG 实例信息按驱动报告展示，未做真实 MIG 机器测试。
- 容器、hidepid、不同用户权限或进程已退出时，cwd/exe 可能不可见；界面明确报告，不绕过系统权限。
- 远端 Python 不存在会提示。无 GPU 主机仍持续保持 SSH 连接；检测不到 NVIDIA 设备时显示“在线 · 无 GPU”。检测到设备却缺驱动／nvidia-smi 时单独显示“在线 · GPU 不可用”。若系统缺少 OpenSSH，可以使用内置模式直连。

## 安全边界

远端只调用 `nvidia-smi -q -x` 并读取 `/proc/<pid>/stat`、进程目录 UID、cwd/exe 链接。不会读环境变量或完整命令行参数，不使用 sudo、ptrace，不向用卡进程发送信号，不修改工作目录、文件、GPU 设置或驱动状态。采集代码通过内存传入，不在服务器安装文件或服务。断开时停止的是本机 SSH 连接与本程序的远端采集循环。

查询 `/proc` 前后比对启动 tick，发现 PID 复用时放弃目录结果。驱动快照与 proc 查询并非原子操作，不能保证在极端退出/复用竞态下获得完整进程归属证明。只读采样仍会有少量 CPU、驱动与网络开销；需要更低开销时可调大间隔。`pwd` 用户名解析可能涉及服务器自身 NSS 配置。

## 开发与构建

Python 3.11+ x64，执行 `powershell -ExecutionPolicy Bypass -File .\build.ps1`。脚本创建项目内隔离环境、安装锁定的直接依赖、运行测试并生成 exe。构建需要网络安装依赖；用户运行 exe 不需要这些构建工具。运行源码：`.\.buildenv\Scripts\python.exe src\app.py`。

图标来自内置 image_gen，原图 `assets/app.png`、多尺寸 Windows 图标 `assets/app.ico`、生成提示词 `assets/icon-prompt.txt`。第三方组件见 `delivery/THIRD_PARTY_NOTICES.md` 与 `delivery/licenses/`。源码、依赖清单和构建脚本一并交付，便于以后维护。

## v3 交互、字体与密码

按钮参考 [Fluent 2 按钮层级](https://fluent2.microsoft.design/components/web/react/core/button/usage/) 和 [字体层级](https://fluent2.microsoft.design/typography)，统一图标、圆角、悬停过渡和按下反馈；非主要操作采用低干扰按钮。随程序打包 Inter、Noto Sans SC、JetBrains Mono；字体来自 Google Fonts 官方仓库，OFL 文件在 assets/fonts 中，运行时不用在线下载或安装字体。

点击单台“暂停监控”或“全部暂停”会保存暂停状态；下次启动不会连接这些主机，即便已经保存密码。恢复监控后重新启用自动连接。正常关闭程序不会把主机误记为暂停。Windows 凭据仅属于当前机器和当前用户，迁移后需重新输入密码。桌面快捷方式指向本机交付目录中的 v3 exe，移动 exe 后需重新创建或调整快捷方式。
