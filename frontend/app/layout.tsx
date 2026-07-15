import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Airco Insights — Financial Categorization Engine',
  description:
    'Upload your bank statement PDF and get a structured, categorized financial report. No insights, no predictions — just clean categorization.',
  icons: {
    icon: '/favicon.ico',
    apple: '/apple-touch-icon.png',
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-white text-black antialiased">
        {children}
      </body>
    </html>
  )
}
