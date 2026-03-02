import { useNavigate } from "react-router-dom";
import { useState, useRef } from "react";
import { GridBackground } from "@/components/GridBackground";
import { Header } from "@/components/Header";

const LandingPage = () => {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("");
  const [status, setStatus] = useState<"idle" | "submitting" | "success" | "error">("idle");

  const waitlistRef = useRef<HTMLDivElement>(null);

  const handleEmailSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setStatus("submitting");
    try {
      const response = await fetch(`https://formspree.io/f/mwvnkgvn`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, email, role }),
      });
      if (response.ok) setStatus("success");
      else setStatus("error");
    } catch {
      setStatus("error");
    }
  };

  return (
    <GridBackground>
      <div className="flex flex-col min-h-screen">
        <Header />

        <main className="flex-1 flex flex-col items-center justify-center px-4 py-16 animate-fade-in-up">
          {/* Headline */}
          <div className="text-center mb-16 max-w-2xl">
            <h1 className="text-3xl md:text-4xl font-bold text-foreground mb-4 leading-tight">
              Is this person a good match?
              <br />
              <span className="text-primary">Show us their code</span>{" "}
              and we'll tell you.
            </h1>
            <p className="text-muted-foreground text-sm font-mono">
              Anti-Soy reads GitHub repos so you don't have to guess.
            </p>
          </div>

          {/* Portal cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 w-full max-w-3xl">
            {/* Recruiter card */}
            <div className="relative flex flex-col gap-6 rounded bg-card border border-primary/40 p-8 hover:border-primary/70 transition-colors">
              {/* Icon */}
              <div className="flex items-center gap-3">
                <div className="h-10 w-10 rounded border border-primary/40 bg-primary/10 flex items-center justify-center text-primary">
                  <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                    <rect x="2" y="7" width="20" height="14" rx="2" />
                    <path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2" />
                    <line x1="12" y1="12" x2="12" y2="16" />
                    <line x1="10" y1="14" x2="14" y2="14" />
                  </svg>
                </div>
                <span className="text-primary font-bold uppercase tracking-widest text-sm">
                  Recruiter
                </span>
              </div>

              <p className="text-muted-foreground text-sm leading-relaxed flex-1">
                Evaluate candidates before the interview. Detect AI slop, expose weak fundamentals, get interview questions that actually probe depth.
              </p>

              <button
                onClick={() => navigate("/recruiter")}
                className="w-full bg-primary text-primary-foreground py-3 px-6 font-bold uppercase tracking-widest text-sm hover:bg-primary/90 active:scale-[0.98] transition-all"
              >
                I'm a Recruiter →
              </button>
            </div>

            {/* Hacker card */}
            <div className="relative flex flex-col gap-6 rounded bg-card border border-hacker/30 p-8 opacity-80">
              {/* Coming Soon badge */}
              <div className="absolute top-4 right-4">
                <span className="text-[10px] font-bold uppercase tracking-widest border border-hacker/50 text-hacker bg-hacker/10 px-2 py-0.5">
                  Coming Soon
                </span>
              </div>

              {/* Icon */}
              <div className="flex items-center gap-3">
                <div className="h-10 w-10 rounded border border-hacker/30 bg-hacker/10 flex items-center justify-center text-hacker">
                  <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="4 17 10 11 4 5" />
                    <line x1="12" y1="19" x2="20" y2="19" />
                  </svg>
                </div>
                <span className="text-hacker font-bold uppercase tracking-widest text-sm">
                  Hacker
                </span>
              </div>

              <p className="text-muted-foreground text-sm leading-relaxed flex-1">
                Evaluating a potential teammate? See if their GitHub backs up what they're claiming before you commit to building together.
              </p>

              <button
                disabled
                className="w-full border border-hacker/30 text-hacker/40 py-3 px-6 font-bold uppercase tracking-widest text-sm cursor-not-allowed"
                title="Coming soon"
              >
                I'm a Hacker →
              </button>
            </div>
          </div>
        </main>

        {/* Waitlist Section */}
        <div ref={waitlistRef} className="border-t border-border bg-card/30 py-16">
          <div className="container mx-auto px-4 flex flex-col items-center">
            <h2 className="text-2xl font-bold text-primary mb-8 uppercase tracking-widest">
              Join The Waitlist
            </h2>
            {status === "success" ? (
              <div className="p-3 rounded border border-success/50 bg-success/10 text-success text-sm">
                Thanks! You're on the list.
              </div>
            ) : (
              <form onSubmit={handleEmailSubmit} className="space-y-2 w-full max-w-md">
                <div className="flex gap-2">
                  <input
                    type="text"
                    required
                    placeholder="Name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    className="flex-1 bg-card/50 border border-border rounded px-4 py-2 text-sm focus:outline-none focus:border-primary transition-colors"
                  />
                  <input
                    type="email"
                    required
                    placeholder="Email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="flex-1 bg-card/50 border border-border rounded px-4 py-2 text-sm focus:outline-none focus:border-primary transition-colors"
                  />
                </div>
                <div className="flex gap-2">
                  <input
                    type="text"
                    placeholder="I am a founder/engineer/recruiter/student"
                    value={role}
                    onChange={(e) => setRole(e.target.value)}
                    className="flex-1 bg-card/50 border border-border rounded px-4 py-2 text-sm focus:outline-none focus:border-primary transition-colors"
                  />
                  <button
                    type="submit"
                    disabled={status === "submitting"}
                    className="bg-primary text-primary-foreground px-4 py-2 rounded text-sm font-bold hover:bg-primary/90 transition-colors disabled:opacity-50"
                  >
                    {status === "submitting" ? "..." : "Join"}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>

        {/* Footer */}
        <footer className="border-t border-border py-6">
          <p className="text-center text-xs text-muted-foreground uppercase tracking-widest font-mono">
            Built to filter signal from noise.
          </p>
        </footer>
      </div>
    </GridBackground>
  );
};

export default LandingPage;
