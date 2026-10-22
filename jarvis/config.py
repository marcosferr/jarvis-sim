"""Settings, read from the environment (see .env.example)."""
import os
from pathlib import Path


def _load_dotenv():
    env = Path(__file__).resolve().parent.parent / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()


def _required(name):
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Missing {name}: copy .env.example to .env and fill it in")
    return value


OWNER_NUMBER = _required("JARVIS_OWNER_NUMBER")          # the only number Jarvis answers / calls
OWNER_NAME = os.environ.get("JARVIS_OWNER_NAME", "el usuario")
PHONE_BT_ADDR = _required("JARVIS_PHONE_BT_ADDR").upper()  # e.g. AA:BB:CC:DD:EE:FF
PHONE_SERIAL = os.environ.get("JARVIS_PHONE_SERIAL", "")   # optional adb serial filter

AWS_PROFILE = os.environ.get("AWS_PROFILE") or None
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
MODEL_ID = os.environ.get("JARVIS_MODEL_ID", "amazon.nova-2-5-sonic")
VOICE = os.environ.get("JARVIS_VOICE", "carlos")  # Spanish (es-US): carlos (masc.) / lupe (fem.)

# PipeWire names the HFP streams bluez_input.<AA_BB_...> / bluez_output.<AA_BB_...>
BT_NODE_ID = PHONE_BT_ADDR.replace(":", "_")
