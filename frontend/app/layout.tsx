import "./globals.css";

export const metadata = {
  title: "Groundwork | Security Verification Agent",
  description: "Enterprise Security Questionnaire Grounding & Hallucination Prevention Pipeline",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
