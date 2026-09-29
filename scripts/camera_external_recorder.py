#!/usr/bin/env python3
import argparse
import queue
import re
import subprocess
import threading
import time
from pathlib import Path

FRAME_RE = re.compile(r"^received_(\d+)\.yuv$")


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--input-dir", required=True)
    p.add_argument("--raw-output", required=True)
    p.add_argument("--mp4-output")
    p.add_argument("--fifo", default="")
    p.add_argument("--width", type=int, default=960)
    p.add_argument("--height", type=int, default=540)
    p.add_argument("--fps", type=float, default=15.0)
    p.add_argument("--duration", type=float, default=20.0)
    p.add_argument("--idle-timeout", type=float, default=3.0)
    p.add_argument("--no-live", action="store_true")
    return p.parse_args()


class LiveWriter:
    def __init__(self, width, height, fps):
        cmd = [
            "ffplay", "-loglevel", "warning",
            "-f", "rawvideo", "-pixel_format", "yuv420p",
            "-video_size", f"{width}x{height}", "-framerate", str(fps),
            "-window_title", "Pandia Receiver Live", "-i", "pipe:0",
        ]
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        self.queue = queue.Queue(maxsize=2)
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        self.submitted = 0

    def _run(self):
        while True:
            data = self.queue.get()
            if data is None:
                break
            try:
                self.proc.stdin.write(data)
                self.proc.stdin.flush()
            except (BrokenPipeError, OSError):
                break
        try:
            self.proc.stdin.close()
        except OSError:
            pass

    def submit(self, data):
        self.submitted += 1
        try:
            self.queue.put_nowait(data)
        except queue.Full:
            try:
                self.queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self.queue.put_nowait(data)
            except queue.Full:
                pass

    def stop(self):
        self.queue.put(None)
        self.thread.join(timeout=2)
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=1)


def encode_mp4(raw_output, mp4_output, width, height, fps):
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "rawvideo", "-pixel_format", "yuv420p",
        "-video_size", f"{width}x{height}", "-framerate", str(fps),
        "-i", str(raw_output),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(mp4_output),
    ]
    subprocess.run(cmd, check=True)


def main():
    args = parse_args()
    input_dir = Path(args.input_dir)
    raw_output = Path(args.raw_output)
    frame_size = args.width * args.height * 3 // 2
    input_dir.mkdir(parents=True, exist_ok=True)
    raw_output.parent.mkdir(parents=True, exist_ok=True)

    live = None if args.no_live else LiveWriter(args.width, args.height, args.fps)
    last_key = -1
    frame_count = 0
    started = time.monotonic()
    last_progress = started
    try:
        with raw_output.open("wb") as out:
            while time.monotonic() - started < args.duration:
                candidates = []
                for path in input_dir.iterdir():
                    m = FRAME_RE.match(path.name)
                    if not m:
                        continue
                    key = int(m.group(1))
                    if key <= last_key:
                        continue
                    try:
                        size = path.stat().st_size
                    except OSError:
                        continue
                    if size == frame_size:
                        candidates.append((key, path))
                candidates.sort()
                for key, path in candidates:
                    data = path.read_bytes()
                    if len(data) != frame_size:
                        continue
                    out.write(data)
                    out.flush()
                    if live is not None:
                        live.submit(data)
                    last_key = key
                    frame_count += 1
                    last_progress = time.monotonic()
                if frame_count and time.monotonic() - last_progress >= args.idle_timeout:
                    break
                time.sleep(0.03)
    finally:
        if live is not None:
            live.stop()

    print(f"FRAMES_RECORDED={frame_count}")
    print(f"LIVE_FRAMES_SUBMITTED={live.submitted if live else 0}")
    print(f"RAW_OUTPUT={raw_output}")
    print(f"RAW_BYTES={raw_output.stat().st_size if raw_output.exists() else 0}")
    if args.mp4_output and frame_count:
        encode_mp4(raw_output, args.mp4_output, args.width, args.height, args.fps)
        print(f"MP4_OUTPUT={args.mp4_output}")
        print(f"MP4_BYTES={Path(args.mp4_output).stat().st_size}")


if __name__ == "__main__":
    main()
