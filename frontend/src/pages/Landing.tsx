import { Link } from "react-router-dom";
import {
  ArrowRight,
  BookOpenCheck,
  BrainCircuit,
  CheckCircle2,
  ClipboardList,
  Database,
  FileSearch,
  Lightbulb,
  SearchCheck,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Users,
} from "lucide-react";
import ThemeToggle from "../components/ThemeToggle";

const features = [
  {
    icon: <Database size={20} />,
    title: "Brand Knowledge Management",
    body: "Store approved brand information, official facts, guidelines, approved claims, and brand assets in one governed workspace so reviews are grounded in company-approved knowledge.",
  },
  {
    icon: <SearchCheck size={20} />,
    color: "cyan",
    title: "AI-Powered Content Verification",
    body: "Analyze uploaded marketing content against approved brand information and surface inconsistencies, findings, and claim classifications for review before publication.",
  },
  {
    icon: <ShieldAlert size={20} />,
    color: "success",
    title: "Unsupported Claim Detection",
    body: "Identify claims that cannot be supported by approved company information, including statements that need stronger evidence or clearer alignment with brand records.",
  },
  {
    icon: <FileSearch size={20} />,
    title: "Evidence-Based Explanations",
    body: "Explain why a statement is flagged and show the relevant approved information, evidence passage, or source reference that supports the finding.",
  },
  {
    icon: <Lightbulb size={20} />,
    color: "cyan",
    title: "Correction Recommendations",
    body: "Suggest improvements to flagged content while preserving the intended message, helping creators revise issues before final review and submission.",
  },
  {
    icon: <BrainCircuit size={20} />,
    title: "Brand Mistake Pattern Analysis",
    body: "Identify repeated mistakes across content submissions by grouping related reviewer feedback and findings into recurring patterns that teams can inspect.",
  },
  {
    icon: <ClipboardList size={20} />,
    color: "success",
    title: "Guideline Improvement Insights",
    body: "Help administrators understand whether repeated mistakes may indicate unclear brand guidelines or recurring user errors. Insights are advisory, and final decisions remain under administrator control.",
  },
];

const roles = [
  {
    icon: <ShieldCheck size={20} />,
    name: "Administrator",
    tag: "Governance",
    purpose: "Manage and protect the organization's brand identity.",
    capabilities: [
      "Manage official brand information, approved claims, and brand assets.",
      "Maintain brand guidelines and review supporting evidence.",
      "Review content verification results and approval outcomes.",
      "Monitor unsupported claims, inconsistencies, and open findings.",
      "Analyze repeated mistakes and recurring issue patterns.",
      "Review guideline-improvement proposals and keep final brand decisions under control.",
    ],
  },
  {
    icon: <Users size={20} />,
    name: "Freelancer",
    tag: "Creator workspace",
    purpose: "Create and verify content according to approved brand standards.",
    capabilities: [
      "Access assigned tasks and approved campaign context.",
      "Upload or submit marketing content for verification.",
      "Check content against brand guidelines and approved information.",
      "View detected inconsistencies and verification findings.",
      "Understand why content has been flagged with supporting evidence.",
      "Apply suggested corrections before resubmission or approval.",
    ],
  },
  {
    icon: <Sparkles size={20} />,
    name: "Marketer",
    tag: "Role overview",
    purpose: "Maintain brand consistency across marketing campaigns and communication.",
    note: "This section describes marketing responsibilities supported by BrandProof's existing review and governance workflows. It is informational unless a dedicated Marketer role is configured in your workspace.",
    capabilities: [
      "Prepare and review marketing content for campaign use.",
      "Verify campaign messaging against approved brand information.",
      "Identify unsupported marketing claims before publication.",
      "Review AI-assisted content for brand consistency and clarity.",
      "Understand recurring content mistakes and feedback patterns.",
      "Improve marketing communication before final publication decisions.",
    ],
  },
];

const steps = [
  {
    n: "01",
    title: "Establish Brand Knowledge",
    body: "The organization provides approved information, brand guidelines, official facts, and assets that become the source of truth for verification.",
  },
  {
    n: "02",
    title: "Upload Content",
    body: "Users submit marketing materials or written content for review within the relevant workflow or campaign context.",
  },
  {
    n: "03",
    title: "AI Verification",
    body: "BrandProof evaluates content against approved brand knowledge, identifies potential problems, and presents claim findings with evidence-based context.",
  },
  {
    n: "04",
    title: "Review and Improve",
    body: "Users review findings, evidence, and suggested corrections. Administrators can analyze recurring issues and make controlled decisions about guideline improvements.",
  },
];

function Brand() {
  return (
    <Link to="/" className="flex items-center gap-2.5" aria-label="BrandProof home">
      <span className="brand-mark">
        <ShieldCheck size={19} />
      </span>
      <span>
        <span className="brand-name block">BrandProof</span>
        <span className="brand-tag block">Brand governance</span>
      </span>
    </Link>
  );
}

