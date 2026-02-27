import championsData from "../data/tft16_champion_weight.json";

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

export type Role = string;

export const CHAMPIONS: Champion[] = championsData as Champion[];

export const ROLES: Role[] = [
  "All",
  ...Array.from(new Set(CHAMPIONS.map((champion) => champion.role))),
];

export const ROLE_ICONS: Record<string, string> = {
  All: "🎮",
  "AD 딜러": "⚔️",
  "AP 딜러": "🔮",
  Tank: "🛡️",
};

export type SortKey = keyof ChampionStats | "name" | "cost";
export type SortDirection = "asc" | "desc";
