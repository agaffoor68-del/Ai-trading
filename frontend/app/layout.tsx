import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'AlphaTradePro - Autonomous Options Trading Platform',
  description: 'Professional algorithmic trading dashboard with AI signals, options chain, and risk management',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="scroll-smooth">
      <body className="bg-true-black text-white min-h-screen overflow-x-hidden">
        <div className="relative min-h-screen">
          {children}
        </div>
      </body>
    </html>
  );
}