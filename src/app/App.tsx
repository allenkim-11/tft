import { ChampionList } from "./components/champion-list";

export default function App() {
  return (
    <div className="min-h-screen" style={{ backgroundColor: "var(--background)", fontFamily: "var(--font-family-roboto)" }}>
      <ChampionList />
    </div>
  );
}
