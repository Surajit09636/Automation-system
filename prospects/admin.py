from django.contrib import admin
from django.utils.html import format_html
from .models import ServiceProfile, Prospect, OpportunityFinding, OutreachDraft


class OpportunityFindingInline(admin.TabularInline):
    model = OpportunityFinding
    extra = 0
    fields = ('category', 'title', 'evidence_snippet', 'evidence_url')
    readonly_fields = ("evidence_url",)


class OutreachDraftInline(admin.StackedInline):
    model = OutreachDraft
    extra = 0
    fields = ('channel', 'status', 'subject', 'body', 'edited_body', 'reviewer_notes')


@admin.register(ServiceProfile)
class ServiceProfileAdmin(admin.ModelAdmin):
    list_display = ('name', 'portfolio_url', 'is_active', 'updated_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'service_description', 'target_icp_criteria')
    exclude = ('embedding',)
    readonly_fields = ('embedding_status', 'created_at', 'updated_at')

    def embedding_status(self, obj):
        if obj.embedding is not None:
            return f"Generated ({len(obj.embedding)} dimensions)"
        return "Not generated"
    embedding_status.short_description = "Vector Embedding"


@admin.register(Prospect)
class ProspectAdmin(admin.ModelAdmin):
    list_display = (
        'company_name',
        'domain',
        'match_score',
        'status',
        'contact_email_display',
        'channels_available',
        'updated_at',
    )
    list_filter = ('status', 'industry', 'created_at')
    search_fields = ('company_name', 'domain', 'contact_email', 'buisness_summery')
    exclude = ('summary_embedding',)
    readonly_fields = ('embedding_status', 'created_at', 'updated_at')
    inlines = [OpportunityFindingInline, OutreachDraftInline]
    actions = ['mark_as_qualified', 'mark_as_disqualified']

    def embedding_status(self, obj):
        if obj.summary_embedding is not None:
            return f"Generated ({len(obj.summary_embedding)} dimensions)"
        return "Not generated"
    embedding_status.short_description = "Summary Embedding"

    def contact_email_display(self, obj):
        if obj.contact_email:
            return format_html('<a href="mailto:{}">{}</a>', obj.contact_email, obj.contact_email)
        return "-"
    contact_email_display.short_description = "Email"

    def channels_available(self, obj):
        channels = []
        if obj.contact_email:
            channels.append("Email")
        if obj.linkedin_url:
            channels.append("LinkedIn")
        if obj.X_url:
            channels.append("X")
        if obj.instagram_url:
            channels.append("IG")
        return ", ".join(channels) if channels else "None"
    channels_available.short_description = "Channels"

    @admin.action(description="Mark selected prospects as Qualified")
    def mark_as_qualified(self, request, queryset):
        queryset.update(status="QUALIFIED")

    @admin.action(description="Mark selected prospects as Disqualified")
    def mark_as_disqualified(self, request, queryset):
        queryset.update(status="DISQUALIFIED")


@admin.register(OpportunityFinding)
class OpportunityFindingAdmin(admin.ModelAdmin):
    list_display = ('prospect', 'category', 'title', 'created_at')
    list_filter = ('category', 'created_at')
    search_fields = ('title', 'description', 'prospect__company_name')


@admin.register(OutreachDraft)
class OutreachDraftAdmin(admin.ModelAdmin):
    list_display = (
        'prospect',
        'channel',
        'status',
        'subject',
        'created_at'
    )
    list_filter = ('channel', 'status', 'created_at')
    search_fields = ('prospect__company_name', 'subject', 'body', 'edited_body')
    readonly_fields = ('created_at', 'updated_at')
    actions = ['mark_as_approved', 'mark_as_rejected', 'mark_as_sent']

    @admin.action(description="Approve selected outreach drafts")
    def mark_as_approved(self, request, queryset):
        queryset.update(status="APPROVED")

    @admin.action(description="Reject selected outreach drafts")
    def mark_as_rejected(self, request, queryset):
        queryset.update(status="REJECTED")

    @admin.action(description="Mark selected outreach drafts as SENT")
    def mark_as_sent(self, request, queryset):
        queryset.update(status="SENT")
