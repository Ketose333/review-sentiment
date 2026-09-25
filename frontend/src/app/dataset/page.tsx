import type { Metadata } from "next";
import { DatasetInsights } from "@/components/dataset/DatasetInsights";

export const metadata: Metadata = {
  title: "데이터 탐색 · 영화 리뷰 감성 분석",
  description: "학습에 사용한 NSMC 리뷰의 레이블·길이·빈출 단어 분포를 확인하세요.",
};

export default function DatasetPage() {
  return <DatasetInsights />;
}
