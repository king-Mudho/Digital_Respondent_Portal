# Builds the one-page respondent guide: manuals/respondent_quick_guide.html -> docs/manuals/Respondent_Quick_Guide.pdf
# (A4, printed by Edge) and Respondent_Quick_Guide.png (for sending on WhatsApp). Bump the version line in the HTML
# whenever the wording changes, as with REVISION for the other manuals.
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$source = Join-Path $here "manuals\respondent_quick_guide.html"
$outDir = Resolve-Path (Join-Path $here "..\manuals")
$pdf = Join-Path $outDir "Respondent_Quick_Guide.pdf"
$png = Join-Path $outDir "Respondent_Quick_Guide.png"
$edge = "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe"
if (-not (Test-Path $edge)) { $edge = "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe" }

$uri = ([System.Uri](Resolve-Path $source).Path).AbsoluteUri
& $edge --headless=new --disable-gpu --no-pdf-header-footer --print-to-pdf="$pdf" $uri | Out-Null
Start-Sleep -Seconds 2
if (-not (Test-Path $pdf)) { throw "Edge did not write $pdf" }

$python = "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe"
& $python -c @"
import sys, pypdfium2 as pdfium
pdf = pdfium.PdfDocument(sys.argv[1])
if len(pdf) != 1:
    sys.exit(f'expected one page, got {len(pdf)}')
pdf[0].render(scale=2.2).to_pil().save(sys.argv[2])
print('1 page;', sys.argv[2])
"@ $pdf $png
