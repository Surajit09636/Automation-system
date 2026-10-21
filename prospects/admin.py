from django.contrib import admin, messages
from django.utils.html import format_html
from .models import ServiceProfile, Prospect, OpportunityFinding, OutreachDraft
from .services.outreach import dispatch_single_draft, generate_action_url


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
    actions = ['mark_as_qualified', 'mark_as_disqualified', 'dispatch_approved_drafts_for_prospects']

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

    @admin.action(description="Dispatch all approved drafts for selected prospects")
    def dispatch_approved_drafts_for_prospects(self, request, queryset):
        total_sent = 0
        total_failed = 0
        for prospect in queryset:
            approved_drafts = prospect.drafts.filter(status="APPROVED")
            for draft in approved_drafts:
                res = dispatch_single_draft(draft)
                if res["success"]:
                    total_sent += 1
                else:
                    total_failed += 1

        if total_sent > 0 or total_failed > 0:
            self.message_user(
                request,
                f"Dispatched {total_sent} approved drafts ({total_failed} failed/skipped).",
                level=messages.SUCCESS if total_failed == 0 else messages.WARNING
            )
        else:
            self.message_user(
                request,
                "No approved drafts found for the selected prospects.",
                level=messages.INFO
            )


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
        'quick_action',
        'created_at'
    )
    list_filter = ('channel', 'status', 'created_at')
    search_fields = ('prospect__company_name', 'subject', 'body', 'edited_body')
    readonly_fields = ('created_at', 'updated_at')
    actions = [
        'mark_as_approved',
        'mark_as_rejected',
        'dispatch_selected_drafts',
        'force_dispatch_selected_drafts',
        'mark_as_sent',
    ]

    def quick_action(self, obj):
        url = generate_action_url(obj)
        if not url:
            return "-"

        labels = {
            "EMAIL": "[Email Client]",
            "LINKEDIN": "[Open LinkedIn]",
            "TWITTER": "[Open X]",
            "INSTAGRAM": "[Open IG]",
        }
        label = labels.get(obj.channel, "[Open Link]")
        return format_html('<a href="{}" target="_blank" rel="noopener noreferrer">{}</a>', url, label)
    quick_action.short_description = "Quick Launch"

    @admin.action(description="Approve selected outreach drafts")
    def mark_as_approved(self, request, queryset):
        queryset.update(status="APPROVED")

    @admin.action(description="Reject selected outreach drafts")
    def mark_as_rejected(self, request, queryset):
        queryset.update(status="REJECTED")

    @admin.action(description="Mark selected outreach drafts as SENT")
    def mark_as_sent(self, request, queryset):
        queryset.update(status="SENT")

    @admin.action(description="Dispatch approved drafts (Send emails / prepare social)")
    def dispatch_selected_drafts(self, request, queryset):
        sent_count = 0
        error_count = 0
        errors = []

        for draft in queryset:
            res = dispatch_single_draft(draft, force=False)
            if res["success"]:
                sent_count += 1
            else:
                error_count += 1
                errors.append(f"Draft #{draft.id} ({draft.channel}): {res.get('error')}")

        msg = f"Dispatched {sent_count} drafts successfully."
        if error_count > 0:
            msg += f" {error_count} failed or skipped (drafts must be APPROVED)."
            self.message_user(request, msg, level=messages.WARNING)
        else:
            self.message_user(request, msg, level=messages.SUCCESS)

    @admin.action(description="Force dispatch selected drafts (Send immediately)")
    def force_dispatch_selected_drafts(self, request, queryset):
        sent_count = 0
        error_count = 0

        for draft in queryset:
            res = dispatch_single_draft(draft, force=True)
            if res["success"]:
                sent_count += 1
            else:
                error_count += 1

        self.message_user(
            request,
            f"Force dispatched {sent_count} drafts ({error_count} failed).",
            level=messages.SUCCESS if error_count == 0 else messages.WARNING
        )
