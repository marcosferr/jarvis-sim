#!/usr/bin/env python3
"""Check the call audio path in both directions, without any AI.

Call the phone from the owner's number (or pass "dial" to have the phone call the owner).
Once the call is up you hear three beeps (laptop -> phone), then talk for 10 s; the script
records what reaches the laptop (phone -> laptop) and prints a per-second level meter.

  python scripts/audio_test.py [listen|dial]
"""
import math
import struct
import subprocess
import sys
import time
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from jarvis import audio, phone  # noqa: E402
from jarvis.log import log  # noqa: E402

SECONDS = 10


def beeps():
    frames = bytearray()
    for i in range(int(audio.RATE * 1.5)):
        on = (i // (audio.RATE // 4)) % 2 == 0  # 250 ms on / off
        frames += struct.pack("<h", int(8000 * math.sin(2 * math.pi * 800 * i / audio.RATE)) if on else 0)
    return bytes(frames)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "listen"
    audio.ensure_virtual_devices()
    if mode == "dial":
        phone.dial()
        if not phone.wait_answered():
            return log("not answered")
    else:
        phone.wait_owner_call()
    if not audio.wire_call():
        phone.hang_up()
        return log("ERROR: HFP audio streams never appeared")
    play = audio.player()
    play.stdin.write(beeps()); play.stdin.close()
    log(f"beeps sent; talk for {SECONDS} s")
    rec = audio.recorder()
    pcm = rec.stdout.read(audio.RATE * 2 * SECONDS)
    rec.terminate()
    phone.hang_up()
    out = Path(f"audio-test-{time.strftime('%Y%m%d-%H%M%S')}.wav")
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(audio.RATE); w.writeframes(pcm)
    for s in range(SECONDS):
        chunk = pcm[s * audio.RATE * 2:(s + 1) * audio.RATE * 2]
        n = len(chunk) // 2
        rms = math.sqrt(sum(v * v for (v,) in struct.iter_unpack("<h", chunk)) / n) if n else 0
        print(f"{s:2d}s {'#' * int(min(60, rms / 100))}")
    log("saved", out, "- silence everywhere means the phone -> laptop path is broken")


if __name__ == "__main__":
    main()
