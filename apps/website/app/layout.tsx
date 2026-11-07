import type { Metadata } from 'next';
import '@fontsource/geist/400.css';
import '@fontsource/geist/500.css';
import '@fontsource/geist/600.css';
import './globals.css';

const title = 'ReplyCue — Live AI Interview Assistant for Windows';
const description = 'Get live interview transcription and real-time AI answer suggestions tailored to your résumé and job description. Try ReplyCue for Windows with a free one-hour trial.';
const shareImage = { url: '/replycue-share.png', width: 1200, height: 630, alt: 'ReplyCue for Windows with a sample answer in the floating reader' };

export const metadata: Metadata = {
  metadataBase: new URL('https://reply-cue.vercel.app'),
  applicationName: 'ReplyCue',
  verification: { google: 'ZaxrNCxI1EwiqKzPK773u98hPwxkNLdNH9UK8KPcSCE' },
  title,
  description,
  icons: {
    icon: [
      { url: '/favicon.ico', sizes: 'any' },
      { url: '/icon-48x48.png', sizes: '48x48', type: 'image/png' },
      { url: '/icon-96x96.png', sizes: '96x96', type: 'image/png' },
      { url: '/icon-192x192.png', sizes: '192x192', type: 'image/png' },
    ],
    apple: [
      { url: '/apple-icon.png', sizes: '180x180', type: 'image/png' },
    ],
  },
  openGraph: { type: 'website', siteName: 'ReplyCue', title, description, images: [shareImage] },
  twitter: { card: 'summary_large_image', title, description, images: [shareImage] },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
