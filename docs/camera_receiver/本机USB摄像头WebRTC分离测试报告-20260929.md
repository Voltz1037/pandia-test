# 本机 USB 摄像头 WebRTC 分离测试报告

日期：2026-09-29
测试人：曹家齐
测试环境：Windows WSL2 Ubuntu 24.04、USB 摄像头、Docker、NVIDIA GPU
测试方式：Sender 与 Receiver 分离运行；实时摄像头输入；外部脚本负责显示和生成视频文件。

## 1. 测试目标

完成本机分离测试，验证完整链路：

```text
USB 摄像头
  -> WSL V4L2 / MJPEG 采集
  -> WebRTC Sender 编码和 GCC 带宽控制
  -> RTP/RTCP
  -> WebRTC Receiver 接收、重组、解码
  -> WSL FFplay 实时显示
  -> FFmpeg 生成 MP4 文件
```

测试要求：

- 使用 WebRTC 自带 GCC 带宽控制；
- 不使用 `tc`；
- 不使用 STUN；
- Sender 和 Receiver 独立运行；
- 使用本机 USB 摄像头实时画面，不使用 Pandia offline 测试视频。

## 2. 本次解决的关键问题

### 2.1 Sender 实时摄像头输入

Sender 已支持：

```bash
--path camera
```

摄像头使用 V4L2 采集，并强制使用 MJPEG 输入格式，避免：

```text
Wrong incoming frame length
```

最终日志持续出现：

```text
Camera device ready: 0
Camera source result: ok
Capture incoming: type=9, size=..., 640x480
FrameCaptured, id: ..., width: 640, height: 480
Camera frame captured: 640x480
```

说明摄像头实时画面已经进入 WebRTC Sender。

### 2.2 Receiver 崩溃问题

使用新编译 Receiver 时曾出现退出码：

```text
139
```

即段错误。定位到 `Conductor::StartRemoteRenderer()` 中存在空指针调用：

```cpp
local_renderer_->SetDumpPath(dump_path_);
```

Receiver 在只接收模式下没有 `local_renderer_`，因此远端视频轨添加后会崩溃。

已改为：

```cpp
remote_renderer_->SetDumpPath(dump_path_);
```

服务器源码位置：

```text
~/Workspace/webrtc-camera-src
```

修改文件：

```text
examples/peerconnection_headless/client/conductor.cc
```

已重新编译并复制到本机：

```text
~/Workspace/Pandia/bin/peerconnection_camera
```

## 3. 外部显示和录制方案

不在 WebRTC Receiver 内部直接实现窗口和 MP4，而是使用外部脚本：

```text
D:\desktop\犀牛鸟\pandia实验\camera_external_recorder.py
```

工作流程：

1. Receiver 使用 `--dump_path /dump` 输出解码后的 I420/YUV 帧；
2. 外部脚本监听 `received_<rtp_sequence>.yuv`；
3. 脚本将 YUV 帧写入连续 raw 文件；
4. 同时通过管道将 YUV 帧送入 `ffplay` 实时显示；
5. 测试结束后由 `ffmpeg` 将 raw 文件编码为 MP4。

输出帧大小：

```text
960 x 540
YUV420p
每帧 777600 字节
```

## 4. 最终集成测试

### 4.1 Receiver

使用新编译 binary，独立运行：

```bash
docker run -d --name pandia-receiver-final \
  --network host \
  --gpus all \
  -v /home/cjq/Workspace/Pandia/bin/peerconnection_camera:/opt/pandia-bin/peerconnection_camera:ro \
  -v /home/cjq/Workspace/Pandia/bin/nvidia-libs:/opt/nvidia-libs:ro \
  -v /home/cjq/camtest/yuvout_final:/dump \
  -e LD_LIBRARY_PATH=/opt/nvidia-libs \
  --entrypoint /opt/pandia-bin/peerconnection_camera \
  johnson163/pandia_receiver:latest \
  --receiving_only \
  --port 9999 \
  --dump_path /dump
```

### 4.2 外部显示和录制

```bash
python3 /home/cjq/camtest/camera_external_recorder.py \
  --input-dir /home/cjq/camtest/yuvout_final \
  --raw-output /home/cjq/camtest/received_final.yuv \
  --mp4-output /home/cjq/camtest/received_final.mp4 \
  --width 960 \
  --height 540 \
  --fps 15 \
  --duration 25 \
  --idle-timeout 4
```

测试过程中启动了 FFplay 窗口：

```text
Pandia Receiver Live
```

### 4.3 Sender

```bash
/home/cjq/Workspace/Pandia/bin/peerconnection_camera \
  --server 127.0.0.1 \
  --port 9999 \
  --width 640 \
  --fps 30 \
  --path camera
```

## 5. 测试结果

| 项目 | 数量/结果 |
|---|---:|
| Sender 采集帧 | 170 |
| Sender 编码帧 | 166 |
| Sender 发送 RTP 包 | 1160 |
| Receiver 收到 RTP 包 | 1152 |
| Receiver 收到完整帧 | 165 |
| Receiver 解码成功帧 | 165 |
| 外部脚本写入帧 | 165 |
| FFplay 提交实时帧 | 165 |
| 输出 MP4 帧数 | 165 |
| 输出分辨率 | 960 x 540 |
| 输出帧率 | 15 fps |
| 输出时长 | 11.000 秒 |
| 丢包率 | 约 0.69% |
| 最终结果 | 通过 |

Sender 中 `FrameCaptured` 为 170，而最终编码为 166，主要包含启动、编码器初始化以及最后一帧尚未完成编码的边界差异。Receiver 中完整接收并解码 165 帧，外部脚本完整写入 165 帧。

## 6. 输出文件

Windows 报告目录：

```text
D:\desktop\犀牛鸟\pandia实验
```

接收端视频文件：

```text
D:\desktop\犀牛鸟\pandia实验\本机摄像头WebRTC接收端输出-20260929.mp4
```

外部显示和录制脚本：

```text
D:\desktop\犀牛鸟\pandia实验\camera_external_recorder.py
```

完整日志：

```text
D:\desktop\犀牛鸟\pandia实验\logs-20260929\sender_final.log
D:\desktop\犀牛鸟\pandia实验\logs-20260929\receiver_final.log
D:\desktop\犀牛鸟\pandia实验\logs-20260929\recorder_final.log
```

WSL 临时文件目录：

```text
/home/cjq/camtest
```

## 7. 结论

本次本机 USB 摄像头 WebRTC 分离测试已经完成：

- USB 摄像头实时采集成功；
- Sender 实时编码成功；
- GCC 正常工作；
- 未使用 `tc`；
- 未使用 STUN；
- RTP 媒体包成功发送和接收；
- 帧重组和解码成功；
- Receiver 实时窗口显示已运行；
- 已生成 MP4 视频文件。

下一阶段可将同一套 Sender/Receiver 流程迁移到双机 WLAN 通信，再进行延迟、丢包、卡顿等真实网络指标测试。
