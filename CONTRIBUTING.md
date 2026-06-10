# Contributing

## 룰 기여 — 가장 가치 있는 기여

trace에서 정제된 게이트 규칙·체크리스트는 프로젝트 코드가 섞이지 않는 일반화 산출물. 사용 중 쌓인 룰을 공유하면 모든 사용자의 게이트가 강해짐.

기여 절차:

1. 내보내기

```sh
python3 <plugin-root>/adapters/claude-code/scripts/pack rules export --out rules_export.yaml
```

2. 자가 검토 — 프로젝트 식별 정보, 내부 경로, 고유 명칭 없음 확인
3. `contrib/rules/<github-id>-<주제>.yaml`로 추가해 PR

자동 처리되는 것: 시크릿 패턴 마스킹, trace 식별자 제거, 중복 제거. `--include-examples`는 프로젝트 코드 인용 가능성이 있어 기본 제외 — 포함 시 직접 검토 필수.

수합된 룰은 검토 후 `core/rules/`의 기본 게이트 규칙으로 승격.

## 코드 기여

- 테스트: `python3 -m unittest tests.test_pack_smoke`
- 원칙: 로컬 전용 (네트워크 코드 금지), 기록 품질 우선, hook 출력은 상태 변화 시에만
- PR 전 테스트 green 확인

## 이슈

grade 오판 사례 환영 — 오판된 프롬프트와 기대 grade를 함께 제출
