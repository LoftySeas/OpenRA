#!/usr/bin/env pwsh
# Insert a `LanguageFonts: zh:` block after each `Fonts:` block in mod.yaml.
# Each mod has its own font set; the override mirrors the same names but
# routes them to SourceHanSansCN so CJK characters render with the right glyphs.

$ErrorActionPreference = 'Stop'
$mods = @('cnc', 'd2k', 'ra', 'ts')
$contentMods = @('cnc-content', 'd2k-content', 'ra-content', 'ts-content')

# Font definitions: each entry produces a (name, fontPath, size, ascender) row.
# Size and Ascender match the existing default font block in each mod so layout
# measurements stay identical between English and Chinese.
$commonFonts = @(
    @{ Name = 'Tiny';       Regular = $true;  Size = 10; Ascender = 8  },
    @{ Name = 'TinyBold';   Regular = $false; Size = 10; Ascender = 8  },
    @{ Name = 'Small';      Regular = $true;  Size = 12; Ascender = 9  },
    @{ Name = 'Regular';    Regular = $true;  Size = 14; Ascender = 11 },
    @{ Name = 'Bold';       Regular = $false; Size = 14; Ascender = 11 },
    @{ Name = 'MediumBold'; Regular = $false; Size = 18; Ascender = 14 },
    @{ Name = 'BigBold';    Regular = $false; Size = 24; Ascender = 18 }
)

$contentFonts = @(
    @{ Name = 'Tiny';       Regular = $true;  Size = 10; Ascender = 8  },
    @{ Name = 'TinyBold';   Regular = $false; Size = 10; Ascender = 8  },
    @{ Name = 'Regular';    Regular = $true;  Size = 14; Ascender = 11 },
    @{ Name = 'Bold';       Regular = $false; Size = 14; Ascender = 11 },
    @{ Name = 'MediumBold'; Regular = $false; Size = 18; Ascender = 14 },
    @{ Name = 'BigBold';    Regular = $false; Size = 24; Ascender = 18 }
)

function Build-LanguageFontsBlock {
    param([array]$FontList, [hashtable]$TitleOverride = $null)

    $lines = @('LanguageFonts:', '	zh:')
    foreach ($f in $FontList)
    {
        $fontFile = if ($f.Regular) { 'common|SourceHanSansCN-Regular.ttf' } else { 'common|SourceHanSansCN-Bold.ttf' }
        $lines += "		$($f.Name):"
        $lines += "			Font: $fontFile"
        $lines += "			Size: $($f.Size)"
        $lines += "			Ascender: $($f.Ascender)"
    }

    if ($TitleOverride)
    {
        $fontFile = if ($TitleOverride.Regular) { 'common|SourceHanSansCN-Regular.ttf' } else { 'common|SourceHanSansCN-Bold.ttf' }
        $lines += '		Title:'
        $lines += "			Font: $fontFile"
        $lines += "			Size: $($TitleOverride.Size)"
        $lines += "			Ascender: $($TitleOverride.Ascender)"
    }

    return $lines
}

# Title font overrides: cnc/ts use FreeSansBold 32/24, d2k uses Dune2k.ttf 32/23 (no CJK),
# ra uses ZoodRangmah.ttf 48/26 (no CJK). For zh we fall back to a CJK-capable font
# while keeping the same metric so chrome layout doesn't shift between languages.
$titleOverrides = @{
    'cnc'  = @{ Regular = $false; Size = 32; Ascender = 24 }
    'd2k'  = @{ Regular = $false; Size = 32; Ascender = 23 }
    'ra'   = @{ Regular = $false; Size = 32; Ascender = 26 }
    'ts'   = @{ Regular = $false; Size = 32; Ascender = 24 }
}

foreach ($mod in $mods)
{
    $path = "D:\github\OpenRA\mods\$mod\mod.yaml"
    $content = Get-Content $path -Raw -Encoding UTF8
    if ($content -match '(?m)^LanguageFonts:')
    {
        Write-Host "$mod : LanguageFonts already present, skipping"
        continue
    }

    $block = Build-LanguageFontsBlock -FontList $commonFonts -TitleOverride $titleOverrides[$mod]
    $blockText = $block -join "`n"
    $content = $content -replace "(?ms)(^Fonts:.*?)(?=^[A-Z][^\n]*:|\z)", "`$1`n`n$blockText`n"
    Set-Content -Path $path -Value $content -Encoding UTF8 -NoNewline
    Write-Host "$mod : added LanguageFonts block"
}

foreach ($mod in $contentMods)
{
    $path = "D:\github\OpenRA\mods\$mod\mod.yaml"
    $content = Get-Content $path -Raw -Encoding UTF8
    if ($content -match '(?m)^LanguageFonts:')
    {
        Write-Host "$mod : LanguageFonts already present, skipping"
        continue
    }

    $block = Build-LanguageFontsBlock -FontList $contentFonts
    $blockText = $block -join "`n"
    $content = $content -replace "(?ms)(^Fonts:.*?)(?=^[A-Z][^\n]*:|\z)", "`$1`n`n$blockText`n"
    Set-Content -Path $path -Value $content -Encoding UTF8 -NoNewline
    Write-Host "$mod : added LanguageFonts block"
}
