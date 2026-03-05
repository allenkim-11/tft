import { useMemo, useState } from "react";
import { Search } from "lucide-react";
import tankScoringRaw from "../../../tank_scoring_results.json";
import dealerScoringRaw from "../../../tft_dealer_scoring_results.json";

type ResultPayload<T> = {
  total: number;
  results: T[];
};

type TankRow = {
  cost: number;
  name: string;
  apiName: string;
  role: string;
  score: number;
  efficiencyScore?: number;
  powerScore?: number;
  baseEHP: number;
  avgMit: number;
  mps: number;
  tcast: number;
  readiness: number;
  damage2: number;
  rawTagDamage2?: number;
  totalCastDamage2?: number;
  targetCountUsed?: number;
  mechanismBonus2?: number;
  shield2: number;
  heal2: number;
};

type DealerRow = {
  cost: number;
  name: string;
  apiName: string;
  role: string;
  score: number;
  efficiencyScore?: number;
  powerScore?: number;
  autoDPS: number;
  spellDPS_hint: number;
  skillDamage2: number;
  rawTagDamage2?: number;
  totalCastDamage2?: number;
  targetCountUsed?: number;
  mechanismBonus2?: number;
  tFirstCast: number;
  readiness: number;
};

type ViewMode = "tank" | "dealer";
type SortKey =
  | "role"
  | "cost"
  | "score"
  | "baseEHP"
  | "shield2"
  | "heal2"
  | "damage2"
  | "readiness"
  | "autoDPS"
  | "spellDPS_hint"
  | "skillDamage2"
  | "tFirstCast";
type SortDirection = "asc" | "desc";

const TANK_DATA = tankScoringRaw as ResultPayload<TankRow>;
const DEALER_DATA = dealerScoringRaw as ResultPayload<DealerRow>;
const ALLOWED_COSTS = new Set([1, 2, 3, 4, 5, 7]);

function formatNum(value: number, digits = 2) {
  return Number.isFinite(value) ? value.toFixed(digits) : "-";
}

const FORMULA = {
  tankScore:
    "PowerScore = 0.35*Efficiency + 0.65*CostAnchor\nEfficiency = 100*(0.45*BaseEHP_N + 0.30*Defense_N + 0.15*Cast_N + 0.10*Offense_N)\nFinal score applies monotonic cost-median correction.",
  dealerScore:
    "PowerScore = 0.35*Efficiency + 0.65*CostAnchor\nEfficiency = 100*(0.40*Sustain_N + 0.30*Burst_N + 0.20*Cast_N + 0.10*Auto_N)\nFinal score applies monotonic cost-median correction.",
  tankBaseEhp: "BaseEHP = HP * ((1 + Armor/100 + 1 + MR/100) / 2)",
  tankDamage2:
    "Damage2(single-target) = (BaseDamage2 * Projectile * Repeat * Summon + MechanismBonus) / TargetCount",
  tankShield2:
    "Shield2 = parsed 2-star shield amount from spell variables/text (single-cast equivalent).",
  tankHeal2:
    "Heal2 = parsed 2-star heal amount from spell variables/text (single-cast equivalent).",
  readiness:
    "Readiness = W / (W + t_first_cast), where t_first_cast = (Mana-InitialMana) / MPS",
  autoDps: "AutoDPS = AD * AttackSpeed * (1 + CritChance * (CritMultiplier - 1))",
  spellDps: "SpellDPS_hint = SkillDamage2 * (MPS / Mana) * Readiness",
  skillDmg:
    "SkillDamage2 = singleTargetEquiv2 from mechanism-aware conversion (projectile/repeat/summon/target + buff bonuses)",
  firstCast: "tFirstCast = (Mana - InitialMana) / MPS",
};

