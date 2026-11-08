import re
from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import (
    ApprovedClaim, ApprovedFact, BrandAsset, BrandGuideline, ContentFactUsage,
    ContentSubmission, ExtractedClaim, KnowledgeDocument, ReviewFinding,
)
from app.services import ai
from app.services.audit import record_audit
from app.services.knowledge_index import build_index, search

SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|\n+")
SUPERLATIVE_RE = re.compile(
    r"\b(fastest|best|number one|no\.? ?1|#1|world'?s|india'?s|unbeatable|revolutionary|"
    r"guaranteed|world[- ]class|best[- ]in[- ]class|leading|most advanced|perfect|"
    r"longest|shortest|largest|biggest|greatest|highest|lowest|cheapest|safest|"
    r"lightest|thinnest|smallest|strongest|most reliable|most powerful)\b",
    re.I,
)
COMPARATIVE_RE = re.compile(r"\b(vs\.?|versus|better than|faster than|more than any|outperforms)\b", re.I)
# Evidence that can actually support a comparative/superlative statement.
COMPARATIVE_EVIDENCE_RE = re.compile(
    r"\b(benchmark|benchmarks|independent|third[- ]party|survey|study|market report|"
    r"ranked|ranking|award|certified|tested by|research)\b",
    re.I,
)


def _has_comparative_support(evidence_text: str) -> bool:
    return bool(SUPERLATIVE_RE.search(evidence_text) or COMPARATIVE_EVIDENCE_RE.search(evidence_text))
FEATURE_VERB_RE = re.compile(
    r"\b(has|have|offers?|comes? with|features?|provides?|includes?|supports?|delivers?|boasts?)\b", re.I
)
PRODUCT_MENTION_RE = re.compile(r"\b(novatech|nexa|pulse|x1|x2|x3)\b", re.I)

WORD_NUMBERS = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
    "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
    "eleven": "11", "twelve": "12",
}
WORD_NUMBER_RE = re.compile(r"\b(" + "|".join(WORD_NUMBERS) + r")\b", re.I)


def _numeric_normalised(text: str) -> str:
    """Replace spelled-out small numbers so e.g. 'three-year' becomes '3 year'."""
    return WORD_NUMBER_RE.sub(lambda m: WORD_NUMBERS[m.group(1).lower()], text or "")


UNITS = [
    ("mAh", re.compile(r"(\d[\d,\.]*)\s*mah\b", re.I)),
    ("years", re.compile(r"(\d+(?:\.\d+)?)\s*[- ]?\s*years?\b", re.I)),
    ("hours", re.compile(r"(\d+(?:\.\d+)?)\s*[- ]?\s*hours?\b", re.I)),
    ("W", re.compile(r"(\d+(?:\.\d+)?)\s*w(?:att)?s?\b", re.I)),
    ("GB", re.compile(r"(\d+(?:\.\d+)?)\s*gb\b", re.I)),
    ("MP", re.compile(r"(\d+(?:\.\d+)?)\s*mp\b", re.I)),
    ("Hz", re.compile(r"(\d+(?:\.\d+)?)\s*hz\b", re.I)),
    ("inches", re.compile(r"(\d+(?:\.\d+)?)\s*(?:inch|inches|\")\b", re.I)),
]

STOPWORDS = {
    "the", "a", "an", "and", "or", "with", "for", "has", "have", "offers", "offer", "comes",
    "come", "features", "feature", "provides", "provide", "includes", "include", "supports",
    "support", "delivers", "deliver", "from", "that", "this", "its", "our", "is", "are", "was",
    "were", "of", "in", "on", "to", "by", "as", "at", "it", "we", "you", "your", "be", "been",
}


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace("\u2019", "'").replace("\u2018", "'")).strip()


def tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9']+", (text or "").lower()) if t not in STOPWORDS and len(t) > 1}


def measurements(text: str) -> list[tuple[float, str, str]]:
    out = []
    for unit, pattern in UNITS:
        for match in pattern.finditer(_numeric_normalised(text or "")):
            try:
                out.append((float(match.group(1).replace(",", "")), unit, match.group(0)))
            except ValueError:
                continue
    return out


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def extract_sentences(text: str) -> list[str]:
    parts = [norm(p) for p in SENTENCE_RE.split(text or "")]
    return [p for p in parts if len(p) > 8]


CLAUSE_SPLIT_RE = re.compile(r"\s*,\s*(?:and|with)\s+|\s+and\s+", re.I)


