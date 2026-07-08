' Autoarranque sin ventana de consola (estilo barra).
' Requiere haber instalado el paquete:  pip install claude-code-meter
Set sh = CreateObject("WScript.Shell")
sh.Run "pythonw.exe -m claude_code_meter.main bar", 0, False
