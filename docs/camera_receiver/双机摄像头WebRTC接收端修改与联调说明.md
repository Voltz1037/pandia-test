# 双机摄像头 WebRTC Receiver 修改与联调说明

日期：2026-09-29
参与人：曹家齐、徐健博、吴浩闻
目标：实现 Sender 从 USB 摄像头实时采集，通过 WebRTC/GCC 发送到另一台电脑的 Receiver，并在 Receiver 实时显示和生成视频文件。

## 1. 当前现象

本次双机网络使用移动热点：

```text
Sender IP:   172.20.10.7
Receiver IP: 172.20.10.2
```

Windows 网络测试结果：

```text
Test-NetConnection 172.20.10.2 -Port 9999
TcpTestSucceeded: True
```

因此 TCP 9999 信令端口已经连通。

### 1.1 Sender 日志

成功的部分：

```text
Connecting to 172.20.10.2
Connecting result: 0
Camera device ready: 0
Camera source result: ok
Connected to the receiver
FrameCaptured, id: ..., width: 640, height: 480
Camera frame captured: 640x480
```

失败的部分：

```text
Finish encoding: 0
SendPacketToNetwork: 0
```

Sender 共采集到 21 帧摄像头画面，但视频编码器没有开始编码，说明 WebRTC 媒体连接尚未建立。

### 1.2 Receiver 日志

成功的部分：

```text
Sender connected
Received 4235 bytes from peer
Sent 4012 bytes
```

失败的部分：

```text
Rtp packet received: 0
Frame received: 0
Notify frame decoded: 0
```

Receiver 能通过 TCP 收到 Offer 并返回 Answer，但没有收到 RTP 视频包。

### 1.3 关键异常

Sender 收到 Answer/Candidate 时出现：

```text
Received 1 bytes from peer
Received 1378 bytes from peer
Received 3989 bytes from peer
Received 18 bytes from peer
Received 1 bytes from peer
```

正常的新版本应该把一行 JSON 作为一条完整信令，例如：

```text
Received 4012 bytes from peer
Received 183 bytes from peer
```

上述碎片说明 Sender 和 Receiver 的信令 framing 不一致。常见原因是：

- Sender 使用了新编译的 `peerconnection_camera`；
- Receiver 仍在使用旧镜像里的 `peerconnection_client_headless_Release`；
- 或者 Receiver 的自定义修改与 Sender 不同。

## 2. 最快解决方式：使用同一 binary

本仓库提供了已经修复并验证过的 Linux x86-64 binary：

```text
bin/peerconnection_camera
```

SHA256：

```text
3de169e3da871b34d065880a133a4beae736866e31bbe069902d193c60211fbf
```

Sender 和 Receiver 必须使用同一版本。Receiver 不要直接执行镜像里的旧文件：

```text
/app/peerconnection_client_headless_Release
```

应把仓库中的文件挂载为：

```text
/opt/pandia-bin/peerconnection_camera
```

## 3. Receiver 启动方法

先停止旧 Receiver：

```bash
docker rm -f pandia-receiver 2>/dev/null || true
```

准备本机文件：

```text
~/Workspace/Pandia/bin/peerconnection_camera
~/Workspace/Pandia/bin/nvidia-libs
```

验证 binary：

```bash
sha256sum ~/Workspace/Pandia/bin/peerconnection_camera
```

应得到：

```text
3de169e3da871b34d065880a133a4beae736866e31bbe069902d193c60211fbf
```

启动 Receiver：

```bash
docker run -d \
  --name pandia-receiver \
  --network host \
  --gpus all \
  -v "$HOME/Workspace/Pandia/bin/peerconnection_camera:/opt/pandia-bin/peerconnection_camera:ro" \
  -v "$HOME/Workspace/Pandia/bin/nvidia-libs:/opt/nvidia-libs:ro" \
  -e LD_LIBRARY_PATH=/opt/nvidia-libs \
  --entrypoint /opt/pandia-bin/peerconnection_camera \
  johnson163/pandia_receiver:latest \
  --receiving_only \
  --port 9999
```

查看日志：

```bash
docker logs -f pandia-receiver
```

最终应该出现：

```text
Sender connected
Rtp packet received
Frame received
DecodeAndMaybeDispatchEncodedFrame
Notify frame decoded
```

## 4. Sender 启动方法

Sender 机器执行：

```bash
/home/cjq/Workspace/Pandia/bin/peerconnection_camera \
  --server 172.20.10.2 \
  --port 9999 \
  --width 640 \
  --fps 30 \
  --path camera \
  2>&1 | tee /home/cjq/camtest/sender_twohost.log
```

成功时 Sender 应出现：

```text
Connected to the receiver
Camera source result: ok
FrameCaptured
Finish encoding
SendPacketToNetwork
Frame decoding acked
```

注意：Sender 是直接运行的程序，不是 Docker 容器。停止 Sender 使用 `Ctrl+C`，不需要执行：

