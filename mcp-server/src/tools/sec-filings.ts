import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";

const EDGAR_USER_AGENT =
  "finance-os/0.1.0 (https://github.com/tolginator/finance-os)";
const EDGAR_SUBMISSIONS_URL = "https://data.sec.gov/submissions";

interface EdgarFiling {
  accessionNumber: string;
  formType: string;
  filingDate: string;
  primaryDocument: string;
  description: string;
}

interface CompanySubmissions {
  cik: string;
  entityType: string;
  name: string;
  tickers: string[];
  exchanges: string[];
  filings: {
    recent: {
      form: string[];
      accessionNumber: string[];
      filingDate: string[];
      primaryDocument: string[];
      primaryDocDescription: string[];
    };
  };
}

async function resolveTickerToCik(ticker: string): Promise<string | null> {
  const url = "https://www.sec.gov/files/company_tickers.json";
  const resp = await fetch(url, {
    headers: { "User-Agent": EDGAR_USER_AGENT },
  });
  if (!resp.ok) return null;

  const data = (await resp.json()) as Record<
    string,
    { cik_str: string; ticker: string; title: string }
  >;

  const upper = ticker.toUpperCase();
  for (const entry of Object.values(data)) {
    if (entry.ticker === upper) {
      return String(entry.cik_str);
    }
  }
  return null;
}

async function fetchSubmissions(cik: string): Promise<CompanySubmissions | null> {
  const padded = cik.padStart(10, "0");
  const url = `${EDGAR_SUBMISSIONS_URL}/CIK${padded}.json`;
  const resp = await fetch(url, {
    headers: { "User-Agent": EDGAR_USER_AGENT },
  });
  if (!resp.ok) return null;
  return (await resp.json()) as CompanySubmissions;
}

function extractFilings(
  submissions: CompanySubmissions,
  formTypes: string[],
  limit: number
): EdgarFiling[] {
  const recent = submissions.filings.recent;
  const allowed = new Set(formTypes.map((f) => f.toUpperCase()));
  const results: EdgarFiling[] = [];

  for (let i = 0; i < recent.form.length && results.length < limit; i++) {
    if (allowed.size > 0 && !allowed.has(recent.form[i].toUpperCase())) {
      continue;
    }
    results.push({
      accessionNumber: recent.accessionNumber[i] ?? "",
      formType: recent.form[i],
      filingDate: recent.filingDate[i] ?? "",
      primaryDocument: recent.primaryDocument[i] ?? "",
      description: recent.primaryDocDescription[i] ?? "",
    });
  }

  return results;
}

async function fetchFilingText(
  cik: string,
  accessionNumber: string,
  document: string
): Promise<string> {
  const padded = cik.padStart(10, "0");
  const accClean = accessionNumber.replace(/-/g, "");
  const url = `https://www.sec.gov/Archives/edgar/data/${padded}/${accClean}/${document}`;
  const resp = await fetch(url, {
    headers: { "User-Agent": EDGAR_USER_AGENT },
  });
  if (!resp.ok) return `Failed to fetch filing: HTTP ${resp.status}`;

  let text = await resp.text();
  // Strip HTML tags for cleaner text extraction
  text = text.replace(/<[^>]*>/g, " ").replace(/\s{2,}/g, " ");
  // Truncate for LLM context
  if (text.length > 100_000) {
    text = text.substring(0, 100_000) + "\n\n[... truncated at 100K chars ...]";
  }
  return text;
}

function extractSection(text: string, sectionName: string): string {
  const sectionPatterns: Record<string, RegExp[]> = {
    "risk-factors": [
      /item\s+1a[.\s\-—:]+risk\s+factors/i,
      /risk\s+factors/i,
    ],
    "mda": [
      /item\s+7[.\s\-—:]+management['']?s?\s+discussion/i,
      /management['']?s?\s+discussion\s+and\s+analysis/i,
    ],
    "business": [
      /item\s+1[.\s\-—:]+business(?!\s+risk)/i,
    ],
    "financials": [
      /item\s+8[.\s\-—:]+financial\s+statements/i,
    ],
    "legal": [
      /item\s+3[.\s\-—:]+legal\s+proceedings/i,
    ],
  };

  const patterns = sectionPatterns[sectionName.toLowerCase()];
  if (!patterns) {
    return `Unknown section: ${sectionName}. Available: ${Object.keys(sectionPatterns).join(", ")}`;
  }

  for (const pattern of patterns) {
    const match = pattern.exec(text);
    if (match) {
      const start = match.index;
      // Try to find the next "Item N" as section boundary
      const nextItem = /\bitem\s+\d+[a-z]?[.\s\-—:]/i.exec(
        text.substring(start + match[0].length)
      );
      const end = nextItem
        ? start + match[0].length + nextItem.index
        : Math.min(start + 50_000, text.length);

      let section = text.substring(start, end).trim();
      if (section.length > 50_000) {
        section = section.substring(0, 50_000) + "\n\n[... section truncated ...]";
      }
      return section;
    }
  }

  return `Section "${sectionName}" not found in filing text.`;
}