export default function LandingPage() {
  return (
    <div className="landing" id="home">
      <header className="landing-nav">
        <Brand />
        <nav className="landing-nav-links" aria-label="Main navigation">
          <a href="#home" className="hide-mobile">Home</a>
          <a href="#features" className="hide-mobile">Features</a>
          <a href="#how-it-works" className="hide-mobile">How It Works</a>
          <a href="#roles" className="hide-mobile">User Roles</a>
          <ThemeToggle />
          <Link to="/get-started" className="btn btn-primary">
            Get Started <ArrowRight size={14} />
          </Link>
        </nav>
      </header>

      <main>
        <section className="landing-hero">
          <div className="landing-hero-glow" aria-hidden="true" />
          <div className="landing-container" style={{ position: "relative" }}>
            <p className="landing-kicker fade-in">BrandProof</p>
            <h1 className="landing-h1 fade-in">Keep Every Brand Message Consistent, Accurate and On-Brand.</h1>
            <p className="landing-lead fade-in">
              BrandProof helps businesses maintain brand consistency by checking marketing content against approved brand
              guidelines, official information, facts and assets. Identify mistakes, understand why they matter and improve
              content before publication.
            </p>
            <div className="landing-actions fade-in">
              <Link to="/get-started" className="btn btn-primary" style={{ padding: "10px 18px", fontSize: 13.5 }}>
                Get Started <ArrowRight size={15} />
              </Link>
              <a href="#features" className="btn btn-secondary" style={{ padding: "10px 18px", fontSize: 13.5 }}>
                Explore Features
              </a>
            </div>
          </div>
        </section>

        <section id="features" className="landing-section landing-section-alt">
          <div className="landing-container">
            <p className="landing-eyebrow">Features</p>
            <h2 className="landing-h2">Capabilities built for brand governance</h2>
            <p className="landing-sub">
              BrandProof connects approved knowledge, content verification, evidence, and administrator oversight so teams can
              improve accuracy and consistency before content goes live.
            </p>
            <div className="landing-grid-3">
              {features.map((f) => (
                <article key={f.title} className="landing-feature">
                  <div className={`landing-icon ${f.color || ""}`}>{f.icon}</div>
                  <h3 className="landing-card-title">{f.title}</h3>
                  <p className="landing-card-body">{f.body}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section id="how-it-works" className="landing-section">
          <div className="landing-container">
            <p className="landing-eyebrow">How It Works</p>
            <h2 className="landing-h2">A clear workflow from knowledge to publication readiness</h2>
            <p className="landing-sub">
              The process keeps evidence, review, and human decisions visible — so teams can understand issues and act on them with confidence.
            </p>
            <div className="landing-grid-2">
              {steps.map((s) => (
                <article key={s.n} className="landing-step">
                  <div className="landing-step-num">{s.n}</div>
                  <h3 className="landing-card-title">{s.title}</h3>
                  <p className="landing-card-body">{s.body}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section id="roles" className="landing-section landing-section-alt">
          <div className="landing-container">
            <p className="landing-eyebrow">User Roles</p>
            <h2 className="landing-h2">Responsibilities across the brand workflow</h2>
            <p className="landing-sub">
              BrandProof supports governance, content creation, and marketing review responsibilities with role-appropriate access to information and verification outcomes.
            </p>
            <div className="landing-grid-3">
              {roles.map((r) => (
                <article key={r.name} className="landing-role">
                  <div className="landing-role-head">
                    <div className="landing-icon">{r.icon}</div>
                    <span className="landing-role-tag">{r.tag}</span>
                  </div>
                  <h3 className="landing-card-title">{r.name}</h3>
                  <p className="landing-card-body" style={{ marginTop: 6 }}>{r.purpose}</p>
                  {r.note && (
                    <p className="landing-card-body" style={{ marginTop: 8, fontSize: 12.5 }}>
                      {r.note}
                    </p>
                  )}
                  <ul className="landing-list">
                    {r.capabilities.map((c) => (
                      <li key={c}>
                        <CheckCircle2 size={14} />
                        <span>{c}</span>
                      </li>
                    ))}
                  </ul>
                </article>
              ))}
            </div>
          </div>
        </section>
      </main>

      <footer className="landing-footer">
        <div className="landing-container">
          <div className="landing-footer-grid">
            <div>
              <Brand />
              <p style={{ marginTop: 12, fontSize: 13.5, lineHeight: 1.7, maxWidth: 360 }}>
                BrandProof helps teams maintain brand consistency and factual accuracy by checking marketing content against approved brand knowledge, with evidence-based review and administrator oversight.
              </p>
            </div>
            <div>
              <h4>Navigation</h4>
              <div className="landing-footer-links">
                <a href="#home">Home</a>
                <a href="#features">Features</a>
                <a href="#how-it-works">How It Works</a>
                <a href="#roles">User Roles</a>
                <Link to="/get-started">Get Started</Link>
              </div>
            </div>
            <div>
              <h4>Features</h4>
              <div className="landing-footer-links">
                <a href="#features">Brand Knowledge</a>
                <a href="#features">Content Verification</a>
                <a href="#features">Claim &amp; Evidence Review</a>
                <a href="#features">Pattern Insights</a>
              </div>
            </div>
            <div>
              <h4>Workflow</h4>
              <div className="landing-footer-links">
                <a href="#how-it-works">Establish Knowledge</a>
                <a href="#how-it-works">Upload Content</a>
                <a href="#how-it-works">Verify &amp; Improve</a>
                <Link to="/get-started">Open Workspace</Link>
              </div>
            </div>
          </div>
          <div style={{ marginTop: 24, paddingTop: 16, borderTop: "1px solid var(--bp-border-soft)", display: "flex", flexWrap: "wrap", gap: 10, justifyContent: "space-between", alignItems: "center", fontSize: 12 }}>
            <span>BrandProof — evidence-backed brand governance and content verification.</span>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}><BookOpenCheck size={13} /> Human review and approval remain part of the workflow.</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
