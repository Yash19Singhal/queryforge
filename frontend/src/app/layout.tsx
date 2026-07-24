import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "QueryForge — SQL Query Optimizer",
  description:
    "Paste your SQL queries and get instant optimizations, query plan visualizations, index suggestions, and performance analysis. Built with a retro arcade aesthetic.",
  keywords: [
    "SQL",
    "query optimizer",
    "database",
    "PostgreSQL",
    "MySQL",
    "SQLite",
    "index suggestions",
    "query plan",
  ],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
