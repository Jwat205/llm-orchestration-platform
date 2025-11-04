# Auto Scaling and Monitoring Configuration
# Part 2 of Enhanced Production Infrastructure

# Auto Scaling for Django Service
resource "aws_appautoscaling_target" "django_scaling_target" {
  max_capacity       = 10
  min_capacity       = 2
  resource_id        = "service/${aws_ecs_cluster.llm_api_cluster.name}/${aws_ecs_service.django_service.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"

  tags = {
    Name = "django-scaling-target"
  }
}

resource "aws_appautoscaling_policy" "django_scale_up" {
  name               = "django-scale-up"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.django_scaling_target.resource_id
  scalable_dimension = aws_appautoscaling_target.django_scaling_target.scalable_dimension
  service_namespace  = aws_appautoscaling_target.django_scaling_target.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value       = 70.0
    scale_out_cooldown = 300
    scale_in_cooldown  = 300
  }
}

resource "aws_appautoscaling_policy" "django_scale_memory" {
  name               = "django-scale-memory"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.django_scaling_target.resource_id
  scalable_dimension = aws_appautoscaling_target.django_scaling_target.scalable_dimension
  service_namespace  = aws_appautoscaling_target.django_scaling_target.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageMemoryUtilization"
    }
    target_value       = 80.0
    scale_out_cooldown = 300
    scale_in_cooldown  = 300
  }
}

# Auto Scaling for FastAPI Service
resource "aws_appautoscaling_target" "fastapi_scaling_target" {
  max_capacity       = 20
  min_capacity       = 3
  resource_id        = "service/${aws_ecs_cluster.llm_api_cluster.name}/${aws_ecs_service.fastapi_service.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"

  tags = {
    Name = "fastapi-scaling-target"
  }
}

resource "aws_appautoscaling_policy" "fastapi_scale_up" {
  name               = "fastapi-scale-up"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.fastapi_scaling_target.resource_id
  scalable_dimension = aws_appautoscaling_target.fastapi_scaling_target.scalable_dimension
  service_namespace  = aws_appautoscaling_target.fastapi_scaling_target.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value       = 60.0
    scale_out_cooldown = 180
    scale_in_cooldown  = 300
  }
}

resource "aws_appautoscaling_policy" "fastapi_scale_memory" {
  name               = "fastapi-scale-memory"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.fastapi_scaling_target.resource_id
  scalable_dimension = aws_appautoscaling_target.fastapi_scaling_target.scalable_dimension
  service_namespace  = aws_appautoscaling_target.fastapi_scaling_target.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageMemoryUtilization"
    }
    target_value       = 75.0
    scale_out_cooldown = 180
    scale_in_cooldown  = 300
  }
}

# CloudWatch Log Groups
resource "aws_cloudwatch_log_group" "django_logs" {
  name              = "/ecs/llm-api-django"
  retention_in_days = 30

  tags = {
    Name = "django-logs"
  }
}

resource "aws_cloudwatch_log_group" "fastapi_logs" {
  name              = "/ecs/llm-api-fastapi"
  retention_in_days = 30

  tags = {
    Name = "fastapi-logs"
  }
}

resource "aws_cloudwatch_log_group" "ecs_exec_logs" {
  name              = "/aws/ecs/exec"
  retention_in_days = 7

  tags = {
    Name = "ecs-exec-logs"
  }
}

# CloudWatch Custom Metrics
resource "aws_cloudwatch_metric_alarm" "django_high_cpu" {
  alarm_name          = "django-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "This metric monitors Django service CPU utilization"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    ServiceName = aws_ecs_service.django_service.name
    ClusterName = aws_ecs_cluster.llm_api_cluster.name
  }

  tags = {
    Name = "django-high-cpu-alarm"
  }
}

resource "aws_cloudwatch_metric_alarm" "fastapi_high_cpu" {
  alarm_name          = "fastapi-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = "300"
  statistic           = "Average"
  threshold           = "70"
  alarm_description   = "This metric monitors FastAPI service CPU utilization"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    ServiceName = aws_ecs_service.fastapi_service.name
    ClusterName = aws_ecs_cluster.llm_api_cluster.name
  }

  tags = {
    Name = "fastapi-high-cpu-alarm"
  }
}

resource "aws_cloudwatch_metric_alarm" "alb_response_time" {
  alarm_name          = "alb-high-response-time"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "TargetResponseTime"
  namespace           = "AWS/ApplicationELB"
  period              = "300"
  statistic           = "Average"
  threshold           = "0.1"  # 100ms threshold
  alarm_description   = "This metric monitors ALB response time to maintain <100ms latency"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    LoadBalancer = aws_lb.llm_api_alb.arn_suffix
  }

  tags = {
    Name = "alb-response-time-alarm"
  }
}