```bash
docker stop pandia-sender
```

## 5. 如果对方坚持自己编译 WebRTC

Receiver 至少需要与 Sender 保持以下三类修改一致。

### 5.1 信令必须是单行 JSON 加换行

`examples/peerconnection_headless/client/peer_connection_client.cc` 中，发送时必须添加换行：

```cpp
bool PeerConnectionClient::SendToPeer(int peer_id, const std::string& message) {
  if (connected) {
    std::string framed = message + "\n";
    auto sent = hanging_get_->Send(framed.c_str(), framed.size());
    return sent > 0;
  }
  // ...
}
```

JSON Writer 必须关闭缩进：

```cpp
Json::StreamWriterBuilder factory;
factory["indentation"] = "";
SendMessage(Json::writeString(factory, jmessage));
```

否则 SDP 中的换行或 pretty JSON 会被接收端误认为多条消息。

### 5.2 接收端必须缓存和按换行拆分消息

`PeerConnectionClient` 需要成员：

```cpp
std::string recv_buffer_;
```

`OnGetMessage()` 应：

1. 把本次 socket 数据追加到 `recv_buffer_`；
2. 以 `\n` 为边界拆分完整消息；
3. 将不完整尾部保留在 `recv_buffer_`；
4. 只把完整的一行交给 `OnMessageFromPeer()`。

如果继续输出：

```text
Received 1 bytes from peer
Received 1378 bytes from peer
Received 3989 bytes from peer
```

说明这一部分没有改对。

### 5.3 修复 Receiver 的远端渲染空指针

`examples/peerconnection_headless/client/conductor.cc` 中，旧代码可能写成：

```cpp
local_renderer_->SetDumpPath(dump_path_);
```

但在 `--receiving_only` 模式下 `local_renderer_` 为空。必须改成：

```cpp
remote_renderer_->SetDumpPath(dump_path_);
```

否则 Receiver 在远端视频轨添加后可能直接退出，状态码为：

```text
139
```

### 5.4 音频设备

如果容器内启动时报：

```text
Failed to initialize the ADM
```

应使用 dummy audio ADM，保证视频 Receiver 可以独立运行。该修改属于 Conductor 初始化 PeerConnectionFactory 的部分。

### 5.5 Sender 专用修改

以下修改主要影响 Sender，Receiver 可以保留，但不是 Receiver 收到 RTP 的必要条件：

- `--path camera`；
- V4L2 摄像头源；
- MJPEG 输入格式；
- `CapturerTrackSource`；
- NVIDIA/WSL 运行库路径。

## 6. 实时显示和生成 MP4

> 显示方案兼容性、旧 FIFO v2 补丁与新版摄像头 binary 的差异，见：docs/camera_receiver/双机实时显示方案统一与待修改项.md。当前双机摄像头测试先使用本文件的 in/peerconnection_camera + 外部录制方案；旧的 peerconnection_client_headless_ffplay_v2 不能直接与新版 Sender 配对。


仓库同时提供：

```text
scripts/camera_external_recorder.py
```

Receiver 使用：

```bash
--dump_path /dump
```

输出解码后的 YUV 帧，再由外部脚本：

1. 保存 raw YUV；
2. 调用 FFplay 实时显示；
3. 调用 FFmpeg 生成 MP4。

详细命令见：

```text
docs/camera_receiver/USB摄像头实时视频传输完整操作指南.md
```

## 7. 判定标准

| 阶段 | Sender | Receiver |
|---|---|---|
| TCP 信令 | `Connected to the receiver` | `Sender connected` |
| 摄像头 | `Camera source result: ok` | 不适用 |
| 编码 | `Finish encoding` | 不适用 |
| RTP | `SendPacketToNetwork` | `Rtp packet received` |
| 帧重组 | 不适用 | `Frame received` |
| 解码确认 | `Frame decoding acked` | `Notify frame decoded` |

只有 Receiver 出现 `Frame received` 和 `Notify frame decoded`，才代表实时视频真正传通。

## 8. 常见问题

### TCP 9999 通，但没有 RTP

`Test-NetConnection` 只验证 TCP 9999，不验证 UDP 媒体。优先检查：

1. 两端是否使用同一个 `peerconnection_camera`；
2. Receiver 是否仍使用旧的 `/app/peerconnection_client_headless_Release`；
3. Sender 是否仍出现 `Received 1 bytes` 等信令碎片；
4. Windows/WSL 防火墙是否允许 WebRTC 动态 UDP。

### Receiver 启动后找不到 libnvcuvid

确保挂载 `nvidia-libs`，并设置：

```text
LD_LIBRARY_PATH=/opt/nvidia-libs
```

### Sender 采集正常但没有 Finish encoding

这不是摄像头故障，而是 ICE/DTLS/RTP 媒体连接没有建立。先修复信令 framing 和 binary 版本一致性。
