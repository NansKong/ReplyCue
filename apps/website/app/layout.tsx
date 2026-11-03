import type { Metadata } from 'next';
import '@fontsource/geist/400.css';
import '@fontsource/geist/500.css';
import '@fontsource/geist/600.css';
import './globals.css';
export const metadata: Metadata = { title: 'ReplyCue — Stay in the conversation', description: 'Your experience. The right context. A calmer conversation. A Windows interview preparation and assistance workspace.' };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
