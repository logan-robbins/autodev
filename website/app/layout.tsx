import type { Metadata } from 'next';
import { Geist, Geist_Mono } from 'next/font/google';
import './globals.css';
const geistSans = Geist({ variable: '--font-geist-sans', subsets: ['latin'] });
const geistMono = Geist_Mono({
  variable: '--font-geist-mono',
  subsets: ['latin'],
});
export const metadata: Metadata = {
  title: 'Autodev — Frontier quality. Face-melting speed.',
  description:
    'The AI-powered human hybrid agency. Extraordinary engineers and our proprietary Autodev platform deliver agentic software development at scale.',
  icons: { icon: '/favicon.svg' },
  openGraph: {
    title: 'Autodev — Human × AI',
    description: 'Frontier engineering. Agentic execution. Verified delivery.',
  },
  twitter: {
    card: 'summary',
    title: 'Autodev — Human × AI',
    description: 'Frontier quality. Face-melting speed.',
  },
};
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className={`${geistSans.variable} ${geistMono.variable}`}>
        {children}
      </body>
    </html>
  );
}
