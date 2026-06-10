# fable-pack

Claude Code 세션의 엔지니어링 의사결정 기록과 품질 게이트

요구사항 해석, 컨텍스트 선택 근거, 기각 대안, 수용 기준, 검증 증거를 프로젝트 안의 구조화된 문서로 보존. 스펙이 작성되기 전에는 구현 수정 차단. 산출물은 코드 리뷰, 감사, 회고, 온보딩 자료로 사용.

기록 대상은 가시적 산출물만 — private chain of thought 미기록

## 설치

```text
/plugin marketplace add SihyeonJeon/fable-pack
/plugin install fable-pack@fable-pack-marketplace
```

- 요구사항: `python3` (표준 라이브러리만, PyYAML 선택)
- 제거: `/plugin uninstall fable-pack`

## 기록 켜기 / 끄기

```text
/fable-pack:on     켜기 — off 전까지 유지 (세션 넘어 지속)
/fable-pack:off    끄기
```

켜진 동안 프롬프트별 자동 분류:

| 프롬프트 | 동작 |
| --- | --- |
| 질문, 잡담 | ambient 기록만 — 차단 없음 |
| 구현, 수정, 리팩터링 | STANDARD trace 자동 시작 + 게이트 |
| 인증, 결제, 마이그레이션, 보안 | HEAVY trace 자동 시작 + 강화 게이트 |

게이트 작동 중: `context_pack.yaml`, `task_spec/final.yaml`, decision/observation 기록 완료 전 구현 수정 차단

## 자동 기록 범위

- 사용자 프롬프트
- 파일 read / edit, 검색, 명령 실행
- plan mode 계획 전문, todo 분해
- 서브에이전트 위임 프롬프트
- 어시스턴트 응답 텍스트
- 세션 경계, 컴팩션 이벤트

## 수동 커맨드

```text
/fable-pack:start <목표>    grade 지정 trace 시작
/fable-pack:status          활성 task와 게이트 상태
/fable-pack:timeline        전 로그 병합 타임라인 — 프롬프트→읽기→관찰→결정→수정 흐름 재구성
/fable-pack:done            done 게이트 통과 시 종료
/fable-pack:shadow <model>  비교 trace 페어 스캐폴드 — 문서화 갭 분석
/fable-pack:promote         리뷰 완료 trace를 코퍼스로 승격
```

CLI 직접 호출:

```sh
python3 <plugin-root>/adapters/claude-code/scripts/pack task start --goal "..." --grade HEAVY
python3 <plugin-root>/adapters/claude-code/scripts/pack validate --gate all
python3 <plugin-root>/adapters/claude-code/scripts/pack corpus promote --task-id <id>
```

## 모델 게이팅

적용 범위를 지정 모델 세션으로 한정하는 개인 설정 안전장치. 모델 감지는 세션 transcript 기준 — `/model` 전환 즉시 반영.

모델 id에 `fable` 없음 또는 기록 off:

- 기록 없음
- 도구 차단 없음
- 컨텍스트 주입 없음 — 토큰 비용 0
- 디스크 쓰기 없음

## 토큰 비용

기록은 전부 harness 측 hook 프로세스 실행 — 모델 토큰 소비 없음. 에이전트 컨텍스트 주입은 행동 변경 신호만:

| 주입 | 시점 | 크기 |
| --- | --- | --- |
| 세션 시작 상태 1줄 | on 프로젝트 세션 시작 | ~30 tok |
| 게이트 에스컬레이션 공지 | trace 자동 시작 시 1회 | ~90 tok |
| 게이트 차단 사유 | 에러 목록 변경 시만 전문, 동일하면 1줄 | 가변 |
| done 게이트 경고 | 상태 변경 시만 | 가변 |
| 슬래시 커맨드 메타 | 상시 | ~100 tok |

- 반복 억제는 해시 기반 상태 변화 감지 — 새 에러는 즉시 전문 표시
- 같은 파일 재독 시 placeholder 중복 생성 없음
- 게이트 장부용 `fable-disk/` 읽기는 기록 제외 — 자기 기록 루프 차단

## 데이터 보안

- 로컬 전용 저장 — 작업 프로젝트의 `fable-disk/` 평문 파일, 네트워크 전송·외부 서비스·텔레메트리 없음 (stdlib 파일 I/O만, 직접 감사 가능)
- 시크릿 자동 마스킹 — `sk-…`, `ghp_…`, `AKIA…`, JWT, `Bearer …`, `KEY=값` 패턴 기록 전 `<redacted>` 처리
- thinking 블록 미추출 — transcript에서 텍스트 응답만 수집
- 유출 경로 차단 — `fable-disk/` gitignore 권장, 일괄 삭제는 `uninstall.sh --purge-data`
- 우회 감사 기록 — `PACK_BYPASS=1` 사용 시 meta에 기록, 해당 trace는 코퍼스 승격 차단

## 데이터 위치

기록은 작업 중인 프로젝트 루트에 저장 (이 repo 아님):

```text
<your-project>/fable-disk/
  trace/<task-id>/    프롬프트, 읽기/수정/명령 로그, 결정 이벤트, spec, 검증 보고
  corpus/             리뷰 통과 사례, 정제된 체크리스트 규칙
```

trace 레이아웃, 게이트 규칙 상세: [fable-pack/README.md](fable-pack/README.md)

## 코퍼스 워크플로우

1. `/fable-pack:on` — 켜두고 평소처럼 작업
2. 작업성 프롬프트마다 trace 자동 생성, 게이트가 spec 작성 강제
3. `/fable-pack:done` — 검증 증거 작성 후 종료
4. `human_review.yaml` rating 기입 — `exemplary` / `normal` / `flawed`
5. `/fable-pack:promote` — `corpus/fable_golden/` 또는 `flawed_examples/`로 승격
6. (선택) `pack rules export` — 정제 룰만 추출해 [기여](CONTRIBUTING.md) — 시크릿·trace 식별자 자동 제거, 프로젝트 코드 미포함

## 개발

```sh
python3 -m unittest tests.test_pack_smoke    # 35 tests
```

- `fable-pack/core/` — lib, schemas, rules, protocols
- `fable-pack/adapters/claude-code/` — hooks, CLI, 설치 스크립트
- `fable-pack/commands/` — 슬래시 커맨드
- `fable-pack/hooks/hooks.json` — plugin hook 선언
- 프로젝트 단위 설치: `sh fable-pack/adapters/claude-code/install.sh` / 제거: `uninstall.sh`
