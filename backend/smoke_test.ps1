param(
  [string]$BaseUrl = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"

function Show-Result($name, $ok, $extra) {
  if ($ok) { Write-Host "[PASS] $name" -ForegroundColor Green }
  else { Write-Host "[FAIL] $name" -ForegroundColor Red }
  if ($extra) { Write-Host "  $extra" }
}

Write-Host "Running smoke test against $BaseUrl"

# Health
try {
  $health = Invoke-RestMethod -Method Get -Uri ($BaseUrl + "/api/health")
  Show-Result "Health" ($health.status -eq "ok") ($health | ConvertTo-Json -Depth 5)
} catch {
  Show-Result "Health" $false $_.Exception.Message
  exit 1
}

# Schema + quick graph checks
try {
  $schema = Invoke-RestMethod -Method Get -Uri ($BaseUrl + "/api/schema")
  $tablesCount = ($schema.PSObject.Properties | Measure-Object).Count
  Show-Result "Schema tables count" ($tablesCount -ge 10) ("tables=" + $tablesCount)
} catch {
  Show-Result "Schema" $false $_.Exception.Message
  exit 1
}

try {
  $stats = Invoke-RestMethod -Method Get -Uri ($BaseUrl + "/api/graph/statistics")
  Show-Result "Graph statistics" (($stats.total_nodes -gt 0) -and ($stats.total_relationships -gt 0)) ("nodes=" + $stats.total_nodes + " rels=" + $stats.total_relationships)
} catch {
  Show-Result "Graph statistics" $false $_.Exception.Message
  exit 1
}

try {
  $broken = Invoke-RestMethod -Method Get -Uri ($BaseUrl + "/api/graph/broken-flows")
  Show-Result "Broken flows" ($broken.total_issues -gt 0) ("issues=" + $broken.total_issues)
} catch {
  Show-Result "Broken flows" $false $_.Exception.Message
  exit 1
}

try {
  $overview = Invoke-RestMethod -Method Get -Uri ($BaseUrl + "/api/graph/overview?limit=1")
  $nid = $overview.nodes[0].id
  $expand = Invoke-RestMethod -Method Get -Uri ($BaseUrl + "/api/graph/expand/" + [uri]::EscapeDataString($nid) + "?limit=5")
  Show-Result "Graph expand" ($expand.nodes.Count -ge 1) ("expanded_nodes=" + $expand.nodes.Count + " expanded_edges=" + $expand.edges.Count)
} catch {
  Show-Result "Graph overview/expand" $false $_.Exception.Message
  exit 1
}

# Chat helper
function Ask-Chat([string]$message) {
  $body = @{
    message = $message
    conversation_history = @()
  }
  return Invoke-RestMethod -Method Post -Uri ($BaseUrl + "/api/chat") -ContentType "application/json" -Body ($body | ConvertTo-Json -Depth 10)
}

Write-Host "----- Chat required examples -----"

$q1 = "Which products are associated with the highest number of billing documents?"
$r1 = Ask-Chat $q1
Show-Result "Chat #1 top products" (-not $r1.is_guardrail_blocked -and $r1.answer -and $r1.answer.Length -gt 10) ("blocked=" + $r1.is_guardrail_blocked)
Write-Host "  answer: " ($r1.answer -replace "\r?\n"," ") -ForegroundColor DarkCyan

$q2 = "Trace the full flow of a billing document 91150153 (Sales Order -> Delivery -> Billing -> Journal Entry)."
$r2 = Ask-Chat $q2
Show-Result "Chat #2 trace billing flow" (-not $r2.is_guardrail_blocked -and $r2.answer) ("blocked=" + $r2.is_guardrail_blocked)
Write-Host "  answer: " ($r2.answer -replace "\r?\n"," ") -ForegroundColor DarkCyan

$q3 = "Identify sales orders that have broken or incomplete flows (delivered but not billed, billed without delivery)."
$r3 = Ask-Chat $q3
Show-Result "Chat #3 broken flows" (-not $r3.is_guardrail_blocked -and $r3.answer) ("blocked=" + $r3.is_guardrail_blocked)
Write-Host "  answer: " ($r3.answer -replace "\r?\n"," ") -ForegroundColor DarkCyan

$off = "Write a poem about the ocean."
$roff = Ask-Chat $off
Show-Result "Guardrail off-topic poem" ($roff.is_guardrail_blocked -eq $true) ("blocked=" + $roff.is_guardrail_blocked)
Write-Host "  answer: " ($roff.answer -replace "\r?\n"," ") -ForegroundColor DarkCyan

Write-Host "Smoke test completed."

