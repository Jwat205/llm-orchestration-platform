# Security Groups and IAM Configuration
# Part 3 of Enhanced Production Infrastructure

# Security Group for Application Load Balancer
resource "aws_security_group" "alb_sg" {
  name_prefix = "llm-api-alb-"
  vpc_id      = aws_vpc.llm_api_vpc.id
  description = "Security group for Application Load Balancer"

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTP"
  }

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTPS"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "All outbound traffic"
  }

  tags = {
    Name = "llm-api-alb-sg"
  }

  lifecycle {
    create_before_destroy = true
  }
}

# Security Group for Django Service
resource "aws_security_group" "django_sg" {
  name_prefix = "llm-api-django-"
  vpc_id      = aws_vpc.llm_api_vpc.id
  description = "Security group for Django service"

  ingress {
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb_sg.id]
    description     = "HTTP from ALB"
  }

  ingress {
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.fastapi_sg.id]
    description     = "HTTP from FastAPI service"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "All outbound traffic"
  }

  tags = {
    Name = "llm-api-django-sg"
  }

  lifecycle {
    create_before_destroy = true
  }
}

# Security Group for FastAPI Service
resource "aws_security_group" "fastapi_sg" {
  name_prefix = "llm-api-fastapi-"
  vpc_id      = aws_vpc.llm_api_vpc.id
  description = "Security group for FastAPI service"

  ingress {
    from_port       = 8001
    to_port         = 8001
    protocol        = "tcp"
    security_groups = [aws_security_group.alb_sg.id]
    description     = "HTTP from ALB"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "All outbound traffic"
  }

  tags = {
    Name = "llm-api-fastapi-sg"
  }

  lifecycle {
    create_before_destroy = true
  }
}

# Security Group for RDS
resource "aws_security_group" "rds_sg" {
  name_prefix = "llm-api-rds-"
  vpc_id      = aws_vpc.llm_api_vpc.id
  description = "Security group for RDS PostgreSQL"

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.django_sg.id]
    description     = "PostgreSQL from Django"
  }

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.fastapi_sg.id]
    description     = "PostgreSQL from FastAPI"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "All outbound traffic"
  }

  tags = {
    Name = "llm-api-rds-sg"
  }

  lifecycle {
    create_before_destroy = true
  }
}

# Security Group for Redis
resource "aws_security_group" "redis_sg" {
  name_prefix = "llm-api-redis-"
  vpc_id      = aws_vpc.llm_api_vpc.id
  description = "Security group for ElastiCache Redis"

  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.django_sg.id]
    description     = "Redis from Django"
  }

  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.fastapi_sg.id]
    description     = "Redis from FastAPI"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "All outbound traffic"
  }

  tags = {
    Name = "llm-api-redis-sg"
  }

  lifecycle {
    create_before_destroy = true
  }
}

# IAM Role for ECS Task Execution
resource "aws_iam_role" "ecs_execution_role" {
  name = "llm-api-ecs-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "llm-api-ecs-execution-role"
  }
}

resource "aws_iam_role_policy_attachment" "ecs_execution_role_policy" {
  role       = aws_iam_role.ecs_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "ecs_execution_custom_policy" {
  name = "ecs-execution-custom-policy"
  role = aws_iam_role.ecs_execution_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = [
          aws_cloudwatch_log_group.django_logs.arn,
          aws_cloudwatch_log_group.fastapi_logs.arn,
          "${aws_cloudwatch_log_group.django_logs.arn}:*",
          "${aws_cloudwatch_log_group.fastapi_logs.arn}:*"
        ]
      }
    ]
  })
}

# IAM Role for ECS Tasks
resource "aws_iam_role" "ecs_task_role" {
  name = "llm-api-ecs-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "llm-api-ecs-task-role"
  }
}

resource "aws_iam_role_policy" "ecs_task_policy" {
  name = "ecs-task-policy"
  role = aws_iam_role.ecs_task_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData",
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject"
        ]
        Resource = [
          "${aws_s3_bucket.model_cache.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = [
          aws_secretsmanager_secret.db_password.arn,
          aws_secretsmanager_secret.django_secret_key.arn,
          aws_secretsmanager_secret.jwt_secret_key.arn
        ]
      }
    ]
  })
}

# IAM Role for RDS Monitoring
resource "aws_iam_role" "rds_monitoring_role" {
  name = "llm-api-rds-monitoring-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "monitoring.rds.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "llm-api-rds-monitoring-role"
  }
}

resource "aws_iam_role_policy_attachment" "rds_monitoring_role_policy" {
  role       = aws_iam_role.rds_monitoring_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}

