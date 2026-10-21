from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Q, Count

from .models import ServiceProfile, Prospect, OpportunityFinding, OutreachDraft, AgentChatMessage
from .serializers import (
    ProspectListSerializer,
    ProspectDetailSerializer,
    OpportunityFindingSerializer,
    OutreachDraftSerializer,
    ServiceProfileSerializer,
    PipelineRunRequestSerializer,
    BatchDispatchSerializer,
    AgentChatMessageSerializer,
)
from .services.outreach import (
    dispatch_single_draft,
    dispatch_approved_drafts,
)
from .services.portfolio import analyze_and_sync_portfolio
from .services.orchestrator import run_portfolio_driven_prospecting
from prospects.services.analyzer import Openrouter_llm, local_llm


class ProspectViewSet(viewsets.ModelViewSet):
    """
    API endpoint to list, search, filter, and manage discovered business prospects.
    """
    queryset = Prospect.objects.all().prefetch_related('findings', 'drafts')

    def get_serializer_class(self):
        if self.action in ['retrieve', 'create', 'update', 'partial_update']:
            return ProspectDetailSerializer
        return ProspectListSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        status_param = self.request.query_params.get('status')
        min_score = self.request.query_params.get('min_score')
        search = self.request.query_params.get('search')
        ordering = self.request.query_params.get('ordering', '-match_score')

        if status_param:
            qs = qs.filter(status=status_param.upper())
        if min_score:
            try:
                qs = qs.filter(match_score__gte=float(min_score))
            except ValueError:
                pass
        if search:
            qs = qs.filter(
                Q(company_name__icontains=search) |
                Q(domain__icontains=search) |
                Q(contact_email__icontains=search)
            )

        valid_orderings = ['match_score', '-match_score', 'created_at', '-created_at', 'company_name']
        if ordering in valid_orderings:
            qs = qs.order_by(ordering)
        else:
            qs = qs.order_by('-match_score')

        return qs

    @action(detail=True, methods=['post'], url_path='dispatch-drafts')
    def dispatch_drafts(self, request, pk=None):
        """
        Dispatches all approved outreach drafts for this specific prospect.
        """
        prospect = self.get_object()
        approved_drafts = prospect.drafts.filter(status='APPROVED')
        results = [dispatch_single_draft(draft) for draft in approved_drafts]

        return Response({
            "prospect_id": prospect.id,
            "company_name": prospect.company_name,
            "dispatched_count": len([r for r in results if r.get('success')]),
            "failed_count": len([r for r in results if not r.get('success')]),
            "details": results
        })


class OpportunityFindingViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint to inspect detected technical gaps and opportunities.
    """
    queryset = OpportunityFinding.objects.all().order_by('-created_at')
    serializer_class = OpportunityFindingSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        prospect_id = self.request.query_params.get('prospect_id')
        category = self.request.query_params.get('category')
        if prospect_id:
            qs = qs.filter(prospect_id=prospect_id)
        if category:
            qs = qs.filter(category=category.upper())
        return qs


class OutreachDraftViewSet(viewsets.ModelViewSet):
    """
    API endpoint to review, edit, approve, and dispatch multi-channel outreach drafts.
    """
    queryset = OutreachDraft.objects.all().select_related('prospect').order_by('-created_at')
    serializer_class = OutreachDraftSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        status_param = self.request.query_params.get('status')
        channel_param = self.request.query_params.get('channel')
        prospect_id = self.request.query_params.get('prospect_id')

        if status_param:
            qs = qs.filter(status=status_param.upper())
        if channel_param:
            qs = qs.filter(channel=channel_param.upper())
        if prospect_id:
            qs = qs.filter(prospect_id=prospect_id)
        return qs

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        draft = self.get_object()
        draft.status = 'APPROVED'
        draft.save(update_fields=['status', 'updated_at'])
        return Response(self.get_serializer(draft).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        draft = self.get_object()
        draft.status = 'REJECTED'
        draft.save(update_fields=['status', 'updated_at'])
        return Response(self.get_serializer(draft).data)

    @action(detail=True, methods=['post'], url_path='dispatch')
    def dispatch_draft(self, request, pk=None):
        draft = self.get_object()
        force = request.data.get('force', False)
        result = dispatch_single_draft(draft, force=force)
        status_code = status.HTTP_200_OK if result.get('success') else status.HTTP_400_BAD_REQUEST
        return Response(result, status=status_code)


    @action(detail=False, methods=['post'], url_path='dispatch-batch')
    def dispatch_batch(self, request):
        serializer = BatchDispatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        draft_ids = serializer.validated_data.get('draft_ids')
        force = serializer.validated_data.get('force', False)

        if draft_ids:
            queryset = OutreachDraft.objects.filter(id__in=draft_ids)
        else:
            queryset = OutreachDraft.objects.filter(status='APPROVED')

        results = dispatch_approved_drafts(queryset=queryset, force=force)
        return Response(results)


class ServiceProfileViewSet(viewsets.ModelViewSet):
    """
    API endpoint to view and update the user's service profile and vector embeddings.
    """
    queryset = ServiceProfile.objects.all().order_by('-created_at')
    serializer_class = ServiceProfileSerializer

    @action(detail=False, methods=['post'], url_path='sync')
    def sync_portfolio(self, request):
        portfolio_url = request.data.get('portfolio_url')
        if not portfolio_url:
            active_profile = ServiceProfile.objects.filter(is_active=True).first()
            portfolio_url = active_profile.portfolio_url if active_profile else "https://surajitsutradhar.in"

        try:
            profile = analyze_and_sync_portfolio(portfolio_url)
            return Response(ServiceProfileSerializer(profile).data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class PipelineRunView(APIView):
    """
    Triggers the end-to-end portfolio discovery and outreach generation pipeline.
    """
    def post(self, request):
        serializer = PipelineRunRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        portfolio_url = serializer.validated_data.get('portfolio_url')
        max_prospects = serializer.validated_data.get('max_prospects_per_niche', 2)

        try:
            prospects = run_portfolio_driven_prospecting(
                portfolio_url=portfolio_url,
                max_prospects_per_niche=max_prospects
            )
            data = ProspectListSerializer(prospects, many=True).data
            return Response({
                "status": "success",
                "total_discovered": len(prospects),
                "prospects": data
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                "status": "error",
                "message": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DashboardStatsView(APIView):
    """
    Returns aggregated KPIs and metrics for the frontend dashboard.
    """
    def get(self, request):
        total_prospects = Prospect.objects.count()
        qualified_prospects = Prospect.objects.filter(status='QUALIFIED').count()
        contacted_prospects = Prospect.objects.filter(status='CONTACTED').count()

        total_drafts = OutreachDraft.objects.count()
        pending_drafts = OutreachDraft.objects.filter(status='PENDING_REVIEW').count()
        approved_drafts = OutreachDraft.objects.filter(status='APPROVED').count()
        sent_drafts = OutreachDraft.objects.filter(status='SENT').count()

        channel_counts = (
            OutreachDraft.objects.values('channel')
            .annotate(count=Count('id'))
            .order_by('channel')
        )

        return Response({
            "prospects": {
                "total": total_prospects,
                "qualified": qualified_prospects,
                "contacted": contacted_prospects,
            },
            "drafts": {
                "total": total_drafts,
                "pending": pending_drafts,
                "approved": approved_drafts,
                "sent": sent_drafts,
            },
            "channel_breakdown": {item['channel']: item['count'] for item in channel_counts}
        })

class AgentChatView(APIView):
    """
    conversational agent endpoint with PostgreSQL presistence.
    Support GET (fetch history), POST (chat & presist), & DELETE (clear history)
    """
    def get(self, request):
        prospect_id = request.query_params.get('prospect_id')
        if prospect_id:
            messages = AgentChatMessage.objects.filter(prospect_id = prospect_id)
        else:
            messages = AgentChatMessage.objects.filter(prospect__isnull = True)
        serializer = AgentChatMessageSerializer(messages, many = True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        user_message = request.data.get("message", "").strip()
        context = request.data.get("context", {})
        prospect_id = request.data.get("prospect_id") or context.get("prospect_id")

        if not user_message:
            return Response({"error": "Message is required"}, status=status.HTTP_400_BAD_REQUEST)

        prospect = None
        if prospect_id:
            prospect = Prospect.objects.filter(id = prospect_id).first()

        # save the user message to the database
        user_msg = AgentChatMessage.objects.create(
            prospect = prospect,
            role='user',
            content=user_message
        )

        company_name = context.get("company_name") or (prospect.company_name if prospect else "None")
        channel = context.get("channel") or "EMAIL"
        current_draft = context.get("current_draft") or "None"
        findings = ", ".join(context.get("findings") or [])

        system_prompt = (
            "You are an expert AI Technical Outreach & Growth Agent for an automation agency.\n"
            f"Active Prospect: {company_name}\n"
            f"Outreach Channel: {channel}\n"
            f"Current Draft: {current_draft}\n"
            f"Detected Opportunities: {findings}\n\n"
            "Task: Assist the user in refining outreach drafts, analyzing technical angles, or answering questions.\n"
            "If asked to rewrite or improve a draft, output ONLY the revised message copy ready to be sent.\n"
            "Keep explanations direct, punchy, and professional."
        )

        llm_messages = [{"role": "system", "content": system_prompt}]
        past_msgs = (
            AgentChatMessage.objects.filter(prospect=prospect).exclude(id = user_msg.id).order_by('-created_at')[:10]
        )
        for m in reversed(list(past_msgs)):
            llm_messages.append({"role": m.role, "content": m.content})
        llm_messages.append({"role": "user", "content": user_message})

        reply_text = ""
        llm = Openrouter_llm()
        if llm:
            try:
                res = llm.invoke(llm_messages)
                reply_text = res.content
            except Exception as e:
                print(f"[Agent Chat] Primary LLM failed: {e}")

        if not reply_text:
            try:
                ollama = local_llm()
                res = ollama.invoke(llm_messages)
                reply_text = res.content
            except Exception as e:
                return Response({"error": f"Model error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Save assistant reply to the database
        assistant_msg = AgentChatMessage.objects.create(
            prospect=prospect,
            role='assistant',
            content=reply_text
        )

        return Response({
            "reply": reply_text,
            "user_message_id": user_msg.id,
            "assistant_message_id": assistant_msg.id
        }, status=status.HTTP_200_OK)

    def delete(self, request):
        prospect_id = request.query_params.get("prospect_id")
        if prospect_id:
            AgentChatMessage.objects.filter(prospect_id=prospect_id).delete()
        else:
            AgentChatMessage.objects.filter(prospect__isnull=True).delete()
        return Response({"status": "cleared"}, status=status.HTTP_200_OK)
