# Jarvis por SIM propia

Un asistente de voz que atiende y hace **llamadas telefónicas reales** con la SIM de un
Android, sin proveedores de telefonía (nada de Twilio, Vapi ni Bland) y **sin root**.
La voz y el cerebro son **Amazon Nova 2.5 Sonic** (voz a voz, en español).

- **Entrante:** llamás al número del Android y charlás con Jarvis.
- **Saliente:** Jarvis te llama cuando pasa algo urgente y te cuenta qué pasó.

## Cómo funciona

```
 Tu celular ──red celular──▶ Android con la SIM de Jarvis
                                   │  Bluetooth HFP (la PC hace de "manos libres de auto")
                                   ▼
                         PC Linux: BlueZ + PipeWire (backend HFP nativo)
                                   │  audio de la llamada 8 kHz ⇄ 16 kHz
                                   ▼
                    jarvis_rx / jarvis_tx (sinks virtuales) ⇄ pw-record / pw-play
                                   │
                                   ▼
                    Strands BidiAgent ⇄ Amazon Nova 2.5 Sonic (Bedrock, us-east-1)

 Control de la llamada (atender, marcar, cortar, estado): adb por USB o depuración inalámbrica
```

En Android, el audio de una llamada va directo del módem al parlante o al Bluetooth: sin root,
ninguna app puede escuchar ni hablar dentro de una llamada. La salida es que la PC se empareje
con el teléfono como si fuera el **manos libres de un auto** (perfil Bluetooth HFP): el teléfono
le manda el audio de la llamada y la PC puede escuchar y hablar.

## Requisitos

| | Probado con |
|---|---|
| Teléfono Android con SIM, sin root | Samsung Galaxy A16 (SM-A165M), Android 16 |
| PC Linux con Bluetooth y WiFi | Ubuntu 24.04, BlueZ 5.72, PipeWire 1.0.5, WirePlumber 0.4.17, Intel AX201 |
| Cuenta de AWS con Bedrock | Acceso a `amazon.nova-2-5-sonic` en us-east-1 |
| Python | 3.12 |

## Instalación

### 1. Preparar la PC

```bash
git clone <este repo> ~/jarvis-sim && cd ~/jarvis-sim
./scripts/setup.sh
```

El script crea el entorno de Python, instala `adb` en tu usuario, configura WirePlumber para que
la PC actúe como manos libres y crea `.env`. Al final imprime dos comandos con `sudo` que tenés
que correr vos: desactivar **oFono** y agregar la regla **udev** para adb por USB.

> **Importante:** oFono tiene que estar apagado. Con oFono, la llamada se atiende pero el audio
> nunca llega a PipeWire (ver [docs/troubleshooting.md](docs/troubleshooting.md)).

### 2. Preparar el teléfono

1. **Opciones de desarrollador** → activar **Depuración USB** y **Depuración inalámbrica**.
2. Samsung: **Ajustes → Seguridad y privacidad → Bloqueador automático → desactivar**.
   Si no, corta la depuración USB cada ~30 minutos.
3. **Ajustes → Conexiones → Hotspot y anclaje → Anclaje USB → desactivado.** Si está activo, la
   PC sale a internet por los datos de la SIM, y durante una llamada eso hace que Sonic se escuche
   entrecortado o directamente no responda.
4. Dejalo enchufado al cargador y cerca de la PC (el Bluetooth llega a unos 10 m).

### 3. Conectar adb

Por USB: enchufá el teléfono y aceptá **"¿Permitir depuración USB?"** (marcá "Permitir siempre").

Por WiFi (recomendado, mismo WiFi que la PC): en **Depuración inalámbrica → Vincular dispositivo
con código de vinculación**:

```bash
adb pair <IP>:<puerto de vinculación> <código>
adb mdns services          # muestra <IP>:<puerto> de conexión
adb connect <IP>:<puerto>
adb devices -l             # debe decir "device"
```

Jarvis elige solo la conexión adb que esté funcionando (el puerto TLS cambia cada vez).

### 4. Emparejar el teléfono por Bluetooth

Con **Ajustes → Bluetooth** abierto en el teléfono (para que sea visible):

