"""Bridge between the call audio and Amazon Nova 2.5 Sonic (Strands bidirectional agent)."""
import asyncio
import base64
import queue
import threading
import time

import boto3
from strands import tool
from strands.bidi import BidiAgent
from strands.bidi.models.bedrock import BedrockNovaSonicModel
from strands.bidi.types.events import BidiAudioDeltaEvent, BidiBargeInEvent, BidiTranscriptBlockEvent
from strands.bidi.types.media import AudioDelta

from . import audio, phone
from .config import AWS_PROFILE, AWS_REGION, DEBUG_TRANSCRIPTS, MODEL_ID, OWNER_NAME, VOICE
from .log import log

CHUNK = audio.RATE * 2 // 50  # 20 ms of 16-bit mono

SYSTEM_PROMPT = f"""Sos Jarvis, el asistente personal de voz de {OWNER_NAME}. Sos hombre.
Hablás por teléfono, en español rioplatense/paraguayo, con voseo, tono cálido y directo.
Respondé corto: una o dos frases, como en una llamada real. Nada de listas ni markdown.
Lo único que podés hacer por ahora es conversar y cortar la llamada. Todavía NO tenés acceso
a agenda, mensajes, recordatorios, apps ni nada del teléfono: si te piden algo de eso, decí
que todavía no podés y que se está construyendo. Nunca inventes capacidades ni resultados.
Cuando {OWNER_NAME} se despida o pida cortar, despedite en una frase y usá la herramienta colgar."""


@tool
def colgar() -> str:
    """Corta la llamada telefónica actual. Usar cuando el usuario se despide o pide cortar."""
    def later():
        time.sleep(4)  # let the goodbye finish playing
        phone.hang_up()
    threading.Thread(target=later, daemon=True).start()
    return "La llamada se corta en unos segundos."


class CallAudioInput:
    """Caller's voice as 16 kHz PCM deltas every 20 ms.

    Sonic stalls if the input stream pauses, and pw-record delivers nothing while the line is
    quiet/unlinked, so a reader thread fills a queue and gaps are padded with silence.
    """

    async def start(self, agent):
        self.proc = audio.recorder()
        self.queue = queue.Queue()
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self):
        while data := self.proc.stdout.read(CHUNK):
            self.queue.put(data)

    async def stop(self):
        self.proc.terminate()

    async def __call__(self):
        await asyncio.sleep(0.02)
        try:
            data = self.queue.get_nowait()
        except queue.Empty:
            data = b"\0" * CHUNK
        return AudioDelta(format="pcm", source={"bytes": data})


class OpeningText:
    """Sends one text turn so Sonic speaks first, then stays quiet."""

    def __init__(self, text):
        self.text = text

    async def start(self, agent):
        self.sent = False

    async def stop(self):
        pass

    async def __call__(self):
        if self.sent:
            await asyncio.Event().wait()
        self.sent = True
        return self.text


class CallAudioOutput:
    """Sonic's voice to the caller. Barge-in drops queued audio by restarting the player."""

    async def start(self, agent):
        self.proc = audio.player()

    async def stop(self):
        self.proc.kill()

    async def __call__(self, event):
        if isinstance(event, BidiAudioDeltaEvent):
            try:
                self.proc.stdin.write(base64.b64decode(event["audio"]))
                self.proc.stdin.flush()
            except BrokenPipeError:
                self.proc = audio.player()
        elif isinstance(event, BidiBargeInEvent):
            self.proc.kill()
            self.proc = audio.player()
        elif isinstance(event, BidiTranscriptBlockEvent):
            if DEBUG_TRANSCRIPTS:
                log(f"[{event.role}] {event.transcript}")
            else:
                log(f"[{event.role}] ({len(event.transcript)} chars)")


async def converse(opening):
    """Talk with the caller until the phone call ends."""
    model = BedrockNovaSonicModel(
        boto_session=boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION),
        model_id=MODEL_ID,
        voice=VOICE,
        audio={"input": {"sample_rate": audio.RATE}, "output": {"sample_rate": audio.RATE}},
    )
    agent = BidiAgent(model=model, tools=[colgar], system_prompt=SYSTEM_PROMPT)
    run = asyncio.create_task(agent.run(
        inputs=[CallAudioInput(), OpeningText(opening)], outputs=[CallAudioOutput()]))
    log("Sonic connected")
    while not run.done():
        if (await asyncio.to_thread(phone.call_state))[0] == 0:
            log("call ended")
            break
        await asyncio.sleep(1)
    run.cancel()
    try:
        await run
    except asyncio.CancelledError:
        pass
    except Exception as e:
        log("agent error:", repr(e))
    try:
        await agent.stop()
    except Exception:
        pass
