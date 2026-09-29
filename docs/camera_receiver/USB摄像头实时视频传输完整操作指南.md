# USB 摄像头实时视频传输完整操作指南

适用场景：本机 WSL 内运行 Sender/Receiver，使用 USB 摄像头实时采集，通过 WebRTC/GCC 传输，FFplay 实时显示并生成 MP4。

> 本文默认使用 `bin/peerconnection_camera` + `camera_external_recorder.py`。旧的 `peerconnection_client_headless_ffplay_v2` FIFO 显示补丁与新版摄像头 Sender 的信令版本不同，暂不能直接混用；兼容性说明见 `双机实时显示方案统一与待修改项.md`。

## 0. 组件说明

```text
USB 摄像头
  -> WSL /dev/video0
  -> peerconnection_camera Sender
  -> WebRTC/GCC + RTP
  -> Docker Receiver
  -> YUV 帧文件
  -> camera_external_recorder.py
  -> FFplay 实时窗口 + MP4
```

不使用 `tc`，不使用 STUN。

## 1. 将 USB 摄像头挂载到 WSL

在 Windows PowerShell 中执行：

```powershell
& 'C:\Program Files\usbipd-win\usbipd.exe' list
& 'C:\Program Files\usbipd-win\usbipd.exe' attach --wsl --busid 2-7
```

`2-7` 是当前摄像头的 BUSID，如果 `usbipd list` 中发生变化，应使用新的 BUSID。

如果提示：

```text
already attached to a client
```

通常可以直接继续。

## 2. 检查 WSL 摄像头

打开 WSL Ubuntu：

```powershell
wsl -d Ubuntu
```

执行：

```bash
ls -l /dev/video*
ffmpeg -hide_banner -f v4l2 -list_formats all -i /dev/video0
```

预期能看到 `/dev/video0` 和 `/dev/video1`，并看到 MJPEG 格式。

可选预览：

```bash
ffplay -f v4l2 \
  -input_format mjpeg \
  -video_size 320x240 \
  -framerate 15 \
  -window_title "WSL USB Camera Live Preview" \
  /dev/video0
```

确认画面后关闭预览，避免摄像头被占用。

## 3. 清理旧进程

在 WSL 中执行：

```bash
docker rm -f pandia-receiver-final pandia-receiver-dump pandia-receiver-live 2>/dev/null || true
```

如果 Sender 还在运行，在对应终端按 `Ctrl+C` 停止。不要使用 `pkill -f peerconnection_camera`，它可能误杀当前 shell。

## 4. 准备输出目录

```bash
mkdir -p /home/cjq/camtest/yuvout_final
rm -rf /home/cjq/camtest/yuvout_final/*
rm -f \
  /home/cjq/camtest/received_final.yuv \
  /home/cjq/camtest/received_final.mp4 \
  /home/cjq/camtest/recorder_final.log
```

## 5. 启动 Receiver

执行：

```bash
docker run -d \
  --name pandia-receiver-final \
  --network host \
  --gpus all \
  -v /home/cjq/Workspace/Pandia/bin/peerconnection_camera_stridefix:/opt/pandia-bin/peerconnection_camera_stridefix:ro \
  -v /home/cjq/Workspace/Pandia/bin/nvidia-libs:/opt/nvidia-libs:ro \
  -v /home/cjq/camtest/yuvout_final:/dump \
  -e LD_LIBRARY_PATH=/opt/nvidia-libs \
  --entrypoint /opt/pandia-bin/peerconnection_camera_stridefix \
  johnson163/pandia_receiver:latest \
  --receiving_only \
  --port 9999 \
  --dump_path /dump
```

检查：

```bash
docker logs pandia-receiver-final
```

应先看到：

```text
Start listen
```

## 6. 启动实时显示和 MP4 录制

执行：

