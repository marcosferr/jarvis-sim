-- Jarvis: the PC acts as a car hands-free (HFP HF) for the phone.
-- PipeWire's native backend handles HFP; oFono must NOT be running (it breaks the SCO audio handoff).
-- mSBC (wideband) is off: some Intel adapters (e.g. AX201) corrupt mSBC SCO packets; CVSD 8 kHz works.
-- For WirePlumber 0.4.x (Ubuntu 24.04). Install to ~/.config/wireplumber/bluetooth.lua.d/
bluez_monitor.properties["bluez5.hfphsp-backend"] = "native"
bluez_monitor.properties["bluez5.enable-msbc"] = false
bluez_monitor.properties["bluez5.roles"] = "[ hfp_hf ]"
