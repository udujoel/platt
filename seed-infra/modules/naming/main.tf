locals {
  compact_prefix = lower("${var.project}${var.environment}${var.instance}")
  dashed_prefix  = lower("${var.project}-${var.environment}-${var.instance}")
}
