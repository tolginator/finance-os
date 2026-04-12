import { describe, it, expect } from "vitest";
import {
  parseQif,
  parseDate,
  parseAmount,
  formatDate,
} from "../src/tools/qif-parser.js";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { registerQifTool } from "../src/tools/qif.js";

// ============================================================================
// parseDate
// ============================================================================

describe("parseDate", () => {
  it("parses M/D/YYYY format", () => {
    const d = parseDate("1/31/2020");
    expect(d).not.toBeNull();
    expect(d!.getFullYear()).toBe(2020);
    expect(d!.getMonth()).toBe(0); // January
    expect(d!.getDate()).toBe(31);
  });

  it("parses M/D/YY with century inference", () => {
    const d = parseDate("2/10/20");
    expect(d).not.toBeNull();
    expect(d!.getFullYear()).toBe(2020);
  });

  it("parses M/D/YY for years >= 50 as 1900s", () => {
    const d = parseDate("6/15/98");
    expect(d).not.toBeNull();
    expect(d!.getFullYear()).toBe(1998);
  });

  it("parses apostrophe format M/D'YYYY", () => {
    const d = parseDate("1/31'2020");
    expect(d).not.toBeNull();
    expect(d!.getFullYear()).toBe(2020);
  });

  it("parses dash format M-D-YYYY", () => {
    const d = parseDate("1-31-2020");
    expect(d).not.toBeNull();
    expect(d!.getFullYear()).toBe(2020);
  });

  it("parses 'D Month YYYY' format", () => {
    const d = parseDate("25 December 2006");
    expect(d).not.toBeNull();
    expect(d!.getFullYear()).toBe(2006);
    expect(d!.getMonth()).toBe(11);
    expect(d!.getDate()).toBe(25);
  });

  it("returns null for empty input", () => {
    expect(parseDate("")).toBeNull();
  });

  it("returns null for garbage input", () => {
    expect(parseDate("not-a-date")).toBeNull();
  });
});

// ============================================================================
// parseAmount
// ============================================================================

describe("parseAmount", () => {
  it("parses positive amounts", () => {
    expect(parseAmount("1234.56")).toBe(1234.56);
  });

  it("parses negative amounts", () => {
    expect(parseAmount("-500.00")).toBe(-500);
  });

  it("strips comma separators", () => {
    expect(parseAmount("1,234,567.89")).toBe(1234567.89);
  });

  it("strips currency symbols", () => {
    expect(parseAmount("$1234.56")).toBe(1234.56);
  });

  it("returns 0 for empty input", () => {
    expect(parseAmount("")).toBe(0);
  });

  it("returns 0 for non-numeric input", () => {
    expect(parseAmount("abc")).toBe(0);
  });
});

// ============================================================================
// formatDate
// ============================================================================

describe("formatDate", () => {
  it("formats date as YYYY-MM-DD", () => {
    const d = new Date(2024, 0, 5); // Jan 5, 2024
    expect(formatDate(d)).toBe("2024-01-05");
  });
});

// ============================================================================
// parseQif
// ============================================================================

