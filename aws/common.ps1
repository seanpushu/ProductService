# Shared names and helpers for up.ps1 / down.ps1. Dot-source this file.

$Region      = "us-east-1"
$Account     = (aws sts get-caller-identity --query Account --output text)
$Bucket      = "shu-product-images-$Account"
$DbId        = "product-db"
$DbName      = "products"
$DbUser      = "productadmin"
$EcrRepo     = "product-service"
$Cluster     = "product-cluster"
$Family      = "product-service"
$ServiceName = "product-service"
$AlbName     = "product-alb"
$TgName      = "product-tg"
$LogGroup    = "/ecs/product-service"
$ExecRole    = "productEcsTaskExecutionRole"
$Domain      = "api.shupu.me"
$HostedZone  = "shupu.me."
$StateFile   = Join-Path $PSScriptRoot "state.local.json"   # gitignored; holds IDs + DB password

function Read-State {
    if (Test-Path $StateFile) { Get-Content $StateFile -Raw | ConvertFrom-Json } else { [pscustomobject]@{} }
}
function Save-State($state) { $state | ConvertTo-Json -Depth 5 | Set-Content $StateFile -Encoding UTF8 }
function Set-StateValue($state, $key, $value) {
    if ($state.PSObject.Properties[$key]) { $state.$key = $value } else { $state | Add-Member -NotePropertyName $key -NotePropertyValue $value }
}
function Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Fail($msg) { Write-Host "ERROR: $msg" -ForegroundColor Red; exit 1 }
function AwsJson { $out = aws @args --output json 2>&1; if ($LASTEXITCODE -ne 0) { return $null }; ($out -join "`n") | ConvertFrom-Json }
function AwsText { $out = aws @args --output text 2>&1; if ($LASTEXITCODE -ne 0) { return $null }; ($out -join "`n").Trim() }
