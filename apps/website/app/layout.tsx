import type { Metadata } from 'next';
import '@fontsource/geist/400.css';
import '@fontsource/geist/500.css';
import '@fontsource/geist/600.css';
import './globals.css';

const title = 'ReplyCue — Practice for your next interview';
const description = 'ReplyCue is a Windows interview practice app with live transcription, AI answer suggestions, résumé and job description context, and a free one-hour trial.';
const shareImage = { url: '/replycue-share.png', width: 1200, height: 630, alt: 'ReplyCue for Windows with a sample answer in the floating reader' };

export const metadata: Metadata = {
  metadataBase: new URL('https://reply-cue.vercel.app'),
  verification: { google: 'ZaxrNCxI1EwiqKzPK773u98hPwxkNLdNH9UK8KPcSCE' },
  title,
  description,
  openGraph: { type: 'website', siteName: 'ReplyCue', title, description, images: [shareImage] },
  twitter: { card: 'summary_large_image', title, description, images: [shareImage] },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