resource "aws_cloudwatch_metric_alarm" "alb_5xx_errors" {
  alarm_name          = "alb-5xx-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "HTTPCode_Target_5XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = "300"
  statistic           = "Sum"
  threshold           = "10"
  alarm_description   = "This metric monitors 5XX errors to maintain 99.5% uptime"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    LoadBalancer = aws_lb.llm_api_alb.arn_suffix
  }

  tags = {
    Name = "alb-5xx-errors-alarm"
  }
}

resource "aws_cloudwatch_metric_alarm" "redis_cpu_high" {
  alarm_name          = "redis-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ElastiCache"
  period              = "300"
  statistic           = "Average"
  threshold           = "75"
  alarm_description   = "This metric monitors Redis CPU utilization"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    CacheClusterId = aws_elasticache_replication_group.llm_api_redis.id
  }

  tags = {
    Name = "redis-high-cpu-alarm"
  }
}

resource "aws_cloudwatch_metric_alarm" "rds_cpu_high" {
  alarm_name          = "rds-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "This metric monitors RDS CPU utilization"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.llm_api_db.id
  }

  tags = {
    Name = "rds-high-cpu-alarm"
  }
}

resource "aws_cloudwatch_metric_alarm" "rds_connections_high" {
  alarm_name          = "rds-high-connections"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "DatabaseConnections"
  namespace           = "AWS/RDS"
  period              = "300"
  statistic           = "Average"
  threshold           = "150"
  alarm_description   = "This metric monitors RDS connection count"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.llm_api_db.id
  }

  tags = {
    Name = "rds-high-connections-alarm"
  }
}

# SNS Topic for Alerts
resource "aws_sns_topic" "alerts" {
  name = "llm-api-alerts"

  tags = {
    Name = "llm-api-alerts"
  }
}

# CloudWatch Dashboard
resource "aws_cloudwatch_dashboard" "llm_api_dashboard" {
  dashboard_name = "LLM-API-Production-Dashboard"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["AWS/ApplicationELB", "RequestCount", "LoadBalancer", aws_lb.llm_api_alb.arn_suffix],
            [".", "TargetResponseTime", ".", "."],
            [".", "HTTPCode_Target_2XX_Count", ".", "."],
            [".", "HTTPCode_Target_5XX_Count", ".", "."]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "Load Balancer Metrics"
          period  = 300
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["AWS/ECS", "CPUUtilization", "ServiceName", aws_ecs_service.django_service.name, "ClusterName", aws_ecs_cluster.llm_api_cluster.name],
            [".", "MemoryUtilization", ".", ".", ".", "."],
            [".", "CPUUtilization", "ServiceName", aws_ecs_service.fastapi_service.name, "ClusterName", aws_ecs_cluster.llm_api_cluster.name],
            [".", "MemoryUtilization", ".", ".", ".", "."]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "ECS Service Metrics"
          period  = 300
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 12
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["AWS/RDS", "CPUUtilization", "DBInstanceIdentifier", aws_db_instance.llm_api_db.id],
            [".", "DatabaseConnections", ".", "."],
            [".", "ReadLatency", ".", "."],
            [".", "WriteLatency", ".", "."]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "RDS Metrics"
          period  = 300
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 18
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["AWS/ElastiCache", "CPUUtilization", "CacheClusterId", aws_elasticache_replication_group.llm_api_redis.id],
            [".", "CacheHitRate", ".", "."],
            [".", "NetworkBytesIn", ".", "."],
            [".", "NetworkBytesOut", ".", "."]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "ElastiCache Redis Metrics"
          period  = 300
        }
      }
    ]
  })

  depends_on = [
    aws_lb.llm_api_alb,
    aws_ecs_service.django_service,
    aws_ecs_service.fastapi_service,
    aws_db_instance.llm_api_db,
    aws_elasticache_replication_group.llm_api_redis
  ]
}

# Performance Insights for RDS
resource "aws_rds_cluster_parameter_group" "llm_api_performance" {
  family      = "postgres15"
  name        = "llm-api-performance"
  description = "Performance optimizations for LLM API"

  parameter {
    name  = "shared_preload_libraries"
    value = "pg_stat_statements,auto_explain"
  }

  parameter {
    name  = "auto_explain.log_min_duration"
    value = "100ms"
  }

  parameter {
    name  = "auto_explain.log_analyze"
    value = "on"
  }

  parameter {
    name  = "log_statement_stats"
    value = "on"
  }

  tags = {
    Name = "llm-api-performance"
  }
}

# X-Ray Tracing (optional for detailed performance monitoring)
resource "aws_xray_sampling_rule" "llm_api_sampling" {
  rule_name      = "llm-api-sampling"
  priority       = 9000
  version        = 1
  reservoir_size = 1
  fixed_rate     = 0.05
  url_path       = "*"
  host           = "*"
  http_method    = "*"
  service_type   = "*"
  service_name   = "*"
  resource_arn   = "*"

  tags = {
    Name = "llm-api-sampling"
  }
}