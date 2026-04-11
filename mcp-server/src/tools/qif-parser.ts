/**
 * QIF Parser — parses Quicken Interchange Format text into structured data.
 *
 * Ported from Slicken's qifParser.js to TypeScript for use in the MCP server.
 *
 * Specification: https://en.wikipedia.org/wiki/Quicken_Interchange_Format
 */

import { randomUUID } from "node:crypto";

// ============================================================================
// Types
// ============================================================================

export interface QifAccount {
  id: string;
  name: string;
  type: string;
  description: string;
}

export interface QifSplit {
  id: string;
  category: string;
  memo: string;
  amount: number;
  percent: string;
}

export interface QifTransaction {
  id: string;
  account: string;
  date: string;
  dateObj: Date | null;
  amount: number;
  memo: string;
  cleared: string;
  category: string;
  payee: string;
  checkNumber: string;
  splits: QifSplit[];
}

export interface QifInvestment {
  id: string;
  account: string;
  date: string;
  dateObj: Date | null;
  amount: number;
  memo: string;
  cleared: string;
  category: string;
  payee: string;
  action: string;
  security: string;
  price: number;
  quantity: number;
  commission: number;
  splits: QifSplit[];
}

export interface QifCategory {
  id: string;
  name: string;
  description: string;
  income: boolean;
  expense: boolean;
  taxRelated: boolean;
}

export interface QifSecurity {
  id: string;
  name: string;
  symbol: string;
  type: string;
}

export interface QifData {
  accounts: Record<string, QifAccount>;
  transactions: QifTransaction[];
  investments: QifInvestment[];
  categories: QifCategory[];
  securities: QifSecurity[];
}

// ============================================================================
// Date Parsing
// ============================================================================

const MONTH_NAMES: Record<string, number> = {
  january: 0, february: 1, march: 2, april: 3, may: 4, june: 5,
  july: 6, august: 7, september: 8, october: 9, november: 10, december: 11,
  jan: 0, feb: 1, mar: 2, apr: 3, jun: 5, jul: 6, aug: 7, sep: 8,
  oct: 9, nov: 10, dec: 11,
};

