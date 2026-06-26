import type {
  PaginaParlamentares,
  Parlamentar,
  PaginaVotos,
  TimelinePoint,
  ParlamentarSimilar,
} from "./types";
import {
  mockGetParlamentares,
  mockGetParlamentar,
  mockGetVotos,
  mockGetTimeline,
  mockGetSimilares,
} from "./mock";

const USE_MOCK = process.env.NEXT_PUBLIC_USE_MOCK === "true";
const BASE =
  (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

async function get<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { next: { revalidate: 60 }, ...opts });
  if (!res.ok) throw new Error(`${res.status}: ${path}`);
  return res.json() as Promise<T>;
}

export type ParlamentaresParams = {
  busca?: string;
  partido?: string;
  cargo?: string;
  estado?: string;
  ordem?: string;
  pagina?: number;
  tamanho?: number;
};

export async function getParlamentares(params: ParlamentaresParams = {}): Promise<PaginaParlamentares> {
  if (USE_MOCK) return Promise.resolve(mockGetParlamentares(params));
  const q = new URLSearchParams();
  if (params.busca) q.set("busca", params.busca);
  if (params.partido) q.set("partido", params.partido);
  if (params.cargo) q.set("cargo", params.cargo);
  if (params.estado) q.set("estado", params.estado);
  if (params.ordem) q.set("ordem", params.ordem);
  if (params.pagina) q.set("pagina", String(params.pagina));
  if (params.tamanho) q.set("tamanho", String(params.tamanho));
  const qs = q.toString();
  return get<PaginaParlamentares>(`/api/politicos${qs ? `?${qs}` : ""}`);
}

export async function getParlamentar(id: number): Promise<Parlamentar> {
  if (USE_MOCK) return Promise.resolve(mockGetParlamentar(id));
  return get<Parlamentar>(`/api/politicos/${id}`);
}

export async function getVotos(
  id: number,
  params: { pagina?: number; tamanho?: number; ordem?: string } = {}
): Promise<PaginaVotos> {
  if (USE_MOCK) return Promise.resolve(mockGetVotos(id, params));
  const q = new URLSearchParams();
  if (params.pagina) q.set("pagina", String(params.pagina));
  if (params.tamanho) q.set("tamanho", String(params.tamanho));
  if (params.ordem) q.set("ordem", params.ordem);
  const qs = q.toString();
  return get<PaginaVotos>(`/api/politicos/${id}/votos${qs ? `?${qs}` : ""}`);
}

export async function getTimeline(id: number): Promise<TimelinePoint[]> {
  if (USE_MOCK) return Promise.resolve(mockGetTimeline(id));
  return get<TimelinePoint[]>(`/api/politicos/${id}/timeline`);
}

export async function getSimilares(id: number, limite = 5): Promise<ParlamentarSimilar[]> {
  if (USE_MOCK) return Promise.resolve(mockGetSimilares(id));
  return get<ParlamentarSimilar[]>(`/api/politicos/${id}/similares?limite=${limite}`);
}
