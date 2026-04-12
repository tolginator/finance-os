import { describe, it, expect } from "vitest";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import {
  registerPortfolioTool,
  calculateExposure,
  calculateConcentration,
  calculateDrawdown,
  portfolioSummary,
  type Holding,
} from "../src/tools/portfolio.js";

const mixedHoldings: Holding[] = [
  { ticker: "AAPL", shares: 10, costBasis: 150, currentPrice: 200, sector: "Technology", assetClass: "equity" },
  { ticker: "JPM", shares: 20, costBasis: 100, currentPrice: 120, sector: "Financials", assetClass: "equity" },
  { ticker: "BND", shares: 50, costBasis: 80, currentPrice: 82, sector: "Fixed Income", assetClass: "bond" },
];

describe("portfolio tool", () => {
  it("registers without error", () => {
    const server = new McpServer({ name: "test", version: "0.0.1" });
    expect(() => registerPortfolioTool(server)).not.toThrow();
  });
});

describe("calculateExposure", () => {
  it("mixed sectors produce correct percentages that sum to ~100", () => {
    const result = calculateExposure(mixedHoldings);
    const sectorSum = Object.values(result.bySector).reduce((a, b) => a + b, 0);
    const classSum = Object.values(result.byAssetClass).reduce((a, b) => a + b, 0);

    expect(sectorSum).toBeCloseTo(100, 0);
    expect(classSum).toBeCloseTo(100, 0);
    expect(Object.keys(result.bySector)).toHaveLength(3);
    expect(result.bySector["Technology"]).toBeGreaterThan(0);
    expect(result.bySector["Financials"]).toBeGreaterThan(0);
    expect(result.bySector["Fixed Income"]).toBeGreaterThan(0);
  });

  it("single sector returns 100%", () => {
    const holdings: Holding[] = [
      { ticker: "AAPL", shares: 10, costBasis: 150, currentPrice: 200, sector: "Technology", assetClass: "equity" },
      { ticker: "MSFT", shares: 5, costBasis: 300, currentPrice: 350, sector: "Technology", assetClass: "equity" },
    ];
    const result = calculateExposure(holdings);
    expect(result.bySector["Technology"]).toBeCloseTo(100, 0);
    expect(result.byAssetClass["equity"]).toBeCloseTo(100, 0);
  });

  it("empty holdings return empty results", () => {
    const result = calculateExposure([]);
    expect(result.bySector).toEqual({});
    expect(result.byAssetClass).toEqual({});
  });

  it("missing sector defaults to 'Unknown'", () => {
    const holdings: Holding[] = [
      { ticker: "XYZ", shares: 10, costBasis: 100, currentPrice: 100 },
    ];
    const result = calculateExposure(holdings);
    expect(result.bySector["Unknown"]).toBe(100);
    expect(result.byAssetClass["Unknown"]).toBe(100);
  });
});

