import { useNavigate } from "react-router-dom";
import { useState, useRef } from "react";
import { GridBackground } from "@/components/GridBackground";
import { Header } from "@/components/Header";
import { TerminalInput } from "@/components/TerminalInput";

const Index = () => {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("");
  const [status, setStatus] = useState<"idle" | "submitting" | "success" | "error">("idle");

  const handleSubmit = (repoUrl: string) => {
    // Basic validation for a GitHub URL
    if (repoUrl.includes("github.com")) {
      gtag("event", "analysis_started", {
        event_category: "engagement",
        repo_url: repoUrl,
      });
      navigate(`/repo/new?link=${encodeURIComponent(repoUrl)}`);
    } else {
      alert("Please enter a valid GitHub repository URL.");
    }
  };

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
    } catch (error) { setStatus("error"); }
  };

  const waitlistRef = useRef<HTMLDivElement>(null);

  const scrollToWaitlist = () => {
    waitlistRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  return (
    <GridBackground>
      <Header />

      <main className="container mx-auto px-4 py-12">
        <div className="flex flex-col items-center justify-center min-h-[70vh] animate-fade-in-up">
          <div className="text-center mb-12 max-w-2xl">
            <h1 className="text-3xl md:text-4xl font-bold text-foreground mb-4">
              Skip The Bullshit,
              <br />
              <span className="text-primary text-glow">Filter Out Soy Devs</span>
            </h1>
            <p className="text-muted-foreground">
               Paste a candidate's GitHub. Get an analysis of their code and specific interview questions that expose what they actually know
            </p>
          </div>

          <h2 className="text-xl md:text-2xl font-bold text-primary mb-6 uppercase tracking-widest">
            Try It Out <span className="text-muted-foreground"></span>
          </h2>

          <TerminalInput
            onSubmit={handleSubmit}
            placeholder="https://github.com/user/repository"
            examples={[
              { label: "To-Do List", url: "https://github.com/chaosium43/METROHACKS22" },
              { label: "GPT Wrapper", url: "https://github.com/EricJujianZou/PromptAssist" },
              { label: "Algorithm", url: "https://github.com/Skullheadx/The-Traveling-Salesman-Problem" },
            ]}
          />

          {/* Join Waitlist CTA */}
          <button
            onClick={scrollToWaitlist}
            className="mt-10 bg-primary text-primary-foreground px-8 py-3 rounded text-sm font-bold uppercase tracking-widest hover:bg-primary/90 transition-colors"
          >
            Join The Waitlist
          </button>
        </div>
      </main>

      {/* Waitlist Form Section */}
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

      <footer className="border-t border-border bg-card/30">
        <div className="container mx-auto px-4 py-6">
          <div className="flex items-center justify-between text-xs text-muted-foreground">


          </div>
        </div>
      </footer>
    </GridBackground>
  );
};

export default Index;
