import type { Metadata } from 'next';
import '@fontsource/geist/400.css';
import '@fontsource/geist/500.css';
import '@fontsource/geist/600.css';
import './globals.css';

const title = 'ReplyCue — Practice for your next interview';
const description = 'Explore the floating answer reader and try the free Windows sign-in beta.';
const shareImage = { url: '/replycue-share.png', width: 1200, height: 630, alt: 'ReplyCue Windows sign-in beta with a sample answer in the floating reader' };

export const metadata: Metadata = {
  metadataBase: new URL('https://reply-cue.vercel.app'),
  title,
  description,
  openGraph: { type: 'website', siteName: 'ReplyCue', title, description, images: [shareImage] },
  twitter: { card: 'summary_large_image', title, description, images: [shareImage] },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
