from django.contrib import admin

from .models import (
    ChatTurn,
    Conversation,
    GeminiUsageTracker,
    ImageUpload,
    JarvisKnowledge,
)


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


class ChatTurnInline(admin.TabularInline):
    model = ChatTurn
    extra = 0
    fields = ('role', 'mode', 'content', 'language', 'safety_severity', 'created_at')
    readonly_fields = ('created_at',)
    can_delete = False
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'user', 'stage', 'language', 'is_active', 'updated_at')
    list_filter = ('stage', 'language', 'is_active')
    search_fields = ('title', 'symptoms', 'user__username', 'vehicle_make', 'vehicle_model')
    autocomplete_fields = ('user',)
    readonly_fields = ('created_at', 'updated_at')
    inlines = [ChatTurnInline]


@admin.register(ChatTurn)
class ChatTurnAdmin(admin.ModelAdmin):
    list_display = ('conversation', 'role', 'mode', 'safety_severity', 'created_at')
    list_filter = ('role', 'mode', 'safety_severity')
    search_fields = ('conversation__title', 'content')
    readonly_fields = ('created_at',)
    exclude = ('structured',)


@admin.register(ImageUpload)
class ImageUploadAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'user', 'conversation', 'mime_type', 'size', 'created_at')
    list_filter = ('mime_type', 'created_at')
    search_fields = ('original_name', 'user__username', 'description')
    readonly_fields = ('file', 'original_name', 'mime_type', 'size', 'width', 'height', 'created_at')
    exclude = ('file',)  # private files are never linked from the public admin

    def has_add_permission(self, request):
        return False
