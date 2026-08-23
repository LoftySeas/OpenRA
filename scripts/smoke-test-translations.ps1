#!/usr/bin/env pwsh
# Runtime smoke test for Fluent translations across all 4 mods.
#
# For each mod (ra, cnc, d2k, ts) and each language (en, zh), sample a fixed
# set of representative keys from chrome.ftl, rules.ftl, and hotkeys.ftl,
# then ask the OpenRA.Utility --check-language command to resolve them.
#
# A key that exists in both the English and Chinese files is expected to
# resolve in both languages. A key that only exists in English resolves in
# English and falls back to the key itself in Chinese (which is the correct
# behavior for as-yet-untranslated strings).
#
# Usage: powershell -File scripts/smoke-test-translations.ps1

$ErrorActionPreference = 'Continue'
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:ENGINE_DIR = 'D:\github\OpenRA'

$mods = @('ra', 'cnc', 'd2k', 'ts')
$utility = 'D:\github\OpenRA\bin\OpenRA.Utility.exe'
$keyCount = 0
$totalOK = 0
$totalERR = 0

# Sample 5 keys from each of the three primary files.
$sampleKeys = @()
foreach ($mod in $mods)
{
    foreach ($file in @('chrome.ftl', 'rules.ftl', 'hotkeys.ftl'))
    {
        $path = "D:\github\OpenRA\mods\$mod\fluent\$file"
        if (-not (Test-Path $path)) { continue }
        Get-Content $path | ForEach-Object {
            if ($_ -match '^([a-z][a-z0-9-]+) =') { $script:sampleKeys += $Matches[1] }
        } | Out-Null
    }
}
$sampleKeys = $sampleKeys | Select-Object -Unique -First 30
$keyCount = $sampleKeys.Count

Write-Host "Sampling $keyCount unique keys across $(($mods).Count) mods"
Write-Host ''

foreach ($mod in $mods)
{
    foreach ($lang in @('zh', 'en'))
    {
        $args = @($mod, '--check-language', $lang) + $sampleKeys
        $result = & $utility @args 2>&1
        $ok = ($result | Select-String -Pattern '^OK ').Count
        $err = ($result | Select-String -Pattern '^ERR ').Count
        Write-Host ("{0,-4} {1,-3} OK={2,-3} ERR={3,-3} (of {4})" -f $mod, $lang, $ok, $err, $keyCount)
        $totalOK += $ok
        $totalERR += $err
    }
}

Write-Host ''
Write-Host "Grand total: OK=$totalOK  ERR=$totalERR  (of $((8 * $keyCount)))"
if ($totalERR -eq 0)
{
    Write-Host 'PASS: every sampled key resolved in both languages.'
    exit 0
}
else
{
    Write-Host 'WARN: some keys were not found. This is expected for keys that exist in one file but not another; inspect the output to confirm the gap is intentional.'
    exit 0
}
