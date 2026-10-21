from django.db import models
from pgvector.django import VectorField

class ServiceProfile(models.Model):
    """
    Stores agencies/freelancer services, skills, portfolio highlights and blah blah blah,
    with vectorrepresentations for semantic matching.
    """

    name = models.CharField(max_length = 255, default = "Default Feature")
    portfolio_url = models.URLField(blank = True, null = True)
    service_description = models.TextField(help_text="Detsiled Description of services offered")
    target_icp_criteria = models.TextField(help_text="Defination of your ideal customer profile")

    #Vector embidding of services + ICP (384-dim for all-MiniLM-l6-v2)
    embedding = VectorField(dimensions=384, null = True, blank = True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add = True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class Prospect(models.Model):
    """
    Represents a target buisness discovered and analyzed.
    """

    STATUS_CHOICES = [
        ('DISCOVERED', 'Discovered'),
        ('RESEARCHED', 'Researched'),
        ('QUALIFIED', 'Qualified'),
        ('DISQUALIFIED', 'Disqualified'),
        ('CONTACTED', 'Contacted'),
        ('RESPONDED', 'Responded'),
    ]

    company_name = models.CharField(max_length=255)
    website_url = models.URLField(unique=True)
    domain = models.CharField(max_length=255, blank = True)
    industry = models.CharField(max_length=255, blank = True)
    decision_maker_name = models.CharField(max_length = 255, blank = True)
    decision_maker_title = models.CharField(max_length = 255, blank = True)
    contact_email = models.EmailField(blank=True, null = False)
    linkedin_url = models.URLField(blank=True, null=True)
    X_url = models.URLField(blank=True, null=True)
    instagram_url = models.URLField(blank=True, null=True) 

    #Research and Scoring
    tech_stack_detected = models.JSONField(default=list, blank = True)
    buisness_summery = models.TextField(blank=True)
    summary_embedding = VectorField(dimensions=384, null = True, blank = True)
    match_score = models.FloatField(default = 0.0, help_text = "Fit score between 0.0 to 100.0")
    qualification_notes = models.TextField(blank = True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="DISCOVERED")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.company_name} ({self.status})"

class OpportunityFinding(models.Model):
    """
    Specific verified problems or growth opportunities detected on the prospect's site.
    (e.g., outdated framework, lack of automations, slow load time, broken UX).
    """
    CATEGORY_CHOICES = [
        ('WEB_DEV', 'Web Development / Modernization'),
        ('BACKEND', 'Backend Systems / APIs'),
        ('AUTOMATION', 'Business Automation'),
        ('PERFORMANCE', 'Speed & Performance'),
        ('UX_UI', 'User Experience / Conversion'),
    ]
    prospect = models.ForeignKey(Prospect, on_delete=models.CASCADE, related_name='findings')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    title = models.CharField(max_length=255)
    description = models.TextField(help_text="Explanation of the gap or opportunity")
    evidence_snippet = models.TextField(blank=True, help_text="Quote or specific proof from their website")
    evidence_url = models.URLField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return f"[{self.category}] {self.title} for {self.prospect.company_name}"

class OutreachDraft(models.Model):
    """
    Generated hyper-personalized outreach draft awaiting human review.
    """
    CHANNEL_CHOICES = [
        ('EMAIL', 'Cold Email'),
        ('LINKEDIN', 'LinkedIn Message / InMail'),
        ('TWITTER', 'Twitter / X DM'),
        ('INSTAGRAM', 'Instagram DM'),
    ]
    STATUS_CHOICES = [
        ('PENDING_REVIEW', 'Pending Review'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('SENT', 'Sent'),
    ]
    prospect = models.ForeignKey(Prospect, on_delete=models.CASCADE, related_name='drafts')
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, default='EMAIL')
    subject = models.CharField(max_length=255, blank=True)
    body = models.TextField(help_text="AI-generated message grounded in findings")
    
    # Human-in-the-Loop Feedback
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING_REVIEW')
    edited_body = models.TextField(blank=True, help_text="Your customized version if edited")
    reviewer_notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    def __str__(self):
        return f"{self.channel} Draft for {self.prospect.company_name} ({self.status})"

class AgentChatMessage(models.Model):
    """
    Persists conversational chat history between user and AI agent in PostgreSQL.
    """
    ROLE_CHOICES = [
        ('user', 'User'),
        ('assistant', 'Assistant'),
        ('system', 'System'),
    ]

    prospect = models.ForeignKey(
        Prospect,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='chat_messages'
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='user')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        target = self.prospect.company_name if self.prospect else "Global"
        return f"[{self.role}] {target} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"
