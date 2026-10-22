"""PipeWire wiring for the HFP call audio.

With the native backend in the hands-free (hfp_hf) role, PipeWire exposes the call as *streams*,
not devices, so tools can't target them directly. Two virtual null sinks bridge them:

  phone -> bluez_input.<addr>  -> jarvis_rx (default sink)  -> pw-record (monitor) -> Sonic
  Sonic -> pw-play -> jarvis_tx (monitor) -> bluez_output.<addr> -> phone
"""
import re
import subprocess
import time

from .config import BT_NODE_ID
from .log import log

RATE = 16000


def _sh(*args):
    return subprocess.run(args, capture_output=True, text=True).stdout


def ensure_virtual_devices():
    nodes = _sh("pw-cli", "ls", "Node")
    for name in ("jarvis_rx", "jarvis_tx"):
        if f'node.name = "{name}"' not in nodes:
            _sh("pw-cli", "create-node", "adapter",
                f"{{ factory.name=support.null-audio-sink node.name={name} node.description={name} "
                f"media.class=Audio/Sink audio.position=[MONO] audio.rate={RATE} object.linger=true "
                "monitor.channel-volumes=true }")
    time.sleep(0.5)
    # Default sink = jarvis_rx, so WirePlumber routes the phone's audio there.
    for line in _sh("wpctl", "status").splitlines():
        m = re.search(r"(\d+)\.\s+jarvis_rx", line)
        if m:
            _sh("wpctl", "set-default", m.group(1))
            break


def wire_call(timeout=20):
    """Wait for the HFP streams, then link phone <-> jarvis_rx/jarvis_tx. Returns True when wired."""
    for _ in range(timeout * 2):
        ins = _sh("pw-link", "-i").split()
        outs = _sh("pw-link", "-o").split()
        tx_in = [p for p in ins if p.startswith(f"bluez_output.{BT_NODE_ID}")]
        rx_out = [p for p in outs if p.startswith(f"bluez_input.{BT_NODE_ID}")]
        if tx_in and rx_out:
            # Drop whatever WirePlumber linked into the phone (e.g. a monitor that would echo
            # the caller back), then feed it only from jarvis_tx.
            current = None
            for line in _sh("pw-link", "-l").splitlines():
                if not line.startswith(" "):
                    current = line.strip()
                elif current == tx_in[0] and "|<-" in line:
                    src = line.split("|<-", 1)[1].strip()
                    if src != "jarvis_tx:monitor_MONO":
                        _sh("pw-link", "-d", src, tx_in[0])
            _sh("pw-link", "jarvis_tx:monitor_MONO", tx_in[0])
            _sh("pw-link", rx_out[0], "jarvis_rx:playback_MONO")
            log("wired:", rx_out[0], "-> jarvis_rx ;", "jarvis_tx ->", tx_in[0])
            return True
        time.sleep(0.5)
    return False


def recorder():
    """Raw s16 mono 16 kHz of the caller's voice on stdout."""
    return subprocess.Popen(
        ["pw-record", "-P", "{ stream.capture.sink=true }", "--target", "jarvis_rx",
         "--rate", str(RATE), "--channels", "1", "--format", "s16", "--latency", "20ms", "-"],
        stdout=subprocess.PIPE)


def player():
    """Raw s16 mono 16 kHz on stdin goes to the caller."""
    return subprocess.Popen(
        ["pw-play", "--target", "jarvis_tx", "--rate", str(RATE), "--channels", "1",
         "--format", "s16", "--latency", "40ms", "-"],
        stdin=subprocess.PIPE)