describe("parseQif", () => {
  const SAMPLE_QIF = `!Type:Bank
D1/15/2024
T-50.00
PGrocery Store
LFood:Groceries
^
D1/20/2024
T1500.00
PEmployer Inc
LIncome:Salary
^
`;

  it("parses banking transactions", () => {
    const data = parseQif(SAMPLE_QIF);
    expect(data.transactions).toHaveLength(2);
    expect(data.transactions[0].payee).toBe("Grocery Store");
    expect(data.transactions[0].amount).toBe(-50);
    expect(data.transactions[0].category).toBe("Food:Groceries");
  });

  it("parses dates correctly", () => {
    const data = parseQif(SAMPLE_QIF);
    expect(data.transactions[0].dateObj).not.toBeNull();
    expect(data.transactions[0].dateObj!.getFullYear()).toBe(2024);
  });

  it("parses account blocks", () => {
    const qif = `!Account
NChecking
TBank
^
!Type:Bank
D3/1/2024
T100.00
PDeposit
^
`;
    const data = parseQif(qif);
    expect(Object.keys(data.accounts)).toHaveLength(1);
    expect(data.accounts["Checking"]).toBeDefined();
    expect(data.accounts["Checking"].type).toBe("Bank");
    expect(data.transactions).toHaveLength(1);
    expect(data.transactions[0].account).toBe("Checking");
  });

  it("parses investment transactions", () => {
    const qif = `!Type:Invst
D2/15/2024
NBuy
YAAPL
I150.00
Q10
O9.99
T-1509.99
^
`;
    const data = parseQif(qif);
    expect(data.investments).toHaveLength(1);
    expect(data.investments[0].action).toBe("Buy");
    expect(data.investments[0].security).toBe("AAPL");
    expect(data.investments[0].price).toBe(150);
    expect(data.investments[0].quantity).toBe(10);
    expect(data.investments[0].commission).toBe(9.99);
  });

  it("parses categories", () => {
    const qif = `!Type:Cat
NFood:Groceries
DGrocery purchases
E
^
NIncome:Salary
DSalary income
I
^
`;
    const data = parseQif(qif);
    expect(data.categories).toHaveLength(2);
    expect(data.categories[0].name).toBe("Food:Groceries");
    expect(data.categories[0].expense).toBe(true);
    expect(data.categories[0].income).toBe(false);
    expect(data.categories[1].income).toBe(true);
  });

  it("parses split transactions", () => {
    const qif = `!Type:Bank
D1/15/2024
T-150.00
PMulti-category
SFood:Groceries
$-100.00
SHousehold
$-50.00
^
`;
    const data = parseQif(qif);
    expect(data.transactions).toHaveLength(1);
    expect(data.transactions[0].splits).toHaveLength(2);
    expect(data.transactions[0].splits[0].category).toBe("Food:Groceries");
    expect(data.transactions[0].splits[0].amount).toBe(-100);
  });

  it("handles empty input gracefully", () => {
    const data = parseQif("");
    expect(data.transactions).toHaveLength(0);
    expect(data.investments).toHaveLength(0);
    expect(Object.keys(data.accounts)).toHaveLength(0);
  });

  it("handles malformed lines without crashing", () => {
    const qif = `!Type:Bank
D1/1/2024
Tgarbage
^
`;
    expect(() => parseQif(qif)).not.toThrow();
    const data = parseQif(qif);
    expect(data.transactions).toHaveLength(1);
    expect(data.transactions[0].amount).toBe(0);
  });

  it("uses fallback account when no account block present", () => {
    const qif = `!Type:Bank
D1/1/2024
T100
^
`;
    const data = parseQif(qif, "My Checking");
    expect(data.transactions[0].account).toBe("My Checking");
  });
});

// ============================================================================
// parseQif — Security sections
// ============================================================================

describe("parseQif security sections", () => {
  it("parses !Type:Security blocks into securities array", () => {
    const qif = `!Type:Security
NAAPL Inc
SAAPL
TStock
^
!Type:Security
NMSFT Corp
SMSFT
TMutual Fund
^
`;
    const data = parseQif(qif);
    expect(data.securities).toHaveLength(2);
    expect(data.securities[0].name).toBe("AAPL Inc");
    expect(data.securities[0].symbol).toBe("AAPL");
    expect(data.securities[0].type).toBe("Stock");
    expect(data.securities[1].name).toBe("MSFT Corp");
    expect(data.securities[1].symbol).toBe("MSFT");
    expect(data.securities[1].type).toBe("Mutual Fund");
  });
});

// ============================================================================
// QIF MCP tool registration
// ============================================================================

describe("qif-query tool", () => {
  it("registers without error", () => {
    const server = new McpServer({ name: "test", version: "0.0.1" });
    expect(() => registerQifTool(server)).not.toThrow();
  });
});
