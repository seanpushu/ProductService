<#
.SYNOPSIS
  Build (or rebuild) the Product Service stack on AWS: S3 -> RDS -> ECR -> ECS Fargate -> ALB -> HTTPS.
  Every step checks whether the resource already exists, so the script can be re-run after down.ps1.

.PARAMETER SkipImagePush   Do not rebuild/push the Docker image (reuse what is in ECR).
.PARAMETER SkipHttps       Do not touch ACM / Route 53 / 443 listener.
#>
param([switch]$SkipImagePush, [switch]$SkipHttps)

. (Join-Path $PSScriptRoot "common.ps1")
$Root  = Split-Path $PSScriptRoot -Parent
$state = Read-State

# ---------------------------------------------------------------- VPC ---
Step "VPC / subnets"
$VpcId = AwsText ec2 describe-vpcs --filters "Name=isDefault,Values=true" --query "Vpcs[0].VpcId"
if (-not $VpcId -or $VpcId -eq "None") { Fail "no default VPC" }
# Fargate/ALB support is patchy in us-east-1e; use a, b (and c, d for the RDS subnet group).
$subnets = AwsJson ec2 describe-subnets --filters "Name=vpc-id,Values=$VpcId" "Name=default-for-az,Values=true" --query "Subnets[].{Id:SubnetId,Az:AvailabilityZone}"
$pick = @{}; foreach ($s in $subnets) { $pick[$s.Az] = $s.Id }
$SubnetA = $pick["${Region}a"]; $SubnetB = $pick["${Region}b"]
if (-not $SubnetA -or -not $SubnetB) { Fail "need default subnets in ${Region}a and ${Region}b" }
$DbSubnets = @("a","b","c","d") | ForEach-Object { $pick["$Region$_"] } | Where-Object { $_ }
Write-Host "vpc=$VpcId  app subnets=$SubnetA,$SubnetB"
Set-StateValue $state VpcId $VpcId; Set-StateValue $state SubnetA $SubnetA; Set-StateValue $state SubnetB $SubnetB

function Ensure-Sg($name, $desc) {
    $id = AwsText ec2 describe-security-groups --filters "Name=vpc-id,Values=$VpcId" "Name=group-name,Values=$name" --query "SecurityGroups[0].GroupId"
    if (-not $id -or $id -eq "None") {
        $id = AwsText ec2 create-security-group --group-name $name --description $desc --vpc-id $VpcId --query GroupId
        Write-Host "created SG $name = $id"
    } else { Write-Host "SG $name exists = $id" }
    return $id
}
function Ensure-SgRule($sgId, $port, $source) {
    if ($source -like "sg-*") { $q = "SecurityGroups[0].IpPermissions[?FromPort==``$port``].UserIdGroupPairs[].GroupId"; $extra = @("--source-group", $source) }
    else { $q = "SecurityGroups[0].IpPermissions[?FromPort==``$port``].IpRanges[].CidrIp"; $extra = @("--cidr", $source) }
    $existing = AwsText ec2 describe-security-groups --group-ids $sgId --query $q
    if ($existing -notlike "*$source*") {
        aws ec2 authorize-security-group-ingress --group-id $sgId --protocol tcp --port $port @extra --output text | Out-Null
        Write-Host "  rule: $sgId allow tcp/$port from $source"
    }
}

Step "Security groups"
$AlbSg = Ensure-Sg "product-alb-sg" "Product Service ALB (public 80/443)"
$EcsSg = Ensure-Sg "product-ecs-sg" "Product Service ECS tasks"
$RdsSg = Ensure-Sg "product-rds-sg" "Product Service RDS (from ECS only)"
Ensure-SgRule $AlbSg 80  "0.0.0.0/0"
Ensure-SgRule $AlbSg 443 "0.0.0.0/0"
Ensure-SgRule $EcsSg 8080 $AlbSg
Ensure-SgRule $RdsSg 5432 $EcsSg
Set-StateValue $state AlbSg $AlbSg; Set-StateValue $state EcsSg $EcsSg; Set-StateValue $state RdsSg $RdsSg
Save-State $state

