import type { Metadata } from 'next';
import { Geist, Geist_Mono } from 'next/font/google';
import './globals.css';

const geistSans = Geist({
  variable: '--font-geist-sans',
  subsets: ['latin'],
});

const geistMono = Geist_Mono({
  variable: '--font-geist-mono',
  subsets: ['latin'],
});

export const metadata: Metadata = {
  title: 'ToolStorm — Break your tools. Trust your recovery.',
  description:
    'A zero-dependency Python library for deterministic tool failures, strict offline replay, and side-effect contracts. Explore the interactive agent resilience lab.',
  icons: { icon: '/favicon.svg' },
  metadataBase: new URL('https://toolstorm-shi1720.sg127977958.chatgpt.site'),
  openGraph: {
    title: 'ToolStorm — Give your agent a bad day.',
    description:
      'Inject the failure. Inspect the recovery. Keep the regression.',
    type: 'website',
  },
  twitter: { card: 'summary', title: 'ToolStorm — Agent Resilience Lab' },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        {children}
      </body>
    </html>
  );
}
