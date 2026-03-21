param(
    [Parameter(Mandatory = $true)]
    [string]$Repo,

    [string]$AwsRegion = "us-east-1",
    [string]$ProjectName = "strype",
    [string]$Environment = "production",
    [string]$TfStateBucket = "",
    [string]$TfStateLockTable = ""
)

$ErrorActionPreference = "Stop"

function Set-RepoVar {
    param(
        [string]$Name,
        [string]$Value
    )
    if ([string]::IsNullOrWhiteSpace($Value)) {
        return
    }
    Write-Host "Setting variable: $Name"
    gh variable set $Name --repo $Repo --body $Value | Out-Null
}

function Set-RepoSecret {
    param(
        [string]$Name,
        [string]$Value,
        [switch]$Optional
    )

    if ([string]::IsNullOrWhiteSpace($Value)) {
        if (-not $Optional) {
            throw "Missing required secret value for $Name"
        }
        return
    }

    Write-Host "Setting secret: $Name"
    $Value | gh secret set $Name --repo $Repo --body - | Out-Null
}

Write-Host "Configuring repository variables for $Repo"
Set-RepoVar -Name "AWS_REGION" -Value $AwsRegion
Set-RepoVar -Name "PROJECT_NAME" -Value $ProjectName
Set-RepoVar -Name "ENVIRONMENT" -Value $Environment

if ([string]::IsNullOrWhiteSpace($TfStateBucket)) {
    $TfStateBucket = Read-Host "TF_STATE_BUCKET (required for Terraform remote state)"
}

if ([string]::IsNullOrWhiteSpace($TfStateBucket)) {
    throw "TF_STATE_BUCKET is required"
}

if ([string]::IsNullOrWhiteSpace($TfStateLockTable)) {
    $TfStateLockTable = Read-Host "TF_STATE_LOCK_TABLE (optional but recommended)"
}

Set-RepoVar -Name "TF_STATE_BUCKET" -Value $TfStateBucket
Set-RepoVar -Name "TF_STATE_LOCK_TABLE" -Value $TfStateLockTable

Write-Host ""
Write-Host "Enter required secret values:"
$awsDeployRoleArn = Read-Host "AWS_DEPLOY_ROLE_ARN (recommended). Leave empty if using access keys"
$awsAccessKeyId = Read-Host "AWS_ACCESS_KEY_ID (optional if using role)"
$awsSecretAccessKey = Read-Host "AWS_SECRET_ACCESS_KEY (optional if using role)"
$dbUsername = Read-Host "DB_USERNAME"
$dbPassword = Read-Host "DB_PASSWORD"
$databaseUrlSecretArn = Read-Host "DATABASE_URL_SECRET_ARN"
$secretKeySecretArn = Read-Host "SECRET_KEY_SECRET_ARN"
$frontendUrl = Read-Host "FRONTEND_URL (for example https://app.example.com)"
$corsOrigins = Read-Host "CORS_ORIGINS (comma-separated)"

$awsCertificateArn = Read-Host "AWS_CERTIFICATE_ARN (optional)"
$stripeSecretKeySecretArn = Read-Host "STRIPE_SECRET_KEY_SECRET_ARN (optional)"
$stripeWebhookSecretArn = Read-Host "STRIPE_WEBHOOK_SECRET_ARN (optional)"
$sendgridApiKeySecretArn = Read-Host "SENDGRID_API_KEY_SECRET_ARN (optional)"
$sentryDsnSecretArn = Read-Host "SENTRY_DSN_SECRET_ARN (optional)"

if ([string]::IsNullOrWhiteSpace($awsDeployRoleArn)) {
    if ([string]::IsNullOrWhiteSpace($awsAccessKeyId) -or [string]::IsNullOrWhiteSpace($awsSecretAccessKey)) {
        throw "Provide AWS_DEPLOY_ROLE_ARN or both AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY"
    }
}

Set-RepoSecret -Name "AWS_DEPLOY_ROLE_ARN" -Value $awsDeployRoleArn -Optional
Set-RepoSecret -Name "AWS_ACCESS_KEY_ID" -Value $awsAccessKeyId -Optional
Set-RepoSecret -Name "AWS_SECRET_ACCESS_KEY" -Value $awsSecretAccessKey -Optional
Set-RepoSecret -Name "DB_USERNAME" -Value $dbUsername
Set-RepoSecret -Name "DB_PASSWORD" -Value $dbPassword
Set-RepoSecret -Name "DATABASE_URL_SECRET_ARN" -Value $databaseUrlSecretArn
Set-RepoSecret -Name "SECRET_KEY_SECRET_ARN" -Value $secretKeySecretArn
Set-RepoSecret -Name "FRONTEND_URL" -Value $frontendUrl
Set-RepoSecret -Name "CORS_ORIGINS" -Value $corsOrigins

Set-RepoSecret -Name "AWS_CERTIFICATE_ARN" -Value $awsCertificateArn -Optional
Set-RepoSecret -Name "STRIPE_SECRET_KEY_SECRET_ARN" -Value $stripeSecretKeySecretArn -Optional
Set-RepoSecret -Name "STRIPE_WEBHOOK_SECRET_ARN" -Value $stripeWebhookSecretArn -Optional
Set-RepoSecret -Name "SENDGRID_API_KEY_SECRET_ARN" -Value $sendgridApiKeySecretArn -Optional
Set-RepoSecret -Name "SENTRY_DSN_SECRET_ARN" -Value $sentryDsnSecretArn -Optional

Write-Host ""
Write-Host "Repository deployment configuration updated."
Write-Host "Trigger deploy: gh workflow run deploy-aws.yml --repo $Repo"
