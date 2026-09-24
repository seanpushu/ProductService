<#
.SYNOPSIS
  Put the stack into its cheap idle state: ECS desired count 0, RDS stopped, ALB + target group deleted.
  Keeps: S3 images, ECR image, ECS cluster/task definition, security groups, IAM role, ACM certificate.
  Idle cost is roughly RDS storage (~$2.3/month) + a few cents. Re-create with up.ps1 -SkipImagePush.

  Note: a stopped RDS instance is automatically started by AWS after 7 days; run this again if needed.
#>
. (Join-Path $PSScriptRoot "common.ps1")

Step "ECS service -> desired 0"
$svc = AwsText ecs describe-services --cluster $Cluster --services $ServiceName --query "services[0].status"
if ($svc -eq "ACTIVE") {
    aws ecs update-service --cluster $Cluster --service $ServiceName --desired-count 0 | Out-Null
    aws ecs wait services-stable --cluster $Cluster --services $ServiceName
    # The service is bound to the target group; delete it so the target group / ALB can go away.
    aws ecs delete-service --cluster $Cluster --service $ServiceName --force | Out-Null
    aws ecs wait services-inactive --cluster $Cluster --services $ServiceName
    Write-Host "service stopped and removed (task definition kept; up.ps1 recreates the service)"
} else { Write-Host "no active service" }

Step "Delete ALB listeners, load balancer, target group"
$albArn = AwsText elbv2 describe-load-balancers --names $AlbName --query "LoadBalancers[0].LoadBalancerArn"
if ($albArn) {
    $listeners = AwsText elbv2 describe-listeners --load-balancer-arn $albArn --query "Listeners[].ListenerArn"
    foreach ($l in ($listeners -split "\s+" | Where-Object { $_ })) { aws elbv2 delete-listener --listener-arn $l }
    aws elbv2 delete-load-balancer --load-balancer-arn $albArn
    aws elbv2 wait load-balancers-deleted --load-balancer-arns $albArn
    Write-Host "ALB deleted"
} else { Write-Host "no ALB" }
$tgArn = AwsText elbv2 describe-target-groups --names $TgName --query "TargetGroups[0].TargetGroupArn"
if ($tgArn) { Start-Sleep 5; aws elbv2 delete-target-group --target-group-arn $tgArn; Write-Host "target group deleted" }

Step "Stop RDS"
$db = AwsText rds describe-db-instances --db-instance-identifier $DbId --query "DBInstances[0].DBInstanceStatus"
if ($db -eq "available") { aws rds stop-db-instance --db-instance-identifier $DbId | Out-Null; Write-Host "RDS stopping (storage still billed, ~`$2.3/month)" }
else { Write-Host "RDS status: $db" }

Step "Idle state reached"
Write-Host "Remaining monthly cost: RDS 20 GB storage ~`$2.3 + S3/ECR cents. Rebuild: .\aws\up.ps1 -SkipImagePush"
