# Problemas reales y soluciones

Todo esto pasó armando Jarvis con un Galaxy A16 y una notebook con Intel AX201 en Ubuntu 24.04.

## La llamada se atiende pero no hay audio (con oFono)

**Síntoma:** oFono atiende la llamada y el teléfono muestra el audio por Bluetooth
(`BT_AUDIO_CONNECTED` en `adb shell dumpsys telecom`), pero PipeWire no crea los nodos de audio.
WirePlumber registra:

```
getsockopt(SCO_OPTIONS) failed: 107 (Transport endpoint is not connected)
```

**Causa:** el traspaso del enlace de voz (SCO) de oFono a PipeWire falla. Probamos desactivar
mSBC y eSCO (`/sys/module/bluetooth/parameters/disable_esco`) y no cambió nada.

**Solución:** no usar oFono. Backend HFP **nativo** de PipeWire (`config/wireplumber/`),
`sudo systemctl disable --now ofono`, y control de llamadas por adb.

Si en algún momento usás oFono: reiniciá WirePlumber *después* de oFono, o WirePlumber queda con
`Failed to start HFP/HSP backend ofono`.

## `corrupted SCO packet` en el kernel

Aparece en `journalctl -k` con el Intel AX201 incluso cuando el audio funciona bien. Con mSBC
(16 kHz) es peor: por eso la configuración lo desactiva y usa CVSD (8 kHz).

## Los nodos `bluez_input` / `bluez_output` existen pero no se puede grabar ni reproducir

Con el rol manos libres (`hfp_hf`) PipeWire los crea como **streams**
(`Stream/Output/Audio` y `Stream/Input/Audio`), no como dispositivos, así que
`pw-record --target bluez_input...` devuelve 0 bytes.

**Solución:** dos sinks virtuales (`jarvis/audio.py`). `jarvis_rx` es el sink por defecto, así que
WirePlumber le manda el audio del teléfono, y se graba su monitor. Para hablar se reproduce en
`jarvis_tx` y su monitor se linkea a mano al stream del teléfono.

Un nodo `Audio/Source/Virtual` **no sirve** para inyectar audio: se escucha ruido en la llamada.
Tiene que ser un `Audio/Sink` y usar su monitor.

## Sonic se queda callado

1. **Ruta de internet.** Si el teléfono tiene el **anclaje USB** activo, la PC sale a internet por
   los datos de la SIM. Bedrock pasa a tardar 4–5 s en conectar y, durante una llamada, la voz
   sale entrecortada o no sale. Revisá:
   ```bash
   ip route | grep default   # no debería haber una ruta por enx...
   ```
   Desactivá el anclaje USB en el teléfono. Cada vez que se reenchufa aparece una interfaz `enx…`
   nueva, así que arreglarlo con `nmcli ... ipv4.never-default yes` no dura.
2. **Audio de entrada continuo.** Sonic necesita recibir audio sin cortes; `pw-record` no entrega
   nada mientras la línea está en silencio, por eso `CallAudioInput` rellena con silencio.
3. **Sesiones colgadas.** Cerrá siempre el agente (`agent.stop()`), no solo cancelar la tarea.

## adb se desconecta

- **Samsung Bloqueador automático** corta la depuración USB cada ~30 minutos: desactivalo.
- `no permissions (missing udev rules?)`: instalá `config/udev/51-android.rules`.
- La **depuración inalámbrica** se apaga sola a veces; el vínculo queda guardado, así que alcanza
  con volver a activarla. El puerto cambia: `adb mdns services` y `adb connect`.

## Jarvis no atiende

`KEYCODE_CALL` no atiende en el Galaxy A16; `KEYCODE_HEADSETHOOK` sí. `phone.answer()` prueba las
dos, después toca el botón en pantalla, y solo sigue cuando el teléfono confirma la llamada en
curso (`mCallState=2`). Para las salientes se espera `Foreground call state: 1` (el otro atendió).

## Jarvis inventa capacidades

Con un prompt genérico, Sonic dice que "puede manejar tu agenda". El prompt de `jarvis/sonic.py`
le dice explícitamente lo único que puede hacer; actualizalo cuando agregues herramientas.
