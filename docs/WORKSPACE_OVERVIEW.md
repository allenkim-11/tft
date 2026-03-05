# Workspace Overview

프로젝트 내 핵심 폴더/파일 역할 요약입니다.

## 1) 프론트엔드
- `src/app/components/champion-list.tsx`: Champion Index 화면
- `src/app/components/scoring-results-view.tsx`: Raw Data(탱커/딜러 점수) 화면
- `src/app/components/champion-data.ts`: 인덱스 데이터 로딩/가공(현재 CP=Raw score 매핑)
- `src/app/data/tft16_champion_weight.json`: Index에서 직접 사용하는 데이터

## 2) 스코어링
- `tft_dealer_scoring.py`: 딜러 점수 산출
- `tank_scoring.py`: 탱커 점수 산출
- `tft_dealer_scoring_results.json`: 딜러 결과 출력
- `tank_scoring_results.json`: 탱커 결과 출력

## 3) 데이터 파이프라인
- `data/champions16_6.json`: 스코어링 기준 최신 데이터
- `data/token.json`: token 오버라이드
- `data/extract_set16_champions.py`: CDragon 추출
- `data/generate_desc_mapping.py`: desc 변수 치환
- `data/generated/16_6/*`: 16.6 생성 산출물
- `data/archive/16_5/*`: 16.5 백업

## 4) 실행 순서(일반)
1. 데이터 갱신: `data/champions16_6.json` 업데이트
2. 점수 생성: `python tft_dealer_scoring.py` / `python tank_scoring.py`
3. 프론트 확인: `npm run dev` (또는 `npm run build`)

## 5) 협업 팁
- 버전 비교는 `data/archive/`와 `data/generated/` 기준으로 수행
- 화면 이상 시, 먼저 `src/app/data/tft16_champion_weight.json`과 스코어 결과 JSON 동기화 여부를 확인
