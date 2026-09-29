# Camera Receiver 联调资料

- `双机摄像头WebRTC接收端修改与联调说明.md`：当前问题、Receiver 修改要求和双机启动方法。
- `双机实时显示方案统一与待修改项.md`：新版摄像头方案与旧 FIFO 显示补丁的兼容性、差异和下一阶段顺序。
- `USB摄像头实时视频传输完整操作指南.md`：从 USB 挂载到实时显示、MP4 输出的完整操作。
- `本机USB摄像头WebRTC分离测试报告-20260929.md`：本机全链路验证结果。
- `../../bin/peerconnection_camera`：已修复的 Linux x86-64 WebRTC Sender/Receiver binary。
- `../../bin/peerconnection_camera.sha256`：binary 校验值。
- `../../scripts/camera_external_recorder.py`：接收端实时显示、YUV 保存和 MP4 生成脚本。

相关但目前尚未完全合并的接收端 FIFO 显示记录：

- `../receiver_preview/接收端实时显示阶段工作总结与复测指南.md`

最重要的结论：Sender 和 Receiver 必须使用同一个 `peerconnection_camera` 信令版本。旧的 `peerconnection_client_headless_ffplay_v2` 不能直接与新版摄像头 Sender 配对；如果要保留 FIFO 显示，需要把显示实现合并到新版源码后重新编译。