def _clauses(sentence: str) -> list[str]:
    """Split a sentence that bundles several independent claims into clause-level claims,
    e.g. "X is fastest, with 24 hours of battery and a 3-year warranty." into three claims.
    Keeps simple single-claim sentences intact."""
    signals = []
    if SUPERLATIVE_RE.search(sentence) or COMPARATIVE_RE.search(sentence):
        signals.append("superlative")
    signals.extend(unit for _, unit, _ in measurements(sentence))
    if len(signals) < 2:
        return [sentence]
    parts = [norm(p) for p in CLAUSE_SPLIT_RE.split(sentence)]
    parts = [p for p in parts if len(p) > 4]
    if len(parts) < 2:
        return [sentence]
    return parts


def claim_candidates(text: str) -> list[dict]:
    found: list[dict] = []
    seen = set()
    for sentence in extract_sentences(text):
        for clause in _clauses(sentence):
            key = clause.lower()
            if key in seen:
                continue
            is_fact = bool(measurements(clause))
            is_super = bool(SUPERLATIVE_RE.search(clause) or COMPARATIVE_RE.search(clause))
            is_product_claim = bool(PRODUCT_MENTION_RE.search(clause) and FEATURE_VERB_RE.search(clause))
            if not (is_fact or is_super or is_product_claim):
                continue
            seen.add(key)
            risk = "high" if is_super else ("medium" if is_fact else "low")
            category = "comparative" if is_super or COMPARATIVE_RE.search(clause) else "product"
            found.append({"claim_text": clause, "category": category, "risk_level": risk})
    return found[:40]


def _restricted_phrases(db: Session, org_id: str) -> list[dict]:
    phrases: list[dict] = []
    claims = db.scalars(
        select(ApprovedClaim).where(
            ApprovedClaim.organisation_id == org_id, ApprovedClaim.status == "prohibited"
        )
    ).all()
    for claim in claims:
        phrases.append({
            "phrase": claim.claim_text,
            "label": "Prohibited promotional claim",
            "category": claim.category,
            "document_id": claim.evidence_document_id,
            "source": "Prohibited claim register",
        })
    docs = db.scalars(
        select(KnowledgeDocument).where(
            KnowledgeDocument.organisation_id == org_id,
            KnowledgeDocument.doc_type == "restricted_language",
            KnowledgeDocument.status == "approved",
        )
    ).all()
    for doc in docs:
        for line in (doc.extracted_text or "").splitlines():
            for piece in re.split(r"[;•]", line):
                entry = piece.strip(" -\t")
                if not entry:
                    continue
                words = entry.split(":", 1)[-1] if ":" in entry else entry
                for term in [t.strip(" \"'“”") for t in re.split(r",| or ", words)]:
                    if 3 <= len(term) <= 90:
                        phrases.append({
                            "phrase": term,
                            "label": doc.title,
                            "category": "restricted_language",
                            "document_id": doc.id,
                            "source": doc.title,
                        })
    return phrases


def _contains_phrase(text: str, phrase: str) -> bool:
    pattern = r"\b" + re.escape(norm(phrase)).replace(r"\ ", r"[\s\-]+") + r"\b"
    return re.search(pattern, norm(text), re.I) is not None


def _fact_matches(fact: ApprovedFact, claim_text: str) -> tuple[bool, str]:
    claim_lower = norm(claim_text).lower()
    if fact.product and norm(fact.product).lower() not in claim_lower:
        product_tokens = tokens(fact.product)
        claim_tokens_all = tokens(claim_text)
        if not product_tokens.issubset(claim_tokens_all):
            # Allow product-suffix omission (e.g. "NovaTech" without "X1") when the
            # claim marker (brand token or model token) or the same measurement
            # unit plus key overlap still identifies the fact.
            brand_hint = bool(product_tokens & claim_tokens_all)
            claim_units = measurements(claim_text)
            fact_units = measurements(fact.value)
            same_unit = bool(claim_units and fact_units and claim_units[0][1] == fact_units[0][1])
            if not (brand_hint and same_unit) and not (claim_units and fact_units):
                return False, ""
    key_tokens = tokens(fact.key) - tokens(fact.product or "")
    key_tokens = {t for t in key_tokens if t not in {"capacity", "specification", "specs", "details", "period"}}
    if not key_tokens:
        key_tokens = tokens(fact.key)
    claim_tokens = tokens(claim_text)
    shared = key_tokens & claim_tokens
    claim_measurements = measurements(claim_text)
    fact_measurements = measurements(fact.value)
    same_unit = bool(claim_measurements and fact_measurements and claim_measurements[0][1] == fact_measurements[0][1])
    if same_unit and (shared or any(t in claim_lower for t in tokens(fact.product or ""))):
        return True, "unit"
    if shared and (len(shared) >= 1 and len(shared) / max(len(key_tokens), 1) >= 0.5):
        return True, "lexical"
    return False, ""


