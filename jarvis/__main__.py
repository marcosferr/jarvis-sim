"""Jarvis: phone calls over your own SIM, voice and brain by Amazon Nova 2.5 Sonic.

  python -m jarvis listen                 answer one call from the owner and talk
  python -m jarvis serve                  forever: answer the owner's calls and phone them about
                                          alerts posted to /alerta (for the systemd service)
  python -m jarvis dial "urgent text"     call the owner; Jarvis opens by delivering the text
"""
import asyncio
import sys
import time

from . import alerts, audio, phone
from .config import OWNER_NAME, OWNER_NUMBER
from .log import log

INCOMING_OPENING = (f"[Llamada entrante: {OWNER_NAME} te acaba de llamar.] "
                    "Saludalo brevemente y preguntale en qué lo ayudás.")


def handle_incoming():
    phone.wait_owner_call()
    talk(INCOMING_OPENING)


def handle_outgoing(message):
    """Call the owner and deliver the message. Returns False if they didn't answer."""
    log("dialing owner")
    phone.dial()
    if not phone.wait_answered():
        log("not answered")
        phone.hang_up()
        return False
    opening = (f"[Llamada saliente: {OWNER_NAME} acaba de atender.] "
               f"Saludalo una sola vez como Jarvis y contale esto: {message}")
    talk(opening)
    return True


def serve():
    """One loop owns the phone: queued alerts are dialed between polls for incoming calls."""
    alerts.start_server()
    log("listening for calls from", OWNER_NUMBER)
    while True:
        due = alerts.pop_due()
        if due:
            message, attempt = due
            if not handle_outgoing(message):
                alerts.retry_later(message, attempt)
        elif phone.check_incoming():
            talk(INCOMING_OPENING)
        time.sleep(0.5)


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
        serve()
    else:
        handle_incoming()


if __name__ == "__main__":
    main()
