' Chay run_sample.bat o che do an (khong hien cua so console).
' Task Scheduler se goi file nay thay vi goi .bat truc tiep.
Set fso = CreateObject("Scripting.FileSystemObject")
Set WshShell = CreateObject("WScript.Shell")
batPath = fso.GetParentFolderName(WScript.ScriptFullName) & "\run_sample.bat"
WshShell.Run chr(34) & batPath & chr(34), 0, False
Set WshShell = Nothing
Set fso = Nothing
