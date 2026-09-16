# Opens each generated manual in Microsoft Word, fills in the table of
# contents and page numbers, saves the .docx, and exports a PDF beside it.
# Run after build_manuals.js:  powershell -ExecutionPolicy Bypass -File finalise_manuals.ps1
# A PDF that is open in a viewer can't be overwritten: that document is
# reported and skipped, and the rest still finish. Close it and run again.
$ErrorActionPreference = "Stop"
$dir = Resolve-Path (Join-Path $PSScriptRoot "..\manuals")
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
$failed = @()
try {
    foreach ($file in Get-ChildItem -Path $dir -Filter *.docx | Where-Object { $_.Name -notlike "~$*" }) {
        $pdf = [System.IO.Path]::ChangeExtension($file.FullName, ".pdf")
        try {
            if (Test-Path $pdf) {
                $stream = [System.IO.File]::Open($pdf, 'Open', 'ReadWrite', 'None'); $stream.Close()
            }
        } catch {
            "{0}: SKIPPED - the PDF is open in another program; close it and run again" -f $file.Name
            $failed += $file.Name
            continue
        }
        $doc = $word.Documents.Open($file.FullName, $false, $false, $false)
        try {
            foreach ($toc in $doc.TablesOfContents) { $toc.Update() }
            $doc.Fields.Update() | Out-Null
            $doc.Repaginate()
            foreach ($toc in $doc.TablesOfContents) { $toc.UpdatePageNumbers() }
            $doc.Save()
            # 17 = PDF; 0 = optimise for print; bookmarks from headings (1)
            $doc.ExportAsFixedFormat($pdf, 17, $false, 0, 0, 0, 0, 0, $true, $true, 1, $true, $true, $false)
            "{0}: {1} pages" -f $file.Name, $doc.ComputeStatistics(2)
        }
        catch {
            "{0}: FAILED - {1}" -f $file.Name, $_.Exception.Message
            $failed += $file.Name
        }
        finally {
            $doc.Close($false)
        }
    }
}
finally {
    $word.Quit()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
}
if ($failed.Count) { exit 1 }