def _doc_excerpt(document, fact: ApprovedFact) -> str:
    """Return the actual line from the source document that backs this fact."""
    if not document or not (document.extracted_text or ""):
        return ""
    unit_words = {unit.lower() for _, unit, _ in measurements(fact.value)}
    if "years" in unit_words:
        unit_words.add("year")
    if "hours" in unit_words:
        unit_words.add("hour")
    key_tokens = tokens(fact.key) - tokens(fact.product or "")
    best_line, best_score = "", -1.0
    for line in (document.extracted_text or "").splitlines():
        line_lower = line.lower()
        has_unit = any(u in line_lower for u in unit_words)
        key_hits = len(tokens(line) & key_tokens)
        score = (0.5 if key_hits else 0.0) + (0.5 if has_unit else 0.0)
        if key_hits and has_unit and score > best_score:
            best_line, best_score = line, score
    if best_line:
        return norm(best_line)[:220]
    for line in (document.extracted_text or "").splitlines():
        if tokens(line) & key_tokens:
            return norm(line)[:220]
    return ""


def _correction_for_fact(fact: ApprovedFact) -> str:
    product = fact.product or "The product"
    key = fact.key
    if product.lower() in key.lower():
        key = re.sub(re.escape(product), "", key, flags=re.I).strip(" -:")
    key = re.sub(r"\bcapacity\b", "", key, flags=re.I).strip(" -:")
    units = measurements(fact.value)
    if units:
        value, unit, _raw = units[0]
        int_value = int(value) if float(value).is_integer() else value
        key_lower = fact.key.lower()
        if unit == "hours" and "battery" in key_lower:
            return f"{product} offers up to {int_value} hours of battery life."
        if unit == "years" and "warranty" in key_lower:
            return f"{product} comes with a {int_value}-year warranty."
        if unit == "mAh":
            return f"{product} features a {fact.value} battery."
        noun = key or "specification"
        return f"{product} comes with a {fact.value} {noun}."
    return f"{fact.key}: {fact.value}."


