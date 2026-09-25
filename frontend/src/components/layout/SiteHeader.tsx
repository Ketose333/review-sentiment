"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { NAV_ITEMS, STREAMLIT_URL } from "@/constants";

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
      <a className="streamlit-link" href={STREAMLIT_URL} target="_blank" rel="noopener noreferrer">
        Streamlit 데모 바로가기 <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 13 13 3M5 3h8v8" /></svg>
      </a>
    </div>
  </header>;
}