```bash
bluetoothctl pairable on
bluetoothctl discoverable on
bluetoothctl scan on            # esperá a ver el nombre del teléfono, después Ctrl+C
bluetoothctl pair <MAC>         # confirmá el código en la PC y en el teléfono
bluetoothctl trust <MAC>
bluetoothctl connect <MAC>
bluetoothctl info <MAC> | grep -E "Connected|Handsfree Audio Gateway"
```

### 5. Configurar `.env`

```ini
JARVIS_OWNER_NUMBER=+595XXXXXXXXX   # el único número que Jarvis atiende y al que llama
JARVIS_OWNER_NAME=Marcos
JARVIS_PHONE_BT_ADDR=AA:BB:CC:DD:EE:FF
AWS_PROFILE=mi-perfil               # vacío = cadena de credenciales por defecto
AWS_REGION=us-east-1
JARVIS_VOICE=carlos                 # o lupe
JARVIS_ANSWER_HIDDEN=0              # 1 = atender también llamadas con número oculto (cualquiera)
JARVIS_DEBUG_TRANSCRIPTS=0          # 1 = guardar en el log lo que se habla en cada llamada
```

Por seguridad, Jarvis **no atiende** si adb no puede ver el número que llama: podría ser cualquiera.
Si tu teléfono nunca muestra el número entrante por adb, el log dice `hidden number -> ignoring`;
en ese caso podés activar `JARVIS_ANSWER_HIDDEN=1`, sabiendo que cualquiera con número privado podrá
hablar con Jarvis.

Verificá el acceso a Sonic:

```bash
aws bedrock get-foundation-model-availability --region us-east-1 \
  --model-id amazon.nova-2-5-sonic --query authorizationStatus
```

### 6. Probar el audio (sin IA)

```bash
.venv/bin/python scripts/audio_test.py          # llamá al teléfono desde tu número
.venv/bin/python scripts/audio_test.py dial     # o que el teléfono te llame
```

Tenés que escuchar tres pitidos; después hablás 10 segundos y el script muestra un medidor de
nivel por segundo. Pitidos y nivel con forma de habla = el audio funciona en los dos sentidos.

### 7. Hablar con Jarvis

```bash
.venv/bin/python -m jarvis listen                                # atiende una llamada tuya
.venv/bin/python -m jarvis dial "Se cayó el servidor de ventas"  # te llama con un aviso
```

Jarvis solo atiende tu número (los demás los ignora), te saluda, conversa, te deja
interrumpirlo, y corta cuando te despedís.

### 8. Dejarlo corriendo siempre (opcional)

```bash
mkdir -p ~/.config/systemd/user
cp config/jarvis.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now jarvis
journalctl --user -u jarvis -f      # ver el log (las conversaciones, solo con JARVIS_DEBUG_TRANSCRIPTS=1)
loginctl enable-linger "$USER"      # que arranque aunque no inicies sesión
```

El servicio asume que el repo está en `~/jarvis-sim`.

## Estructura

```
jarvis/
  __main__.py   modos listen / serve / dial
  phone.py      control de llamadas por adb (estado, atender, marcar, cortar)
  audio.py      cableado de PipeWire (sinks virtuales jarvis_rx / jarvis_tx)
  sonic.py      puente con Nova 2.5 Sonic (Strands BidiAgent) y herramienta "colgar"
  config.py     configuración desde .env
scripts/
  setup.sh       instalación
  audio_test.py  prueba del audio en los dos sentidos, sin IA
config/
  wireplumber/   backend HFP nativo (0.4 .lua y 0.5 .conf)
  udev/          regla para adb por USB (Samsung)
  jarvis.service unidad systemd --user
docs/
  troubleshooting.md  problemas reales que encontramos y cómo se resolvieron
```

## Limitaciones conocidas

- **Calidad telefónica:** el audio va en CVSD a 8 kHz (mSBC/16 kHz falla en algunos adaptadores
  Intel). Alcanza de sobra para conversar.
- **Arranque:** la primera frase de Jarvis tarda unos segundos, porque la conexión con Sonic se
  abre recién cuando se atiende la llamada.
- **Herramientas:** por ahora Jarvis solo conversa y corta. Leer apps del teléfono (por ejemplo
  capturas por adb + un modelo con visión como Nova 2 Lite) está pendiente.
- **Nova Sonic** corta cada conexión a los ~8 minutos; Strands la reconecta sola a los 7.
- Atender por adb usa teclas del sistema; probado en Samsung. Otros teléfonos pueden necesitar
  ajustar `phone.answer()`.
