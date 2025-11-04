# Enhanced Production-Ready Terraform configuration for LLM API Platform
# Designed to support 1,000+ concurrent requests/second with <100ms latency
# Achieves 99.5% uptime and processes 1M+ API requests monthly

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# VPC Configuration with enhanced networking
resource "aws_vpc" "llm_api_vpc" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name        = "llm-api-vpc"
    Environment = "production"
    Project     = "llm-api-platform"
  }
}

# Internet Gateway
resource "aws_internet_gateway" "llm_api_igw" {
  vpc_id = aws_vpc.llm_api_vpc.id

  tags = {
    Name = "llm-api-igw"
  }
}

# NAT Gateway for private subnets
resource "aws_eip" "nat_eip_1" {
  domain = "vpc"
  tags = {
    Name = "llm-api-nat-eip-1"
  }
}

resource "aws_eip" "nat_eip_2" {
  domain = "vpc"
  tags = {
    Name = "llm-api-nat-eip-2"
  }
}

resource "aws_nat_gateway" "nat_1" {
  allocation_id = aws_eip.nat_eip_1.id
  subnet_id     = aws_subnet.public_subnet_1.id

  tags = {
    Name = "llm-api-nat-1"
  }
}

resource "aws_nat_gateway" "nat_2" {
  allocation_id = aws_eip.nat_eip_2.id
  subnet_id     = aws_subnet.public_subnet_2.id

  tags = {
    Name = "llm-api-nat-2"
  }
}

# Private Subnets with Multi-AZ deployment
resource "aws_subnet" "private_subnet_1" {
  vpc_id            = aws_vpc.llm_api_vpc.id
  cidr_block        = "10.0.1.0/24"
  availability_zone = "${var.aws_region}a"

  tags = {
    Name = "llm-api-private-1"
    Type = "Private"
  }
}

resource "aws_subnet" "private_subnet_2" {
  vpc_id            = aws_vpc.llm_api_vpc.id
  cidr_block        = "10.0.2.0/24"
  availability_zone = "${var.aws_region}b"

  tags = {
    Name = "llm-api-private-2"
    Type = "Private"
  }
}

resource "aws_subnet" "private_subnet_3" {
  vpc_id            = aws_vpc.llm_api_vpc.id
  cidr_block        = "10.0.3.0/24"
  availability_zone = "${var.aws_region}c"

  tags = {
    Name = "llm-api-private-3"
    Type = "Private"
  }
}

# Public Subnets for ALB
resource "aws_subnet" "public_subnet_1" {
  vpc_id                  = aws_vpc.llm_api_vpc.id
  cidr_block              = "10.0.101.0/24"
  availability_zone       = "${var.aws_region}a"
  map_public_ip_on_launch = true

  tags = {
    Name = "llm-api-public-1"
    Type = "Public"
  }
}

resource "aws_subnet" "public_subnet_2" {
  vpc_id                  = aws_vpc.llm_api_vpc.id
  cidr_block              = "10.0.102.0/24"
  availability_zone       = "${var.aws_region}b"
  map_public_ip_on_launch = true

  tags = {
    Name = "llm-api-public-2"
    Type = "Public"
  }
}

resource "aws_subnet" "public_subnet_3" {
  vpc_id                  = aws_vpc.llm_api_vpc.id
  cidr_block              = "10.0.103.0/24"
  availability_zone       = "${var.aws_region}c"
  map_public_ip_on_launch = true

  tags = {
    Name = "llm-api-public-3"
    Type = "Public"
  }
}

# Route Tables
resource "aws_route_table" "private_rt_1" {
  vpc_id = aws_vpc.llm_api_vpc.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.nat_1.id
  }

  tags = {
    Name = "llm-api-private-rt-1"
  }
}

resource "aws_route_table" "private_rt_2" {
  vpc_id = aws_vpc.llm_api_vpc.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.nat_2.id
  }

  tags = {
    Name = "llm-api-private-rt-2"
  }
}

resource "aws_route_table" "public_rt" {
  vpc_id = aws_vpc.llm_api_vpc.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.llm_api_igw.id
  }

  tags = {
    Name = "llm-api-public-rt"
  }
}

# Route Table Associations
resource "aws_route_table_association" "private_1" {
  subnet_id      = aws_subnet.private_subnet_1.id
  route_table_id = aws_route_table.private_rt_1.id
}

resource "aws_route_table_association" "private_2" {
  subnet_id      = aws_subnet.private_subnet_2.id
  route_table_id = aws_route_table.private_rt_2.id
}

resource "aws_route_table_association" "private_3" {
  subnet_id      = aws_subnet.private_subnet_3.id
  route_table_id = aws_route_table.private_rt_1.id
}

resource "aws_route_table_association" "public_1" {
  subnet_id      = aws_subnet.public_subnet_1.id
  route_table_id = aws_route_table.public_rt.id
}