def verify_claim(db: Session, org_id: str, claim: dict, index: list[dict], restricted: list[dict]) -> dict:
    text = claim["claim_text"]
    is_comparative = bool(SUPERLATIVE_RE.search(text) or COMPARATIVE_RE.search(text))
    status = "unsupported"
    confidence = 0.35
    explanation = ""
    action = ""
    correction = ""
    evidence = {}
    matched_fact: ApprovedFact | None = None

    matched_restricted = next((p for p in restricted if _contains_phrase(text, p["phrase"])), None)
    if matched_restricted:
        status = "unsupported"
        confidence = 0.55
        explanation = (
            f"This wording matches a prohibited claim in the brand knowledge base "
            f"(\"{matched_restricted['phrase']}\"). No approved evidence is attached to it, and "
            f"missing evidence is not proof that it is false — it simply cannot be published as-is. "
            f"For comparative claims such as \"fastest\", the required approved benchmark evidence "
            f"was not found in the organisation's approved sources."
        )
        action = "Remove the restricted wording or obtain and attach approved benchmark evidence."
        correction = "Rewrite without the restricted superlative or attach the approved benchmark evidence."
        evidence = {
            "source_label": matched_restricted["source"],
            "document_id": matched_restricted["document_id"],
            "passage": matched_restricted["phrase"],
            "locator": "Prohibited language register",
            "is_rule": True,
        }

    # 1) Exact/feature-level comparison against approved facts.
    facts = db.scalars(
        select(ApprovedFact).where(ApprovedFact.organisation_id == org_id, ApprovedFact.status == "approved")
    ).all()
    for fact in facts:
        matches, how = _fact_matches(fact, text)
        if not matches:
            continue
        matched_fact = fact
        stale = bool(fact.review_date and fact.review_date < date.today())
        claim_measurements = measurements(text)
        fact_measurements = measurements(fact.value)
        if claim_measurements and fact_measurements and how == "unit":
            claim_value = claim_measurements[0][0]
            fact_value = fact_measurements[0][0]
            source_label = fact.document.title if fact.document else (fact.key + " (approved fact)")
            excerpt = _doc_excerpt(fact.document, fact) if fact.document else ""
            entry = {
                "source_label": source_label,
                "document_id": fact.document_id,
                "passage": f"{fact.key}: {fact.value}" + (f" — {excerpt}" if excerpt else ""),
                "locator": fact.source_locator or ("Approved fact record" if not fact.document else ""),
                "review_date": fact.review_date.isoformat() if fact.review_date else None,
                "stale": stale,
            }
            if claim_value != fact_value:
                status = "contradicted"
                confidence = 0.95
                explanation = (
                    f"The submitted claim does not match the approved specification. "
                    f"Approved {fact.key} is {fact.value}."
                )
                action = f"Replace the claim with the approved value ({fact.value})."
                correction = _correction_for_fact(fact)
                evidence = entry
                break
            if stale:
                status = "inconclusive"
                confidence = 0.55
                explanation = (
                    f"An approved record matches this claim, but its review date "
                    f"({fact.review_date.isoformat()}) has passed. The evidence exists yet may be out of date."
                )
                action = "Ask the knowledge owner to confirm the value before publishing."
                correction = f"Confirm {fact.key}: the approved record lists {fact.value} (review overdue)."
                evidence = entry
                break
            status = "supported"
            confidence = 0.93
            explanation = f"The claim matches the approved value in the knowledge vault ({fact.key}: {fact.value})."
            action = "No action required."
            correction = ""
            evidence = entry
            break

    if matched_restricted:
        return {
            **claim, "status": "unsupported", "confidence": confidence, "explanation": explanation,
            "suggested_action": action, "correction": correction, "evidence": evidence,
            "fact": None,
        }

    # A comparative or superlative statement cannot be supported by a generic
    # product fact. It needs approved comparative evidence for the market named.
    if status == "supported" and is_comparative:
        support_text = " ".join(str(value) for value in (evidence or {}).values() if isinstance(value, str))
        if not _has_comparative_support(support_text):
            return {
                **claim, "status": "unsupported", "confidence": 0.4,
                "explanation": (
                    "This is a comparative or superlative statement, but no approved comparative "
                    "evidence (benchmark, independent test, survey or market research) exists for "
                    "the specific market named. The approved product facts do not prove it."
                ),
                "suggested_action": (
                    "Remove the superlative, or attach approved comparative evidence for this market "
                    "and period."
                ),
                "correction": (
                    "Rewrite without the comparative claim, e.g. state the approved measured value "
                    "instead of claiming it is the best or longest."
                ),
                "evidence": {}, "fact": None,
            }

    if status in {"supported", "contradicted", "inconclusive"}:
        return {
            **claim, "status": status, "confidence": confidence, "explanation": explanation,
            "suggested_action": action, "correction": correction, "evidence": evidence,
            "fact": matched_fact,
        }

    # 2) Direct match with an approved marketing claim.
    approved = db.scalars(
        select(ApprovedClaim).where(
            ApprovedClaim.organisation_id == org_id, ApprovedClaim.status == "approved"
        )
    ).all()
    claim_tokens = tokens(text)
    best_claim = max(approved, key=lambda c: jaccard(claim_tokens, tokens(c.claim_text)), default=None)
    matches_claim = bool(best_claim and jaccard(claim_tokens, tokens(best_claim.claim_text)) >= 0.55)
    if matches_claim and is_comparative and best_claim and not _has_comparative_support(best_claim.claim_text):
        # A generic approved claim cannot support a comparative statement.
        matches_claim = False
    if matches_claim and best_claim:
        expired = bool(best_claim.expiry_date and best_claim.expiry_date < date.today())
        stale = expired or bool(best_claim.review_date and best_claim.review_date < date.today())
        status = "inconclusive" if stale else "supported"
        confidence = 0.8 if not stale else 0.5
        explanation = (
            "This claim aligns with an approved marketing claim, but that approval has expired or is due for review."
            if stale else
            "This claim closely matches an approved marketing claim stored in the knowledge vault."
        )
        return {
            **claim, "status": status, "confidence": confidence, "explanation": explanation,
            "suggested_action": "Refresh the approval before reuse." if stale else "No action required.",
            "correction": "Obtain a renewed claim approval." if stale else "",
            "evidence": {
                "source_label": "Approved marketing claim",
                "document_id": best_claim.evidence_document_id,
                "passage": best_claim.claim_text,
                "locator": "Approved claim register",
                "stale": stale,
            },
            "fact": None,
        }

    # 3) Vector retrieval over approved documents/facts/claims.
    results = search(index, text, top_k=4, kinds=("document_chunk", "fact", "approved_claim"))
    strong = [r for r in results if r["score"] >= 0.36 and len(tokens(r["text"]) & claim_tokens) >= 2]
    partial = [r for r in results if r["score"] >= 0.2]
    if strong:
        top = strong[0]
        evidence = {
            "source_label": top["document_title"],
            "document_id": top.get("document_id"),
            "passage": top["text"],
            "locator": top.get("locator", ""),
            "review_date": top.get("review_date").isoformat() if top.get("review_date") else None,
            "stale": top.get("stale", False),
        }
        if top.get("stale"):
            status = "inconclusive"
            confidence = 0.5
            explanation = (
                "A related approved source was found, but it is past its review date. "
                "The wording overlaps without confirming the specific claim."
            )
            action = "Request an updated source or human confirmation."
            correction = "Confirm this claim against a current approved source."
        elif is_comparative and not _has_comparative_support(top["text"]):
            return {
                **claim, "status": "unsupported", "confidence": 0.4,
                "explanation": (
                    "A related approved source exists, but it contains no comparative benchmark, "
                    "independent test or market research. It therefore cannot support this "
                    "comparative statement."
                ),
                "suggested_action": "Remove the comparative wording or attach approved comparative evidence.",
                "correction": (
                    "State the approved measured value instead of claiming a ranking or superiority."
                ),
                "evidence": {}, "fact": None,
            }
        else:
            status = "supported"
            confidence = 0.72
            explanation = (
                f"An approved source contains closely related information. The quoted passage is the "
                f"actual evidence from {top['document_title']}."
            )
            action = "No action required. Verify the passage supports the exact wording."
        return {
            **claim, "status": status, "confidence": confidence, "explanation": explanation,
            "suggested_action": action, "correction": correction, "evidence": evidence, "fact": None,
        }
    if partial:
        top = partial[0]
        return {
            **claim, "status": "inconclusive", "confidence": 0.45,
            "explanation": (
                "A related approved source exists but does not specifically confirm this claim "
                "(its scope or wording is insufficient). This is not a contradiction."
            ),
            "suggested_action": "Ask a reviewer to confirm scope, or add a more specific approved source.",
            "correction": "Narrow the claim or attach a specific approved evidence reference.",
            "evidence": {
                "source_label": top["document_title"],
                "document_id": top.get("document_id"),
                "passage": top["text"],
                "locator": top.get("locator", ""),
                "stale": top.get("stale", False),
            },
            "fact": None,
        }

    return {
        **claim, "status": "unsupported", "confidence": 0.3,
        "explanation": (
            "No approved source in this workspace supports this claim. Missing evidence does not "
            "mean the claim is false — it means it cannot be verified and needs human review."
        ),
        "suggested_action": "Provide an approved evidence source, soften the wording, or escalate to a reviewer.",
        "correction": (
            "Remove the comparative or absolute wording unless approved evidence is supplied."
            if SUPERLATIVE_RE.search(text) else "Attach an approved source supporting this statement."
        ),
        "evidence": {}, "fact": None,
    }


