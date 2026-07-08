' Lanza las cifras incrustadas en la barra de tareas, sin ventana de consola.
Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = "C:\Users\marcm\ClaudeCodeMeter"
sh.Run "pythonw.exe ""C:\Users\marcm\ClaudeCodeMeter\bar.py""", 0, False