export function parseDate(s: string): Date | null {
  if (!s) return null;
  s = s.trim();

  // "D Month YYYY" format
  const longMatch = s.match(/^(\d{1,2})\s+(\w+)\s+(\d{2,4})$/);
  if (longMatch) {
    const day = parseInt(longMatch[1], 10);
    const moName = longMatch[2].toLowerCase();
    let yr = parseInt(longMatch[3], 10);
    if (MONTH_NAMES[moName] !== undefined) {
      if (yr < 100) yr += yr < 50 ? 2000 : 1900;
      const d = new Date(yr, MONTH_NAMES[moName], day);
      if (!isNaN(d.getTime())) return d;
    }
  }

  // Normalize separators
  const norm = s.replace(/'/g, "/").replace(/-/g, "/").replace(/\s+/g, "");

  const fmts = [
    /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/,
    /^(\d{1,2})\/(\d{1,2})\/(\d{1,2})$/,
  ];
  for (const re of fmts) {
    const m = norm.match(re);
    if (m) {
      const mo = parseInt(m[1], 10);
      const dy = parseInt(m[2], 10);
      let yr = parseInt(m[3], 10);
      if (yr < 100) yr += yr < 50 ? 2000 : 1900;
      const d = new Date(yr, mo - 1, dy);
      if (!isNaN(d.getTime())) return d;
    }
  }

  return null;
}

// ============================================================================
// Amount Parsing
// ============================================================================

export function parseAmount(s: string): number {
  if (!s) return 0;
  const cleaned = s.replace(/[$£¥€]/g, "").replace(/,/g, "").trim();
  const v = parseFloat(cleaned);
  return isNaN(v) ? 0 : v;
}

// ============================================================================
// Date Formatting
// ============================================================================

export function formatDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const dy = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${dy}`;
}

// ============================================================================
// QIF Parser
// ============================================================================

const BANKING_TYPES = new Set(["bank", "cash", "ccard", "oth a", "oth l"]);
const TRANSACTION_TYPES = new Set([
  "bank", "cash", "ccard", "oth a", "oth l",
  "invst", "memorized", "invoice",
]);

export function parseQif(text: string, fallbackAccount?: string): QifData {
  const accounts: Record<string, QifAccount> = {};
  const transactions: QifTransaction[] = [];
  const investments: QifInvestment[] = [];
  const categories: QifCategory[] = [];
  const securities: QifSecurity[] = [];

  let currentSection: string | null = null;
  let currentAccount: string | null = null;
  let record: Record<string, string> = {};
  let splits: Array<{ category: string; memo: string; amount: number; percent: string }> = [];
  let addresses: string[] = [];

  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.replace(/[\r\n]+$/, "");
    if (!line) continue;

    // Section headers
    if (line.startsWith("!")) {
      const low = line.toLowerCase().trim();

      if (low === "!option:autoswitch") {
        currentSection = null;
        continue;
      }
      if (low === "!clear:autoswitch") {
        continue;
      }
      if (low === "!account") {
        currentSection = "account";
        record = {};
        addresses = [];
        continue;
      }
      if (low.startsWith("!type:")) {
        const rawSection = line.substring(6).trim().toLowerCase();
        // Strip control chars from corrupt QIF files (e.g. 0x01 in type headers)
        // eslint-disable-next-line no-control-regex
        currentSection = rawSection.replace(/[\x00-\x1f]/g, "").trim() || "bank";

        if (currentAccount && accounts[currentAccount] && !accounts[currentAccount].type) {
          if (BANKING_TYPES.has(currentSection) || currentSection === "invst") {
            accounts[currentAccount].type = currentSection;
          }
        }
        record = {};
        splits = [];
        addresses = [];
        continue;
      }
      continue;
    }

    // Record separator
    if (line.trim() === "^") {
      if (currentSection === "account") {
        const name = record["N"] || "Unknown";
        // eslint-disable-next-line no-control-regex
        const rawType = (record["T"] || "").replace(/[\x00-\x1f]/g, "").trim();
        accounts[name] = {
          id: randomUUID(),
          name,
          type: rawType,
          description: record["D"] || "",
        };
        currentAccount = name;
        record = {};
        addresses = [];
        continue;
      }

      if (BANKING_TYPES.has(currentSection ?? "")) {
        const acctName = currentAccount || fallbackAccount || "Unknown";
        transactions.push({
          id: randomUUID(),
          account: acctName,
          date: record["D"] || "",
          dateObj: parseDate(record["D"] || ""),
          amount: parseAmount(record["T"] || record["U"] || ""),
          memo: record["M"] || "",
          cleared: record["C"] || "",
          category: record["L"] || "",
          payee: record["P"] || "",
          checkNumber: record["N"] || "",
          splits: splits.map((s) => ({ ...s, id: randomUUID() })),
        });
        record = {};
        splits = [];
        addresses = [];
        continue;
      }

      if (currentSection === "invst") {
        const acctName = currentAccount || fallbackAccount || "Unknown";
        investments.push({
          id: randomUUID(),
          account: acctName,
          date: record["D"] || "",
          dateObj: parseDate(record["D"] || ""),
          amount: parseAmount(record["T"] || record["U"] || ""),
          memo: record["M"] || "",
          cleared: record["C"] || "",
          category: record["L"] || "",
          payee: record["P"] || "",
          action: record["N"] || "",
          security: record["Y"] || "",
          price: parseAmount(record["I"] || ""),
          quantity: parseAmount(record["Q"] || ""),
          commission: parseAmount(record["O"] || ""),
          splits: splits.map((s) => ({ ...s, id: randomUUID() })),
        });
        record = {};
        splits = [];
        addresses = [];
        continue;
      }

      if (currentSection === "cat") {
        categories.push({
          id: randomUUID(),
          name: record["N"] || "",
          description: record["D"] || "",
          income: "I" in record,
          expense: "E" in record,
          taxRelated: (record["T"] || "") !== "" || (record["R"] || "") !== "",
        });
        record = {};
        continue;
      }

      if (currentSection === "security") {
        securities.push({
          id: randomUUID(),
          name: record["N"] || "",
          symbol: record["S"] || "",
          type: record["T"] || "",
        });
        record = {};
        continue;
      }

      record = {};
      splits = [];
      addresses = [];
      continue;
    }

    // Field lines
    const code = line[0];
    const value = line.substring(1);

    if (TRANSACTION_TYPES.has(currentSection ?? "")) {
      if (code === "S") {
        splits.push({ category: value, memo: "", amount: 0, percent: "" });
        continue;
      }
      if (code === "E" && splits.length) {
        splits[splits.length - 1].memo = value;
        continue;
      }
      if (code === "$" && splits.length) {
        splits[splits.length - 1].amount = parseAmount(value);
        continue;
      }
      if (code === "%" && splits.length) {
        splits[splits.length - 1].percent = value;
        continue;
      }
    }

    if (code === "A") {
      addresses.push(value);
      continue;
    }

    record[code] = value;
  }

  return { accounts, transactions, investments, categories, securities };
}
