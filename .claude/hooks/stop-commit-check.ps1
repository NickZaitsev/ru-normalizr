# Stop hook: if uncommitted changes remain when the agent finishes, remind it once
# to commit them. One-shot behavior relies on stop_hook_active: Claude Code
# sets it to true when Stop fires after this hook already blocked, so we don't loop.
# NOTE: keep this file ASCII-only - Windows PowerShell 5.1 reads BOM-less .ps1 as ANSI
# and non-ASCII text breaks parsing.

$hookInput = [Console]::In.ReadToEnd()
try { $payload = $hookInput | ConvertFrom-Json } catch { exit 0 }
if ($payload.stop_hook_active) { exit 0 }

if (-not (Test-Path ".git")) { exit 0 }

$status = git status --porcelain 2>$null
if ($LASTEXITCODE -ne 0 -or -not $status) { exit 0 }

$files = ($status | Select-Object -First 20) -join "`n"
$reason = "Uncommitted changes remain in the working tree:`n$files`n" +
    "If the task is finished, commit them as atomic conventional commits. " +
    "If this is unfinished work or files left on purpose, just finish your reply."

@{ decision = "block"; reason = $reason } | ConvertTo-Json | Write-Output
exit 0
