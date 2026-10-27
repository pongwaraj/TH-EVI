Option Explicit
Dim word, document, source, target, failure
source = WScript.Arguments(0)
target = WScript.Arguments(1)
Set word = CreateObject("Word.Application")
word.Visible = False
word.DisplayAlerts = 0
word.Options.PrintBackground = False
On Error Resume Next
Set document = word.Documents.Open(source, False, True)
If Err.Number <> 0 Then
    WScript.Echo "Open failed: " & Err.Description
    word.Quit 0
    WScript.Quit 1
End If
document.Repaginate
WScript.Echo "Pages: " & document.ComputeStatistics(2)
document.ExportAsFixedFormat target, 17
failure = Err.Number
If failure <> 0 Then WScript.Echo "Export failed: " & Err.Description
document.Close 0
word.Quit 0
If failure <> 0 Then WScript.Quit 1
WScript.Echo target
