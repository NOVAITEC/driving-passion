import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'Driving Passion | Auto Import Calculator',
  description: 'Bereken direct je winstmarge op Duitse import auto\'s. BPM berekening, marktanalyse en AI taxatie in seconden.',
  keywords: ['auto import', 'BPM calculator', 'Duitse auto', 'import marge', 'driving passion'],
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="nl">
      <body className={inter.className}>{children}</body>
    </html>
  )
}
