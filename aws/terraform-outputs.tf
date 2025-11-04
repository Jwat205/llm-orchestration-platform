# Terraform Outputs for LLM API Platform
# Infrastructure endpoints and resource identifiers

# Load Balancer Outputs
output "alb_dns_name" {
  description = "DNS name of the Application Load Balancer"
  value       = aws_lb.llm_api_alb.dns_name
}

output "alb_zone_id" {
  description = "The canonical hosted zone ID of the load balancer"
  value       = aws_lb.llm_api_alb.zone_id
}

output "alb_arn" {
  description = "ARN of the Application Load Balancer"
  value       = aws_lb.llm_api_alb.arn
}

# ECS Cluster Outputs
output "ecs_cluster_name" {
  description = "Name of the ECS cluster"
  value       = aws_ecs_cluster.llm_api_cluster.name
}

output "ecs_cluster_arn" {
  description = "ARN of the ECS cluster"
  value       = aws_ecs_cluster.llm_api_cluster.arn
}

# ECR Repository Outputs
output "django_ecr_repository_url" {
  description = "URL of the Django ECR repository"
  value       = aws_ecr_repository.django_service.repository_url
}

output "fastapi_ecr_repository_url" {
  description = "URL of the FastAPI ECR repository"
  value       = aws_ecr_repository.fastapi_service.repository_url
}

# Database Outputs
output "database_endpoint" {
  description = "RDS PostgreSQL instance endpoint"
  value       = aws_db_instance.llm_api_db.endpoint
  sensitive   = true
}

output "database_replica_endpoint" {
  description = "RDS PostgreSQL read replica endpoint"
  value       = aws_db_instance.llm_api_db_replica.endpoint
  sensitive   = true
}

output "database_port" {
  description = "RDS instance port"
  value       = aws_db_instance.llm_api_db.port
}

output "database_name" {
  description = "RDS database name"
  value       = aws_db_instance.llm_api_db.db_name
}

# Redis Cache Outputs
output "redis_endpoint" {
  description = "ElastiCache Redis primary endpoint"
  value       = aws_elasticache_replication_group.llm_api_redis.primary_endpoint_address
  sensitive   = true
}

output "redis_reader_endpoint" {
  description = "ElastiCache Redis reader endpoint"
  value       = aws_elasticache_replication_group.llm_api_redis.reader_endpoint_address
  sensitive   = true
}

output "redis_port" {
  description = "ElastiCache Redis port"
  value       = aws_elasticache_replication_group.llm_api_redis.port
}

# VPC Outputs
output "vpc_id" {
  description = "ID of the VPC"
  value       = aws_vpc.llm_api_vpc.id
}

output "vpc_cidr_block" {
  description = "CIDR block of the VPC"
  value       = aws_vpc.llm_api_vpc.cidr_block
}

output "private_subnet_ids" {
  description = "IDs of the private subnets"
  value       = [
    aws_subnet.private_subnet_1.id,
    aws_subnet.private_subnet_2.id,
    aws_subnet.private_subnet_3.id
  ]
}

output "public_subnet_ids" {
  description = "IDs of the public subnets"
  value       = [
    aws_subnet.public_subnet_1.id,
    aws_subnet.public_subnet_2.id,
    aws_subnet.public_subnet_3.id
  ]
}

# Security Group Outputs
output "alb_security_group_id" {
  description = "ID of the ALB security group"
  value       = aws_security_group.alb_sg.id
}

output "django_security_group_id" {
  description = "ID of the Django security group"
  value       = aws_security_group.django_sg.id
}

output "fastapi_security_group_id" {
  description = "ID of the FastAPI security group"
  value       = aws_security_group.fastapi_sg.id
}

output "rds_security_group_id" {
  description = "ID of the RDS security group"
  value       = aws_security_group.rds_sg.id
}

output "redis_security_group_id" {
  description = "ID of the Redis security group"
  value       = aws_security_group.redis_sg.id
}

