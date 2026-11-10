import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'TradeFlow — Options Trading Dashboard',
  description: 'Live options trading dashboard with watchlists, charts, and options chain.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
