import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'TVS Recovery Lab',
  icons: { icon: '/favicon.svg' },
  description: 'Recovery estimates, lending comparisons and transparent portfolio stress scenarios. Local hackathon POC.',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        {children}
      </body>
    </html>
  );
}
