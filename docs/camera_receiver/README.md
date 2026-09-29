# Camera Receiver 联调资料

- [双机视频延迟波动分析与测试计划](双机视频延迟波动分析与测试计划-20260929.md)：距离相关延迟、同距离抖动、当前显示链路风险，以及不使用 tc 的分层验证方案。
- [摄像头到 FFplay 端到端流程与排障说明](摄像头到FFplay端到端流程与排障说明-20260929.md)：从采集、编码、网络、解码、stride 导出到外部显示的完整机制，包含徐健博侧挂载修复、脚本限制及验证边界。
- `双机摄像头WebRTC接收端修改与联调说明.md`：当前问题、Receiver 修改要求和双机启动方法。
- `双机实时显示方案统一与待修改项.md`：新版摄像头方案与旧 FIFO 显示补丁的兼容性、差异和下一阶段顺序。
- `USB摄像头实时视频传输完整操作指南.md`：从 USB 挂载到实时显示、MP4 输出的完整操作。
- `接收端Stride花屏修复结果-20260929.md`：花屏根因、修复实现、stride 统计和部署命令。
- `stridefix-source-changes.patch`：接收端 stride 修复源码 diff。
- `本机USB摄像头WebRTC分离测试报告-20260929.md`：本机全链路验证结果。
- `../../bin/peerconnection_camera`：原新版 Linux x86-64 WebRTC Sender/Receiver binary。
- `../../bin/peerconnection_camera_stridefix`：修复 YUV stride 花屏后的 Receiver 推荐 binary。
- `../../bin/peerconnection_camera_stridefix.sha256`：stridefix binary 校验值。
- `../../bin/peerconnection_camera.sha256`：binary 校验值。
- `../../scripts/camera_external_recorder.py`：接收端实时显示、YUV 保存和 MP4 生成脚本。

相关但目前尚未完全合并的接收端 FIFO 显示记录：

- `../receiver_preview/接收端实时显示阶段工作总结与复测指南.md`

最重要的结论：Sender 和 Receiver 必须使用同一个 `peerconnection_camera` 信令版本。旧的 `peerconnection_client_headless_ffplay_v2` 不能直接与新版摄像头 Sender 配对；如果要保留 FIFO 显示，需要把显示实现合并到新版源码后重新编译。