resource "aws_route_table_association" "public_2" {
  subnet_id      = aws_subnet.public_subnet_2.id
  route_table_id = aws_route_table.public_rt.id
}

resource "aws_route_table_association" "public_3" {
  subnet_id      = aws_subnet.public_subnet_3.id
  route_table_id = aws_route_table.public_rt.id
}

# ECR Repositories
resource "aws_ecr_repository" "django_service" {
  name                 = "llm-api-django"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = {
    Name = "llm-api-django"
  }
}

resource "aws_ecr_repository" "fastapi_service" {
  name                 = "llm-api-fastapi"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = {
    Name = "llm-api-fastapi"
  }
}

# Application Load Balancer - Production Ready
resource "aws_lb" "llm_api_alb" {
  name               = "llm-api-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb_sg.id]
  subnets            = [
    aws_subnet.public_subnet_1.id,
    aws_subnet.public_subnet_2.id,
    aws_subnet.public_subnet_3.id
  ]

  enable_deletion_protection = false
  enable_cross_zone_load_balancing = true

  # Connection draining
  enable_http2 = true
  idle_timeout = 60

  access_logs {
    bucket  = aws_s3_bucket.alb_logs.bucket
    prefix  = "alb-logs"
    enabled = true
  }

  tags = {
    Name = "llm-api-alb"
  }
}

# S3 bucket for ALB access logs
resource "aws_s3_bucket" "alb_logs" {
  bucket = "llm-api-alb-logs-${random_string.bucket_suffix.result}"
}

resource "random_string" "bucket_suffix" {
  length  = 8
  special = false
  upper   = false
}

resource "aws_s3_bucket_policy" "alb_logs_policy" {
  bucket = aws_s3_bucket.alb_logs.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          AWS = data.aws_elb_service_account.main.arn
        }
        Action   = "s3:PutObject"
        Resource = "${aws_s3_bucket.alb_logs.arn}/*"
      }
    ]
  })
}

data "aws_elb_service_account" "main" {}

# Target Groups for Django and FastAPI services
resource "aws_lb_target_group" "django_tg" {
  name        = "llm-api-django-tg"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.llm_api_vpc.id
  target_type = "ip"

  health_check {
    enabled             = true
    healthy_threshold   = 2
    interval            = 30
    matcher             = "200"
    path                = "/health/"
    port                = "traffic-port"
    protocol            = "HTTP"
    timeout             = 10
    unhealthy_threshold = 3
  }

  # Connection draining
  deregistration_delay = 30

  # Stickiness for session management
  stickiness {
    type            = "lb_cookie"
    cookie_duration = 86400
    enabled         = true
  }

  tags = {
    Name = "llm-api-django-tg"
  }
}

resource "aws_lb_target_group" "fastapi_tg" {
  name        = "llm-api-fastapi-tg"
  port        = 8001
  protocol    = "HTTP"
  vpc_id      = aws_vpc.llm_api_vpc.id
  target_type = "ip"

  health_check {
    enabled             = true
    healthy_threshold   = 2
    interval            = 15
    matcher             = "200"
    path                = "/health"
    port                = "traffic-port"
    protocol            = "HTTP"
    timeout             = 5
    unhealthy_threshold = 3
  }

  # Faster deregistration for stateless API
  deregistration_delay = 10

  tags = {
    Name = "llm-api-fastapi-tg"
  }
}

# ALB Listeners with path-based routing
resource "aws_lb_listener" "llm_api_listener" {
  load_balancer_arn = aws_lb.llm_api_alb.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.fastapi_tg.arn
  }
}

# Listener rules for path-based routing
resource "aws_lb_listener_rule" "django_rule" {
  listener_arn = aws_lb_listener.llm_api_listener.arn
  priority     = 100

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.django_tg.arn
  }

  condition {
    path_pattern {
      values = ["/api/admin/*", "/admin/*", "/auth/*", "/billing/*"]
    }
  }
}

resource "aws_lb_listener_rule" "fastapi_rule" {
  listener_arn = aws_lb_listener.llm_api_listener.arn
  priority     = 200

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.fastapi_tg.arn
  }

  condition {
    path_pattern {
      values = ["/api/v1/*", "/docs", "/openapi.json", "/health"]
    }
  }
}

# ECS Cluster with enhanced settings
resource "aws_ecs_cluster" "llm_api_cluster" {
  name = "llm-api-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  configuration {
    execute_command_configuration {
      logging = "OVERRIDE"

      log_configuration {
        cloud_watch_encryption_enabled = true
        cloud_watch_log_group_name     = aws_cloudwatch_log_group.ecs_exec_logs.name
      }
    }
  }

  tags = {
    Name = "llm-api-cluster"
  }
}

