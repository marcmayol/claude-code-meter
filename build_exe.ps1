# Construye el ejecutable independiente (dist\claude-code-meter.exe).
# Requiere: pip install pyinstaller
#
#   .\build_exe.ps1
#
# Nota: main.py importa bar/tray/meter de forma dinámica, por eso hace falta
# --collect-submodules claude_code_meter para que PyInstaller los incluya.

python -m PyInstaller --onefile --windowed `
  --name claude-code-meter `
  --icon assets/claude-code-meter.ico `
  --collect-submodules claude_code_meter `
  --collect-all pystray `
  --collect-submodules PIL `
  --noconfirm --clean `
  app_entry.py

Write-Host "`nListo: dist\claude-code-meter.exe"
