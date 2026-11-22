Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
pythonw = scriptDir & "\.venv\Scripts\pythonw.exe"
appScript = scriptDir & "\app.py"
WshShell.Run """" & pythonw & """ """ & appScript & """", 0, False
