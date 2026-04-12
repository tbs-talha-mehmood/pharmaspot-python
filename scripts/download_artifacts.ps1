param(
  [string]$OwnerRepo,
  [string]$WorkflowFile = 'macos-build.yml',
  [string]$OutputDir = 'output/macos',
  [string]$Token = $env:GITHUB_TOKEN
)

function Resolve-OwnerRepo {
  param([string]$Provided)
  if ($Provided) { return $Provided }
  $remote = (git remote get-url origin) 2>$null
  if (-not $remote) { throw 'Cannot determine origin remote. Pass -OwnerRepo owner/repo.' }
  if ($remote -match 'github.com[:/]{1,2}([^/]+)/([^/.]+)') {
    return "$($Matches[1])/$($Matches[2])"
  }
  throw "Unrecognized remote URL: $remote"
}

if (-not $Token) {
  throw 'Set GITHUB_TOKEN env var (requires actions:read) or pass -Token.'
}

$OwnerRepo = Resolve-OwnerRepo -Provided $OwnerRepo
Write-Host "Repo: $OwnerRepo"

$headers = @{
  'Authorization' = "Bearer $Token"
  'Accept' = 'application/vnd.github+json'
  'X-GitHub-Api-Version' = '2022-11-28'
}
$base = "https://api.github.com/repos/$OwnerRepo"

Write-Host 'Finding latest successful macOS Build run...'
$wfUrl = "$base/actions/workflows/$WorkflowFile/runs?per_page=1&status=success"
try {
  $wfRuns = Invoke-RestMethod -Headers $headers -Uri $wfUrl -Method Get
} catch {
  throw "Failed to list workflow runs: $($_.Exception.Message)"
}
if (-not $wfRuns.workflow_runs -or $wfRuns.workflow_runs.Count -eq 0) {
  Write-Warning 'No successful runs found; trying last completed run...'
  $wfRuns = Invoke-RestMethod -Headers $headers -Uri ("$base/actions/workflows/$WorkflowFile/runs?per_page=1&status=completed") -Method Get
  if (-not $wfRuns.workflow_runs -or $wfRuns.workflow_runs.Count -eq 0) {
    throw 'No completed runs found for the macOS Build workflow.'
  }
}
$run = $wfRuns.workflow_runs[0]
$runId = $run.id
$runStatus = $run.status
$runConclusion = $run.conclusion
Write-Host "Using run: id=$runId status=$runStatus conclusion=$runConclusion"

Write-Host 'Listing artifacts...'
$arts = Invoke-RestMethod -Headers $headers -Uri "$base/actions/runs/$runId/artifacts?per_page=100" -Method Get
if (-not $arts.artifacts) { throw 'No artifacts found on the selected run.' }

$want = @('PharmaSpot-macOS-app','PharmaSpot-macOS-dmg')
$selected = $arts.artifacts | Where-Object { $_.name -in $want -and $_.expired -ne $true }
if (-not $selected -or $selected.Count -eq 0) {
  throw 'Expected artifacts not found (PharmaSpot-macOS-app / PharmaSpot-macOS-dmg).'
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

foreach ($a in $selected) {
  $zipPath = Join-Path $OutputDir ("$($a.name).zip")
  Write-Host "Downloading '$($a.name)' -> $zipPath"
  $dlHeaders = @{
    'Authorization' = "Bearer $Token"
    'Accept' = 'application/octet-stream'
    'X-GitHub-Api-Version' = '2022-11-28'
  }
  Invoke-WebRequest -Headers $dlHeaders -Uri $a.archive_download_url -OutFile $zipPath
  $dest = Join-Path $OutputDir $a.name
  try {
    Expand-Archive -Force -Path $zipPath -DestinationPath $dest
  } catch {
    Write-Warning "Could not expand $zipPath automatically: $($_.Exception.Message)"
  }
}

Write-Host 'Done.'
Get-ChildItem -Recurse -Force $OutputDir | Format-List -Property FullName,Length