function formatFilingList(
  companyName: string,
  filings: EdgarFiling[]
): string {
  const lines = [`**${companyName}** — ${filings.length} filing(s):\n`];
  for (const f of filings) {
    lines.push(
      `- **${f.formType}** filed ${f.filingDate} — ${f.description || f.primaryDocument} [${f.accessionNumber}]`
    );
  }
  return lines.join("\n");
}

export function registerSecFilingsTool(server: McpServer): void {
  server.tool(
    "sec-filings",
    "Search SEC EDGAR filings by ticker or CIK. List recent filings, fetch full text, or extract specific sections (risk-factors, mda, business, financials, legal).",
    {
      identifier: z
        .string()
        .describe("Ticker symbol (e.g. 'AAPL') or CIK number"),
      action: z
        .enum(["list", "fetch", "section"])
        .describe(
          "'list' to list recent filings, 'fetch' to get full filing text, 'section' to extract a specific section"
        ),
      formTypes: z
        .string()
        .optional()
        .describe(
          "Comma-separated form types to filter (e.g. '10-K,10-Q'). Default: '10-K,10-Q'"
        ),
      accessionNumber: z
        .string()
        .optional()
        .describe("Accession number for fetch/section actions"),
      document: z
        .string()
        .optional()
        .describe("Primary document filename for fetch/section actions"),
      sectionName: z
        .string()
        .optional()
        .describe(
          "Section to extract: risk-factors, mda, business, financials, legal"
        ),
      limit: z
        .number()
        .optional()
        .describe("Max filings to return (default: 10)"),
    },
    async ({
      identifier,
      action,
      formTypes,
      accessionNumber,
      document,
      sectionName,
      limit,
    }) => {
      try {
        // Resolve ticker to CIK if needed
        let cik = identifier;
        if (!/^\d+$/.test(identifier)) {
          const resolved = await resolveTickerToCik(identifier);
          if (!resolved) {
            return {
              content: [
                {
                  type: "text" as const,
                  text: `Could not resolve ticker "${identifier}" to a CIK. Try providing a CIK number directly.`,
                },
              ],
              isError: true,
            };
          }
          cik = resolved;
        }

        const submissions = await fetchSubmissions(cik);
        if (!submissions) {
          return {
            content: [
              {
                type: "text" as const,
                text: `Failed to fetch EDGAR submissions for CIK ${cik}.`,
              },
            ],
            isError: true,
          };
        }

        const forms = formTypes
          ? formTypes.split(",").map((f) => f.trim())
          : ["10-K", "10-Q"];
        const maxResults = limit ?? 10;

        if (action === "list") {
          const filings = extractFilings(submissions, forms, maxResults);
          if (filings.length === 0) {
            return {
              content: [
                {
                  type: "text" as const,
                  text: `No ${forms.join("/")} filings found for ${submissions.name} (CIK ${cik}).`,
                },
              ],
            };
          }
          return {
            content: [
              {
                type: "text" as const,
                text: formatFilingList(submissions.name, filings),
              },
            ],
          };
        }

        if (action === "fetch" || action === "section") {
          if (!accessionNumber || !document) {
            // Auto-select the most recent filing
            const filings = extractFilings(submissions, forms, 1);
            if (filings.length === 0) {
              return {
                content: [
                  {
                    type: "text" as const,
                    text: `No filings found to fetch for ${submissions.name}.`,
                  },
                ],
                isError: true,
              };
            }
            accessionNumber = filings[0].accessionNumber;
            document = filings[0].primaryDocument;
          }

          const text = await fetchFilingText(cik, accessionNumber, document);

          if (action === "section") {
            if (!sectionName) {
              return {
                content: [
                  {
                    type: "text" as const,
                    text: "Please specify a sectionName: risk-factors, mda, business, financials, or legal.",
                  },
                ],
                isError: true,
              };
            }
            const section = extractSection(text, sectionName);
            return {
              content: [
                {
                  type: "text" as const,
                  text: `## ${sectionName.toUpperCase()} — ${submissions.name}\n\n${section}`,
                },
              ],
            };
          }

          return {
            content: [
              {
                type: "text" as const,
                text: `## Filing: ${submissions.name} [${accessionNumber}]\n\n${text}`,
              },
            ],
          };
        }

        return {
          content: [
            {
              type: "text" as const,
              text: `Unknown action: ${action}`,
            },
          ],
          isError: true,
        };
      } catch (error: unknown) {
        const message = error instanceof Error ? error.message : String(error);
        return {
          content: [
            {
              type: "text" as const,
              text: `SEC filings error: ${message}`,
            },
          ],
          isError: true,
        };
      }
    }
  );
}