export function ScoringResultsView() {
  const [viewMode, setViewMode] = useState<ViewMode>("tank");
  const [searchQuery, setSearchQuery] = useState("");
  const [roleFilter, setRoleFilter] = useState("All");
  const [costFilter, setCostFilter] = useState("All");
  const [sortKey, setSortKey] = useState<SortKey>("score");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");

  const activePayload = viewMode === "tank" ? TANK_DATA : DEALER_DATA;
  const activeRows = useMemo(
    () =>
      activePayload.results.filter((row) =>
        ALLOWED_COSTS.has(row.cost)
      ),
    [activePayload.results]
  );

  const roleOptions = useMemo(
    () => ["All", ...Array.from(new Set(activeRows.map((row) => row.role))).sort()],
    [activeRows]
  );

  const costOptions = useMemo(
    () => ["All", ...Array.from(new Set(activeRows.map((row) => String(row.cost)))).sort((a, b) => Number(a) - Number(b))],
    [activeRows]
  );

  const filteredRows = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    const rows = activeRows.filter((row) => {
      if (roleFilter !== "All" && row.role !== roleFilter) return false;
      if (costFilter !== "All" && String(row.cost) !== costFilter) return false;
      if (!query) return true;
      return row.name.toLowerCase().includes(query) || row.apiName.toLowerCase().includes(query);
    });
    return [...rows].sort((a, b) => {
      if (sortKey === "role") {
        const result = a.role.localeCompare(b.role);
        return sortDirection === "asc" ? result : -result;
      }
      const aVal =
        sortKey === "cost"
          ? a.cost
          : Number((a as Record<string, unknown>)[sortKey] ?? 0);
      const bVal =
        sortKey === "cost"
          ? b.cost
          : Number((b as Record<string, unknown>)[sortKey] ?? 0);
      const result = aVal - bVal;
      return sortDirection === "asc" ? result : -result;
    });
  }, [activeRows, costFilter, roleFilter, searchQuery, sortDirection, sortKey]);

  const averageScore = useMemo(() => {
    if (!filteredRows.length) return 0;
    return filteredRows.reduce((sum, row) => sum + row.score, 0) / filteredRows.length;
  }, [filteredRows]);

  const topScore = filteredRows[0]?.score ?? 0;

  const switchView = (next: ViewMode) => {
    setViewMode(next);
    setSearchQuery("");
    setRoleFilter("All");
    setCostFilter("All");
    setSortKey("score");
    setSortDirection("desc");
  };

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDirection((prev) => (prev === "asc" ? "desc" : "asc"));
      return;
    }
    setSortKey(key);
    setSortDirection(key === "score" ? "desc" : "asc");
  };

  return (
    <div style={{ fontFamily: "var(--font-family-roboto)" }}>
      <div className="max-w-[1080px] mx-auto px-3 py-4">
        <div className="flex items-start p-1 rounded-md mb-3" style={{ backgroundColor: "var(--card)" }}>
          <button
            onClick={() => switchView("tank")}
            className="flex-1 px-4 py-2.5 rounded-md cursor-pointer transition-colors"
            style={{
              fontSize: "var(--text-base)",
              fontWeight: viewMode === "tank" ? "var(--font-weight-bold)" : "var(--font-weight-normal)",
              backgroundColor: viewMode === "tank" ? "var(--primary)" : "transparent",
              color: viewMode === "tank" ? "var(--primary-foreground)" : "var(--foreground)",
            }}
          >
            Tank Raw Data
          </button>
          <button
            onClick={() => switchView("dealer")}
            className="flex-1 px-4 py-2.5 rounded-md cursor-pointer transition-colors"
            style={{
              fontSize: "var(--text-base)",
              fontWeight: viewMode === "dealer" ? "var(--font-weight-bold)" : "var(--font-weight-normal)",
              backgroundColor: viewMode === "dealer" ? "var(--primary)" : "transparent",
              color: viewMode === "dealer" ? "var(--primary-foreground)" : "var(--foreground)",
            }}
          >
            Dealer Raw Data
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-3">
          <SummaryCard label="Rows" value={`${filteredRows.length} / ${activeRows.length}`} />
          <SummaryCard label="Top Score" value={formatNum(topScore)} />
          <SummaryCard label="Average Score" value={formatNum(averageScore)} />
        </div>

        <div className="rounded-md p-3 mb-3" style={{ backgroundColor: "var(--card)" }}>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
            <div className="md:col-span-2">
              <div className="flex items-center gap-3 px-3 py-2 rounded-md" style={{ backgroundColor: "var(--background)" }}>
                <Search size={16} style={{ color: "var(--text-muted-opgg)", flexShrink: 0 }} />
                <input
                  type="text"
                  value={searchQuery}
                  placeholder="Search by name or apiName"
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="flex-1 bg-transparent outline-none min-w-0"
                  style={{ color: "var(--foreground)", fontSize: "var(--text-base)" }}
                />
              </div>
            </div>
            <div>
              <select
                value={roleFilter}
                onChange={(e) => setRoleFilter(e.target.value)}
                className="w-full px-3 py-2 rounded-md border outline-none"
                style={{
                  backgroundColor: "var(--background)",
                  borderColor: "var(--border)",
                  color: "var(--foreground)",
                  fontSize: "var(--text-base)",
                }}
              >
                {roleOptions.map((role) => (
                  <option key={role} value={role}>
                    {role === "All" ? "All Roles" : role}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <select
                value={costFilter}
                onChange={(e) => setCostFilter(e.target.value)}
                className="w-full px-3 py-2 rounded-md border outline-none"
                style={{
                  backgroundColor: "var(--background)",
                  borderColor: "var(--border)",
                  color: "var(--foreground)",
                  fontSize: "var(--text-base)",
                }}
              >
                {costOptions.map((cost) => (
                  <option key={cost} value={cost}>
                    {cost === "All" ? "All Costs" : `Cost ${cost}`}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        <div className="rounded-md overflow-hidden" style={{ backgroundColor: "var(--card)" }}>
          <div className="overflow-x-auto">
            {viewMode === "tank" ? (
              <TankTable
                rows={filteredRows as TankRow[]}
                sortKey={sortKey}
                sortDirection={sortDirection}
                onSort={handleSort}
              />
            ) : (
              <DealerTable
                rows={filteredRows as DealerRow[]}
                sortKey={sortKey}
                sortDirection={sortDirection}
                onSort={handleSort}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function SummaryCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md p-3" style={{ backgroundColor: "var(--card)" }}>
      <div style={{ fontSize: "12px", color: "var(--text-muted-opgg)" }}>{label}</div>
      <div style={{ fontSize: "18px", fontWeight: "var(--font-weight-bold)", color: "var(--foreground)" }}>{value}</div>
    </div>
  );
}

function TankTable({
  rows,
  sortKey,
  sortDirection,
  onSort,
}: {
  rows: TankRow[];
  sortKey: SortKey;
  sortDirection: SortDirection;
  onSort: (key: SortKey) => void;
}) {
  return (
    <table className="w-full" style={{ borderCollapse: "collapse" }}>
      <thead>
        <tr style={{ backgroundColor: "var(--secondary)" }}>
          <HeaderCell label="#" />
          <HeaderCell label="Champion" align="left" />
          <SortableHeaderCell
            label="Role"
            active={sortKey === "role"}
            direction={sortDirection}
            onClick={() => onSort("role")}
          />
          <SortableHeaderCell
            label="Cost"
            active={sortKey === "cost"}
            direction={sortDirection}
            onClick={() => onSort("cost")}
          />
          <SortableHeaderCell
            label="Score"
            active={sortKey === "score"}
            direction={sortDirection}
            onClick={() => onSort("score")}
            formula={FORMULA.tankScore}
          />
          <SortableHeaderCell
            label="BaseEHP"
            active={sortKey === "baseEHP"}
            direction={sortDirection}
            onClick={() => onSort("baseEHP")}
            formula={FORMULA.tankBaseEhp}
          />
          <SortableHeaderCell
            label="Shield2"
            active={sortKey === "shield2"}
            direction={sortDirection}
            onClick={() => onSort("shield2")}
            formula={FORMULA.tankShield2}
          />
          <SortableHeaderCell
            label="Heal2"
            active={sortKey === "heal2"}
            direction={sortDirection}
            onClick={() => onSort("heal2")}
            formula={FORMULA.tankHeal2}
          />
          <SortableHeaderCell
            label="Damage2"
            active={sortKey === "damage2"}
            direction={sortDirection}
            onClick={() => onSort("damage2")}
            formula={FORMULA.tankDamage2}
          />
          <SortableHeaderCell
            label="Readiness"
            active={sortKey === "readiness"}
            direction={sortDirection}
            onClick={() => onSort("readiness")}
            formula={FORMULA.readiness}
          />
        </tr>
      </thead>
      <tbody>
        {rows.map((row, index) => (
          <tr key={row.apiName} className="border-t" style={{ borderColor: "var(--border)" }}>
            <BodyCell value={String(index + 1)} />
            <BodyCell value={row.name} align="left" />
            <BodyCell value={row.role} />
            <BodyCell value={String(row.cost)} />
            <BodyCell
              value={formatNum(row.score)}
              tooltip={
                `Score=${formatNum(row.score)}\n` +
                `Power=${formatNum(row.powerScore ?? row.score)} / Efficiency=${formatNum(row.efficiencyScore ?? row.score)}\n\n` +
                FORMULA.tankScore
              }
            />
            <BodyCell value={formatNum(row.baseEHP)} />
            <BodyCell value={formatNum(row.shield2)} />
            <BodyCell value={formatNum(row.heal2)} />
            <BodyCell value={formatNum(row.damage2)} />
            <BodyCell value={formatNum(row.readiness, 3)} />
          </tr>
        ))}
        {!rows.length && (
          <tr>
            <td
              colSpan={10}
              className="text-center py-12"
              style={{ fontSize: "var(--text-base)", color: "var(--text-muted-opgg)" }}
            >
              No rows found
            </td>
          </tr>
        )}
      </tbody>
    </table>
  );
}

function DealerTable({
  rows,
  sortKey,
  sortDirection,
  onSort,
}: {
  rows: DealerRow[];
  sortKey: SortKey;
  sortDirection: SortDirection;
  onSort: (key: SortKey) => void;
}) {
  return (
    <table className="w-full" style={{ borderCollapse: "collapse" }}>
      <thead>
        <tr style={{ backgroundColor: "var(--secondary)" }}>
          <HeaderCell label="#" />
          <HeaderCell label="Champion" align="left" />
          <SortableHeaderCell
            label="Role"
            active={sortKey === "role"}
            direction={sortDirection}
            onClick={() => onSort("role")}
          />
          <SortableHeaderCell
            label="Cost"
            active={sortKey === "cost"}
            direction={sortDirection}
            onClick={() => onSort("cost")}
          />
          <SortableHeaderCell
            label="Score"
            active={sortKey === "score"}
            direction={sortDirection}
            onClick={() => onSort("score")}
            formula={FORMULA.dealerScore}
          />
          <SortableHeaderCell
            label="AutoDPS"
            active={sortKey === "autoDPS"}
            direction={sortDirection}
            onClick={() => onSort("autoDPS")}
            formula={FORMULA.autoDps}
          />
          <SortableHeaderCell
            label="SpellDPS"
            active={sortKey === "spellDPS_hint"}
            direction={sortDirection}
            onClick={() => onSort("spellDPS_hint")}
            formula={FORMULA.spellDps}
          />
          <SortableHeaderCell
            label="SkillDmg2"
            active={sortKey === "skillDamage2"}
            direction={sortDirection}
            onClick={() => onSort("skillDamage2")}
            formula={FORMULA.skillDmg}
          />
          <SortableHeaderCell
            label="FirstCast(s)"
            active={sortKey === "tFirstCast"}
            direction={sortDirection}
            onClick={() => onSort("tFirstCast")}
            formula={FORMULA.firstCast}
          />
          <SortableHeaderCell
            label="Readiness"
            active={sortKey === "readiness"}
            direction={sortDirection}
            onClick={() => onSort("readiness")}
            formula={FORMULA.readiness}
          />
        </tr>
      </thead>
      <tbody>
        {rows.map((row, index) => (
          <tr key={row.apiName} className="border-t" style={{ borderColor: "var(--border)" }}>
            <BodyCell value={String(index + 1)} />
            <BodyCell value={row.name} align="left" />
            <BodyCell value={row.role} />
            <BodyCell value={String(row.cost)} />
            <BodyCell
              value={formatNum(row.score)}
              tooltip={
                `Score=${formatNum(row.score)}\n` +
                `Power=${formatNum(row.powerScore ?? row.score)} / Efficiency=${formatNum(row.efficiencyScore ?? row.score)}\n\n` +
                FORMULA.dealerScore
              }
            />
            <BodyCell value={formatNum(row.autoDPS)} tooltip={FORMULA.autoDps} />
            <BodyCell value={formatNum(row.spellDPS_hint)} tooltip={FORMULA.spellDps} />
            <BodyCell
              value={formatNum(row.skillDamage2)}
              tooltip={
                `SkillDamage2=${formatNum(row.skillDamage2)}\n` +
                `RawTag=${formatNum(row.rawTagDamage2 ?? 0)} / TotalCast=${formatNum(row.totalCastDamage2 ?? 0)} / Target=${formatNum(row.targetCountUsed ?? 1)} / Bonus=${formatNum(row.mechanismBonus2 ?? 0)}\n\n` +
                FORMULA.skillDmg
              }
            />
            <BodyCell value={formatNum(row.tFirstCast)} />
            <BodyCell value={formatNum(row.readiness, 3)} />
          </tr>
        ))}
        {!rows.length && (
          <tr>
            <td
              colSpan={10}
              className="text-center py-12"
              style={{ fontSize: "var(--text-base)", color: "var(--text-muted-opgg)" }}
            >
              No rows found
            </td>
          </tr>
        )}
      </tbody>
    </table>
  );
}

function HeaderCell({ label, align = "center" }: { label: string; align?: "left" | "center" }) {
  return (
    <th
      className={`${align === "left" ? "text-left" : "text-center"} px-3 py-2 whitespace-nowrap`}
      style={{
        fontSize: "12px",
        fontWeight: "var(--font-weight-bold)",
        color: "var(--text-secondary)",
      }}
    >
      {label}
    </th>
  );
}

function SortableHeaderCell({
  label,
  active,
  direction,
  onClick,
  formula,
}: {
  label: string;
  active: boolean;
  direction: SortDirection;
  onClick: () => void;
  formula?: string;
}) {
  return (
    <th
      onClick={onClick}
      className="text-center px-3 py-2 whitespace-nowrap cursor-pointer select-none"
      title={formula}
      style={{
        fontSize: "12px",
        fontWeight: active ? "var(--font-weight-bold)" : "var(--font-weight-normal)",
        color: active ? "var(--foreground)" : "var(--text-muted-opgg)",
        boxShadow: active ? "inset 0 -3px 0 var(--primary)" : "none",
      }}
    >
      {label} {active ? (direction === "asc" ? "\u25B2" : "\u25BC") : ""}
    </th>
  );
}

function BodyCell({
  value,
  align = "center",
  tooltip,
}: {
  value: string;
  align?: "left" | "center";
  tooltip?: string;
}) {
  return (
    <td
      className={`${align === "left" ? "text-left" : "text-center"} px-3 py-2 whitespace-nowrap`}
      title={tooltip}
      style={{
        fontSize: "12px",
        color: "var(--foreground)",
      }}
    >
      {value}
    </td>
  );
}
