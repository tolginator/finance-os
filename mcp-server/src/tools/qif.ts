import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { readFile } from "node:fs/promises";
import { parseQif, formatDate } from "./qif-parser.js";
import type { QifTransaction, QifInvestment, QifData } from "./qif-parser.js";

function matchesFilters(
  txn: QifTransaction | QifInvestment,
  filters: { account?: string; category?: string; startDate?: string; endDate?: string }
): boolean {
  if (filters.account && txn.account.toLowerCase() !== filters.account.toLowerCase()) {
    return false;
  }
  if (filters.category && txn.category.toLowerCase() !== filters.category.toLowerCase()) {
    return false;
  }
  if (txn.dateObj) {
    const dateStr = formatDate(txn.dateObj);
    if (filters.startDate && dateStr < filters.startDate) return false;
    if (filters.endDate && dateStr > filters.endDate) return false;
  }
  return true;
}

function formatTransaction(txn: QifTransaction): string {
  const date = txn.dateObj ? formatDate(txn.dateObj) : txn.date;
  const parts = [`${date}  ${txn.amount >= 0 ? "+" : ""}${txn.amount.toFixed(2)}`];
  if (txn.payee) parts.push(`  Payee: ${txn.payee}`);
  if (txn.category) parts.push(`  Category: ${txn.category}`);
  if (txn.memo) parts.push(`  Memo: ${txn.memo}`);
  return parts.join("\n");
}

function summarizeData(data: QifData): string {
  const accountNames = Object.keys(data.accounts);
  const lines: string[] = [
    `**Accounts**: ${accountNames.length}`,
  ];
  for (const name of accountNames) {
    const acct = data.accounts[name];
    lines.push(`  - ${name} (${acct.type || "unknown type"})`);
  }
  lines.push(`**Transactions**: ${data.transactions.length}`);
  lines.push(`**Investments**: ${data.investments.length}`);
  lines.push(`**Categories**: ${data.categories.length}`);
  lines.push(`**Securities**: ${data.securities.length}`);
  return lines.join("\n");
}

/**
 * Register the QIF data access tool on the MCP server.
 *
 * Parses QIF files and exposes transaction/account/category queries.
 */
export function registerQifTool(server: McpServer): void {
  server.tool(
    "qif-query",
    "Parse a QIF (Quicken) file and query transactions, accounts, and categories",
    {
      filePath: z.string().describe("Absolute path to the QIF file"),
      query: z
        .enum(["summary", "transactions", "accounts", "categories", "investments"])
        .default("summary")
        .describe("What to query from the QIF file"),
      account: z.string().optional().describe("Filter by account name"),
      category: z.string().optional().describe("Filter by category"),
      startDate: z
        .string()
        .optional()
        .describe("Filter start date (YYYY-MM-DD)"),
      endDate: z
        .string()
        .optional()
        .describe("Filter end date (YYYY-MM-DD)"),
      limit: z
        .number()
        .default(50)
        .describe("Max number of results to return (default 50)"),
    },
    async ({ filePath, query, account, category, startDate, endDate, limit }) => {
      try {
        const raw = await readFile(filePath, "latin1");
        const data = parseQif(raw);

        switch (query) {
          case "summary":
            return { content: [{ type: "text", text: summarizeData(data) }] };

          case "accounts": {
            const accts = Object.values(data.accounts)
              .map((a) => `- **${a.name}** (${a.type || "unknown"})`)
              .join("\n");
            return {
              content: [{ type: "text", text: accts || "No accounts found." }],
            };
          }

          case "categories": {
            const cats = data.categories
              .map((c) => {
                const flags = [
                  c.income ? "income" : null,
                  c.expense ? "expense" : null,
                  c.taxRelated ? "tax" : null,
                ]
                  .filter(Boolean)
                  .join(", ");
                return `- **${c.name}**${flags ? ` (${flags})` : ""}`;
              })
              .join("\n");
            return {
              content: [{ type: "text", text: cats || "No categories found." }],
            };
          }

          case "transactions": {
            const filters = { account, category, startDate, endDate };
            const filtered = data.transactions
              .filter((t) => matchesFilters(t, filters))
              .slice(0, limit);
            const output = filtered.map(formatTransaction).join("\n\n");
            const header = `Showing ${filtered.length} of ${data.transactions.length} transactions`;
            return {
              content: [
                { type: "text", text: `${header}\n\n${output || "No matching transactions."}` },
              ],
            };
          }

          case "investments": {
            const filters = { account, category, startDate, endDate };
            const filtered = data.investments
              .filter((t) => matchesFilters(t, filters))
              .slice(0, limit);
            const output = filtered
              .map((inv) => {
                const date = inv.dateObj ? formatDate(inv.dateObj) : inv.date;
                return `${date}  ${inv.action} ${inv.security || ""} qty:${inv.quantity} @ ${inv.price}`;
              })
              .join("\n");
            const header = `Showing ${filtered.length} of ${data.investments.length} investments`;
            return {
              content: [
                { type: "text", text: `${header}\n\n${output || "No matching investments."}` },
              ],
            };
          }

          default:
            return {
              content: [{ type: "text", text: `Unknown query type: ${query as string}` }],
              isError: true,
            };
        }
      } catch (error: unknown) {
        const message = error instanceof Error ? error.message : String(error);
        return {
          content: [{ type: "text", text: `Failed to process QIF file: ${message}` }],
          isError: true,
        };
      }
    }
  );
}