# Secrets Manager for sensitive data
resource "aws_secretsmanager_secret" "db_password" {
  name        = "llm-api-db-password"
  description = "PostgreSQL database password"

  tags = {
    Name = "llm-api-db-password"
  }
}

resource "aws_secretsmanager_secret_version" "db_password" {
  secret_id     = aws_secretsmanager_secret.db_password.id
  secret_string = var.db_password
}

resource "aws_secretsmanager_secret" "django_secret_key" {
  name        = "llm-api-django-secret-key"
  description = "Django secret key"

  tags = {
    Name = "llm-api-django-secret-key"
  }
}

resource "aws_secretsmanager_secret_version" "django_secret_key" {
  secret_id     = aws_secretsmanager_secret.django_secret_key.id
  secret_string = random_password.django_secret_key.result
}

resource "aws_secretsmanager_secret" "jwt_secret_key" {
  name        = "llm-api-jwt-secret-key"
  description = "JWT secret key"

  tags = {
    Name = "llm-api-jwt-secret-key"
  }
}

resource "aws_secretsmanager_secret_version" "jwt_secret_key" {
  secret_id     = aws_secretsmanager_secret.jwt_secret_key.id
  secret_string = random_password.jwt_secret_key.result
}

resource "random_password" "django_secret_key" {
  length  = 50
  special = true
}

resource "random_password" "jwt_secret_key" {
  length  = 32
  special = true
}

# S3 Bucket for Model Cache
resource "aws_s3_bucket" "model_cache" {
  bucket = "llm-api-model-cache-${random_string.bucket_suffix.result}"

  tags = {
    Name = "llm-api-model-cache"
  }
}

resource "aws_s3_bucket_versioning" "model_cache_versioning" {
  bucket = aws_s3_bucket.model_cache.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_encryption" "model_cache_encryption" {
  bucket = aws_s3_bucket.model_cache.id

  server_side_encryption_configuration {
    rule {
      apply_server_side_encryption_by_default {
        sse_algorithm = "AES256"
      }
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "model_cache_lifecycle" {
  bucket = aws_s3_bucket.model_cache.id

  rule {
    id     = "model_cache_lifecycle"
    status = "Enabled"

    expiration {
      days = 90
    }

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}

# KMS Keys for additional encryption
resource "aws_kms_key" "llm_api_key" {
  description             = "KMS key for LLM API encryption"
  deletion_window_in_days = 7

  tags = {
    Name = "llm-api-key"
  }
}

resource "aws_kms_alias" "llm_api_key_alias" {
  name          = "alias/llm-api"
  target_key_id = aws_kms_key.llm_api_key.key_id
}

# WAF Web ACL for additional security
resource "aws_wafv2_web_acl" "llm_api_waf" {
  name  = "llm-api-waf"
  scope = "REGIONAL"

  default_action {
    allow {}
  }

  # Rate limiting rule
  rule {
    name     = "RateLimitRule"
    priority = 1

    statement {
      rate_based_statement {
        limit              = 2000
        aggregate_key_type = "IP"
      }
    }

    action {
      block {}
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                 = "RateLimitRule"
      sampled_requests_enabled    = true
    }
  }

  # AWS Managed Core Rule Set
  rule {
    name     = "AWSManagedRulesCommonRuleSet"
    priority = 10

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"
      }
    }

    override_action {
      none {}
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                 = "CommonRuleSetMetric"
      sampled_requests_enabled    = true
    }
  }

  tags = {
    Name = "llm-api-waf"
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                 = "llmApiWAF"
    sampled_requests_enabled    = true
  }
}

# Associate WAF with ALB
resource "aws_wafv2_web_acl_association" "llm_api_waf_association" {
  resource_arn = aws_lb.llm_api_alb.arn
  web_acl_arn  = aws_wafv2_web_acl.llm_api_waf.arn
}

# Network ACLs for additional security
resource "aws_network_acl" "private_nacl" {
  vpc_id     = aws_vpc.llm_api_vpc.id
  subnet_ids = [
    aws_subnet.private_subnet_1.id,
    aws_subnet.private_subnet_2.id,
    aws_subnet.private_subnet_3.id
  ]

  # Allow inbound from VPC
  ingress {
    protocol   = "-1"
    rule_no    = 100
    action     = "allow"
    cidr_block = aws_vpc.llm_api_vpc.cidr_block
  }

  # Allow outbound to anywhere (for external API calls)
  egress {
    protocol   = "-1"
    rule_no    = 100
    action     = "allow"
    cidr_block = "0.0.0.0/0"
  }

  tags = {
    Name = "llm-api-private-nacl"
  }
}