from rest_framework import serializers
from .models import ServiceProfile, Prospect, OpportunityFinding, OutreachDraft, AgentChatMessage
from .services.outreach import generate_action_url, get_draft_content


class OpportunityFindingSerializer(serializers.ModelSerializer):
    class Meta:
        model = OpportunityFinding
        fields = [
            'id',
            'prospect',
            'category',
            'title',
            'description',
            'evidence_snippet',
            'evidence_url',
            'created_at',
        ]


class OutreachDraftSerializer(serializers.ModelSerializer):
    action_url = serializers.SerializerMethodField()
    final_content = serializers.SerializerMethodField()
    company_name = serializers.CharField(source='prospect.company_name', read_only=True)
    recipient_email = serializers.CharField(source='prospect.contact_email', read_only=True)

    class Meta:
        model = OutreachDraft
        fields = [
            'id',
            'prospect',
            'company_name',
            'recipient_email',
            'channel',
            'subject',
            'body',
            'status',
            'edited_body',
            'reviewer_notes',
            'action_url',
            'final_content',
            'created_at',
            'updated_at',
        ]

    def get_action_url(self, obj):
        return generate_action_url(obj)

    def get_final_content(self, obj):
        return get_draft_content(obj)


class ProspectListSerializer(serializers.ModelSerializer):
    findings_count = serializers.IntegerField(source='findings.count', read_only=True)
    drafts_count = serializers.IntegerField(source='drafts.count', read_only=True)
    approved_drafts_count = serializers.SerializerMethodField()

    class Meta:
        model = Prospect
        fields = [
            'id',
            'company_name',
            'website_url',
            'domain',
            'industry',
            'contact_email',
            'linkedin_url',
            'X_url',
            'instagram_url',
            'match_score',
            'status',
            'findings_count',
            'drafts_count',
            'approved_drafts_count',
            'created_at',
            'updated_at',
        ]

    def get_approved_drafts_count(self, obj):
        return obj.drafts.filter(status='APPROVED').count()


class ProspectDetailSerializer(serializers.ModelSerializer):
    findings = OpportunityFindingSerializer(many=True, read_only=True)
    drafts = OutreachDraftSerializer(many=True, read_only=True)
    has_embedding = serializers.SerializerMethodField()

    class Meta:
        model = Prospect
        fields = [
            'id',
            'company_name',
            'website_url',
            'domain',
            'industry',
            'decision_maker_name',
            'decision_maker_title',
            'contact_email',
            'linkedin_url',
            'X_url',
            'instagram_url',
            'tech_stack_detected',
            'buisness_summery',
            'match_score',
            'qualification_notes',
            'status',
            'has_embedding',
            'findings',
            'drafts',
            'created_at',
            'updated_at',
        ]

    def get_has_embedding(self, obj):
        return obj.summary_embedding is not None


class ServiceProfileSerializer(serializers.ModelSerializer):
    has_embedding = serializers.SerializerMethodField()

    class Meta:
        model = ServiceProfile
        fields = [
            'id',
            'name',
            'portfolio_url',
            'service_description',
            'target_icp_criteria',
            'is_active',
            'has_embedding',
            'created_at',
            'updated_at',
        ]

    def get_has_embedding(self, obj):
        return obj.embedding is not None


class PipelineRunRequestSerializer(serializers.Serializer):
    portfolio_url = serializers.URLField(required=False)
    max_prospects_per_niche = serializers.IntegerField(required=False, default=2, min_value=1, max_value=10)


class BatchDispatchSerializer(serializers.Serializer):
    draft_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        default=list
    )
    force = serializers.BooleanField(required=False, default=False)

class AgentChatMessageSerializer(serializers.ModelSerializer):
    text = serializers.CharField(source='content', read_only = True)

    class Meta:
        model = AgentChatMessage
        fields = ['id', 'prospect', 'role', 'text', 'created_at']
