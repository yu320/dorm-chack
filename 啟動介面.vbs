Set WshShell = CreateObject("WScript.Shell")
WshShell.Run """.venv\Scripts\pythonw.exe"" main.py --gui", 0, False
