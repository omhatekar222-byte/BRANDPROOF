from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import (
    ApprovalRecord, ApprovedClaim, ApprovedFact, AuditEvent, BrandAsset, BrandGuideline,
    Campaign, Comment, ContentSubmission, ContentVersion, DocumentVersion, GuidelineProposal,
    GuidelineVersion, KnowledgeDocument, Membership, Notification, Organisation,
    ReviewerFeedback, ReviewFinding, TaskAssignment, User,
)
from app.services.analysis import run_analysis
from app.services.intelligence import analyse_feedback, create_proposal

DEMO_PASSWORD = "BrandProof123!"
TODAY = date.today()


def _days_ago(n: int, hour: int = 10) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=n, hours=hour % 12)


def _user(db: Session, email: str, name: str, title: str, color: str) -> User:
    user = db.scalars(select(User).where(User.email == email)).first()
    if user:
        return user
    user = User(
        email=email, full_name=name, title=title, avatar_color=color,
        hashed_password=hash_password(DEMO_PASSWORD), preferences={"theme": "light"},
    )
    db.add(user)
    db.flush()
    return user


def seed_demo(db: Session) -> bool:
    if db.scalars(select(Organisation).where(Organisation.slug == "novatech")).first():
        return False

    # ---------------- Organisation & people ----------------
    novatech = Organisation(
        name="NovaTech", slug="novatech", industry="Consumer electronics",
        brand_colors=["#0B1F3A", "#2F6BFF", "#00C2A8", "#F5F7FB"], is_demo=True,
        settings={"require_approval": True, "default_content_type": "advertisement"},
    )
    helios = db.scalars(select(Organisation).where(Organisation.slug == "helios-foods")).first()
    if helios is None:
        helios = Organisation(
            name="Helios Foods", slug="helios-foods", industry="Food & beverage",
            brand_colors=["#7A3E00", "#F2B705", "#FFF8E7"], is_demo=True,
            settings={"require_approval": True},
        )
        db.add(helios)
    db.add(novatech)
    db.flush()

    admin = _user(db, "admin@novatech.demo", "Aarav Mehta", "Head of Brand", "#2F6BFF")
    creator = _user(db, "creator@novatech.demo", "Priya Nair", "Content Strategist", "#00C2A8")
    reviewer = _user(db, "reviewer@novatech.demo", "Daniel Okafor", "Brand Reviewer", "#7C5CFF")
    approver = _user(db, "approver@novatech.demo", "Meera Kapoor", "Brand Director", "#F2B705")
    rohit = _user(db, "rohit@novatech.demo", "Rohit Verma", "Performance Marketer", "#E4557A")
    ananya = _user(db, "ananya@novatech.demo", "Ananya Bose", "Social Media Lead", "#2B9EB3")
    liam = _user(db, "liam@novatech.demo", "Liam Chen", "Product Marketing", "#8B6B3F")
    helios_admin = _user(db, "admin@helios.demo", "Elena Rossi", "Marketing Director", "#7A3E00")

    db.add_all([
        Membership(user_id=admin.id, organisation_id=novatech.id, role="admin"),
        Membership(user_id=creator.id, organisation_id=novatech.id, role="content_creator"),
        Membership(user_id=reviewer.id, organisation_id=novatech.id, role="reviewer"),
        Membership(user_id=approver.id, organisation_id=novatech.id, role="approver"),
        Membership(user_id=rohit.id, organisation_id=novatech.id, role="content_creator"),
        Membership(user_id=ananya.id, organisation_id=novatech.id, role="content_creator"),
        Membership(user_id=liam.id, organisation_id=novatech.id, role="content_creator"),
        Membership(user_id=helios_admin.id, organisation_id=helios.id, role="admin"),
        Membership(user_id=admin.id, organisation_id=helios.id, role="admin"),
    ])
    db.flush()

    # ---------------- Guidelines ----------------
    guidelines_data = [
        {
            "title": "Brand tone and voice",
            "category": "tone",
            "summary": "How NovaTech sounds across every channel.",
            "content": (
                "NovaTech speaks with calm confidence. Use appropriate promotional language and avoid "
                "exaggerated claims where possible. Keep sentences short and concrete. Prefer specific, "
                "measurable benefits over absolute statements. Do not use words such as revolutionary, "
                "unbeatable, guaranteed, world-class or best-in-class unless an approved evidence source is attached."
            ),
            "effective_date": date(2025, 1, 10), "review_date": date(2026, 12, 31),
        },
        {
            "title": "Advertising claims policy",
            "category": "claims",
            "summary": "Evidence requirements for product and comparative claims.",
            "content": (
                "Every factual product claim must trace to an approved specification record in the Brand Knowledge Vault. "
                "Comparative or superlative claims (for example fastest, number one, best) require approved comparative "
                "evidence for the specific market and period named. If no approved evidence exists, the claim must be "
                "removed or rewritten. Missing evidence is not proof that a claim is false; it means the claim cannot be verified. "
                "Restricted language list: World's number one smartphone; India's fastest smartphone; guaranteed best performance."
            ),
            "effective_date": date(2025, 2, 1), "review_date": date(2027, 2, 1),
        },
        {
            "title": "Visual identity standards",
            "category": "visual",
            "summary": "Approved palette, logo use and layout rules.",
            "content": (
                "The NovaTech logo must appear on all campaign assets. Approved colours are navy #0B1F3A, "
                "signal blue #2F6BFF and teal #00C2A8 on light #F5F7FB. Do not introduce colours outside this palette. "
                "Use the wordmark at least 24px high with clear space equal to the height of the N. "
                "Typography: Inter for digital, with no more than two weights per layout."
            ),
            "effective_date": date(2025, 1, 1), "review_date": date(2026, 11, 30),
        },
        {
            "title": "Accessibility checklist",
            "category": "accessibility",
            "summary": "Minimum accessibility requirements for marketing content.",
            "content": (
                "Every image needs alternative text describing its purpose. Body copy should be at least 16px with "
                "contrast of at least 4.5:1 against its background. Avoid long passages in capitals. "
                "Do not rely on colour alone to convey meaning. Video requires captions."
            ),
            "effective_date": date(2025, 3, 1), "review_date": date(2026, 9, 1),
        },
        {
            "title": "Product naming and terminology",
            "category": "terminology",
            "summary": "Approved product names and preferred terms.",
            "content": (
                "Always write NovaTech X1 in full on first mention. Use smartphone rather than phone or handset. "
                "Model suffixes are capitalised (X1, X2). Do not abbreviate NovaTech to NT in customer-facing copy."
            ),
            "effective_date": date(2025, 1, 5), "review_date": date(2026, 12, 1),
        },
    ]
    guideline_objs = {}
    for index, data in enumerate(guidelines_data):
        guideline = BrandGuideline(
            organisation_id=novatech.id, title=data["title"], category=data["category"],
            content=data["content"], summary=data["summary"], status="approved", version=2,
            owner_id=admin.id, effective_date=data["effective_date"], review_date=data["review_date"],
            created_at=_days_ago(180 - index * 5), updated_at=_days_ago(60 - index * 3),
        )
        db.add(guideline)
        db.flush()
        db.add(GuidelineVersion(
            guideline_id=guideline.id, version=2, content=guideline.content,
            change_summary="Annual review with evidence requirements added", status="approved",
            created_by=admin.id, approved_by=approver.id, created_at=_days_ago(60 - index * 3),
        ))
        db.add(GuidelineVersion(
            guideline_id=guideline.id, version=1, content=guideline.content.split(".")[0] + ".",
            change_summary="Initial publication", status="approved", created_by=admin.id,
            approved_by=approver.id, created_at=_days_ago(180 - index * 5),
        ))
        guideline_objs[data["category"]] = guideline

    # ---------------- Knowledge documents ----------------
    def add_doc(**kwargs) -> KnowledgeDocument:
        doc = KnowledgeDocument(organisation_id=novatech.id, **kwargs)
        db.add(doc)
        db.flush()
        db.add(DocumentVersion(
            document_id=doc.id, version=doc.version, content=doc.extracted_text,
            change_summary="Seeded approved record", created_by=admin.id, created_at=doc.created_at,
        ))
        return doc

    spec = add_doc(
        title="NovaTech X1 Product Specification", doc_type="product_spec", category="Products",
        status="approved", version=3, owner_id=admin.id, approved_by=approver.id,
        effective_date=date(2025, 1, 15), review_date=date(2026, 12, 31),
        extracted_text=(
            "NovaTech X1 — approved product specification.\n\n"
            "Display: 6.7 inches OLED, 120Hz.\n"
            "Battery capacity: 5000 mAh.\n"
            "Battery life: up to 16 hours.\n"
            "Fast charging: 45W wired.\n"
            "Storage: 256 GB.\n"
            "Rear camera: 50 MP main sensor.\n"
            "Processor: NovaCore N3.\n"
            "Colours: Midnight Navy, Signal Blue, Arctic White.\n"
            "Price: ₹54,999 (8 GB + 256 GB).\n"
        ),
        tags=["X1", "specification"], created_at=_days_ago(160),
    )
    warranty = add_doc(
        title="NovaTech X1 Warranty Terms", doc_type="warranty_pricing", category="Support",
        status="approved", version=2, owner_id=admin.id, approved_by=approver.id,
        effective_date=date(2025, 1, 15), review_date=date(2026, 10, 1),
        extracted_text=(
            "NovaTech X1 warranty.\n\n"
            "The NovaTech X1 includes a 2-year limited warranty covering manufacturing defects.\n"
            "Battery degradation below 80% capacity within two years is covered.\n"
            "Accidental damage and water damage are not covered.\n"
        ),
        tags=["warranty"], created_at=_days_ago(150),
    )
    brand_book = add_doc(
        title="NovaTech Brand Guidelines 2026", doc_type="guideline", category="Brand",
        status="approved", version=4, owner_id=admin.id, approved_by=approver.id,
        effective_date=date(2025, 1, 1), review_date=date(2026, 12, 31),
        extracted_text=(
            "NovaTech brand guidelines.\n\n"
            "Our promise: reliable technology for everyday life. Approved brand line: \"Reliable performance for everyday use.\"\n\n"
            "Voice: clear, warm and precise. We explain the benefit, then prove it. We never shout.\n\n"
            "Logo: the NovaTech wordmark is navy #0B1F3A on light backgrounds and white on navy. "
            "Never stretch, recolour or place the logo on a busy photograph. Approved palette: #0B1F3A, #2F6BFF, #00C2A8, #F5F7FB.\n\n"
            "Photography: natural light, real people, no heavy filters. Product shots use the signal blue gradient backdrop.\n"
        ),
        tags=["guidelines", "logo"], created_at=_days_ago(200),
    )
    add_doc(
        title="Approved promotional language", doc_type="approved_claim", category="Messaging",
        status="approved", version=2, owner_id=admin.id, approved_by=approver.id,
        effective_date=date(2025, 2, 1), review_date=date(2026, 12, 15),
        extracted_text=(
            "Approved marketing claims for NovaTech X1.\n\n"
            "\"Reliable performance for everyday use.\"\n"
            "\"A 5000 mAh battery built for a full day.\"\n"
            "\"Two years of warranty cover, as standard.\"\n"
        ),
        tags=["claims"], created_at=_days_ago(140),
    )
    add_doc(
        title="NovaTech restricted language list", doc_type="restricted_language", category="Compliance",
        status="approved", version=2, owner_id=admin.id, approved_by=approver.id,
        effective_date=date(2025, 2, 1), review_date=date(2026, 12, 31),
        extracted_text=(
            "The following phrases are prohibited unless approved comparative evidence is attached:\n"
            "World's number one smartphone\n"
            "India's fastest smartphone\n"
            "guaranteed best performance\n"
            "unbeatable value\n"
            "revolutionary design\n"
            "world-class camera\n"
        ),
        tags=["restricted"], created_at=_days_ago(140),
    )
    terminology = add_doc(
        title="Brand terminology register", doc_type="terminology", category="Brand",
        status="approved", version=1, owner_id=admin.id, approved_by=approver.id,
        effective_date=date(2025, 1, 5), review_date=date(2026, 12, 1),
        extracted_text=(
            "Preferred: smartphone | Avoid: phone\n"
            "Preferred: NovaTech X1 | Avoid: X1 phone\n"
            "Preferred: fast charging | Avoid: super charging\n"
        ),
        tags=["terminology"], created_at=_days_ago(130),
    )
    add_doc(
        title="NovaTech X1 charging note (2024)", doc_type="product_spec", category="Products",
        status="approved", version=1, owner_id=admin.id, approved_by=approver.id,
        effective_date=date(2024, 4, 1), review_date=date(2025, 6, 30),
        extracted_text=(
            "NovaTech X1 charging reference.\n\n"
            "NovaTech X1 fast charging wattage: 45W.\n"
            "A 30-minute charge reaches approximately 60 percent.\n"
            "This note was prepared before the 2025 product refresh and is due for review.\n"
        ),
        tags=["charging", "review-needed"], created_at=_days_ago(300),
    )
    legal = add_doc(
        title="Legal required statements", doc_type="company_info", category="Compliance",
        status="approved", version=3, owner_id=admin.id, approved_by=approver.id,
        effective_date=date(2025, 1, 1), review_date=date(2026, 12, 31),
        extracted_text=(
            "Required statements by content type.\n\n"
            "Advertisements, social posts, landing pages and press releases must include the battery disclaimer: "
            "\"Battery life varies with usage.\"\n"
            "Pricing statements must state the market (India) and include GST.\n"
        ),
        tags=["legal"], created_at=_days_ago(190),
    )
    add_doc(
        title="NovaTech X2 launch brief (draft)", doc_type="product_spec", category="Products",
        status="draft", version=1, owner_id=creator.id,
        effective_date=None, review_date=None,
        extracted_text=(
            "DRAFT — not approved. NovaTech X2 early specification notes.\n"
            "Battery capacity: 6000 mAh (unconfirmed).\n"
            "This draft must not be used as evidence in verification.\n"
        ),
        tags=["X2", "draft"], created_at=_days_ago(4),
    )
    helios_doc = KnowledgeDocument(
        organisation_id=helios.id, title="Helios product catalogue", doc_type="product_spec",
        category="Products", status="approved", version=1, owner_id=helios_admin.id,
        effective_date=date(2025, 1, 1), review_date=date(2026, 12, 31),
        extracted_text="Helios Golden Blend olive oil. Bottle size: 500 ml. Cold pressed. Price: ₹899.",
        tags=["catalogue"], created_at=_days_ago(100),
    )
    db.add(helios_doc)
    db.flush()

    # ---------------- Approved facts & claims ----------------
    facts = [
        ("NovaTech X1 battery capacity", "5000 mAh", "product", spec, "Section: Display and battery", "approved", date(2026, 12, 31)),
        ("NovaTech X1 battery life", "Up to 16 hours", "product", spec, "Section: Display and battery", "approved", date(2026, 12, 31)),
        ("NovaTech X1 warranty period", "2 years", "product", warranty, "Section: Warranty cover", "approved", date(2026, 10, 1)),
        ("NovaTech X1 display size", "6.7 inches", "product", spec, "Section: Display and battery", "approved", date(2026, 12, 31)),
        ("NovaTech X1 storage", "256 GB", "product", spec, "Section: Storage", "approved", date(2026, 12, 31)),
        ("NovaTech X1 rear camera", "50 MP", "product", spec, "Section: Camera", "approved", date(2026, 12, 31)),
        ("NovaTech X1 fast charging wattage", "45W", "product", None, "Approved fact record", "approved", date(2025, 6, 30)),
        ("NovaTech X1 price", "₹54,999", "pricing", spec, "Section: Price", "approved", date(2026, 12, 31)),
        ("Required statement: Battery disclaimer", "Battery life varies with usage.", "compliance", legal, "Legal required statements", "approved", date(2026, 12, 31)),
    ]
    for key, value, category, doc, locator, status, review in facts:
        db.add(ApprovedFact(
            organisation_id=novatech.id, document_id=doc.id if doc else None, key=key, value=value,
            product="NovaTech X1", category=category, status=status, approved_by=approver.id,
            effective_date=date(2025, 1, 15), review_date=review, source_locator=locator,
            created_at=_days_ago(150), updated_at=_days_ago(20),
        ))
    # The stale charging fact points at the 2024 note so its evidence is traceable.
    charging_fact = next(f for f in facts if f[0].endswith("wattage"))
    charging_doc = db.scalars(select(KnowledgeDocument).where(
        KnowledgeDocument.organisation_id == novatech.id,
        KnowledgeDocument.title == "NovaTech X1 charging note (2024)")).first()
    # fix document link for charging fact
    db.flush()
    for fact in db.scalars(select(ApprovedFact).where(ApprovedFact.organisation_id == novatech.id)).all():
        if fact.key == charging_fact[0] and charging_doc:
            fact.document_id = charging_doc.id
            fact.source_locator = "Section: Charging reference"

    approved_claims = [
        ("Reliable performance for everyday use.", "promotional", "approved", brand_book, None),
        ("A 5000 mAh battery built for a full day.", "product", "approved", spec, None),
        ("Nova X1 offers up to 16 hours of battery life.", "product", "approved", spec, None),
        ("Two years of warranty cover, as standard.", "warranty", "approved", warranty, None),
        ("World's number one smartphone", "restricted", "prohibited", None, None),
        ("India's fastest smartphone", "restricted", "prohibited", None, None),
        ("Revolutionary design", "tone", "prohibited", None, None),
        ("Unbeatable value", "tone", "prohibited", None, None),
        ("Guaranteed best performance", "tone", "prohibited", None, None),
        ("World-class camera", "tone", "prohibited", None, None),
        ("Best-in-class battery life", "tone", "prohibited", None, None),
        ("Number one smartphone brand in India", "restricted", "prohibited", None, None),
    ]
    for text, category, status, doc, expiry in approved_claims:
        db.add(ApprovedClaim(
            organisation_id=novatech.id, claim_text=text, category=category, status=status,
            evidence_document_id=doc.id if doc else None, created_by=admin.id,
            review_date=date(2026, 12, 15), expiry_date=expiry, created_at=_days_ago(120),
        ))
    # Claims nearing expiry make the Claim Expiry Radar meaningful.
    db.add(ApprovedClaim(
        organisation_id=novatech.id, claim_text="NovaTech X1 is the lightest flagship in its class.",
        category="product", status="approved", evidence_document_id=spec.id, created_by=admin.id,
        review_date=TODAY + timedelta(days=12), expiry_date=TODAY + timedelta(days=25),
        created_at=_days_ago(200),
    ))
    db.add(ApprovedClaim(
        organisation_id=novatech.id, claim_text="NovaTech X1 supports 45W fast charging.",
        category="product", status="approved", evidence_document_id=charging_doc.id if charging_doc else None,
        created_by=admin.id, review_date=TODAY - timedelta(days=5), expiry_date=TODAY - timedelta(days=2),
        created_at=_days_ago(260),
    ))

    # ---------------- Brand assets ----------------
    for name, kind, color, notes in [
        ("NovaTech primary wordmark", "logo", "#0B1F3A", "Navy wordmark on light backgrounds"),
        ("NovaTech reversed wordmark", "logo", "#FFFFFF", "For navy or photographic backgrounds"),
        ("Signal blue", "colour", "#2F6BFF", "Primary accent"),
        ("NovaTech teal", "colour", "#00C2A8", "Secondary accent, data visualisation"),
        ("Midnight navy", "colour", "#0B1F3A", "Primary text and dark surfaces"),
        ("Inter", "font", None, "Digital typography"),
    ]:
        db.add(BrandAsset(
            organisation_id=novatech.id, name=name, asset_type=kind, color_hex=color,
            is_approved=True, notes=notes, created_at=_days_ago(180),
        ))

    # ---------------- Content submissions ----------------
    def add_submission(
        title, text, content_type, campaign, status, author, days, product="NovaTech X1",
        analyze=True, source_type="text", file_name=None, approved_by=None, approved_days=None,
    ):
        submission = ContentSubmission(
            organisation_id=novatech.id, title=title, content_type=content_type,
            campaign=campaign, product=product, raw_text=text, status=status,
            submitted_by=author.id, current_version=1, created_at=_days_ago(days),
            updated_at=_days_ago(max(days - 2, 0)), source_type=source_type, file_name=file_name,
        )
        db.add(submission)
        db.flush()
        db.add(ContentVersion(
            submission_id=submission.id, version=1, text=text, note="Initial submission",
            created_by=author.id, created_at=_days_ago(days),
        ))
        if analyze:
            run_analysis(db, submission, author.id)
            db.execute(
                AuditEvent.__table__.update()
                .where(AuditEvent.entity_id == submission.id)
                .values(created_at=_days_ago(days))
            )
        if status == "approved":
            submission.approved_by = approved_by or approver.id
            submission.approved_at = _days_ago(approved_days if approved_days is not None else max(days - 2, 0))
        db.flush()
        return submission

    disclaimer = "Battery life varies with usage."

    s1 = add_submission(
        "X1 everyday performance campaign", 
        "The NovaTech X1 features a 5000 mAh battery and a 2-year warranty. "
        "Reliable performance for everyday use. Battery life varies with usage.",
        "advertisement", "Everyday reliability", "under_review", creator, 6,
    )
    s2 = add_submission(
        "X1 battery social teaser",
        "Meet the NovaTech X1. A massive 7000 mAh battery keeps you going all week. "
        "Battery life varies with usage.",
        "social_post", "Battery hero", "under_review", ananya, 5,
    )
    s3 = add_submission(
        "X1 speed campaign (India)",
        "NovaTech X1 is India's fastest smartphone. Experience speed without compromise. "
        "Battery life varies with usage.",
        "advertisement", "Speed launch", "submitted", rohit, 3,
    )
    s4 = add_submission(
        "X1 charging explainer",
        "NovaTech X1 supports 45W fast charging, reaching 60 percent in 30 minutes. "
        "Battery life varies with usage.",
        "product_description", "Always-on", "changes_requested", liam, 9,
    )
    s5 = add_submission(
        "X1 launch announcement",
        "NovaTech X1 brings reliable performance for everyday use with a 5000 mAh battery and a 2-year warranty. "
        "Battery life varies with usage.",
        "press_release", "X1 launch", "approved", creator, 24, approved_days=22,
    )
    s6 = add_submission(
        "X1 festive offer email",
        "The NovaTech X1 is now available at ₹54,999. A 2-year warranty is included. "
        "Battery life varies with usage.",
        "email", "Festive 2025", "approved", rohit, 19, approved_days=17,
    )
    s7 = add_submission(
        "X1 comparison banner",
        "NovaTech X1 has the world's number one smartphone camera and a 5500 mAh battery. "
        "Battery life varies with usage.",
        "landing_page", "Camera push", "rejected", ananya, 14,
    )
    s8 = add_submission(
        "X1 retail product page",
        "NovaTech X1 smartphone with 6.7 inches display and 256 GB storage. "
        "Battery life varies with usage.",
        "product_description", "Retail always-on", "approved", liam, 12, approved_days=10,
    )

    # Case 5 — ten drafts with repeated exaggerated promotional language
    tone_samples = [
        ("X1 monsoon promo", "The NovaTech X1 delivers revolutionary design and unbeatable value. Battery life varies with usage."),
        ("X1 campus campaign", "Unbeatable value for students. The NovaTech X1 is guaranteed best performance. Battery life varies with usage."),
        ("X1 camera reel", "A world-class camera in your pocket. NovaTech X1, revolutionary design. Battery life varies with usage."),
        ("X1 festive ad", "Guaranteed best performance this festive season with the NovaTech X1. Battery life varies with usage."),
        ("X1 trade-in email", "Unbeatable value on trade-in. The NovaTech X1 is a revolutionary design. Battery life varies with usage."),
        ("X1 gaming post", "World-class camera and guaranteed best performance. NovaTech X1. Battery life varies with usage."),
        ("X1 weekend social", "Revolutionary design, unbeatable value. Meet the NovaTech X1. Battery life varies with usage."),
        ("X1 influencer brief", "Use the line: guaranteed best performance. NovaTech X1 with world-class camera. Battery life varies with usage."),
        ("X1 billboard copy", "Unbeatable value. Revolutionary design. NovaTech X1. Battery life varies with usage."),
        ("X1 year-end landing page", "Guaranteed best performance and a world-class camera. NovaTech X1. Battery life varies with usage."),
    ]
    tone_submissions = []
    for i, (title, text) in enumerate(tone_samples):
        author = [rohit, ananya, liam, creator][i % 4]
        status = "approved" if i < 6 else "changes_requested"
        content = add_submission(
            title, text, "social_post" if i % 2 == 0 else "advertisement",
            ["Monsoon", "Campus", "Camera", "Festive", "Trade-in"][i % 5],
            status, author, 30 - i * 2, approved_days=28 - i * 2,
        )
        tone_submissions.append(content)

    db.flush()

    # Reviewer feedback that powers Guideline Intelligence
    tone_guideline = guideline_objs["tone"]
    findings = db.scalars(
        select(ReviewFinding).where(
            ReviewFinding.submission_id.in_([s.id for s in tone_submissions]),
            ReviewFinding.category == "tone",
        )
    ).all()
    reasons = [
        "The guideline does not say which absolute terms are banned.",
        "Reviewer had to interpret 'appropriate promotional language'.",
        "No worked examples were available for social copy.",
        "The approved promotional examples conflict with the tone rule.",
        "Reviewer asked for evidence but no evidence register exists for comparisons.",
    ]
    for i, finding in enumerate(findings[:10]):
        db.add(ReviewerFeedback(
            organisation_id=novatech.id, finding_id=finding.id, submission_id=finding.submission_id,
            reviewer_id=reviewer.id, original_content=finding.original_text,
            issue_category="tone", issue_title="Exaggerated promotional language",
            original_suggestion=finding.suggested_correction,
            final_correction=f"Replace \"{finding.original_text}\" with a specific, measured benefit.",
            decision="modified" if i % 3 == 0 else "accepted",
            feedback_reason=reasons[i % len(reasons)], guideline_id=tone_guideline.id,
            created_at=_days_ago(26 - i * 2),
        ))
        finding.status = "resolved"
        finding.resolved_by = reviewer.id
        finding.resolved_at = _days_ago(26 - i * 2)

    # A few feedback rows for other categories so the engine has more than one group
    other_feedback = [
        ("terminology", "Off-brand terminology", "Use \"smartphone\" instead of \"phone\".",
         "NovaTech smartphone instead of NovaTech phone", 2),
        ("product_accuracy", "Claim contradicts approved product information",
         "Replace with approved 5000 mAh value.", "NovaTech X1 comes with a 5000 mAh battery.", 4),
        ("product_accuracy", "Claim contradicts approved product information",
         "Replace with approved 5000 mAh value.", "NovaTech X1 has a 5000 mAh battery.", 3),
    ]
    for category, title, suggestion, final, days in other_feedback:
        db.add(ReviewerFeedback(
            organisation_id=novatech.id, reviewer_id=reviewer.id,
            original_content=title, issue_category=category, issue_title=title,
            original_suggestion=suggestion, final_correction=final, decision="accepted",
            feedback_reason="Reviewer confirmed the approved value.", created_at=_days_ago(days),
        ))

    db.flush()
    groups = analyse_feedback(db, novatech.id)
    tone_group = next((g for g in groups if g.category == "tone"), None)
    if tone_group:
        create_proposal(db, novatech.id, tone_group, admin.id)

    # Comments, approvals and audit trail
    db.add(Comment(
        organisation_id=novatech.id, submission_id=s2.id, author_id=reviewer.id,
        body="Battery figure does not match the approved 5000 mAh spec. Please correct before resubmitting.",
        created_at=_days_ago(4),
    ))
    db.add(Comment(
        organisation_id=novatech.id, submission_id=s1.id, author_id=approver.id,
        body="Evidence is clean. Waiting on the campaign owner to confirm the final call-to-action.",
        created_at=_days_ago(2),
    ))
    for submission, decision, days in [(s5, "approved", 22), (s6, "approved", 17), (s7, "rejected", 13), (s8, "approved", 10)]:
        db.add(ApprovalRecord(
            organisation_id=novatech.id, entity_type="content", entity_id=submission.id,
            decision=decision, notes="Final approval review" if decision == "approved" else "Unsupported comparative claim",
            previous_status="under_review", new_status=decision, actor_id=approver.id,
            created_at=_days_ago(days),
        ))

    if tone_group:
        db.add(Notification(
            organisation_id=novatech.id, title="Guideline insight ready",
            message=f"Repeated issue \"{tone_group.title}\" found across {tone_group.finding_count} reviewed items.",
            type="insight", link="/guideline-intelligence", created_at=_days_ago(20),
        ))
    db.add(Notification(
        organisation_id=novatech.id, title="Source review overdue",
        message="\"NovaTech X1 charging note (2024)\" is past its review date.",
        type="expiry", link="/analytics", created_at=_days_ago(3),
    ))
    db.add(Notification(
        organisation_id=novatech.id, title="Content submitted for review",
        message=f"\"{s3.title}\" is waiting for brand review.", type="review",
        link="/approval-centre", created_at=_days_ago(3),
    ))

    timeline = [
        ("content.submitted", "content", s3, "Submitted for review", 3),
        ("content.analyzed", "content", s3, "Analyzed in demo mode", 3),
        ("content.approved", "content", s5, "Approved", 22),
        ("content.rejected", "content", s7, "Rejected", 13),
    ]
    for action, entity_type, submission, label, days in timeline:
        db.add(AuditEvent(
            organisation_id=novatech.id, actor_id=approver.id if "approved" in action or "rejected" in action else creator.id,
            action=action, entity_type=entity_type, entity_id=submission.id,
            entity_label=submission.title, updated_value=label, decision=label,
            content_version=1, created_at=_days_ago(days),
        ))

    # Helios isolation demo content
    helios_sub = ContentSubmission(
        organisation_id=helios.id, title="Golden Blend launch", content_type="social_post",
        campaign="Harvest", product="Golden Blend", status="approved",
        raw_text="Helios Golden Blend olive oil is cold pressed. Bottle size: 500 ml.",
        submitted_by=helios_admin.id, current_version=1, analysis_mode="not_analyzed",
        created_at=_days_ago(30),
    )
    db.add(helios_sub)
    db.flush()

    # ─── Nova X1 Campaign + Task Assignment (Two-workspace demo) ─────────────
    nova_campaign = Campaign(
        organisation_id=novatech.id,
        name="Nova X1 Launch — Q4 Digital Campaign",
        product="Nova X1",
        objective=(
            "Create compelling digital advertisements for the Nova X1 smartphone launch. "
            "Drive awareness and purchase intent across Instagram and LinkedIn. "
            "Highlight battery life, warranty and performance within approved claims."
        ),
        target_audience=(
            "Tech-savvy professionals aged 25–40, urban markets, India. "
            "Early adopters, frequent smartphone upgraders."
        ),
        platform="Instagram, LinkedIn",
        content_type="advertisement",
        description=(
            "Q4 launch campaign for the Nova X1 flagship smartphone. "
            "Creators must verify all technical claims against the Product Specification document "
            "before submission. Do NOT use benchmark comparisons without approved data."
        ),
        approved_claims_text=(
            "• Nova X1 delivers up to 16 hours of continuous battery life\n"
            "• 2-year comprehensive manufacturer warranty\n"
            "• High-performance Helio G99 processor\n"
            "• Premium 6.7-inch AMOLED display\n"
            "• 50MP triple camera system"
        ),
        prohibited_claims_text=(
            "• Do NOT claim 'India's fastest smartphone' — no approved benchmark data exists\n"
            "• Do NOT claim '24-hour battery' — approved figure is 16 hours\n"
            "• Do NOT claim '3-year warranty' — approved is 2 years\n"
            "• Do NOT make price comparisons without approval\n"
            "• Do NOT use competitor brand names"
        ),
        mandatory_messages=(
            "• Include: 'BrandProof Verified' or equivalent trust signal\n"
            "• Include legal disclaimer: 'Battery life varies by usage conditions'\n"
            "• All ads must carry NovaTech brand logo"
        ),
        tone_of_voice="Confident, modern, aspirational. Avoid superlatives without evidence.",
        cta="Pre-order Now at novatech.in",
        priority="high",
        status="active",
        deliverables=[
            {"format": "Instagram Story Ad", "quantity": 2, "platform": "Instagram"},
            {"format": "LinkedIn Sponsored Post", "quantity": 1, "platform": "LinkedIn"},
        ],
        created_by=admin.id,
        created_at=_days_ago(5),
        updated_at=_days_ago(2),
    )
    db.add(nova_campaign)
    db.flush()

    nova_task = TaskAssignment(
        organisation_id=novatech.id,
        campaign_id=nova_campaign.id,
        creator_id=creator.id,
        manager_id=admin.id,
        title="Nova X1 — Instagram Story Ad Copy",
        instructions=(
            "Write ad copy for a 15-second Instagram Story promoting the Nova X1. "
            "Focus on battery life and warranty. "
            "Keep it under 100 words. Use the approved claims only. "
            "Avoid unverified performance comparisons. "
            "Submit text copy first — do not add images yet."
        ),
        priority="high",
        status="assigned",
        deadline=_days_ago(-7),  # 7 days from now
        created_at=_days_ago(2),
        updated_at=_days_ago(2),
    )
    db.add(nova_task)
    db.flush()

    # ─── Nova X1 Product Launch (spec demo campaign, assigned to the demo creator) ───
    launch_campaign = Campaign(
        organisation_id=novatech.id,
        name="Nova X1 Product Launch",
        product="Nova X1",
        objective=(
            "Launch the Nova X1 smartphone with verified advertising. "
            "Every technical claim in the launch creative must match approved product facts."
        ),
        target_audience="Tech-savvy professionals aged 25-40, urban India",
        platform="Instagram, LinkedIn",
        content_type="advertisement",
        description=(
            "Product launch advertisement for the Nova X1. "
            "Use only approved claims. Comparative claims require approved benchmark evidence."
        ),
        approved_claims_text=(
            "Nova X1 offers up to 16 hours of battery life.\n"
            "The Nova X1 includes a 2-year limited warranty."
        ),
        prohibited_claims_text=(
            "Do not claim 'India's fastest smartphone' (no approved benchmark evidence exists).\n"
            "Do not claim battery life above 'up to 16 hours'.\n"
            "Do not claim warranty longer than 2 years."
        ),
        mandatory_messages="Battery life varies with usage.",
        tone_of_voice="Confident, modern, aspirational. Avoid superlatives without evidence.",
        cta="Pre-order Now",
        priority="high",
        status="active",
        deliverables=[{"format": "Launch advertisement", "quantity": 1, "platform": "Instagram"}],
        created_by=admin.id,
        created_at=_days_ago(1),
        updated_at=_days_ago(1),
    )
    db.add(launch_campaign)
    db.flush()

    launch_task = TaskAssignment(
        organisation_id=novatech.id,
        campaign_id=launch_campaign.id,
        creator_id=creator.id,
        manager_id=admin.id,
        title="Nova X1 Product Launch — advertisement copy",
        instructions=(
            "Write the launch advertisement copy for the Nova X1. "
            "You may only use the approved claims in the campaign brief. "
            "Submit the copy for AI review before it goes to the manager."
        ),
        priority="high",
        status="assigned",
        deadline=_days_ago(-14),
        created_at=_days_ago(1),
        updated_at=_days_ago(1),
    )
    db.add(launch_task)
    db.flush()

    db.commit()
    return True


