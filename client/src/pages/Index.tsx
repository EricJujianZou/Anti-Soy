import { useNavigate } from "react-router-dom";
// import { GridBackground } from "@/components/GridBackground";
import { Header } from "@/components/Header";
import { TerminalInput } from "@/components/TerminalInput";
import { type PriorityKey } from "@/services/api";

const Index = () => {
  const navigate = useNavigate();

  const handleSubmit = (repoUrl: string, priorities: PriorityKey[]) => {
    // Basic validation for a GitHub URL
    if (repoUrl.includes("github.com")) {
      gtag("event", "analysis_started", {
        event_category: "engagement",
        repo_url: repoUrl,
      });
      const params = new URLSearchParams({
        link: repoUrl,
        priorities: priorities.join(","),
      });
      navigate(`/repo/new?${params.toString()}`);
    } else {
      alert("Please enter a valid GitHub repository URL.");
    }
  };

  return (
    <div>
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
            onSecondaryAction={(priorities) => {
              navigate(`/upload?priorities=${priorities.join(",")}`);
            }}
          />
        </div>
      </main>
    </div>
  );
};

export default Index;
