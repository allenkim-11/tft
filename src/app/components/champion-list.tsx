import { useState, useMemo } from "react";
import {
  CHAMPIONS,
  ROLES,
  ROLE_ICONS,
  type Role,
  type SortKey,
  type SortDirection,
  type Champion,
} from "./champion-data";
import { Search } from "lucide-react";
import { ImageWithFallback } from "./figma/ImageWithFallback";

const COST_COLORS: Record<number, string> = {
  1: "var(--cost-1)",
  2: "var(--cost-2)",
  3: "var(--cost-3)",
  4: "var(--cost-4)",
  5: "var(--cost-5)",
};

const COST_OPTIONS = Array.from(new Set(CHAMPIONS.map((champion) => champion.cost))).sort((a, b) => a - b);
const DEFAULT_COST = COST_OPTIONS.includes(1) ? 1 : (COST_OPTIONS[0] ?? 1);

const STAT_COLUMNS: { key: SortKey; label: string; shortLabel: string; korLabel: string }[] = [
  { key: "classPower", label: "Class Power", shortLabel: "CP", korLabel: "클래스 파워" },
  { key: "hp", label: "HP", shortLabel: "HP", korLabel: "체력" },
  { key: "armor", label: "Armor", shortLabel: "AR", korLabel: "방어력" },
  { key: "magicResist", label: "Magic Resist", shortLabel: "MR", korLabel: "마법 저항력" },
  { key: "damage", label: "Damage", shortLabel: "DMG", korLabel: "공격력" },
  { key: "attackSpeed", label: "Attack Speed", shortLabel: "AS", korLabel: "공격 속도" },
  { key: "range", label: "Range", shortLabel: "RNG", korLabel: "사거리" },
  { key: "mana", label: "Mana", shortLabel: "Mana", korLabel: "마나" },
  { key: "initialMana", label: "Initial Mana", shortLabel: "I.Mana", korLabel: "초기 마나" },
];

function Tooltip({ text, children }: { text: string; children: React.ReactNode }) {
  return (
    <span className="relative group/tip inline-flex items-center justify-center">
      {children}
      <span
        className="pointer-events-none absolute left-1/2 -translate-x-1/2 top-full mt-[6px] flex flex-col items-center opacity-0 group-hover/tip:opacity-100 transition-opacity duration-150 z-50"
      >
        <svg
          width="13"
          height="8"
          viewBox="0 0 13 8"
          fill="none"
          className="block -mb-px"
        >
          <path d="M6.5 0L13 8H0L6.5 0Z" fill="#000" />
        </svg>
        <span
          className="px-3 py-2 rounded whitespace-nowrap"
          style={{
            backgroundColor: "#000",
            color: "#fff",
            fontSize: "12px",
            fontFamily: "var(--font-family-roboto)",
            fontWeight: "var(--font-weight-normal)",
            lineHeight: "16px",
          }}
        >
          {text}
        </span>
      </span>
    </span>
  );
}

function StatBar({ value, max }: { value: number; max: number }) {
  const pct = Math.min((value / max) * 100, 100);
  return (
    <div className="w-full rounded-sm h-[3px] mt-0.5" style={{ backgroundColor: "var(--bar-bg)" }}>
      <div
        className="h-full rounded-sm transition-all duration-300"
        style={{ width: `${pct}%`, backgroundColor: "var(--bar-fill)" }}
      />
    </div>
  );
}

