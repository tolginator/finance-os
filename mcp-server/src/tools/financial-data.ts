import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";

/**
 * Yahoo Finance quote response shape (subset of v8 API).
 */
interface QuoteResult {
  symbol: string;
  shortName?: string;
  longName?: string;
  regularMarketPrice?: number;
  regularMarketChange?: number;
  regularMarketChangePercent?: number;
  regularMarketVolume?: number;
  marketCap?: number;
  trailingPE?: number;
  forwardPE?: number;
  trailingAnnualDividendYield?: number;
  fiftyTwoWeekHigh?: number;
  fiftyTwoWeekLow?: number;
  currency?: string;
  exchange?: string;
  quoteType?: string;
}

async function fetchQuotes(symbols: string[]): Promise<QuoteResult[]> {
  const joined = symbols.map((s) => encodeURIComponent(s.toUpperCase())).join(",");
  const url = `https://query1.finance.yahoo.com/v7/finance/quote?symbols=${joined}`;

  const response = await fetch(url, {
    headers: {
      "User-Agent": "finance-os/0.1.0",
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Yahoo Finance API returned ${response.status}`);
  }

  const data = (await response.json()) as {
    quoteResponse?: { result?: QuoteResult[] };
  };

  return data.quoteResponse?.result ?? [];
}

function formatQuote(q: QuoteResult): string {
  const lines: string[] = [
    `**${q.shortName || q.longName || q.symbol}** (${q.symbol})`,
    `Price: ${q.regularMarketPrice ?? "N/A"} ${q.currency ?? ""}`,
    `Change: ${q.regularMarketChange?.toFixed(2) ?? "N/A"} (${q.regularMarketChangePercent?.toFixed(2) ?? "N/A"}%)`,
    `Volume: ${q.regularMarketVolume?.toLocaleString() ?? "N/A"}`,
  ];

  if (q.marketCap != null) {
    lines.push(`Market Cap: ${formatLargeNumber(q.marketCap)}`);
  }
  if (q.trailingPE != null) {
    lines.push(`P/E (TTM): ${q.trailingPE.toFixed(2)}`);
  }
  if (q.forwardPE != null) {
    lines.push(`P/E (Fwd): ${q.forwardPE.toFixed(2)}`);
  }
  if (q.trailingAnnualDividendYield != null) {
    lines.push(`Div Yield: ${(q.trailingAnnualDividendYield * 100).toFixed(2)}%`);
  }
  if (q.fiftyTwoWeekHigh != null && q.fiftyTwoWeekLow != null) {
    lines.push(`52w Range: ${q.fiftyTwoWeekLow} – ${q.fiftyTwoWeekHigh}`);
  }
  if (q.exchange) {
    lines.push(`Exchange: ${q.exchange}`);
  }

  return lines.join("\n");
}

function formatLargeNumber(n: number): string {
  if (n >= 1e12) return `${(n / 1e12).toFixed(2)}T`;
  if (n >= 1e9) return `${(n / 1e9).toFixed(2)}B`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(2)}M`;
  return n.toLocaleString();
}

/**
 * Register the financial-data tool on the MCP server.
 *
 * Provides real-time stock quotes and basic fundamentals via Yahoo Finance.
 */
export function registerFinancialDataTool(server: McpServer): void {
  server.tool(
    "financial-data",
    "Get real-time stock quotes and basic fundamentals for one or more ticker symbols",
    {
      symbols: z
        .string()
        .describe("Comma-separated ticker symbols (e.g. 'AAPL,MSFT,GOOGL')"),
    },
    async ({ symbols }) => {
      const tickers = symbols
        .split(",")
        .map((s) => s.trim())
        .filter((s) => s.length > 0);

      if (tickers.length === 0) {
        return {
          content: [{ type: "text", text: "No valid ticker symbols provided." }],
          isError: true,
        };
      }

      try {
        const quotes = await fetchQuotes(tickers);

        if (quotes.length === 0) {
          return {
            content: [
              {
                type: "text",
                text: `No data found for: ${tickers.join(", ")}`,
              },
            ],
          };
        }

        const output = quotes.map(formatQuote).join("\n\n---\n\n");
        return {
          content: [{ type: "text", text: output }],
        };
      } catch (error: unknown) {
        const message = error instanceof Error ? error.message : String(error);
        return {
          content: [
            {
              type: "text",
              text: `Failed to fetch financial data: ${message}`,
            },
          ],
          isError: true,
        };
      }
    }
  );
}