```bash
nohup python3 /home/cjq/camtest/camera_external_recorder.py \
  --input-dir /home/cjq/camtest/yuvout_final \
  --raw-output /home/cjq/camtest/received_final.yuv \
  --mp4-output /home/cjq/camtest/received_final.mp4 \
  --width 960 \
  --height 540 \
  --fps 15 \
  --duration 3600 \
  --idle-timeout 5 \
  > /home/cjq/camtest/recorder_final.log 2>&1 &
```

脚本会：

- 监听 Receiver 输出的 YUV 帧；
- 保存原始 YUV；
- 将实时帧送入 FFplay；
- Sender 停止并闲置 5 秒后自动生成 MP4。

## 7. 启动 Sender

另开一个 WSL 终端：

```bash
wsl -d Ubuntu
```

执行：

```bash
/home/cjq/Workspace/Pandia/bin/peerconnection_camera_5fps \
  --server 127.0.0.1 \
  --port 9999 \
  --width 640 \
  --fps 5 \
  --path camera
```

预期输出：

```text
Camera device ready: 0
Camera source result: ok
Connected to the receiver
Capture incoming: type=9, size:..., 640x480
FrameCaptured, id: ..., width: 640, height: 480
Finish encoding
SendPacketToNetwork
```

此时应出现：

```text
Pandia Receiver Live
```

实时显示窗口。

## 8. 检查接收端

另开 WSL 终端执行：

```bash
docker logs -f pandia-receiver-final
```

成功时出现：

```text
Sender connected
Rtp packet received
Frame received
DecodeAndMaybeDispatchEncodedFrame
Notify frame decoded
```

查看录制日志：

```bash
tail -f /home/cjq/camtest/recorder_final.log
```

## 9. 停止传输

在 Sender 终端按：

```text
Ctrl+C
```

然后等待约 5 秒，录制脚本会自动生成 MP4并退出。

查看结果：

```bash
cat /home/cjq/camtest/recorder_final.log
ls -lh /home/cjq/camtest/received_final.mp4
ffprobe \
  -show_entries format=duration,size:stream=codec_name,width,height,avg_frame_rate,nb_frames \
  -of default=noprint_wrappers=1 \
  /home/cjq/camtest/received_final.mp4
```

播放视频：

```bash
ffplay /home/cjq/camtest/received_final.mp4
```

复制到 Windows：

```bash
cp /home/cjq/camtest/received_final.mp4 \
  '/mnt/d/desktop/犀牛鸟/pandia实验/本机摄像头WebRTC接收端输出.mp4'
```

## 10. 清理

```bash
docker rm -f pandia-receiver-final
```

## 11. 双机传输时的修改

Receiver 机器仍执行第 5、6 步。

Sender 机器只修改服务器地址：

```bash
/home/cjq/Workspace/Pandia/bin/peerconnection_camera_5fps \
  --server 192.168.18.接收端IP \
  --port 9999 \
  --width 640 \
  --fps 5 \
  --path camera
```

例如 Receiver 是 `192.168.18.65`：

```bash
/home/cjq/Workspace/Pandia/bin/peerconnection_camera_5fps \
  --server 192.168.18.65 \
  --port 9999 \
  --width 640 \
  --fps 5 \
  --path camera
```

两端需要能够通过 WLAN 互相访问，并允许 TCP 9999 和 WebRTC 动态 UDP 端口。

## 12. 常见问题

### /dev/video0: Device or resource busy

关闭 `ffplay`、`ffmpeg` 或上一个 Sender，再重新启动。

### usbipd 提示 already attached

通常可以继续。若 `/dev/video0` 不存在，保持 WSL 运行并重新执行：

```powershell
& 'C:\Program Files\usbipd-win\usbipd.exe' attach --wsl --busid 2-7
```

### FFplay 窗口不出现

执行：

```bash
export DISPLAY=:0
```

然后重新启动录制脚本。即使窗口不可用，MP4仍可正常生成。

### 输出是 960x540

Sender 采集是 640x480，但 WebRTC 内部视频适配后输出为 960x540；当前录制参数按 960x540 设置。
