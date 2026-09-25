import type { Metadata } from "next";
import { ProjectAbout } from "@/components/about/ProjectAbout";

export const metadata: Metadata = {
  title: "프로젝트 소개 · 영화 리뷰 감성 분석",
  description: "NSMC 데이터셋, 비교 모델, 입력과 보관 정책을 설명합니다.",
};

export default function AboutPage() {
  return <ProjectAbout />;
}
