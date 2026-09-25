"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { NAV_ITEMS } from "@/constants";

export function SiteHeader() {
  const pathname = usePathname();
  return <header className="site-header">
    <div className="page-container header-inner">
      <Link className="brand" href="/">영화 리뷰 감성 분석</Link>
      <nav className="site-nav" aria-label="주요 화면">
        {NAV_ITEMS.map((item) => <Link
          key={item.href}
          href={item.href}
          className={`nav-link ${pathname === item.href ? "is-current" : ""}`}
          aria-current={pathname === item.href ? "page" : undefined}
        >{item.label}</Link>)}
      </nav>
    </div>
  </header>;
}
