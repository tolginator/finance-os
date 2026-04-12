import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";

export interface Holding {
  ticker: string;
  shares: number;
  costBasis: number;
  currentPrice: number;
  sector?: string;
  assetClass?: string;
}

export interface ExposureResult {
  bySector: Record<string, number>;
  byAssetClass: Record<string, number>;
}

export interface ConcentrationResult {
  hhi: number;
  level: "CONCENTRATED" | "MODERATE" | "DIVERSIFIED";
  topHoldings: { ticker: string; weightPct: number }[];
}

export interface DrawdownResult {
  maxDrawdownPct: number;
  currentDrawdownPct: number;
  peakValue: number;
  troughValue: number;
}

export interface SummaryResult {
  totalValue: number;
  totalCost: number;
  totalPnL: number;
  pnlPct: number;
  exposure: ExposureResult;
  concentration: ConcentrationResult;
}

function round2(n: number): number {
  return Math.round(n * 100) / 100;
}

function holdingValue(h: Holding): number {
  return h.shares * h.currentPrice;
}

export function calculateExposure(holdings: Holding[]): ExposureResult {
  const totalValue = holdings.reduce((sum, h) => sum + holdingValue(h), 0);

  if (totalValue === 0) {
    return { bySector: {}, byAssetClass: {} };
  }

  const bySector: Record<string, number> = {};
  const byAssetClass: Record<string, number> = {};

  for (const h of holdings) {
    const value = holdingValue(h);
    const sector = h.sector || "Unknown";
    const assetClass = h.assetClass || "Unknown";

    bySector[sector] = round2((bySector[sector] ?? 0) + (value / totalValue) * 100);
    byAssetClass[assetClass] = round2(
      (byAssetClass[assetClass] ?? 0) + (value / totalValue) * 100
    );
  }

  return { bySector, byAssetClass };
}

export function calculateConcentration(holdings: Holding[]): ConcentrationResult {
  const totalValue = holdings.reduce((sum, h) => sum + holdingValue(h), 0);

  if (totalValue === 0) {
    return { hhi: 0, level: "DIVERSIFIED", topHoldings: [] };
  }

  const weights = holdings.map((h) => ({
    ticker: h.ticker,
    weightPct: round2((holdingValue(h) / totalValue) * 100),
  }));

  weights.sort((a, b) => b.weightPct - a.weightPct);

  const hhi = round2(weights.reduce((sum, w) => sum + w.weightPct ** 2, 0));

  let level: ConcentrationResult["level"];
  if (hhi > 2500) level = "CONCENTRATED";
  else if (hhi >= 1500) level = "MODERATE";
  else level = "DIVERSIFIED";

  return { hhi, level, topHoldings: weights };
}

export function calculateDrawdown(priceHistory: number[]): DrawdownResult {
  if (priceHistory.length === 0) {
    return { maxDrawdownPct: 0, currentDrawdownPct: 0, peakValue: 0, troughValue: 0 };
  }

  let peak = priceHistory[0];
  let maxDrawdown = 0;
  let maxPeak = peak;
  let maxTrough = peak;

  for (const price of priceHistory) {
    if (price > peak) {
      peak = price;
    }
    const drawdown = (peak - price) / peak;
    if (drawdown > maxDrawdown) {
      maxDrawdown = drawdown;
      maxPeak = peak;
      maxTrough = price;
    }
  }

  // Current drawdown from the most recent peak
  let currentPeak = priceHistory[0];
  for (const price of priceHistory) {
    if (price > currentPeak) currentPeak = price;
  }
  const currentPrice = priceHistory[priceHistory.length - 1];
  const currentDrawdown = (currentPeak - currentPrice) / currentPeak;

  return {
    maxDrawdownPct: round2(maxDrawdown * 100),
    currentDrawdownPct: round2(currentDrawdown * 100),
    peakValue: maxPeak,
    troughValue: maxTrough,
  };
}

export function portfolioSummary(holdings: Holding[]): SummaryResult {
  const totalValue = round2(holdings.reduce((sum, h) => sum + holdingValue(h), 0));
  const totalCost = round2(
    holdings.reduce((sum, h) => sum + h.shares * h.costBasis, 0)
  );
  const totalPnL = round2(totalValue - totalCost);
  const pnlPct = totalCost === 0 ? 0 : round2((totalPnL / totalCost) * 100);

  return {
    totalValue,
    totalCost,
    totalPnL,
    pnlPct,
    exposure: calculateExposure(holdings),
    concentration: calculateConcentration(holdings),
  };
}

const holdingSchema = z.object({
  ticker: z.string(),
  shares: z.number(),
  costBasis: z.number(),
  currentPrice: z.number(),
  sector: z.string().optional(),
  assetClass: z.string().optional(),
});

export function registerPortfolioTool(server: McpServer): void {
  server.tool(
    "portfolio",
    "Portfolio diagnostics: exposure analysis, concentration risk (HHI), drawdown calculation, and summary metrics.",
    {
      action: z
        .enum(["exposure", "drawdown", "concentration", "summary"])
        .describe(
          "'exposure' for sector/asset-class breakdown, 'concentration' for HHI risk, 'drawdown' for peak-to-trough analysis, 'summary' for all metrics"
        ),
      holdings: z
        .array(holdingSchema)
        .optional()
        .describe("Array of portfolio holdings (required for exposure, concentration, summary)"),
      priceHistory: z
        .array(z.number())
        .optional()
        .describe("Array of historical prices for drawdown calculation"),
    },
    async ({ action, holdings, priceHistory }) => {
      try {
        const h: Holding[] = holdings ?? [];

        switch (action) {
          case "exposure": {
            const result = calculateExposure(h);
            return {
              content: [{ type: "text" as const, text: JSON.stringify(result, null, 2) }],
            };
          }
          case "concentration": {
            const result = calculateConcentration(h);
            return {
              content: [{ type: "text" as const, text: JSON.stringify(result, null, 2) }],
            };
          }
          case "drawdown": {
            const result = calculateDrawdown(priceHistory ?? []);
            return {
              content: [{ type: "text" as const, text: JSON.stringify(result, null, 2) }],
            };
          }
          case "summary": {
            const result = portfolioSummary(h);
            return {
              content: [{ type: "text" as const, text: JSON.stringify(result, null, 2) }],
            };
          }
          default:
            return {
              content: [{ type: "text" as const, text: `Unknown action: ${action}` }],
              isError: true,
            };
        }
      } catch (error: unknown) {
        const message = error instanceof Error ? error.message : String(error);
        return {
          content: [{ type: "text" as const, text: `Portfolio error: ${message}` }],
          isError: true,
        };
      }
    }
  );
}
