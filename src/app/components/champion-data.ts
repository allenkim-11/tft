import championsData from "../data/tft16_champion_weight.json";
import tankScoringRaw from "../../../tank_scoring_results.json";
import dealerScoringRaw from "../../../tft_dealer_scoring_results.json";

export interface ChampionStats {
  armor: number | null;
  attackSpeed: number | null;
  classPower: number | null;
  damage: number | null;
  hp: number | null;
  initialMana: number | null;
  magicResist: number | null;
  mana: number | null;
  range: number | null;
}

export interface Champion {
  id: string;
  apiName: string;
  name: string;
  cost: number;
  role: string;
  detailRole: string | null;
  isHybridRole: boolean;
  traits: string[];
  stats: ChampionStats;
  imageUrl: string;
}

type ScoreRow = {
  apiName: string;
  score: number;
};

type ResultPayload = {
  total: number;
  results: ScoreRow[];
};

export type Role = string;

const ROLE_AD = "AD 딜러";
const ROLE_AP = "AP 딜러";
const ROLE_TANK = "Tank";

const TANK_DATA = tankScoringRaw as ResultPayload;
const DEALER_DATA = dealerScoringRaw as ResultPayload;
const RAW_SCORE_BY_API = new Map<string, number>();

for (const row of [...TANK_DATA.results, ...DEALER_DATA.results]) {
  if (typeof row.score === "number" && Number.isFinite(row.score)) {
    RAW_SCORE_BY_API.set(row.apiName, row.score);
  }
}

function normalizeRole(role: string | null | undefined, detailRole: string | null | undefined): string {
  const rawRole = (role ?? "").trim().toLowerCase();
  const rawDetail = (detailRole ?? "").trim().toLowerCase();

  if (rawDetail.includes("tank") || rawRole.includes("tank")) {
    return ROLE_TANK;
  }
  if (rawDetail.startsWith("ap") || rawRole.startsWith("ap")) {
    return ROLE_AP;
  }
  if (rawDetail.startsWith("ad") || rawDetail.startsWith("h") || rawRole.startsWith("ad")) {
    return ROLE_AD;
  }
  return ROLE_TANK;
}

export const CHAMPIONS: Champion[] = (championsData as Champion[]).map((champion) => {
  const rawScore = RAW_SCORE_BY_API.get(champion.apiName);
  const scoreAsCp = typeof rawScore === "number" ? Number(rawScore.toFixed(2)) : champion.stats.classPower;

  return {
    ...champion,
    role: normalizeRole(champion.role, champion.detailRole),
    stats: {
      ...champion.stats,
      classPower: scoreAsCp,
    },
  };
});

const roleSet = new Set(CHAMPIONS.map((champion) => champion.role));
const preferredRoleOrder = [ROLE_AD, ROLE_AP, ROLE_TANK];

export const ROLES: Role[] = [
  "All",
  ...preferredRoleOrder.filter((role) => roleSet.has(role)),
  ...Array.from(roleSet).filter((role) => !preferredRoleOrder.includes(role)),
];

export const ROLE_ICONS: Record<string, string> = {
  All: "\uD83C\uDFF7\uFE0F",
  [ROLE_AD]: "\uD83D\uDDE1\uFE0F",
  [ROLE_AP]: "\uD83D\uDD2E",
  [ROLE_TANK]: "\uD83D\uDEE1\uFE0F",
};

export type SortKey = keyof ChampionStats | "name" | "cost";
export type SortDirection = "asc" | "desc";
