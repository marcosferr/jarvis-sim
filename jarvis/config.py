"""Settings, read from the environment (see .env.example)."""
import os

from .dotenv import load_dotenv

load_dotenv()


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


def _flag(name):
    return os.environ.get(name, "").lower() in ("1", "true", "yes", "si", "sí")


# Off by default: a call whose number adb can't see could be anyone, so it is not answered.
ANSWER_HIDDEN = _flag("JARVIS_ANSWER_HIDDEN")
# Off by default: transcripts are what you said on the phone; only log them when debugging.
DEBUG_TRANSCRIPTS = _flag("JARVIS_DEBUG_TRANSCRIPTS")

# Alert endpoint (POST /alerta). Without a token it stays off. 127.0.0.1 = only this machine;
# use the Tailscale IP to receive alerts / MCP calls from other machines.
ALERT_TOKEN = os.environ.get("JARVIS_ALERT_TOKEN", "")
HTTP_HOST = os.environ.get("JARVIS_HTTP_HOST", "127.0.0.1")
HTTP_PORT = int(os.environ.get("JARVIS_HTTP_PORT", "8765"))

# PipeWire names the HFP streams bluez_input.<AA_BB_...> / bluez_output.<AA_BB_...>
BT_NODE_ID = PHONE_BT_ADDR.replace(":", "_")