# IAM Role Outputs
output "ecs_execution_role_arn" {
  description = "ARN of the ECS execution role"
  value       = aws_iam_role.ecs_execution_role.arn
}

output "ecs_task_role_arn" {
  description = "ARN of the ECS task role"
  value       = aws_iam_role.ecs_task_role.arn
}

# S3 Bucket Outputs
output "model_cache_bucket_name" {
  description = "Name of the S3 bucket for model cache"
  value       = aws_s3_bucket.model_cache.bucket
}

output "alb_logs_bucket_name" {
  description = "Name of the S3 bucket for ALB access logs"
  value       = aws_s3_bucket.alb_logs.bucket
}

# CloudWatch Outputs
output "cloudwatch_dashboard_url" {
  description = "URL to the CloudWatch dashboard"
  value       = "https://${var.aws_region}.console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=${aws_cloudwatch_dashboard.llm_api_dashboard.dashboard_name}"
}

output "django_log_group_name" {
  description = "Name of the Django CloudWatch log group"
  value       = aws_cloudwatch_log_group.django_logs.name
}

output "fastapi_log_group_name" {
  description = "Name of the FastAPI CloudWatch log group"
  value       = aws_cloudwatch_log_group.fastapi_logs.name
}

# Secrets Manager Outputs
output "db_password_secret_arn" {
  description = "ARN of the database password secret"
  value       = aws_secretsmanager_secret.db_password.arn
  sensitive   = true
}

output "django_secret_key_arn" {
  description = "ARN of the Django secret key"
  value       = aws_secretsmanager_secret.django_secret_key.arn
  sensitive   = true
}

output "jwt_secret_key_arn" {
  description = "ARN of the JWT secret key"
  value       = aws_secretsmanager_secret.jwt_secret_key.arn
  sensitive   = true
}

# Auto Scaling Outputs
output "django_autoscaling_target_arn" {
  description = "ARN of the Django auto scaling target"
  value       = aws_appautoscaling_target.django_scaling_target.arn
}

output "fastapi_autoscaling_target_arn" {
  description = "ARN of the FastAPI auto scaling target"
  value       = aws_appautoscaling_target.fastapi_scaling_target.arn
}

# KMS Key Outputs
output "kms_key_id" {
  description = "ID of the KMS key for encryption"
  value       = aws_kms_key.llm_api_key.key_id
}

output "kms_key_arn" {
  description = "ARN of the KMS key for encryption"
  value       = aws_kms_key.llm_api_key.arn
}

# WAF Outputs
output "waf_web_acl_arn" {
  description = "ARN of the WAF Web ACL"
  value       = aws_wafv2_web_acl.llm_api_waf.arn
}

# SNS Topic Output
output "alerts_topic_arn" {
  description = "ARN of the SNS topic for alerts"
  value       = aws_sns_topic.alerts.arn
}

# Performance Metrics Summary
output "infrastructure_summary" {
  description = "Summary of infrastructure capabilities"
  value = {
    max_concurrent_requests = "1000+"
    target_latency         = "<100ms"
    uptime_target         = "99.5%"
    monthly_request_capacity = "1M+"
    auto_scaling_min       = {
      django  = aws_appautoscaling_target.django_scaling_target.min_capacity
      fastapi = aws_appautoscaling_target.fastapi_scaling_target.min_capacity
    }
    auto_scaling_max = {
      django  = aws_appautoscaling_target.django_scaling_target.max_capacity
      fastapi = aws_appautoscaling_target.fastapi_scaling_target.max_capacity
    }
    database_instance_class = aws_db_instance.llm_api_db.instance_class
    redis_node_type        = aws_elasticache_replication_group.llm_api_redis.node_type
    multi_az_deployment    = aws_db_instance.llm_api_db.multi_az
    redis_cluster_nodes    = aws_elasticache_replication_group.llm_api_redis.num_cache_clusters
  }
}