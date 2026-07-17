# 온톨로지 프리셋 가이드

에이전트는 문서 폴더를 훑은 뒤 **추천 1개**를 고르고, 사용자 승인 후 `bootstrap_wiki.py --preset …` 에 넣는다.

## lecture — 강의안·교육

**신호:** 파일명에 강의/교안/교재/커리큘럼/교육/특강, pptx·pdf 다수, 기관명 폴더

**폴더:** sources, concepts, curriculum, messages, methods, practices, entities, catalog, queries

**검색 계약 예:**
- 이 주제 강의안 어디? → concepts.sources + curriculum + catalog
- 어떻게 설명했지? → methods + messages

## research — 연구·논문

**신호:** pdf 논문, notes, arxiv, 방법론·실험 용어

**폴더:** sources, concepts, methods, entities, catalog, queries

## project — 코딩 프로젝트

**신호:** 여러 git 루트, README, package.json, 앱/도구 이름

**폴더:** projects(스택 줄 필수), purpose, pattern, concepts, entities, sources, queries

## mixed — 혼합 (기본)

강의+프로젝트+메모가 섞이면 선택. 폴더가 가장 넓다.

## 추천 절차

1. 상위 폴더명 20개 + 확장자 분포 요약
2. 위 표로 1개 추천 + 한 줄 이유
3. 사용자가 바꾸면 그 preset으로 bootstrap
4. schema.md 는 bootstrap 후 사용자가 폴더 추가를 원하면 병합만 (대규모 재작성 금지)
