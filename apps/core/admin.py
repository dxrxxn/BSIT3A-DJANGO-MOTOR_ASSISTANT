from django.contrib import admin
from .models import JarvisKnowledge, GeminiUsageTracker


@admin.register(JarvisKnowledge)
class JarvisKnowledgeAdmin(admin.ModelAdmin):
    list_display = ('user_query', 'hit_count', 'source', 'updated_at')
    search_fields = ('user_query', 'keywords', 'ai_response')
    list_filter = ('source', 'updated_at')
    readonly_fields = ('created_at', 'updated_at', 'hit_count')


@admin.register(GeminiUsageTracker)
class GeminiUsageTrackerAdmin(admin.ModelAdmin):
    list_display = ('date', 'requests_count', 'total_tokens', 'prompt_tokens', 'candidates_tokens', 'updated_at')
    readonly_fields = ('date', 'requests_count', 'total_tokens', 'prompt_tokens', 'candidates_tokens', 'updated_at')