describe("calculateConcentration", () => {
  it("single holding → HHI = 10000 → CONCENTRATED", () => {
    const holdings: Holding[] = [
      { ticker: "AAPL", shares: 100, costBasis: 150, currentPrice: 200 },
    ];
    const result = calculateConcentration(holdings);
    expect(result.hhi).toBe(10000);
    expect(result.level).toBe("CONCENTRATED");
  });

  it("many equal holdings → low HHI → DIVERSIFIED", () => {
    const holdings: Holding[] = Array.from({ length: 20 }, (_, i) => ({
      ticker: `T${i}`,
      shares: 10,
      costBasis: 100,
      currentPrice: 100,
    }));
    const result = calculateConcentration(holdings);
    // 20 equal holdings → each 5% → HHI = 20 * 25 = 500
    expect(result.hhi).toBe(500);
    expect(result.level).toBe("DIVERSIFIED");
  });

  it("empty holdings → zero HHI", () => {
    const result = calculateConcentration([]);
    expect(result.hhi).toBe(0);
    expect(result.level).toBe("DIVERSIFIED");
    expect(result.topHoldings).toEqual([]);
  });

  it("holdings producing HHI between 1500 and 2500 → MODERATE", () => {
    // 3 holdings: 50%, 30%, 20% → HHI = 2500+900+400 = 3800 (too high)
    // 4 holdings: 40%, 30%, 20%, 10% → HHI = 1600+900+400+100 = 3000 (too high)
    // 5 holdings: 30%, 25%, 20%, 15%, 10% → HHI = 900+625+400+225+100 = 2250 ✓
    const holdings: Holding[] = [
      { ticker: "A", shares: 30, costBasis: 100, currentPrice: 100 },
      { ticker: "B", shares: 25, costBasis: 100, currentPrice: 100 },
      { ticker: "C", shares: 20, costBasis: 100, currentPrice: 100 },
      { ticker: "D", shares: 15, costBasis: 100, currentPrice: 100 },
      { ticker: "E", shares: 10, costBasis: 100, currentPrice: 100 },
    ];
    const result = calculateConcentration(holdings);
    expect(result.hhi).toBeGreaterThanOrEqual(1500);
    expect(result.hhi).toBeLessThanOrEqual(2500);
    expect(result.level).toBe("MODERATE");
  });
});

describe("calculateDrawdown", () => {
  it("[100, 90, 95, 80, 110] → max drawdown 20%, current 0%", () => {
    const result = calculateDrawdown([100, 90, 95, 80, 110]);
    expect(result.maxDrawdownPct).toBe(20);
    expect(result.currentDrawdownPct).toBe(0);
    expect(result.peakValue).toBe(100);
    expect(result.troughValue).toBe(80);
  });

  it("empty history → zero drawdown", () => {
    const result = calculateDrawdown([]);
    expect(result.maxDrawdownPct).toBe(0);
    expect(result.currentDrawdownPct).toBe(0);
    expect(result.peakValue).toBe(0);
    expect(result.troughValue).toBe(0);
  });

  it("monotonically increasing prices → zero drawdown", () => {
    const result = calculateDrawdown([100, 110, 120, 130, 140]);
    expect(result.maxDrawdownPct).toBe(0);
    expect(result.currentDrawdownPct).toBe(0);
  });

  it("monotonically decreasing prices → max drawdown equals total decline", () => {
    const result = calculateDrawdown([200, 180, 150, 120, 100]);
    // Peak 200, trough 100 → 50% drawdown
    expect(result.maxDrawdownPct).toBe(50);
    expect(result.currentDrawdownPct).toBe(50);
    expect(result.peakValue).toBe(200);
    expect(result.troughValue).toBe(100);
  });

  it("single price → zero drawdown", () => {
    const result = calculateDrawdown([42]);
    expect(result.maxDrawdownPct).toBe(0);
    expect(result.currentDrawdownPct).toBe(0);
  });
});

describe("portfolioSummary", () => {
  it("calculates total value, cost, and P&L correctly", () => {
    const holdings: Holding[] = [
      { ticker: "AAPL", shares: 10, costBasis: 150, currentPrice: 200 },
      { ticker: "MSFT", shares: 5, costBasis: 300, currentPrice: 350 },
    ];
    const result = portfolioSummary(holdings);
    // AAPL: 10*200=2000, MSFT: 5*350=1750 → total=3750
    expect(result.totalValue).toBe(3750);
    // AAPL: 10*150=1500, MSFT: 5*300=1500 → cost=3000
    expect(result.totalCost).toBe(3000);
    expect(result.totalPnL).toBe(750);
    expect(result.pnlPct).toBe(25);
    expect(result.exposure).toBeDefined();
    expect(result.concentration).toBeDefined();
  });

  it("empty holdings → graceful zero results", () => {
    const result = portfolioSummary([]);
    expect(result.totalValue).toBe(0);
    expect(result.totalCost).toBe(0);
    expect(result.totalPnL).toBe(0);
    expect(result.pnlPct).toBe(0);
    expect(result.exposure.bySector).toEqual({});
    expect(result.concentration.hhi).toBe(0);
  });
});
