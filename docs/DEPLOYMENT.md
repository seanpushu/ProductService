# Product Service deployment (GitHub Actions + CloudFormation)

## Flow

```
PR to main ──> ci.yml: pytest (SQLite + PostgreSQL 16), Docker smoke test, cfn-lint   (no AWS access)
push to main ─> deploy.yml: ci.yml ─(pass)─> OIDC role ─> docker build :<sha> ─> ECR
                          ─> cloudformation deploy productservice-app ─> ECS rolling update
                          ─> verify: image = <sha>, target healthy, https /version = <sha>, /health, /products
```

A failing test stops the same commit from deploying (`deploy` job `needs: ci`).
ECS deployment circuit breaker rolls back to the previous task definition if new tasks never pass `/health`.
`concurrency: productservice-deploy` keeps deploys serial and never cancels a running stack update.

A normal deploy only changes the image / task definition. It never seeds products, creates, replaces or
deletes the database.

## What is managed where

| Resource | Name | Managed by |
|---|---|---|
| RDS PostgreSQL | `productservice-db` | existing, not in any stack; passed via the secret |
| DB connection string | Secrets Manager `productservice/database-url` | created once by admin |
| RDS security group | `productservice-rds-sg` | existing; app stack only adds one ingress rule |
| ECR repository | `productservice` | existing |
| ECS cluster | `productservice-cluster` | existing |
| Log group | `/ecs/productservice` | existing |
| Image bucket | `shupu-product-images` | existing |
| ACM cert | `api.shupu.me` | existing |
| ALB, target group, listeners, SGs, task def, ECS service `productservice-api`, exec/task roles, DNS `api.shupu.me` | | stack `productservice-app` |
| GitHub OIDC provider, `productservice-github-deploy`, `productservice-cfn-exec` | | stack `productservice-github-bootstrap` |

## Roles

- `productservice-github-deploy`: assumed by GitHub only for `repo:seanpushu/ProductService:ref:refs/heads/main`.
  Can push to the one ECR repo, drive the one stack, and pass `productservice-cfn-exec` to CloudFormation.
- `productservice-cfn-exec`: CloudFormation uses it to create the app resources. IAM rights are limited to roles
  named `productservice-app-*`.
- ECS execution role (stack-created): pull image, write logs, read only the DB secret.
- ECS task role (stack-created): no permissions; the app calls no AWS APIs.

## One-time setup (admin, local AWS CLI)

1. Store the existing DATABASE_URL in Secrets Manager (`productservice/database-url`). Never commit it.
2. Deploy `infra/github-deploy-bootstrap.yml` as `productservice-github-bootstrap` with `CAPABILITY_NAMED_IAM`.
3. Remove the stale `api.shupu.me` A record that points to the deleted console ALB, so the stack can own it.
4. Repository secret `AWS_ROLE_ARN` = bootstrap output `GitHubDeployRoleArn`.
5. Repository variables: `CFN_EXEC_ROLE_ARN`, `VPC_ID`, `SUBNET_IDS` (comma separated, us-east-1a and 1b),
   `RDS_SECURITY_GROUP_ID`, `DATABASE_URL_SECRET_ARN`, `CERTIFICATE_ARN`, `HOSTED_ZONE_ID`,
   `CORS_ALLOW_ORIGINS` (local dev origin + the CloudFront origin of ProductFrontend).
6. Start RDS if it is stopped, then run `Deploy` via push to main or `workflow_dispatch`.

## Pausing to save money

- Pause: `aws ecs update-service --cluster productservice-cluster --service productservice-api --desired-count 0`
  and `aws rds stop-db-instance --db-instance-identifier productservice-db`. The ALB still costs about
  $16/month; `aws cloudformation delete-stack --stack-name productservice-app` removes it (the database, images,
  ECR and secret are outside the stack and are kept).
- Resume: start RDS, then re-run `Deploy` (workflow_dispatch). The stack is recreated from the template.
- A stopped RDS starts by itself after 7 days.

`aws/up.ps1` / `aws/down.ps1` are the older manual scripts and use outdated names. Do not run them.
