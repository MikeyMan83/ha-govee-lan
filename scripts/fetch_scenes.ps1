<#
.SYNOPSIS
    Pulls the scene/effect catalog for a Govee SKU from Govee's cloud API and
    writes it in the format govee_lan's scenes.py expects.

.DESCRIPTION
    This does NOT touch your Home Assistant setup or your network at all --
    it's a one-shot call to Govee's own servers to grab scene definitions
    (name/code/param) for a given SKU, purely so you have a local copy to
    drop into custom_components/govee_lan/scene_data/. Requires internet
    access on whatever machine you run it on; does not require HA to be
    reachable.

.PARAMETER Sku
    The Govee model number, e.g. H702B, H6076, H7094.

.PARAMETER OutFile
    Output path. Defaults to "<Sku>.json" in the current directory.

.EXAMPLE
    .\fetch_scenes.ps1 -Sku H702B
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$Sku,

    [string]$OutFile = "$Sku.json",

    [string]$AppVersion = "6.6.30"
)

try {
    $response = Invoke-RestMethod `
        -Uri "https://app2.govee.com/appsku/v1/light-effect-libraries?sku=$Sku" `
        -Headers @{ "AppVersion" = $AppVersion }
}
catch {
    Write-Error "Request failed: $($_.Exception.Message)"
    Write-Host "If this is an SSL/TLS error on older Windows PowerShell, try:"
    Write-Host '  [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12'
    exit 1
}

$scenes = foreach ($cat in $response.data.categories) {
    foreach ($s in $cat.scenes) {
        $effect = $s.lightEffects[0]
        [PSCustomObject]@{
            name     = $s.sceneName
            code     = $effect.sceneCode
            param    = $effect.scenceParam   # not a typo -- matches Govee's own (misspelled) field name
            category = $cat.categoryName
        }
    }
}

if (-not $scenes -or $scenes.Count -eq 0) {
    Write-Warning "No scenes returned for SKU '$Sku'. Either the SKU is wrong, or Govee doesn't have a catalog for it under this endpoint -- try bumping -AppVersion, or fall back to sniffing the Govee app's own traffic."
    exit 1
}

# Some "scenes" are actually simple built-in modes (single/double-digit codes,
# no param payload) rather than ptReal-encoded effects -- encode_scene() in
# scenes.py can't do anything useful with an empty param, so drop them here
# rather than shipping broken entries.
$before = $scenes.Count
$clean = $scenes | Where-Object { $_.param -ne "" }
$dropped = $before - $clean.Count

# IMPORTANT: -InputObject @($clean) forces a JSON array even if only one
# scene comes back. Piping into ConvertTo-Json instead
# ($clean | ConvertTo-Json) unrolls a single-item array into a bare object,
# which scenes.py's loader does not expect.
ConvertTo-Json -InputObject @($clean) -Depth 5 |
    Set-Content -Path $OutFile -Encoding utf8NoBOM   # utf8 (not utf8NoBOM) on Windows PowerShell 5.1 silently prepends a BOM that breaks scenes.py's json.loads()

$dupes = $clean | Group-Object name | Where-Object { $_.Count -gt 1 } | Select-Object -ExpandProperty Name

Write-Host "$($clean.Count) scenes written to $OutFile (dropped $dropped with no param)"
if ($dupes) {
    Write-Warning "Duplicate scene names found: $($dupes -join ', ') -- govee_lan keys effects by name, so only the last of each duplicate will be selectable in Home Assistant. Rename one of each pair in the JSON if you want both."
}
Write-Host "Copy $OutFile into custom_components/govee_lan/scene_data/ and reload the integration."
