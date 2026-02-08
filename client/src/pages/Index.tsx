import { useNavigate } from "react-router-dom";
import { GridBackground } from "@/components/GridBackground";
import { Header } from "@/components/Header";
import { TerminalInput } from "@/components/TerminalInput";

const Index = () => {
  const navigate = useNavigate();

  const handleSubmit = (repoUrl: string) => {
    // Basic validation for a GitHub URL
    if (repoUrl.includes("github.com")) {
      // Navigate to the analysis page, passing the repo URL as a query param
      navigate(`/repo/new?link=${encodeURIComponent(repoUrl)}`);
    } else {
      // Simple alert for now, could be a more elegant toast/notification
      alert("Please enter a valid GitHub repository URL.");
    }
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
              We help startup founders, who are struggling to find the right talent, filter out bad engineers quickly by scanning talents' project repos.
            </p>
          </div>

          <TerminalInput
            onSubmit={handleSubmit}
            placeholder="https://github.com/user/repository"
          />
        </div>
      </main>

      <footer className="border-t border-border bg-card/30 mt-auto">
        <div className="container mx-auto px-4 py-6">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            
            
          </div>
        </div>
      </footer>
    </GridBackground>
  );
};

export default Index;
