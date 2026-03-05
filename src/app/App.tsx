import { useState } from "react";
import { ChampionList } from "./components/champion-list";
import { ScoringResultsView } from "./components/scoring-results-view";

export default function App() {
  const [page, setPage] = useState<"champions" | "scores">("champions");

  return (
    <div className="min-h-screen" style={{ backgroundColor: "var(--background)", fontFamily: "var(--font-family-roboto)" }}>
      <div className="max-w-[1080px] mx-auto px-3 pt-4">
        <div className="flex items-start p-1 rounded-md mb-3" style={{ backgroundColor: "var(--card)" }}>
          <button
            onClick={() => setPage("champions")}
            className="flex-1 px-4 py-2.5 rounded-md cursor-pointer transition-colors"
            style={{
              fontSize: "var(--text-base)",
              fontWeight: page === "champions" ? "var(--font-weight-bold)" : "var(--font-weight-normal)",
              backgroundColor: page === "champions" ? "var(--primary)" : "transparent",
              color: page === "champions" ? "var(--primary-foreground)" : "var(--foreground)",
            }}
          >
            Champion Index
          </button>
          <button
            onClick={() => setPage("scores")}
            className="flex-1 px-4 py-2.5 rounded-md cursor-pointer transition-colors"
            style={{
              fontSize: "var(--text-base)",
              fontWeight: page === "scores" ? "var(--font-weight-bold)" : "var(--font-weight-normal)",
              backgroundColor: page === "scores" ? "var(--primary)" : "transparent",
              color: page === "scores" ? "var(--primary-foreground)" : "var(--foreground)",
            }}
          >
            Raw Data
          </button>
        </div>
      </div>

      {page === "champions" ? <ChampionList /> : <ScoringResultsView />}
    </div>
  );
}

