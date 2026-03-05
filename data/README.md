# Data Folder Guide

이 폴더는 **Set16 데이터 원본/가공/아카이브**를 분리해 관리합니다.

## 현재 기준(운영)
- `champions16_6.json`: 스코어링 입력으로 쓰는 최신 Set16.6 원본(토큰 치환 포함)
- `token.json`: 수동 토큰 매핑 오버라이드
- `extract_set16_champions.py`: CDragon에서 set 챔피언 추출
- `generate_desc_mapping.py`: token 매핑 + desc 값 치환

## 아카이브
- `archive/16_5/champions16_5.json`: 이전 16.5 기준 파일
- `archive/16_5/set16_champions_full.json`: 16.5 추출 중간산출물

## 16.6 가공 산출물
- `generated/16_6/champions16_6_list.json`: 치환 완료 리스트 형태
- `generated/16_6/set16_champions_full_16_6.json`: 16.6 전체 추출본
- `generated/16_6/tft16_6_auto_map.json`: token->variable 매핑 결과
- `generated/16_6/tft16_6_auto_report.json`: 매핑 리포트
- `generated/16_6/tft16_6_unresolved.json`: 미해결 token

## 주의
- 앱 화면은 `src/app/data/tft16_champion_weight.json`을 직접 읽습니다.
- 스코어링은 루트 스크립트(`tft_dealer_scoring.py`, `tank_scoring.py`)가 `data/champions16_6.json`을 기본 입력으로 사용합니다.
