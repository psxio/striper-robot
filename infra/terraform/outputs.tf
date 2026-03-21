output "alb_dns_name" {
  value = aws_lb.app.dns_name
}

output "ecr_repository_url" {
  value = aws_ecr_repository.app.repository_url
}

output "private_bucket_name" {
  value = aws_s3_bucket.private.bucket
}

output "reports_bucket_name" {
  value = aws_s3_bucket.reports.bucket
}

output "rds_endpoint" {
  value = aws_db_instance.postgres.address
}