# ----------------------------------------------------------------- S3 ---
Step "S3 bucket for product images: $Bucket"
aws s3api head-bucket --bucket $Bucket 2>$null
if ($LASTEXITCODE -ne 0) {
    aws s3api create-bucket --bucket $Bucket --region $Region | Out-Null
    Write-Host "created bucket"
} else { Write-Host "bucket exists" }
aws s3api put-public-access-block --bucket $Bucket --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=false,RestrictPublicBuckets=false
$policy = (Get-Content (Join-Path $PSScriptRoot "s3-public-read-policy.template.json") -Raw) -replace "BUCKET_NAME", $Bucket
$policyFile = Join-Path $PSScriptRoot "s3-public-read-policy.local.json"; Set-Content $policyFile $policy -Encoding ascii
aws s3api put-bucket-policy --bucket $Bucket --policy "file://$policyFile"
aws s3 sync (Join-Path $Root "seed\images") "s3://$Bucket/products/" --exclude "*.md" --content-type image/jpeg
Set-StateValue $state Bucket $Bucket; Set-StateValue $state ImageBaseUrl "https://$Bucket.s3.amazonaws.com/products/"
Save-State $state

# ---------------------------------------------------------------- RDS ---
Step "RDS PostgreSQL: $DbId"
if (-not $state.DbPassword) {
    $chars = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    $pw = -join (1..24 | ForEach-Object { $chars[(Get-Random -Maximum $chars.Length)] })
    Set-StateValue $state DbPassword $pw; Save-State $state
}
$sgName = "product-db-subnets"
$null = AwsText rds describe-db-subnet-groups --db-subnet-group-name $sgName --query "DBSubnetGroups[0].DBSubnetGroupName"
if ($LASTEXITCODE -ne 0) {
    aws rds create-db-subnet-group --db-subnet-group-name $sgName --db-subnet-group-description "Product Service RDS" --subnet-ids $DbSubnets | Out-Null
    Write-Host "created DB subnet group"
}
$dbStatus = AwsText rds describe-db-instances --db-instance-identifier $DbId --query "DBInstances[0].DBInstanceStatus"
if (-not $dbStatus) {
    aws rds create-db-instance --db-instance-identifier $DbId --engine postgres --db-instance-class db.t4g.micro `
        --allocated-storage 20 --storage-type gp3 --master-username $DbUser --master-user-password $state.DbPassword `
        --db-name $DbName --vpc-security-group-ids $RdsSg --db-subnet-group-name $sgName `
        --no-publicly-accessible --no-multi-az --backup-retention-period 0 --no-deletion-protection `
        --tags Key=project,Value=product-service | Out-Null
    Write-Host "creating RDS instance (5-10 min)..."
} elseif ($dbStatus -eq "stopped") {
    aws rds start-db-instance --db-instance-identifier $DbId | Out-Null
    Write-Host "starting stopped RDS instance..."
} else { Write-Host "RDS status: $dbStatus" }
aws rds wait db-instance-available --db-instance-identifier $DbId
$DbHost = AwsText rds describe-db-instances --db-instance-identifier $DbId --query "DBInstances[0].Endpoint.Address"
$DatabaseUrl = "postgresql+psycopg://${DbUser}:$($state.DbPassword)@${DbHost}:5432/$DbName"
Set-StateValue $state DbHost $DbHost; Save-State $state
Write-Host "RDS available at $DbHost"

# ---------------------------------------------------------------- ECR ---
Step "ECR: $EcrRepo"
$repoUri = AwsText ecr describe-repositories --repository-names $EcrRepo --query "repositories[0].repositoryUri"
if (-not $repoUri) {
    $repoUri = AwsText ecr create-repository --repository-name $EcrRepo --image-scanning-configuration scanOnPush=true --query "repository.repositoryUri"
    Write-Host "created repository"
}
$ImageUri = "${repoUri}:latest"
if (-not $SkipImagePush) {
    aws ecr get-login-password --region $Region | docker login --username AWS --password-stdin "$Account.dkr.ecr.$Region.amazonaws.com"
    docker build --platform linux/amd64 -t "${EcrRepo}:latest" $Root
    if ($LASTEXITCODE -ne 0) { Fail "docker build failed" }
    docker tag "${EcrRepo}:latest" $ImageUri
    docker push $ImageUri
    if ($LASTEXITCODE -ne 0) { Fail "docker push failed" }
}
Set-StateValue $state ImageUri $ImageUri; Save-State $state

