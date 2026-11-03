# 14.0.1：重启后主机列表退回一条的根因

## 实际问题

旧版把默认数据放在 `%LOCALAPPDATA%\GPUChecker`。在本机，工具进程打开这一逻辑路径时，Windows 文件句柄返回的真实文件却位于：

```
%LOCALAPPDATA%\Packages\<package-id>\LocalCache\Local\GPUChecker\profiles.json
```

工具环境里看到 8 台，桌面启动曾显示 1 台；两份数据并不是同一个物理文件。此前的列表同步、额外登记表和启动测试仍处在同一虚拟文件视图中，因此没有消除跨启动环境差异。

该机制与微软描述的 [MSIX AppData 文件系统重定向](https://learn.microsoft.com/windows/msix/desktop/desktop-to-uwp-behind-the-scenes) 一致。排查使用 `GetFinalPathNameByHandleW` 核实真实文件位置，而不是只比较显示出来的路径字符串。

## 修复

- 默认数据改放 `%USERPROFILE%\.gpu-checker`。实际文件句柄已确认落在该目录，不再依赖受包上下文影响的 AppData 视图。
- 首次使用时自动发现旧普通目录及包缓存中的 GPUChecker 目录，合并有效主机。保留完整登记表、稳定 ID、暂停设置、SSH 配置／信任记录、规则、主题和快照。
- 同一端点的重复默认条目不会额外增加一台；优先保留完整登记里的 ID，避免破坏已保存密码及快照的绑定。
- 迁移保留原目录，并把旧配置复制到新目录的 `backups/`。新目录一旦成为权威存储，不会在每次启动时重新导入旧目录；明确删除的主机不会复活。
- 显式便携模式仍使用 exe 旁的 `data/`。自动测试和管理员可以通过 `GPUCHECKER_DATA_DIR` 指定独立目录，不从旧环境导入主机。
- 运行诊断记录实际物理文件路径及旧存储视图的条目数，顶栏显示 `14.0.1`，便于区分旧程序。

## 回归验证

用两份旧目录模拟工具视图 8 台、桌面视图 1 台，交替启动 4 个独立进程。每次读取同一个新目录，均保持 8 台、相同 ID 和暂停设置。另检查原目录未改写、备份保留、快照复制及明确删除后不再迁回。

`GPUChecker.exe --storage-self-test` 执行同一启动读取流程并写入本地 `runtime_state.json`，随后退出；不展示窗口、不启动 SSH 监控。使用该模式可自动验证多次重启和不同环境变量下的物理路径一致性。

此修复不修改 Windows、Codex 或其他应用的虚拟化／安全设置。没有把任何个人配置写进 exe 或 Release。
