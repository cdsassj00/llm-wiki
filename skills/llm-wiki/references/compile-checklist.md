# 컴파일 체크리스트

## 페이지 frontmatter

```yaml
---
type: source | concept | curriculum | message | method | practice | entity | project | purpose | pattern | catalog | query
title: "실제 제목"
sources:
  - "원본파일명"
created: YYYY-MM-DD
updated: YYYY-MM-DD
---
```

## 링크

- `[[페이지 제목]]` 타겟 = 그 페이지의 `title:`
- 별칭: `[[실제 제목|표시]]`

## 소스 페이지 (sources/)

- 3~6문장 요약 + 구성 + 연결 개념 3개 이상
- 가능하면 `file://` 원본·추출 경로

## 개념 (concepts/)

- 정의 + 이 위키에서의 쓰임 + 관련 링크
- 새 소스면 sources 목록에 파일명 추가, updated 갱신

## 카탈로그 (catalog/) — 대량일 때

- **상위 폴더 1개 = 페이지 1개**
- 표: 상대경로 | 추정 주제 | 상태(미심화/심화)
- 문서 전체를 다 읽지 않아도 됨

## manifest

컴파일 후 해당 항목:

```json
"status": "compiled",
"compiled_at": "ISO-8601"
```

## 마무리 명령

```bash
python scripts/reindex.py --root <wiki>
python scripts/build_graph_view.py --root <wiki>
python scripts/open_graph.py --root <wiki>
```
