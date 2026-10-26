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
    <html lang="en" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `try{var t=localStorage.getItem('airco-theme');if(t==='dark'||(!t&&window.matchMedia('(prefers-color-scheme: dark)').matches)){document.documentElement.classList.add('dark')}}catch(e){}`,
          }}
        />
      </head>
      <body className="min-h-screen bg-[#f4f7fb] text-slate-900 antialiased transition-colors duration-200 dark:bg-[#061022] dark:text-slate-100">
        {children}
      </body>
    </html>
  )
}