# --------------------------------------------------- ECS cluster / role ---
Step "ECS cluster, execution role, log group"
$cs = AwsText ecs describe-clusters --clusters $Cluster --query "clusters[?status=='ACTIVE'].clusterName | [0]"
if (-not $cs -or $cs -eq "None") { aws ecs create-cluster --cluster-name $Cluster | Out-Null; Write-Host "created cluster" }
$roleArn = AwsText iam get-role --role-name $ExecRole --query Role.Arn
if (-not $roleArn) {
    $roleArn = AwsText iam create-role --role-name $ExecRole --assume-role-policy-document "file://$(Join-Path $PSScriptRoot 'ecs-task-trust.json')" --query Role.Arn
    aws iam attach-role-policy --role-name $ExecRole --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy
    Write-Host "created execution role"; Start-Sleep 10
}
$lg = AwsText logs describe-log-groups --log-group-name-prefix $LogGroup --query "logGroups[?logGroupName=='$LogGroup'].logGroupName | [0]"
if (-not $lg -or $lg -eq "None") { aws logs create-log-group --log-group-name $LogGroup; aws logs put-retention-policy --log-group-name $LogGroup --retention-in-days 14 }

Step "Task definition"
$td = (Get-Content (Join-Path $PSScriptRoot "task-definition.template.json") -Raw) `
    -replace "ACCOUNT_ID", $Account -replace "AWS_REGION", $Region -replace "DATABASE_URL_VALUE", $DatabaseUrl
$td = $td -replace '"image": "[^"]+"', ('"image": "' + $ImageUri + '"')
$tdFile = Join-Path $PSScriptRoot "task-definition.local.json"; Set-Content $tdFile $td -Encoding ascii
$TdArn = AwsText ecs register-task-definition --cli-input-json "file://$tdFile" --query "taskDefinition.taskDefinitionArn"
if (-not $TdArn) { Fail "register-task-definition failed" }
Write-Host "registered $TdArn"

# ---------------------------------------------------------------- ALB ---
Step "Application Load Balancer"
$AlbArn = AwsText elbv2 describe-load-balancers --names $AlbName --query "LoadBalancers[0].LoadBalancerArn"
if (-not $AlbArn) {
    $AlbArn = AwsText elbv2 create-load-balancer --name $AlbName --type application --scheme internet-facing `
        --subnets $SubnetA $SubnetB --security-groups $AlbSg --query "LoadBalancers[0].LoadBalancerArn"
    Write-Host "created ALB"
}
$TgArn = AwsText elbv2 describe-target-groups --names $TgName --query "TargetGroups[0].TargetGroupArn"
if (-not $TgArn) {
    $TgArn = AwsText elbv2 create-target-group --name $TgName --protocol HTTP --port 8080 --vpc-id $VpcId --target-type ip `
        --health-check-path /health --health-check-interval-seconds 30 --healthy-threshold-count 2 --unhealthy-threshold-count 3 `
        --query "TargetGroups[0].TargetGroupArn"
    Write-Host "created target group"
}
$http = AwsText elbv2 describe-listeners --load-balancer-arn $AlbArn --query "Listeners[?Port==``80``].ListenerArn | [0]"
if (-not $http -or $http -eq "None") {
    aws elbv2 create-listener --load-balancer-arn $AlbArn --protocol HTTP --port 80 --default-actions Type=forward,TargetGroupArn=$TgArn | Out-Null
    Write-Host "created HTTP:80 listener"
}
$AlbDns  = AwsText elbv2 describe-load-balancers --load-balancer-arns $AlbArn --query "LoadBalancers[0].DNSName"
$AlbZone = AwsText elbv2 describe-load-balancers --load-balancer-arns $AlbArn --query "LoadBalancers[0].CanonicalHostedZoneId"
Set-StateValue $state AlbArn $AlbArn; Set-StateValue $state TgArn $TgArn; Set-StateValue $state AlbDns $AlbDns; Save-State $state

