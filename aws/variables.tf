# Terraform Variables for LLM API Platform
# Configure these values for your specific deployment

variable "aws_region" {
  description = "AWS region for deployment"
  type        = string
  default     = "us-east-1"
  validation {
    condition = can(regex("^[a-z]{2}-[a-z]+-[0-9]$", var.aws_region))
    error_message = "AWS region must be in format: us-east-1, eu-west-1, etc."
  }
}

variable "db_password" {
  description = "Password for the PostgreSQL database"
  type        = string
  sensitive   = true
  validation {
    condition     = length(var.db_password) >= 8
    error_message = "Database password must be at least 8 characters long."
  }
}

variable "environment" {
  description = "Environment name (production, staging, development)"
  type        = string
  default     = "production"
  validation {
    condition     = contains(["production", "staging", "development"], var.environment)
    error_message = "Environment must be one of: production, staging, development."
  }
}

variable "project_name" {
  description = "Name of the project for resource naming"
  type        = string
  default     = "llm-api-platform"
  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.project_name))
    error_message = "Project name must contain only lowercase letters, numbers, and hyphens."
  }
}

# ECS Configuration Variables
variable "django_cpu" {
  description = "CPU units for Django service (1024 = 1 vCPU)"
  type        = number
  default     = 1024
  validation {
    condition     = contains([256, 512, 1024, 2048, 4096], var.django_cpu)
    error_message = "Django CPU must be one of: 256, 512, 1024, 2048, 4096."
  }
}

variable "django_memory" {
  description = "Memory in MiB for Django service"
  type        = number
  default     = 2048
  validation {
    condition     = var.django_memory >= 512 && var.django_memory <= 30720
    error_message = "Django memory must be between 512 and 30720 MiB."
  }
}

variable "fastapi_cpu" {
  description = "CPU units for FastAPI service (1024 = 1 vCPU)"
  type        = number
  default     = 2048
  validation {
    condition     = contains([256, 512, 1024, 2048, 4096], var.fastapi_cpu)
    error_message = "FastAPI CPU must be one of: 256, 512, 1024, 2048, 4096."
  }
}

variable "fastapi_memory" {
  description = "Memory in MiB for FastAPI service"
  type        = number
  default     = 4096
  validation {
    condition     = var.fastapi_memory >= 512 && var.fastapi_memory <= 30720
    error_message = "FastAPI memory must be between 512 and 30720 MiB."
  }
}

variable "django_min_capacity" {
  description = "Minimum number of Django tasks"
  type        = number
  default     = 2
  validation {
    condition     = var.django_min_capacity >= 1 && var.django_min_capacity <= 100
    error_message = "Django minimum capacity must be between 1 and 100."
  }
}

variable "django_max_capacity" {
  description = "Maximum number of Django tasks"
  type        = number
  default     = 10
  validation {
    condition     = var.django_max_capacity >= 1 && var.django_max_capacity <= 100
    error_message = "Django maximum capacity must be between 1 and 100."
  }
}

variable "fastapi_min_capacity" {
  description = "Minimum number of FastAPI tasks"
  type        = number
  default     = 3
  validation {
    condition     = var.fastapi_min_capacity >= 1 && var.fastapi_min_capacity <= 100
    error_message = "FastAPI minimum capacity must be between 1 and 100."
  }
}

variable "fastapi_max_capacity" {
  description = "Maximum number of FastAPI tasks"
  type        = number
  default     = 20
  validation {
    condition     = var.fastapi_max_capacity >= 1 && var.fastapi_max_capacity <= 100
    error_message = "FastAPI maximum capacity must be between 1 and 100."
  }
}

# Database Configuration Variables
variable "db_instance_class" {
  description = "RDS instance class for PostgreSQL database"
  type        = string
  default     = "db.r6g.xlarge"
  validation {
    condition = can(regex("^db\\.(t3|r6g|r5)\\.(micro|small|medium|large|xlarge|2xlarge|4xlarge|8xlarge)$", var.db_instance_class))
    error_message = "Database instance class must be a valid RDS instance type."
  }
}

variable "db_allocated_storage" {
  description = "Initial allocated storage for RDS instance in GB"
  type        = number
  default     = 100
  validation {
    condition     = var.db_allocated_storage >= 20 && var.db_allocated_storage <= 65536
    error_message = "Database allocated storage must be between 20 and 65536 GB."
  }
}

variable "db_max_allocated_storage" {
  description = "Maximum allocated storage for RDS auto-scaling in GB"
  type        = number
  default     = 1000
  validation {
    condition     = var.db_max_allocated_storage >= 100 && var.db_max_allocated_storage <= 65536
    error_message = "Database max allocated storage must be between 100 and 65536 GB."
  }
}

variable "db_backup_retention_period" {
  description = "Number of days to retain database backups"
  type        = number
  default     = 7
  validation {
    condition     = var.db_backup_retention_period >= 0 && var.db_backup_retention_period <= 35
    error_message = "Database backup retention period must be between 0 and 35 days."
  }
}

variable "enable_db_read_replica" {
  description = "Enable read replica for database queries optimization"
  type        = bool
  default     = true
}

# Redis Configuration Variables
variable "redis_node_type" {
  description = "ElastiCache Redis node type"
  type        = string
  default     = "cache.r6g.large"
  validation {
    condition = can(regex("^cache\\.(t3|r6g|r5)\\.(micro|small|medium|large|xlarge|2xlarge|4xlarge)$", var.redis_node_type))
    error_message = "Redis node type must be a valid ElastiCache instance type."
  }
}

