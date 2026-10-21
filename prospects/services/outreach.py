import urllib.parse
from django.conf import settings
from django.core.mail import send_mail
from prospects.models import OutreachDraft, Prospect


def get_draft_content(draft):
    """
    Returns the final copy text, prioritizing user edits if present.
    """
    if draft.edited_body and draft.edited_body.strip():
        return draft.edited_body.strip()
    return (draft.body or "").strip()


def generate_action_url(draft):
    """
    Generates a direct one-click action URL for the given draft and channel.
    """
    content = get_draft_content(draft)
    prospect = draft.prospect

    if draft.channel == "EMAIL":
        if not prospect.contact_email:
            return None
        subject = draft.subject or "Collaboration Opportunity"
        params = urllib.parse.urlencode({"subject": subject, "body": content})
        return f"mailto:{prospect.contact_email}?{params}"

    if draft.channel == "LINKEDIN":
        return prospect.linkedin_url

    if draft.channel == "TWITTER":
        if not prospect.X_url:
            return None
        # If it's a profile URL, can also offer web intent
        encoded_text = urllib.parse.quote(content[:280])
        intent_url = f"https://twitter.com/intent/tweet?text={encoded_text}"
        return intent_url if not prospect.X_url else prospect.X_url

    if draft.channel == "INSTAGRAM":
        return prospect.instagram_url

    return None


def dispatch_single_draft(draft, force=False):
    """
    Dispatches a single outreach draft.
    For EMAIL: sends an automated email using Django's email backend.
    For social channels: validates handles and prepares dispatch metadata.
    """
    if draft.status != "APPROVED" and not force:
        return {
            "success": False,
            "draft_id": draft.id,
            "channel": draft.channel,
            "error": f"Draft status is '{draft.status}'. Must be 'APPROVED' or forced."
        }

    prospect = draft.prospect
    content = get_draft_content(draft)

    if not content:
        return {
            "success": False,
            "draft_id": draft.id,
            "channel": draft.channel,
            "error": "Draft body is empty."
        }

    if draft.channel == "EMAIL":
        recipient = prospect.contact_email
        if not recipient:
            return {
                "success": False,
                "draft_id": draft.id,
                "channel": "EMAIL",
                "error": f"No contact email found for prospect '{prospect.company_name}'."
            }

        subject = draft.subject or "Quick observation regarding your business"
        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@surajitsutradhar.in")

        try:
            print(f"[Outreach] Sending Email to {recipient} ({prospect.company_name})...")
            send_mail(
                subject=subject,
                message=content,
                from_email=from_email,
                recipient_list=[recipient],
                fail_silently=False,
            )
            draft.status = "SENT"
            draft.save(update_fields=["status", "updated_at"])

            if prospect.status != "RESPONDED":
                prospect.status = "CONTACTED"
                prospect.save(update_fields=["status", "updated_at"])

            return {
                "success": True,
                "draft_id": draft.id,
                "channel": "EMAIL",
                "recipient": recipient,
                "message": f"Email successfully sent to {recipient}."
            }
        except Exception as e:
            print(f"[Outreach Error] Failed sending email to {recipient}: {e}")
            return {
                "success": False,
                "draft_id": draft.id,
                "channel": "EMAIL",
                "recipient": recipient,
                "error": str(e)
            }

    # Social Channels (LinkedIn, Twitter / X, Instagram)
    social_urls = {
        "LINKEDIN": prospect.linkedin_url,
        "TWITTER": prospect.X_url,
        "INSTAGRAM": prospect.instagram_url,
    }
    target_url = social_urls.get(draft.channel)

    if not target_url:
        return {
            "success": False,
            "draft_id": draft.id,
            "channel": draft.channel,
            "error": f"No {draft.channel} URL or handle found for prospect '{prospect.company_name}'."
        }

    # If force-marking or user executed social dispatch
    if force:
        draft.status = "SENT"
        draft.save(update_fields=["status", "updated_at"])
        if prospect.status != "RESPONDED":
            prospect.status = "CONTACTED" 
            prospect.save(update_fields=["status", "updated_at"])

    return {
        "success": True,
        "draft_id": draft.id,
        "channel": draft.channel,
        "target_url": target_url,
        "content": content,
        "message": f"{draft.channel} message prepared for {target_url}."
    }


def dispatch_approved_drafts(queryset=None, force=False):
    """
    Batch dispatches all approved drafts or a specified queryset of drafts.
    """
    if queryset is None:
        queryset = OutreachDraft.objects.filter(status="APPROVED")

    results = {
        "total": queryset.count(),
        "sent_count": 0,
        "error_count": 0,
        "details": []
    }

    print(f"\n[Outreach] Starting batch dispatch for {results['total']} drafts...")

    for draft in queryset:
        res = dispatch_single_draft(draft, force=force)
        results["details"].append(res)
        if res["success"]:
            results["sent_count"] += 1
            print(f"[Outreach] [Success] {draft.channel} -> {draft.prospect.company_name}")
        else:
            results["error_count"] += 1
            print(f"[Outreach] [Failed] {draft.channel} -> {draft.prospect.company_name}: {res.get('error')}")

    print(f"[Outreach] Dispatch complete: {results['sent_count']} successful, {results['error_count']} failed.\n")
    return results