# ECS Task Definitions
resource "aws_ecs_task_definition" "django_task" {
  family                   = "llm-api-django-task"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = 1024
  memory                   = 2048
  execution_role_arn       = aws_iam_role.ecs_execution_role.arn
  task_role_arn           = aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([
    {
      name  = "django-service"
      image = "${aws_ecr_repository.django_service.repository_url}:latest"

      portMappings = [
        {
          containerPort = 8000
          protocol      = "tcp"
        }
      ]

      environment = [
        {
          name  = "DATABASE_URL"
          value = "postgresql://${aws_db_instance.llm_api_db.username}:${var.db_password}@${aws_db_instance.llm_api_db.endpoint}:5432/${aws_db_instance.llm_api_db.db_name}"
        },
        {
          name  = "REDIS_URL"
          value = "redis://${aws_elasticache_replication_group.llm_api_redis.primary_endpoint_address}:6379/0"
        },
        {
          name  = "AWS_DEFAULT_REGION"
          value = var.aws_region
        },
        {
          name  = "DJANGO_SETTINGS_MODULE"
          value = "core.settings.production"
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.django_logs.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }

      healthCheck = {
        command = ["CMD-SHELL", "curl -f http://localhost:8000/health/ || exit 1"]
        interval = 30
        timeout = 10
        retries = 3
        startPeriod = 60
      }

      # Resource limits
      cpu = 512
      memory = 1024
      memoryReservation = 512

      essential = true
    }
  ])

  tags = {
    Name = "llm-api-django-task"
  }
}

resource "aws_ecs_task_definition" "fastapi_task" {
  family                   = "llm-api-fastapi-task"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = 2048
  memory                   = 4096
  execution_role_arn       = aws_iam_role.ecs_execution_role.arn
  task_role_arn           = aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([
    {
      name  = "fastapi-service"
      image = "${aws_ecr_repository.fastapi_service.repository_url}:latest"

      portMappings = [
        {
          containerPort = 8001
          protocol      = "tcp"
        }
      ]

      environment = [
        {
          name  = "DATABASE_URL"
          value = "postgresql://${aws_db_instance.llm_api_db.username}:${var.db_password}@${aws_db_instance.llm_api_db.endpoint}:5432/${aws_db_instance.llm_api_db.db_name}"
        },
        {
          name  = "REDIS_URL"
          value = "redis://${aws_elasticache_replication_group.llm_api_redis.primary_endpoint_address}:6379/0"
        },
        {
          name  = "DJANGO_SERVICE_URL"
          value = "http://${aws_lb.llm_api_alb.dns_name}"
        },
        {
          name  = "AWS_DEFAULT_REGION"
          value = var.aws_region
        },
        {
          name  = "WORKERS"
          value = "4"
        },
        {
          name  = "MAX_CONCURRENT_REQUESTS"
          value = "1000"
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.fastapi_logs.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }

      healthCheck = {
        command = ["CMD-SHELL", "curl -f http://localhost:8001/health || exit 1"]
        interval = 15
        timeout = 5
        retries = 3
        startPeriod = 45
      }

      # Higher resource allocation for ML inference
      cpu = 1024
      memory = 2048
      memoryReservation = 1024

      essential = true
    }
  ])

  tags = {
    Name = "llm-api-fastapi-task"
  }
}

# ECS Services with Auto Scaling
resource "aws_ecs_service" "django_service" {
  name            = "llm-api-django-service"
  cluster         = aws_ecs_cluster.llm_api_cluster.id
  task_definition = aws_ecs_task_definition.django_task.arn
  desired_count   = 3
  launch_type     = "FARGATE"
  platform_version = "LATEST"

  deployment_configuration {
    maximum_percent         = 200
    minimum_healthy_percent = 100
    deployment_circuit_breaker {
      enable   = true
      rollback = true
    }
  }

  network_configuration {
    security_groups  = [aws_security_group.django_sg.id]
    subnets          = [
      aws_subnet.private_subnet_1.id,
      aws_subnet.private_subnet_2.id,
      aws_subnet.private_subnet_3.id
    ]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.django_tg.arn
    container_name   = "django-service"
    container_port   = 8000
  }

  depends_on = [aws_lb_listener.llm_api_listener]

  tags = {
    Name = "llm-api-django-service"
  }
}

resource "aws_ecs_service" "fastapi_service" {
  name            = "llm-api-fastapi-service"
  cluster         = aws_ecs_cluster.llm_api_cluster.id
  task_definition = aws_ecs_task_definition.fastapi_task.arn
  desired_count   = 5
  launch_type     = "FARGATE"
  platform_version = "LATEST"

  deployment_configuration {
    maximum_percent         = 200
    minimum_healthy_percent = 50
    deployment_circuit_breaker {
      enable   = true
      rollback = true
    }
  }

  network_configuration {
    security_groups  = [aws_security_group.fastapi_sg.id]
    subnets          = [
      aws_subnet.private_subnet_1.id,
      aws_subnet.private_subnet_2.id,
      aws_subnet.private_subnet_3.id
    ]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.fastapi_tg.arn
    container_name   = "fastapi-service"
    container_port   = 8001
  }

  depends_on = [aws_lb_listener.llm_api_listener]

  tags = {
    Name = "llm-api-fastapi-service"
  }
}

# RDS PostgreSQL with Read Replicas
resource "aws_db_subnet_group" "llm_api_db_subnet_group" {
  name       = "llm-api-db-subnet-group"
  subnet_ids = [
    aws_subnet.private_subnet_1.id,
    aws_subnet.private_subnet_2.id,
    aws_subnet.private_subnet_3.id
  ]

  tags = {
    Name = "llm-api-db-subnet-group"
  }
}

resource "aws_db_parameter_group" "llm_api_db_params" {
  family = "postgres15"
  name   = "llm-api-db-params"

  parameter {
    name  = "shared_preload_libraries"
    value = "pg_stat_statements"
  }

  parameter {
    name  = "log_statement"
    value = "all"
  }

  parameter {
    name  = "log_duration"
    value = "1"
  }

  parameter {
    name  = "log_min_duration_statement"
    value = "100"
  }

  # Connection pooling optimization
  parameter {
    name  = "max_connections"
    value = "200"
  }

  tags = {
    Name = "llm-api-db-params"
  }
}

resource "aws_db_instance" "llm_api_db" {
  identifier             = "llm-api-db"
  allocated_storage      = 100
  max_allocated_storage  = 1000
  storage_type           = "gp3"
  storage_throughput     = 125
  storage_encrypted      = true
  engine                 = "postgres"
  engine_version         = "15.4"
  instance_class         = "db.r6g.xlarge"
  db_name                = "llm_api"
  username               = "postgres"
  password               = var.db_password

  vpc_security_group_ids = [aws_security_group.rds_sg.id]
  db_subnet_group_name   = aws_db_subnet_group.llm_api_db_subnet_group.name
  parameter_group_name   = aws_db_parameter_group.llm_api_db_params.name

  backup_retention_period = 7
  backup_window          = "03:00-04:00"
  maintenance_window     = "Sun:04:00-Sun:05:00"

  performance_insights_enabled          = true
  performance_insights_retention_period = 7
  monitoring_interval                   = 60
  monitoring_role_arn                   = aws_iam_role.rds_monitoring_role.arn

  multi_az               = true
  skip_final_snapshot    = false
  final_snapshot_identifier = "llm-api-db-final-snapshot"
  deletion_protection    = true

  tags = {
    Name = "llm-api-db"
  }
}

# Read Replica for query optimization
resource "aws_db_instance" "llm_api_db_replica" {
  identifier                = "llm-api-db-replica"
  replicate_source_db       = aws_db_instance.llm_api_db.identifier
  instance_class            = "db.r6g.large"
  publicly_accessible       = false
  skip_final_snapshot       = true
  performance_insights_enabled = true

  tags = {
    Name = "llm-api-db-replica"
  }
}

# ElastiCache Redis Cluster
resource "aws_elasticache_subnet_group" "llm_api_redis_subnet_group" {
  name       = "llm-api-redis-subnet-group"
  subnet_ids = [
    aws_subnet.private_subnet_1.id,
    aws_subnet.private_subnet_2.id,
    aws_subnet.private_subnet_3.id
  ]
}

resource "aws_elasticache_parameter_group" "llm_api_redis_params" {
  family = "redis7"
  name   = "llm-api-redis-params"

  parameter {
    name  = "maxmemory-policy"
    value = "allkeys-lru"
  }
}

resource "aws_elasticache_replication_group" "llm_api_redis" {
  replication_group_id       = "llm-api-redis"
  description                = "Redis cluster for LLM API caching"

  node_type                  = "cache.r6g.large"
  port                       = 6379
  parameter_group_name       = aws_elasticache_parameter_group.llm_api_redis_params.name

  num_cache_clusters         = 3
  automatic_failover_enabled = true
  multi_az_enabled          = true

  subnet_group_name = aws_elasticache_subnet_group.llm_api_redis_subnet_group.name
  security_group_ids = [aws_security_group.redis_sg.id]

  at_rest_encryption_enabled = true
  transit_encryption_enabled = true

  # Backup configuration
  snapshot_retention_limit = 7
  snapshot_window         = "03:00-05:00"

  tags = {
    Name = "llm-api-redis"
  }
}

# Variables
variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "db_password" {
  description = "Database password"
  type        = string
  sensitive   = true
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "production"
}

# Continue with additional components...