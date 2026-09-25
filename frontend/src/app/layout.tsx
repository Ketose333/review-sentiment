import type { Metadata } from "next";
import { SiteFooter } from "@/components/layout/SiteFooter";
import { SiteHeader } from "@/components/layout/SiteHeader";
import "./globals.css";

export const metadata: Metadata = {
  title: "영화 리뷰 감성 분석",
  description: "한국어 영화 리뷰를 분석하고 모델 평가 범위를 확인하세요.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="ko"><body>
    <div className="site-shell">
      <SiteHeader />
      <main className="page-container">{children}</main>
      <SiteFooter />
    </div>
  </body></html>;
}
