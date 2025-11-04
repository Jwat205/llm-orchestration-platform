{{/*
Expand the name of the chart.
*/}}
{{- define "llm-platform.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "llm-platform.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "llm-platform.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "llm-platform.labels" -}}
helm.sh/chart: {{ include "llm-platform.chart" . }}
{{ include "llm-platform.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "llm-platform.selectorLabels" -}}
app.kubernetes.io/name: {{ include "llm-platform.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "llm-platform.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "llm-platform.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Component-specific selector labels
*/}}
{{- define "llm-platform.componentSelectorLabels" -}}
app.kubernetes.io/name: {{ include "llm-platform.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
component: {{ .component }}
{{- end }}

{{/*
Django service name
*/}}
{{- define "llm-platform.django.name" -}}
{{- printf "%s-%s" (include "llm-platform.fullname" .) "django" }}
{{- end }}

{{/*
FastAPI service name
*/}}
{{- define "llm-platform.fastapi.name" -}}
{{- printf "%s-%s" (include "llm-platform.fullname" .) "fastapi" }}
{{- end }}

{{/*
FastAPI GPU service name
*/}}
{{- define "llm-platform.fastapi-gpu.name" -}}
{{- printf "%s-%s" (include "llm-platform.fullname" .) "fastapi-gpu" }}
{{- end }}

{{/*
Graph service name
*/}}
{{- define "llm-platform.graph-service.name" -}}
{{- printf "%s-%s" (include "llm-platform.fullname" .) "graph-service" }}
{{- end }}

{{/*
Document processor service name
*/}}
{{- define "llm-platform.document-processor.name" -}}
{{- printf "%s-%s" (include "llm-platform.fullname" .) "document-processor" }}
{{- end }}

{{/*
Training service name
*/}}
{{- define "llm-platform.training-service.name" -}}
{{- printf "%s-%s" (include "llm-platform.fullname" .) "training-service" }}
{{- end }}

{{/*
Billing service name
*/}}
{{- define "llm-platform.billing-service.name" -}}
{{- printf "%s-%s" (include "llm-platform.fullname" .) "billing-service" }}
{{- end }}

{{/*
Security service name
*/}}
{{- define "llm-platform.security-service.name" -}}
{{- printf "%s-%s" (include "llm-platform.fullname" .) "security-service" }}
{{- end }}

{{/*
Monitoring service name
*/}}
{{- define "llm-platform.monitoring-service.name" -}}
{{- printf "%s-%s" (include "llm-platform.fullname" .) "monitoring-service" }}
{{- end }}

{{/*
PostgreSQL service name
*/}}
{{- define "llm-platform.postgresql.name" -}}
{{- if .Values.postgresql.enabled }}
{{- printf "%s-%s" (include "llm-platform.fullname" .) "postgresql" }}
{{- else }}
{{- .Values.config.database.host }}
{{- end }}
{{- end }}

{{/*
Redis service name
*/}}
{{- define "llm-platform.redis.name" -}}
{{- if .Values.redis.enabled }}
{{- printf "%s-%s" (include "llm-platform.fullname" .) "redis-master" }}
{{- else }}
{{- .Values.config.redis.host }}
{{- end }}
{{- end }}

{{/*
Storage class for PVCs
*/}}
{{- define "llm-platform.storageClass" -}}
{{- if .Values.persistence.storageClass }}
{{- .Values.persistence.storageClass }}
{{- else }}
{{- "default" }}
{{- end }}
{{- end }}

{{/*
Image pull policy
*/}}
{{- define "llm-platform.imagePullPolicy" -}}
{{- .pullPolicy | default "IfNotPresent" }}
{{- end }}

{{/*
Common environment variables
*/}}
{{- define "llm-platform.commonEnv" -}}
- name: ENVIRONMENT
  value: {{ .Values.config.api.environment | quote }}
- name: LOG_LEVEL
  value: {{ .Values.config.monitoring.logLevel | quote }}
- name: METRICS_ENABLED
  value: {{ .Values.config.monitoring.metricsEnabled | quote }}
- name: TRACING_ENABLED
  value: {{ .Values.config.monitoring.tracingEnabled | quote }}
{{- end }}

{{/*
Database environment variables
*/}}
{{- define "llm-platform.databaseEnv" -}}
- name: DATABASE_HOST
  value: {{ include "llm-platform.postgresql.name" . }}
- name: DATABASE_PORT
  value: {{ .Values.config.database.port | quote }}
- name: DATABASE_NAME
  value: {{ .Values.config.database.name | quote }}
- name: DATABASE_USER
  value: {{ .Values.config.database.user | quote }}
- name: DATABASE_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ include "llm-platform.fullname" . }}-secrets
      key: database-password
- name: DATABASE_SSL
  value: {{ .Values.config.database.ssl | quote }}
{{- end }}

{{/*
Redis environment variables
*/}}
{{- define "llm-platform.redisEnv" -}}
- name: REDIS_HOST
  value: {{ include "llm-platform.redis.name" . }}
- name: REDIS_PORT
  value: {{ .Values.config.redis.port | quote }}
- name: REDIS_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ include "llm-platform.fullname" . }}-secrets
      key: redis-password
{{- end }}

{{/*
GPU node selector
*/}}
{{- define "llm-platform.gpuNodeSelector" -}}
{{- if .Values.gpu.enabled }}
nodeSelector:
  {{- toYaml .Values.gpu.nodeSelector | nindent 2 }}
{{- end }}
{{- end }}

{{/*
GPU tolerations
*/}}
{{- define "llm-platform.gpuTolerations" -}}
{{- if .Values.gpu.enabled }}
tolerations:
  {{- toYaml .Values.gpu.tolerations | nindent 2 }}
{{- end }}
{{- end }}