# ---------------------------------------------------------- ECS service ---
Step "ECS service (desired 1)"
$svcStatus = AwsText ecs describe-services --cluster $Cluster --services $ServiceName --query "services[0].status"
if ($svcStatus -eq "ACTIVE") {
    aws ecs update-service --cluster $Cluster --service $ServiceName --task-definition $TdArn --desired-count 1 --force-new-deployment | Out-Null
    Write-Host "updated service to new task definition"
} else {
    aws ecs create-service --cluster $Cluster --service-name $ServiceName --task-definition $TdArn --desired-count 1 --launch-type FARGATE `
        --network-configuration "awsvpcConfiguration={subnets=[$SubnetA,$SubnetB],securityGroups=[$EcsSg],assignPublicIp=ENABLED}" `
        --load-balancers "targetGroupArn=$TgArn,containerName=product-service,containerPort=8080" `
        --health-check-grace-period-seconds 60 | Out-Null
    Write-Host "created service"
}
Write-Host "waiting for service to stabilise (2-4 min)..."
aws ecs wait services-stable --cluster $Cluster --services $ServiceName

# -------------------------------------------------------------- HTTPS ---
if (-not $SkipHttps) {
    Step "HTTPS: ACM certificate + Route 53 for $Domain"
    $zoneId = AwsText route53 list-hosted-zones-by-name --dns-name $HostedZone --query "HostedZones[?Name=='$HostedZone'].Id | [0]"
    $zoneId = $zoneId -replace "/hostedzone/", ""
    $certArn = AwsText acm list-certificates --certificate-statuses ISSUED PENDING_VALIDATION --query "CertificateSummaryList[?DomainName=='$Domain'].CertificateArn | [0]"
    if (-not $certArn -or $certArn -eq "None") {
        $certArn = AwsText acm request-certificate --domain-name $Domain --validation-method DNS --query CertificateArn
        Write-Host "requested certificate $certArn"; Start-Sleep 8
    }
    $rr = AwsJson acm describe-certificate --certificate-arn $certArn --query "Certificate.DomainValidationOptions[0].ResourceRecord"
    if ($rr) {
        $change = @{ Changes = @(@{ Action = "UPSERT"; ResourceRecordSet = @{ Name = $rr.Name; Type = $rr.Type; TTL = 300; ResourceRecords = @(@{ Value = $rr.Value }) } }) } | ConvertTo-Json -Depth 6
        $cf = Join-Path $PSScriptRoot "r53-validation.local.json"; Set-Content $cf $change -Encoding ascii
        aws route53 change-resource-record-sets --hosted-zone-id $zoneId --change-batch "file://$cf" | Out-Null
    }
    Write-Host "waiting for certificate validation..."
    aws acm wait certificate-validated --certificate-arn $certArn
    $https = AwsText elbv2 describe-listeners --load-balancer-arn $AlbArn --query "Listeners[?Port==``443``].ListenerArn | [0]"
    if (-not $https -or $https -eq "None") {
        aws elbv2 create-listener --load-balancer-arn $AlbArn --protocol HTTPS --port 443 --ssl-policy ELBSecurityPolicy-TLS13-1-2-2021-06 `
            --certificates CertificateArn=$certArn --default-actions Type=forward,TargetGroupArn=$TgArn | Out-Null
        Write-Host "created HTTPS:443 listener"
    }
    $alias = @{ Changes = @(@{ Action = "UPSERT"; ResourceRecordSet = @{ Name = $Domain; Type = "A"; AliasTarget = @{ HostedZoneId = $AlbZone; DNSName = $AlbDns; EvaluateTargetHealth = $false } } }) } | ConvertTo-Json -Depth 6
    $af = Join-Path $PSScriptRoot "r53-alias.local.json"; Set-Content $af $alias -Encoding ascii
    aws route53 change-resource-record-sets --hosted-zone-id $zoneId --change-batch "file://$af" | Out-Null
    Set-StateValue $state CertArn $certArn; Set-StateValue $state ApiUrl "https://$Domain"; Save-State $state
    Write-Host "Route 53: $Domain -> $AlbDns"
}

Step "Done"
Write-Host "HTTP : http://$AlbDns/docs"
if (-not $SkipHttps) { Write-Host "HTTPS: https://$Domain/docs" }
Write-Host "Seed : python scripts\seed_products.py --base-url http://$AlbDns"