def ensure_nova_demo(db: Session) -> None:
    """Idempotent upgrade for databases seeded before the Nova X1 demo facts existed.

    Adds the battery-life approved fact + claim and the 'Nova X1 Product Launch'
    campaign/task only when missing. Safe to call on every startup.
    """
    novatech = db.scalars(select(Organisation).where(Organisation.slug == "novatech")).first()
    if not novatech:
        return
    admin = db.scalars(select(User).where(User.email == "admin@novatech.demo")).first()
    creator = db.scalars(select(User).where(User.email == "creator@novatech.demo")).first()
    spec = db.scalars(select(KnowledgeDocument).where(
        KnowledgeDocument.organisation_id == novatech.id,
        KnowledgeDocument.title == "NovaTech X1 Product Specification",
    )).first()
    approver = db.scalars(select(User).where(User.email == "approver@novatech.demo")).first()
    if not (admin and creator and spec):
        return

    fact = db.scalars(select(ApprovedFact).where(
        ApprovedFact.organisation_id == novatech.id,
        ApprovedFact.key == "NovaTech X1 battery life",
    )).first()
    if not fact:
        db.add(ApprovedFact(
            organisation_id=novatech.id, document_id=spec.id,
            key="NovaTech X1 battery life", value="Up to 16 hours",
            product="NovaTech X1", category="product", status="approved",
            approved_by=approver.id if approver else admin.id,
            effective_date=date(2025, 1, 15), review_date=date(2026, 12, 31),
            source_locator="Section: Display and battery",
            created_at=_days_ago(150), updated_at=_days_ago(20),
        ))

    claim = db.scalars(select(ApprovedClaim).where(
        ApprovedClaim.organisation_id == novatech.id,
        ApprovedClaim.claim_text == "Nova X1 offers up to 16 hours of battery life.",
    )).first()
    if not claim:
        db.add(ApprovedClaim(
            organisation_id=novatech.id,
            claim_text="Nova X1 offers up to 16 hours of battery life.",
            category="product", status="approved", evidence_document_id=spec.id,
            created_by=admin.id, review_date=date(2026, 12, 15),
            created_at=_days_ago(120),
        ))

    if spec.extracted_text and "Battery life" not in spec.extracted_text:
        spec.extracted_text = spec.extracted_text.replace(
            "Battery capacity: 5000 mAh.",
            "Battery capacity: 5000 mAh.\nBattery life: up to 16 hours.",
        )

    campaign = db.scalars(select(Campaign).where(
        Campaign.organisation_id == novatech.id,
        Campaign.name == "Nova X1 Product Launch",
    )).first()
    if not campaign:
        campaign = Campaign(
            organisation_id=novatech.id,
            name="Nova X1 Product Launch",
            product="Nova X1",
            objective=(
                "Launch the Nova X1 smartphone with verified advertising. "
                "Every technical claim in the launch creative must match approved product facts."
            ),
            target_audience="Tech-savvy professionals aged 25-40, urban India",
            platform="Instagram, LinkedIn",
            content_type="advertisement",
            description=(
                "Product launch advertisement for the Nova X1. "
                "Use only approved claims. Comparative claims require approved benchmark evidence."
            ),
            approved_claims_text=(
                "Nova X1 offers up to 16 hours of battery life.\n"
                "The Nova X1 includes a 2-year limited warranty."
            ),
            prohibited_claims_text=(
                "Do not claim 'India's fastest smartphone' (no approved benchmark evidence exists).\n"
                "Do not claim battery life above 'up to 16 hours'.\n"
                "Do not claim warranty longer than 2 years."
            ),
            mandatory_messages="Battery life varies with usage.",
            tone_of_voice="Confident, modern, aspirational. Avoid superlatives without evidence.",
            cta="Pre-order Now",
            priority="high",
            status="active",
            deliverables=[{"format": "Launch advertisement", "quantity": 1, "platform": "Instagram"}],
            created_by=admin.id,
            created_at=_days_ago(1),
            updated_at=_days_ago(1),
        )
        db.add(campaign)
        db.flush()
        db.add(TaskAssignment(
            organisation_id=novatech.id,
            campaign_id=campaign.id,
            creator_id=creator.id,
            manager_id=admin.id,
            title="Nova X1 Product Launch — advertisement copy",
            instructions=(
                "Write the launch advertisement copy for the Nova X1. "
                "You may only use the approved claims in the campaign brief. "
                "Submit the copy for AI review before it goes to the manager."
            ),
            priority="high",
            status="assigned",
            deadline=_days_ago(-14),
            created_at=_days_ago(1),
            updated_at=_days_ago(1),
        ))

    db.commit()