def _add_finding(db: Session, submission: ContentSubmission, **kwargs) -> ReviewFinding:
    finding = ReviewFinding(
        submission_id=submission.id, organisation_id=submission.organisation_id, **kwargs
    )
    db.add(finding)
    return finding


def _guideline_for(db: Session, org_id: str, category_hint: str) -> BrandGuideline | None:
    guidelines = db.scalars(
        select(BrandGuideline).where(
            BrandGuideline.organisation_id == org_id, BrandGuideline.status == "approved"
        )
    ).all()
    for g in guidelines:
        if category_hint.lower() in (g.category + " " + g.title + " " + g.content).lower():
            return g
    return guidelines[0] if guidelines else None


def run_analysis(db: Session, submission: ContentSubmission, actor_id: str | None = None) -> dict:
    org_id = submission.organisation_id
    text = submission.raw_text or ""
    mode = "demo"
    analysis_error = None

    db.execute(delete(ContentFactUsage).where(ContentFactUsage.submission_id == submission.id))
    db.execute(delete(ReviewFinding).where(ReviewFinding.submission_id == submission.id))
    db.execute(delete(ExtractedClaim).where(ExtractedClaim.submission_id == submission.id))
    db.flush()

    claims = claim_candidates(text)
    if ai.status()["configured"]:
        try:
            ai_claims = ai.extract_claims_ai(text, submission.content_type)
            existing = {c["claim_text"].lower() for c in claims}
            claims.extend([c for c in ai_claims if c["claim_text"].lower() not in existing])
            mode = "ai"
        except ai.AIUnavailable as exc:
            analysis_error = (
                f"{exc} Deterministic rule checks and local evidence retrieval completed instead. "
                "No AI-generated results are shown."
            )

    restricted = _restricted_phrases(db, org_id)
    index = build_index(db, org_id)
    created_claims: list[ExtractedClaim] = []

    for claim in claims:
        verified = verify_claim(db, org_id, claim, index, restricted)
        evidence = verified.get("evidence") or {}
        fact = verified.get("fact")
        record = ExtractedClaim(
            submission_id=submission.id,
            organisation_id=org_id,
            claim_text=verified["claim_text"],
            normalized_key=(fact.key if fact else "")[:200],
            category=verified.get("category", "product"),
            risk_level=verified.get("risk_level", "medium"),
            status=verified["status"],
            confidence=verified["confidence"],
            explanation=verified["explanation"],
            suggested_action=verified["suggested_action"],
            correction=verified["correction"],
            evidence_document_id=evidence.get("document_id"),
            evidence_source_label=evidence.get("source_label", ""),
            evidence_passage=evidence.get("passage", ""),
            evidence_locator=evidence.get("locator", ""),
            evidence_snapshot={k: v for k, v in evidence.items() if k != "document_id"},
            extractor=mode,
        )
        db.add(record)
        created_claims.append(record)
        if fact:
            db.add(ContentFactUsage(
                submission_id=submission.id, fact_id=fact.id, matched_text=verified["claim_text"][:500]
            ))
        if verified["status"] in {"contradicted", "unsupported", "inconclusive"}:
            severity = "high" if verified["status"] == "contradicted" else (
                "high" if verified.get("risk_level") == "high" and verified["status"] == "unsupported" else "medium"
            )
            guideline = _guideline_for(db, org_id, "claim")
            _add_finding(
                db, submission,
                title={
                    "contradicted": "Claim contradicts approved product information",
                    "unsupported": "Claim lacks approved evidence",
                    "inconclusive": "Claim evidence is incomplete or out of date",
                }[verified["status"]],
                category={"contradicted": "product_accuracy", "unsupported": "unsupported_claim"}.get(
                    verified["status"], "outdated_information"),
                severity=severity,
                original_text=verified["claim_text"],
                explanation=verified["explanation"],
                guideline_ref=guideline.title if guideline else "",
                guideline_id=guideline.id if guideline else None,
                source_document_id=evidence.get("document_id"),
                source_passage=evidence.get("passage", ""),
                source_locator=evidence.get("locator", ""),
                suggested_correction=verified["correction"],
                confidence=verified["confidence"],
                detector=mode,
            )

    # --- Deterministic rule checks independent of claim extraction ---
    # Prohibited / restricted language (data-driven from the vault)
    seen_restricted = set()
    for phrase in restricted:
        if phrase["phrase"].lower() in seen_restricted:
            continue
        if _contains_phrase(text, phrase["phrase"]):
            seen_restricted.add(phrase["phrase"].lower())
            _add_finding(
                db, submission,
                title="Restricted brand language used",
                category="restricted_language",
                severity="high",
                original_text=phrase["phrase"],
                explanation=(
                    f"\"{phrase['phrase']}\" appears on the prohibited language list. "
                    f"It is blocked unless suitable approved evidence exists."
                ),
                guideline_ref=phrase["source"],
                source_document_id=phrase["document_id"],
                source_passage=phrase["phrase"],
                source_locator="Prohibited language register",
                suggested_correction="Remove the restricted phrase or attach approved evidence.",
                confidence=0.9,
                detector="rule",
            )

    # Exaggerated promotional terms stored as prohibited claims (category=tone)
    prohibited_terms = db.scalars(
        select(ApprovedClaim).where(
            ApprovedClaim.organisation_id == org_id,
            ApprovedClaim.status == "prohibited",
            ApprovedClaim.category.in_(["tone", "exaggerated_language"]),
        )
    ).all()
    tone_guideline = _guideline_for(db, org_id, "tone")
    for term in prohibited_terms:
        if _contains_phrase(text, term.claim_text):
            _add_finding(
                db, submission,
                title="Exaggerated promotional language",
                category="tone",
                severity="medium",
                original_text=term.claim_text,
                explanation=(
                    f"The brand tone guideline disallows absolute promotional wording such as "
                    f"\"{term.claim_text}\". Comparative or absolute statements need measurable evidence."
                ),
                guideline_ref=tone_guideline.title if tone_guideline else "Brand tone guideline",
                guideline_id=tone_guideline.id if tone_guideline else None,
                source_document_id=None,
                source_passage=term.claim_text,
                source_locator="Prohibited style register",
                suggested_correction=f"Replace \"{term.claim_text}\" with a specific, evidenced benefit.",
                confidence=0.85,
                detector="rule",
            )

    # Required statements
    required = db.scalars(
        select(ApprovedFact).where(
            ApprovedFact.organisation_id == org_id,
            ApprovedFact.status == "approved",
            ApprovedFact.category == "compliance",
            ApprovedFact.key.like("Required statement:%"),
        )
    ).all()
    if submission.content_type in {"advertisement", "social_post", "landing_page", "press_release"}:
        for fact in required:
            if norm(fact.value).lower() not in norm(text).lower():
                _add_finding(
                    db, submission,
                    title="Required statement missing",
                    category="missing_statement",
                    severity="high",
                    original_text=fact.value,
                    explanation=f"The approved compliance rule requires this statement: \"{fact.value}\".",
                    guideline_ref=fact.key.replace("Required statement:", "").strip(),
                    source_document_id=fact.document_id,
                    source_passage=f"{fact.key}: {fact.value}",
                    source_locator=fact.source_locator,
                    suggested_correction=f"Add: \"{fact.value}\"",
                    confidence=0.98,
                    detector="rule",
                )

    # Approved terminology
    terminology_docs = db.scalars(
        select(KnowledgeDocument).where(
            KnowledgeDocument.organisation_id == org_id,
            KnowledgeDocument.doc_type == "terminology",
            KnowledgeDocument.status == "approved",
        )
    ).all()
    for doc in terminology_docs:
        for line in (doc.extracted_text or "").splitlines():
            match = re.search(r"preferred\s*:\s*(.+?)\s*\|\s*avoid\s*:\s*(.+)", line, re.I)
            if not match:
                continue
            preferred, avoid = match.group(1).strip(), match.group(2).strip()
            if _contains_phrase(text, avoid):
                _add_finding(
                    db, submission,
                    title="Off-brand terminology",
                    category="terminology",
                    severity="low",
                    original_text=avoid,
                    explanation=f"The approved term is \"{preferred}\"; \"{avoid}\" is not approved terminology.",
                    guideline_ref=doc.title,
                    source_document_id=doc.id,
                    source_passage=line.strip(),
                    source_locator="Terminology register",
                    suggested_correction=f"Use \"{preferred}\" instead of \"{avoid}\".",
                    confidence=0.9,
                    detector="rule",
                )

    # Accessibility checks that are actually measurable on text
    if re.search(r"!\[\s*\]\(", text) or re.search(r"<img(?![^>]*\balt=)[^>]*>", text, re.I):
        _add_finding(
            db, submission,
            title="Image without alternative text",
            category="accessibility",
            severity="medium",
            original_text="Image reference without alt text",
            explanation="An image was referenced without a description. Screen readers cannot convey it.",
            guideline_ref="Accessibility guideline",
            source_passage="Images must include alternative text.",
            suggested_correction="Add a concise description of the image's purpose.",
            confidence=0.95,
            detector="rule",
        )
    for block in re.findall(r"\b[A-Z][A-Z0-9 ,'\-]{30,}\b", text):
        _add_finding(
            db, submission,
            title="Long block of capitalised text",
            category="accessibility",
            severity="low",
            original_text=block.strip(),
            explanation="Sustained capitals are harder to read and may be announced letter-by-letter.",
            guideline_ref="Accessibility guideline",
            source_passage="Avoid long passages set in capitals.",
            suggested_correction="Use sentence case for body copy.",
            confidence=0.8,
            detector="rule",
        )

    # Selected visual checks where the information is available in the content
    brands = db.scalars(
        select(BrandAsset).where(BrandAsset.organisation_id == org_id, BrandAsset.is_approved.is_(True))
    ).all()
    approved_colors = {c.upper().lstrip("#") for c in (submission_org_colors(db, org_id))}
    for asset in brands:
        if asset.color_hex:
            approved_colors.add(asset.color_hex.upper().lstrip("#"))
    for hex_code in set(re.findall(r"#([0-9a-fA-F]{6})\b", text)):
        if hex_code.upper() not in approved_colors:
            _add_finding(
                db, submission,
                title="Brand colour outside approved palette",
                category="brand_colour",
                severity="low",
                original_text=f"#{hex_code.upper()}",
                explanation="The colour code is not in the approved brand palette loaded in the vault.",
                guideline_ref="Visual identity",
                source_passage="Approved palette: " + ", ".join(f"#{c}" for c in sorted(approved_colors)),
                suggested_correction="Replace with an approved brand colour.",
                confidence=0.75,
                detector="rule",
            )

    # Proof scorecard is a transparent internal summary, never a certification.
    counts = {"supported": 0, "contradicted": 0, "unsupported": 0, "inconclusive": 0}
    for c in created_claims:
        counts[c.status] = counts.get(c.status, 0) + 1
    score = {
        **counts,
        "total_claims": len(created_claims),
        "findings_total": 0,
        "findings_resolved": 0,
        "pending_approval": submission.status not in {"approved", "rejected"},
        "label": "Internal review summary — not a certified compliance score",
    }
    submission.proof_score = score
    submission.analysis_mode = mode
    submission.analysis_error = analysis_error
    db.flush()

    db.refresh(submission)
    findings = db.scalars(select(ReviewFinding).where(ReviewFinding.submission_id == submission.id)).all()
    score["findings_total"] = len(findings)
    score["findings_resolved"] = len([f for f in findings if f.status == "resolved"])
    submission.proof_score = score

    # Risk classification is rule-based, never an unexplained AI score.
    contradicteds = [c for c in created_claims if c.status == "contradicted"]
    inconclusives = [c for c in created_claims if c.status == "inconclusive"]
    high_risk_claims = [c for c in created_claims if c.status == "unsupported" and c.risk_level == "high"]
    severe_findings = [f for f in findings if f.severity in {"high", "critical"}]
    if contradicteds or severe_findings:
        risk_level = "high"
        risk_reason = (
            "Contradicted specifications or critical guideline violations require human review."
        )
    elif high_risk_claims or len(inconclusives) > 0:
        risk_level = "medium"
        risk_reason = (
            "High-risk unsupported claims or inconclusive evidence require human review or additional evidence."
        )
    else:
        risk_level = "low"
        risk_reason = (
            "All claims are supported and no high-severity findings remain. "
            "Low-risk content may be cleared by automated policy; it is never auto-published."
        )
    score["risk_level"] = risk_level
    score["risk_reason"] = risk_reason
    submission.proof_score = score

    # Low-risk content: mark cleared by automated policy (audit retained).
    cleared = False
    previous_status = submission.status
    if risk_level == "low" and submission.status in {"submitted", "under_review"}:
        submission.status = "cleared_by_policy"
        cleared = True

    record_audit(
        db, org_id, actor_id, "content.analyzed", "content", submission.id, submission.title,
        previous_value=previous_status if cleared else "",
        updated_value=f"{len(created_claims)} claims, {len(findings)} findings, risk={risk_level}"
        + (" (cleared by policy)" if cleared else "")
        + (f". {risk_reason}" if risk_reason else ""),
        content_version=submission.current_version,
        meta={"mode": mode, "ai_error": bool(analysis_error), "risk_level": risk_level, "cleared": cleared},
    )
    if cleared:
        notify = __import__("app.services.audit", fromlist=["notify"]).notify
        notify(
            db, org_id,
            title="Content cleared by automated policy",
            message=f"\"{submission.title}\" passed all checks (risk: low) and was cleared by policy. It is not published automatically.",
            type="success", link=f"/content/{submission.id}",
        )
    db.commit()
    return {
        "analysis_mode": mode,
        "analysis_error": analysis_error,
        "claims": len(created_claims),
        "findings": len(findings),
        "proof_score": score,
        "risk_level": risk_level,
        "cleared_by_policy": cleared,
    }


def submission_org_colors(db: Session, org_id: str) -> list[str]:
    from app.models import Organisation
    org = db.get(Organisation, org_id)
    return (org.brand_colors if org and org.brand_colors else [])