export function ChampionList() {
  const [selectedRole, setSelectedRole] = useState<Role>("All");
  const [selectedCost, setSelectedCost] = useState<number>(DEFAULT_COST);
  const [searchQuery, setSearchQuery] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("classPower");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
  const sortLabel = sortKey === "name"
    ? "Champion"
    : (STAT_COLUMNS.find((col) => col.key === sortKey)?.shortLabel ?? String(sortKey));

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDirection((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDirection("desc");
    }
  };

  const filtered = useMemo(() => {
    let list = CHAMPIONS;
    list = list.filter((c) => c.cost === selectedCost);

    if (selectedRole !== "All") {
      list = list.filter((c) => c.role === selectedRole);
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      list = list.filter(
        (c) =>
          c.name.toLowerCase().includes(q) ||
          c.traits.some((t) => t.toLowerCase().includes(q))
      );
    }
    return [...list].sort((a, b) => {
      let va: number | null, vb: number | null;
      if (sortKey === "name") {
        return sortDirection === "asc"
          ? a.name.localeCompare(b.name)
          : b.name.localeCompare(a.name);
      } else if (sortKey === "cost") {
        va = a.cost;
        vb = b.cost;
      } else {
        va = a.stats[sortKey];
        vb = b.stats[sortKey];
      }
      const numA = va ?? 0;
      const numB = vb ?? 0;
      return sortDirection === "asc" ? numA - numB : numB - numA;
    });
  }, [selectedCost, selectedRole, searchQuery, sortKey, sortDirection]);

  const roleCount = useMemo(() => {
    const counts: Record<string, number> = { All: CHAMPIONS.length };
    CHAMPIONS.forEach((c) => {
      counts[c.role] = (counts[c.role] || 0) + 1;
    });
    return counts;
  }, []);

  return (
    <div style={{ fontFamily: "var(--font-family-roboto)" }}>
      <div className="max-w-[1080px] mx-auto px-3 py-4">
        {/* Role Filter Tabs - styled like OP.GG tabs */}
        <div
          className="flex items-start p-1 rounded-md mb-3"
          style={{ backgroundColor: "var(--card)" }}
        >
          {ROLES.map((role) => {
            const isActive = selectedRole === role;
            return (
              <button
                key={role}
                onClick={() => setSelectedRole(role)}
                className="flex-1 flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-md cursor-pointer transition-colors relative"
                style={{
                  fontSize: "var(--text-base)",
                  fontWeight: isActive ? "var(--font-weight-bold)" : "var(--font-weight-normal)",
                  fontFamily: "var(--font-family-roboto)",
                  backgroundColor: isActive ? "var(--primary)" : "transparent",
                  color: isActive ? "var(--primary-foreground)" : "var(--foreground)",
                  lineHeight: "20px",
                }}
              >
                <span>{ROLE_ICONS[role] ?? "🏷️"}</span>
                <span>{role}</span>
              </button>
            );
          })}
        </div>

        {/* Cost Filter Tabs */}
        <div
          className="flex items-start p-1 rounded-md mb-3"
          style={{ backgroundColor: "var(--card)" }}
        >
          {COST_OPTIONS.map((cost) => {
            const isActive = selectedCost === cost;
            return (
              <button
                key={cost}
                onClick={() => setSelectedCost(cost)}
                className="flex-1 flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-md cursor-pointer transition-colors relative"
                style={{
                  fontSize: "var(--text-base)",
                  fontWeight: isActive ? "var(--font-weight-bold)" : "var(--font-weight-normal)",
                  fontFamily: "var(--font-family-roboto)",
                  backgroundColor: isActive ? "var(--primary)" : "transparent",
                  color: isActive ? "var(--primary-foreground)" : "var(--foreground)",
                  lineHeight: "20px",
                }}
                title={`Cost ${cost}`}
              >
                <span
                  className="inline-flex items-center justify-center w-5 h-5 rounded"
                  style={{
                    backgroundColor: COST_COLORS[cost] || "var(--cost-1)",
                    color: "#fff",
                    fontSize: "11px",
                    fontWeight: "var(--font-weight-bold)",
                  }}
                >
                  {cost}
                </span>
                <span>Cost {cost}</span>
              </button>
            );
          })}
        </div>

        {/* Search & Info Bar */}
        <div
          className="flex items-center justify-between p-1 rounded-md mb-3"
          style={{ backgroundColor: "var(--card)" }}
        >
          <div
            className="px-3 py-2 rounded-md"
            style={{ fontSize: "12px", color: "var(--text-secondary)", fontFamily: "var(--font-family-roboto)", lineHeight: "16px" }}
          >
            Cost {selectedCost} | Sort: {sortLabel} {sortDirection === "desc" ? "Desc" : "Asc"} | Showing {filtered.length} champion{filtered.length !== 1 ? "s" : ""}
          </div>
          <div
            className="flex items-center gap-4 px-4 py-2 rounded-md w-[240px]"
            style={{ backgroundColor: "var(--background)" }}
          >
            <input
              type="text"
              placeholder="Search a Champion"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="flex-1 bg-transparent outline-none min-w-0"
              style={{
                fontSize: "var(--text-base)",
                fontFamily: "var(--font-family-roboto)",
                color: "var(--foreground)",
                lineHeight: "20px",
              }}
            />
            <Search size={16} style={{ color: "var(--text-muted-opgg)", flexShrink: 0 }} />
          </div>
        </div>

        {/* Table */}
        <div className="rounded-md overflow-hidden" style={{ backgroundColor: "var(--card)" }}>
          <div className="overflow-x-auto">
            <table className="w-full" style={{ borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ backgroundColor: "var(--secondary)" }}>
                  <th
                    className="text-left px-3 py-2 cursor-pointer select-none whitespace-nowrap"
                    onClick={() => handleSort("name")}
                    style={{
                      fontSize: "12px",
                      fontWeight: sortKey === "name" ? "var(--font-weight-bold)" : "var(--font-weight-normal)",
                      color: sortKey === "name" ? "var(--foreground)" : "var(--text-muted-opgg)",
                      fontFamily: "var(--font-family-roboto)",
                      lineHeight: "16px",
                      boxShadow: sortKey === "name" ? "inset 0 -3px 0 var(--primary)" : "none",
                    }}
                  >
                    <Tooltip text="챔피언">
                      <span className="inline-flex items-center">Champion</span>
                    </Tooltip>
                  </th>
                  {STAT_COLUMNS.map((col) => (
                    <th
                      key={col.key}
                      className="text-center px-2 py-2 cursor-pointer select-none whitespace-nowrap"
                      onClick={() => handleSort(col.key)}
                      style={{
                        fontSize: "12px",
                        fontWeight: sortKey === col.key ? "var(--font-weight-bold)" : "var(--font-weight-normal)",
                        color: sortKey === col.key ? "var(--foreground)" : "var(--text-muted-opgg)",
                        fontFamily: "var(--font-family-roboto)",
                        lineHeight: "16px",
                        boxShadow: sortKey === col.key ? "inset 0 -3px 0 var(--primary)" : "none",
                      }}
                    >
                      <Tooltip text={col.korLabel}>
                        <span className="inline-flex items-center justify-center">{col.shortLabel}</span>
                      </Tooltip>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.map((champ) => (
                  <ChampionRow key={champ.id} champion={champ} />
                ))}
                {filtered.length === 0 && (
                  <tr>
                    <td
                      colSpan={STAT_COLUMNS.length + 1}
                      className="text-center py-12"
                      style={{ fontSize: "var(--text-base)", color: "var(--text-muted-opgg)", fontFamily: "var(--font-family-roboto)" }}
                    >
                      No champions found
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

function ChampionRow({ champion }: { champion: Champion }) {
  const costColor = COST_COLORS[champion.cost] || "var(--cost-1)";

  const statValue = (val: number | null) => {
    if (val === null) return "—";
    return val;
  };

  const statMaxes: Record<string, number> = {
    classPower: 100,
    hp: 1200,
    armor: 80,
    magicResist: 80,
    damage: 100,
    attackSpeed: 1.0,
    range: 5,
    mana: 160,
    initialMana: 60,
  };

  return (
    <tr
      className="border-t transition-colors"
      style={{ borderColor: "var(--border)" }}
      onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = "var(--secondary)")}
      onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = "")}
    >
      {/* Champion Name + Icon */}
      <td className="px-3 py-2">
        <div className="flex items-center gap-2.5">
          {/* Champion image with cost-colored border like OP.GG */}
          <div
            className="w-[36px] h-[36px] rounded-lg overflow-hidden flex-shrink-0"
            style={{ border: `2px solid ${costColor}` }}
          >
            <ImageWithFallback
              src={champion.imageUrl}
              alt={champion.name}
              className="w-full h-full object-cover"
            />
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <span
                style={{
                  fontSize: "12px",
                  fontWeight: "var(--font-weight-bold)",
                  color: "var(--foreground)",
                  fontFamily: "var(--font-family-roboto)",
                  lineHeight: "16px",
                }}
              >
                {champion.name}
              </span>
            </div>
            <div className="flex gap-1 flex-wrap mt-0.5">
              {champion.traits.map((trait) => (
                <span
                  key={trait}
                  className="px-1.5 rounded-xl"
                  style={{
                    fontSize: "var(--text-caption)",
                    fontFamily: "var(--font-family-roboto)",
                    backgroundColor: "var(--background)",
                    color: "var(--text-muted-opgg)",
                    fontWeight: "var(--font-weight-normal)",
                    lineHeight: "18px",
                  }}
                >
                  {trait}
                </span>
              ))}
            </div>
          </div>
        </div>
      </td>

      {/* Stats */}
      {STAT_COLUMNS.map((col) => {
        const rawVal = champion.stats[col.key as keyof typeof champion.stats];
        const numVal = typeof rawVal === "number" ? rawVal : 0;
        const maxVal = statMaxes[col.key] || 100;

        return (
          <td key={col.key} className="text-center px-2 py-2" style={{ minWidth: 55 }}>
            <div
              style={{
                fontSize: "12px",
                fontWeight: "var(--font-weight-normal)",
                color: "var(--text-secondary)",
                fontFamily: "var(--font-family-roboto)",
                lineHeight: "16px",
              }}
            >
              {statValue(rawVal as number | null)}
            </div>
            {rawVal !== null && (
              <StatBar value={numVal} max={maxVal} />
            )}
          </td>
        );
      })}
    </tr>
  );
}
