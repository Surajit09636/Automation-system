from rest_framework import serializers
from prospects.models import Prospect


class AgentPipelineRunSerializer(serializers.Serializer):
    category = serializers.ChoiceField(
        choices=Prospect.CATEGORY_CHOICES,
        default='LOCAL_BUSINESS'
    )
    niche = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        default='coaching centre'
    )
    location = serializers.CharField(
        max_length=150,
        required=False,
        allow_blank=True,
        default='Bangalore'
    )
    max_prospects = serializers.IntegerField(
        min_value=1,
        max_value=10,
        default=3
    )


class AgentAuditUrlSerializer(serializers.Serializer):
    url = serializers.URLField(required=True)
    category = serializers.ChoiceField(
        choices=Prospect.CATEGORY_CHOICES,
        default='LOCAL_BUSINESS'
    )
