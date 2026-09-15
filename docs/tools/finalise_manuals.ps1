# Opens each generated manual in Microsoft Word, fills in the table of
# contents and page numbers, saves the .docx, and exports a PDF beside it.
# Run after build_manuals.js:  powershell -ExecutionPolicy Bypass -File finalise_manuals.ps1
$ErrorActionPreference = "Stop"
$dir = Resolve-Path (Join-Path $PSScriptRoot "..\manuals")
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
    Get-ChildItem -Path $dir -Filter *.docx | Where-Object { $_.Name -notlike "~$*" } | ForEach-Object {
        $doc = $word.Documents.Open($_.FullName, $false, $false, $false)
        foreach ($toc in $doc.TablesOfContents) { $toc.Update() }
        $doc.Fields.Update() | Out-Null
        $doc.Repaginate()
        foreach ($toc in $doc.TablesOfContents) { $toc.UpdatePageNumbers() }
        $doc.Save()
        $pdf = [System.IO.Path]::ChangeExtension($_.FullName, ".pdf")
        # 17 = PDF; 0 = optimise for print; bookmarks from headings (1)
        $doc.ExportAsFixedFormat($pdf, 17, $false, 0, 0, 0, 0, 0, $true, $true, 1, $true, $true, $false)
        "{0}: {1} pages" -f $_.Name, $doc.ComputeStatistics(2)
        $doc.Close($false)
    }
}
finally {
    $word.Quit()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
}
