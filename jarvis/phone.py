"""Call control on the Android phone through adb (no root needed)."""
import re
import subprocess
import time

from .config import ANSWER_HIDDEN, OWNER_NUMBER, PHONE_SERIAL
from .log import log


def pick_serial():
    """First adb transport in 'device' state (USB or Wireless debugging; the TLS port changes)."""
    out = subprocess.run(["adb", "devices", "-l"], capture_output=True, text=True).stdout
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device" and (not PHONE_SERIAL or PHONE_SERIAL in line):
            return parts[0]
    raise SystemExit("Phone not reachable over adb: enable USB debugging or Wireless debugging")


_serial = None


def adb(*args):
    global _serial
    _serial = _serial or pick_serial()
    return subprocess.run(["adb", "-s", _serial, "shell", *args], capture_output=True, text=True).stdout


def same_number(a, b):
    digits = lambda s: "".join(c for c in s if c.isdigit())
    da, db = digits(a), digits(b)
    return len(da) >= 8 and len(db) >= 8 and da[-9:] == db[-9:]


def call_state():
    """(state, incoming number). state: 0 idle, 1 ringing, 2 offhook."""
    out = adb("dumpsys", "telephony.registry")
    st = re.search(r"mCallState=(\d)", out)
    num = re.search(r"mCallIncomingNumber=(\S*)", out)
    return (int(st.group(1)) if st else 0), (num.group(1) if num else "")


def foreground_state():
    """PreciseCallState of the foreground call: 0 idle, 1 active, 3 dialing, 4 alerting, 7 disconnected."""
    m = re.search(r"Foreground call state: (\d+)", adb("dumpsys", "telephony.registry"))
    return int(m.group(1)) if m else -1


def answer():
    """Answer the ringing call and confirm it went offhook. Some phones ignore some keys, so try several."""
    for key in ("KEYCODE_HEADSETHOOK", "KEYCODE_CALL"):  # HEADSETHOOK works on the Galaxy A16
        adb("input", "keyevent", key)
        for _ in range(6):
            time.sleep(0.5)
            if call_state()[0] == 2:
                log("answered with", key)
                return True
    # Last resort: tap the on-screen answer button. The dump goes to /data/local/tmp (only the adb
    # shell user can write there, unlike /sdcard where other apps could swap the file).
    dump = "/data/local/tmp/jarvis-ui.xml"
    adb("uiautomator", "dump", dump)
    ui = adb("cat", dump)
    adb("rm", "-f", dump)
    for label in ("Responder", "Contestar", "Aceptar", "Answer"):
        m = re.search(rf'(?:text|content-desc)="{label}"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', ui)
        if m:
            x1, y1, x2, y2 = map(int, m.groups())
            adb("input", "tap", str((x1 + x2) // 2), str((y1 + y2) // 2))
            for _ in range(6):
                time.sleep(0.5)
                if call_state()[0] == 2:
                    log("answered by tapping", label)
                    return True
    return False


def hang_up():
    adb("input", "keyevent", "KEYCODE_ENDCALL")


def dial(number=OWNER_NUMBER):
    adb("am", "start", "-a", "android.intent.action.CALL", "-d", f"tel:{number}")


def wait_answered(timeout=45):
    """After dialing, wait until the other side picks up (foreground call goes ACTIVE)."""
    deadline, seen_call = time.time() + timeout, False
    while time.time() < deadline:
        st = foreground_state()
        if st == 1:
            log("answered by remote")
            return True
        if st in (3, 4):
            seen_call = True
        elif seen_call and st in (0, 7):
            return False  # rejected or dropped
        time.sleep(0.5)
    return False


def check_incoming():
    """One poll. If the owner is calling, answer and return True. Other numbers, and hidden ones,
    are ignored (this waits until they hang up)."""
    state, num = call_state()
    if state != 1:
        return False
    log("ringing:", num or "(number hidden from adb)")
    if not num and not ANSWER_HIDDEN:
        log("hidden number -> ignoring (set JARVIS_ANSWER_HIDDEN=1 to answer these)")
    elif num and not same_number(num, OWNER_NUMBER):
        log("not owner -> ignoring")
    elif answer():
        return True
    else:
        log("ERROR: could not answer")
    while call_state()[0] != 0:
        time.sleep(0.5)
    return False


def wait_owner_call():
    """Block until the owner calls, answer it."""
    log("listening for calls from", OWNER_NUMBER)
    while not check_incoming():
        time.sleep(0.5)