variable "redis_num_cache_clusters" {
  description = "Number of cache clusters in Redis replication group"
  type        = number
  default     = 3
  validation {
    condition     = var.redis_num_cache_clusters >= 2 && var.redis_num_cache_clusters <= 6
    error_message = "Redis number of cache clusters must be between 2 and 6."
  }
}

# Monitoring Configuration Variables
variable "log_retention_days" {
  description = "Number of days to retain CloudWatch logs"
  type        = number
  default     = 30
  validation {
    condition     = contains([1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1827, 3653], var.log_retention_days)
    error_message = "Log retention days must be a valid CloudWatch retention period."
  }
}

variable "enable_container_insights" {
  description = "Enable CloudWatch Container Insights for ECS"
  type        = bool
  default     = true
}

variable "enable_performance_insights" {
  description = "Enable Performance Insights for RDS"
  type        = bool
  default     = true
}

variable "performance_insights_retention_period" {
  description = "Performance Insights retention period in days"
  type        = number
  default     = 7
  validation {
    condition     = contains([7, 731], var.performance_insights_retention_period)
    error_message = "Performance Insights retention period must be 7 or 731 days."
  }
}

# Security Configuration Variables
variable "enable_waf" {
  description = "Enable AWS WAF for additional security"
  type        = bool
  default     = true
}

variable "waf_rate_limit" {
  description = "WAF rate limit per IP (requests per 5 minutes)"
  type        = number
  default     = 2000
  validation {
    condition     = var.waf_rate_limit >= 100 && var.waf_rate_limit <= 20000
    error_message = "WAF rate limit must be between 100 and 20000 requests per 5 minutes."
  }
}

variable "enable_encryption_at_rest" {
  description = "Enable encryption at rest for all supported services"
  type        = bool
  default     = true
}

variable "enable_encryption_in_transit" {
  description = "Enable encryption in transit for all supported services"
  type        = bool
  default     = true
}

# Network Configuration Variables
variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
  validation {
    condition     = can(cidrhost(var.vpc_cidr, 0))
    error_message = "VPC CIDR must be a valid CIDR block."
  }
}

variable "availability_zones" {
  description = "List of availability zones to use"
  type        = list(string)
  default     = []
  validation {
    condition     = length(var.availability_zones) >= 0 && length(var.availability_zones) <= 3
    error_message = "Availability zones list must contain 0-3 zones."
  }
}

# Auto Scaling Configuration Variables
variable "cpu_scale_out_threshold" {
  description = "CPU utilization threshold for scaling out (%)"
  type        = number
  default     = 70
  validation {
    condition     = var.cpu_scale_out_threshold >= 50 && var.cpu_scale_out_threshold <= 90
    error_message = "CPU scale out threshold must be between 50 and 90 percent."
  }
}

variable "memory_scale_out_threshold" {
  description = "Memory utilization threshold for scaling out (%)"
  type        = number
  default     = 80
  validation {
    condition     = var.memory_scale_out_threshold >= 50 && var.memory_scale_out_threshold <= 90
    error_message = "Memory scale out threshold must be between 50 and 90 percent."
  }
}

variable "scale_out_cooldown" {
  description = "Cooldown period for scaling out (seconds)"
  type        = number
  default     = 300
  validation {
    condition     = var.scale_out_cooldown >= 60 && var.scale_out_cooldown <= 3600
    error_message = "Scale out cooldown must be between 60 and 3600 seconds."
  }
}

variable "scale_in_cooldown" {
  description = "Cooldown period for scaling in (seconds)"
  type        = number
  default     = 300
  validation {
    condition     = var.scale_in_cooldown >= 60 && var.scale_in_cooldown <= 3600
    error_message = "Scale in cooldown must be between 60 and 3600 seconds."
  }
}

# Cost Optimization Variables
variable "enable_spot_instances" {
  description = "Enable Spot instances for cost optimization (not recommended for production)"
  type        = bool
  default     = false
}

variable "enable_s3_lifecycle_policies" {
  description = "Enable S3 lifecycle policies for cost optimization"
  type        = bool
  default     = true
}

# Alert Configuration Variables
variable "alert_email_endpoints" {
  description = "List of email addresses for alerts"
  type        = list(string)
  default     = []
  validation {
    condition = alltrue([
      for email in var.alert_email_endpoints : can(regex("^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$", email))
    ])
    error_message = "All email addresses must be valid."
  }
}

variable "enable_slack_alerts" {
  description = "Enable Slack alerts integration"
  type        = bool
  default     = false
}

variable "slack_webhook_url" {
  description = "Slack webhook URL for alerts (if enabled)"
  type        = string
  default     = ""
  sensitive   = true
}

# Tags
variable "common_tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default = {
    Project     = "llm-api-platform"
    Environment = "production"
    ManagedBy   = "terraform"
    Owner       = "platform-team"
  }
}

# Domain and SSL Configuration
variable "domain_name" {
  description = "Domain name for the application (optional)"
  type        = string
  default     = ""
}

variable "ssl_certificate_arn" {
  description = "ARN of existing SSL certificate in ACM (optional)"
  type        = string
  default     = ""
}

variable "enable_https_redirect" {
  description = "Enable automatic HTTPS redirect"
  type        = bool
  default     = false
}