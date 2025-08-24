from datetime import datetime, timezone
from models.self_help import SelfHelpAnalyticsModel

def record_self_help_view(analytics: SelfHelpAnalyticsModel) -> SelfHelpAnalyticsModel:
    analytics.views = (analytics.views or 0) + 1
    analytics.last_viewed_at = datetime.now(timezone.utc)
    return analytics

def update_helpful_stats(analytics: SelfHelpAnalyticsModel, is_helpful: bool) -> SelfHelpAnalyticsModel:
    if is_helpful:
        analytics.helpful_count = (analytics.helpful_count or 0) + 1
    else:
        analytics.not_helpful_count = (analytics.not_helpful_count or 0) + 1
    return analytics
