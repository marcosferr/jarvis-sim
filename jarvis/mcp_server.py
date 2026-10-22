"""MCP server so any agent (Claude Code, Claude Desktop, ...) can phone the owner through Jarvis.

It only forwards to Jarvis's alert endpoint (POST /alerta), so it can run on another machine:

  claude mcp add jarvis -e JARVIS_URL=http://<linux>:8765 -e JARVIS_ALERT_TOKEN=<token> \\
      -- <python with mcp installed> -m jarvis.mcp_server
"""
import json
import os
import urllib.error
import urllib.request

try:
    from mcp.server import MCPServer
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as MCPServer

from .dotenv import load_dotenv

load_dotenv()
URL = os.environ.get("JARVIS_URL") or f"http://127.0.0.1:{os.environ.get('JARVIS_HTTP_PORT', '8765')}"
TOKEN = os.environ.get("JARVIS_ALERT_TOKEN", "")

mcp = MCPServer("jarvis")


@mcp.tool()
def llamar_por_telefono(mensaje: str) -> str:
    """Llama al celular del dueño y Jarvis le dice el mensaje en voz, en español, y puede conversar.

    Usalo solo para lo que necesita su atención ya: algo terminó, falló o hace falta que decida.
    Escribí el mensaje para ser escuchado: corto (máx. 500 caracteres), sin código ni enlaces.
    La llamada sale en segundos; si no atiende se reintenta una vez. El mismo mensaje repetido
    dentro de 5 minutos se ignora.
    """
    request = urllib.request.Request(
        URL.rstrip("/") + "/alerta",
        data=json.dumps({"mensaje": mensaje}).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {TOKEN}"},
        method="POST")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return "Llamada " + json.loads(response.read()).get("estado", "en cola")
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read())
        except ValueError:
            body = {}
        return f"No se llamó ({e.code}): {body.get('error') or body.get('estado') or e.reason}"
    except OSError as e:
        return f"Jarvis no responde en {URL}: {e}"


if __name__ == "__main__":
    mcp.run()
