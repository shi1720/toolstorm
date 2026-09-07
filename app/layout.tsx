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
  title: 'ToolStorm — Test recovery from tool failures',
  description:
    'A Python library with no runtime dependencies for deterministic tool failures, strict offline replay, and side-effect contracts. Explore the interactive agent resilience lab.',
  icons: { icon: '/favicon.svg' },
  metadataBase: new URL('https://toolstorm-shi1720.sg127977958.chatgpt.site'),
  openGraph: {
    title: 'ToolStorm — Test recovery from tool failures',
    description:
      'Inject failures into Python tools, check committed effects, and replay recorded calls offline.',
    type: 'website',
  },
  twitter: { card: 'summary', title: 'ToolStorm — Python tool testing' },
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
