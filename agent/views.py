from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny

from prospects.serializers import ProspectListSerializer
from agent.coordinator import AgentCoordinator
from agent.scout import ScoutAgent
from agent.auditor import AuditorAgent
from agent.serializers import AgentPipelineRunSerializer, AgentAuditUrlSerializer

CATEGORY_METADATA = [
    {
        "id": "LOCAL_BUSINESS",
        "title": "Local Business Owners",
        "badge": "Best Starting Point",
        "audience": "Coaching centres, gyms, salons, clinics, repair shops, and local service providers.",
        "problems": "No website, outdated website, manual enquiry handling, or poor online presence.",
        "offer": "Simple business website, enquiry form, WhatsApp integration, or lead-tracking system.",
        "sample_niches": ["Gym & Fitness", "Dental Clinic", "Coaching Centre", "Beauty Salon", "Auto Repair"],
        "default_niche": "Gym",
        "requires_location": True,
        "default_location": "Bangalore",
    },
    {
        "id": "STARTUP_FOUNDER",
        "title": "Startup Founders & Solo Entrepreneurs",
        "badge": "High Demand",
        "audience": "People launching SaaS products, online businesses, or new software services.",
        "problems": "Need an MVP, backend APIs, authentication, dashboards, or integrations without hiring full-time.",
        "offer": "Django REST APIs, MVP development, database-backed applications, and backend integrations.",
        "sample_niches": ["Micro SaaS", "AI Tool", "Creator Platform", "Fintech MVP", "Developer Tools"],
        "default_niche": "Micro SaaS",
        "requires_location": False,
        "default_location": "Remote",
    },
    {
        "id": "SMALL_AGENCY",
        "title": "Small Digital Agencies",
        "badge": "Repeat Client Potential",
        "audience": "Web design, marketing, and branding agencies with small teams (3-10 people).",
        "problems": "Too many projects, limited development capacity, and clients asking for technical features.",
        "offer": "White-label website development, backend work, API integrations, and overflow support.",
        "sample_niches": ["Web Design Studio", "Branding Agency", "Marketing Boutique", "Shopify Agency"],
        "default_niche": "Web Design Studio",
        "requires_location": True,
        "default_location": "Austin",
    },
    {
        "id": "CONSULTANT",
        "title": "Consultants & Lead-Gen Businesses",
        "badge": "High ROI Offer",
        "audience": "Recruiters, executive coaches, real estate agents, and B2B service providers.",
        "problems": "Leads get lost, follow-ups are delayed, and repetitive administrative tasks consume time.",
        "offer": "Lead-management dashboards, form-to-CRM workflows, email automation, and follow-up systems.",
        "sample_niches": ["Executive Coach", "Recruiter", "Real Estate Advisor", "B2B Sales Consultant"],
        "default_niche": "Executive Coach",
        "requires_location": False,
        "default_location": "Remote",
    },
    {
        "id": "CREATOR",
        "title": "Creators & Personal Brands",
        "badge": "Direct Outreach",
        "audience": "YouTubers, educators, coaches, and independent professionals.",
        "problems": "Need portfolio websites, booking forms, newsletters, or ways to organize enquiries.",
        "offer": "Portfolio websites, landing pages, booking systems, and simple automations.",
        "sample_niches": ["Course Educator", "Tech YouTuber", "Newsletter Creator", "Fitness Coach"],
        "default_niche": "Course Educator",
        "requires_location": False,
        "default_location": "Remote",
    },
]


class AgentCategoriesView(APIView):
    """
    Returns available niche categories, sample targets, and beginner offer packages.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(CATEGORY_METADATA)


class AgentPipelineView(APIView):
    """
    Runs the multi-agent coordinated pipeline concurrently:
    ScoutAgent -> Fan-out (AuditorAgent + StrategistAgent + CopywriterAgent) -> PostgreSQL
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = AgentPipelineRunSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        category = serializer.validated_data.get('category')
        niche = serializer.validated_data.get('niche')
        location = serializer.validated_data.get('location')
        max_prospects = serializer.validated_data.get('max_prospects', 3)

        coordinator = AgentCoordinator()
        result = coordinator.run(
            category=category,
            niche=niche,
            location=location,
            max_prospects=max_prospects,
        )

        serialized_prospects = ProspectListSerializer(result["prospects"], many=True).data

        return Response({
            "status": "success",
            "category": result["category"],
            "niche": result["niche"],
            "location": result["location"],
            "total_discovered": result["total_discovered"],
            "duration_seconds": result["duration_seconds"],
            "prospects": serialized_prospects,
        }, status=status.HTTP_200_OK)


class AgentAuditView(APIView):
    """
    Runs an on-demand audit on a specific website URL using Scout + Auditor agents.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = AgentAuditUrlSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        url = serializer.validated_data.get('url')
        category = serializer.validated_data.get('category', 'LOCAL_BUSINESS')

        scout = ScoutAgent()
        probe = scout.quick_probe_and_extract(url)
        if not probe.get("reachable"):
            return Response(
                {"error": f"Could not reach URL {url}. Please verify the website is online."},
                status=status.HTTP_400_BAD_REQUEST
            )

        probe["category"] = category
        auditor = AuditorAgent()
        audit_res = auditor.run(probe)

        return Response({
            "url": url,
            "category": category,
            "heuristics": probe.get("heuristics", {}),
            "contacts": probe.get("contacts", {}),
            "audit": audit_res,
        }, status=status.HTTP_200_OK)
