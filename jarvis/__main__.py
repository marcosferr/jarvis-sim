"""Jarvis: phone calls over your own SIM, voice and brain by Amazon Nova 2.5 Sonic.

  python -m jarvis listen                 answer calls from the owner and talk
  python -m jarvis serve                  same as listen, forever (for the systemd service)
  python -m jarvis dial "urgent text"     call the owner; Jarvis opens by delivering the text
"""
import asyncio
import sys

from . import audio, phone
from .config import OWNER_NAME
from .log import log


def handle_incoming():
    phone.wait_owner_call()
    opening = (f"[Llamada entrante: {OWNER_NAME} te acaba de llamar.] "
               "Saludalo brevemente y preguntale en qué lo ayudás.")
    talk(opening)


def handle_outgoing(message):
    log("dialing owner")
    phone.dial()
    if not phone.wait_answered():
        log("not answered")
        phone.hang_up()
        return
    opening = (f"[Llamada saliente: {OWNER_NAME} acaba de atender.] "
               f"Saludalo una sola vez como Jarvis y contale esto: {message}")
    talk(opening)


def talk(opening):
    if audio.wire_call():
        asyncio.run(sonic_converse(opening))
    else:
        log("ERROR: HFP audio streams never appeared (is the phone connected over Bluetooth?)")
    phone.hang_up()
    log("done")


def sonic_converse(opening):
    from .sonic import converse  # heavy import, only when a call is up
    return converse(opening)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "listen"
    audio.ensure_virtual_devices()
    if mode == "dial":
        handle_outgoing(sys.argv[2] if len(sys.argv) > 2 else "Es una llamada de prueba de Jarvis.")
    elif mode == "serve":
        while True:
            handle_incoming()
    else:
        handle_incoming()


if __name__ == "__main__":
    main()
