# fable-pack

Claude Code 세션의 **엔지니어링 의사결정 기록**을 프로젝트에 영속화하고, spec/context/done 품질 게이트를 강제하는 개인 워크플로우 플러그인.

목적: AI 협업 세션은 끝나면 사라진다 — 무엇을 근거로 요구사항을 해석했는지, 어떤 대안을 왜 기각했는지, 무엇이 검증되어야 done인지가 코드에 남지 않는다. 이 플러그인은 그 의사결정 산출물(요구사항 분석, 컨텍스트 선택 근거, 기각 대안, 수용 기준, 검증 증거)을 프로젝트 안의 구조화된 문서로 남기고, 작성 전에는 구현을 막는 게이트로 **작업 표준을 강제**한다. 산출물은 코드 리뷰·감사·회고·온보딩 자료로 쓰인다. **사적 사고(chain of thought)는 기록하지 않음** — 가시적 산출물만 기록.

## 모델 게이팅: 지정 모델 세션이 아니면 아무것도 안 함

기록·게이트의 적용 범위를 특정 모델 세션으로 한정하는 **개인 설정상의 안전장치**다 — 내가 이 워크플로우를 쓰기로 한 세션에서만 동작하고, 나머지 세션에는 일절 간섭하지 않기 위함. 활성 모델은 세션 transcript에서 감지한다 (`/model` 전환 즉시 반영). 모델 id에 `fable`이 없으면:

- 기록 0 — 어떤 로그 파일도 쓰지 않음
- 차단 0 — 게이트가 어떤 도구 호출도 막지 않음
- 출력 0 — 에이전트 컨텍스트에 아무것도 주입하지 않음 → **토큰 비용 0**
- 디스크 쓰기 0 — `fable-disk/`조차 만들지 않음

Opus/Sonnet/Haiku 세션에는 존재 자체가 보이지 않는다. 기록을 끈(`off`) 프로젝트에서도 동일하게 완전 무음이다.

## 토큰 비용: 왜 거의 공짜인가

기록은 전부 **harness 측 hook 프로세스**에서 실행된다 — 파일 read/edit/명령/프롬프트/응답 캡처는 모델 컨텍스트를 거치지 않으므로 **모델 토큰을 1도 쓰지 않는다**. 에이전트 컨텍스트에 들어가는 것은 행동 변경이 필요한 신호뿐:

| 주입되는 것 | 시점 | 크기 |
|---|---|---|
| 세션 시작 상태 1줄 | `on`인 프로젝트에서 세션 시작 시 | ~30 tok |
| 게이트 에스컬레이션 공지 | 작업성 프롬프트로 trace 자동 시작될 때 1회 | ~90 tok |
| 게이트 차단 사유 | **에러 목록이 달라졌을 때만** 전문, 동일하면 1줄 | 가변 |
| done 게이트 경고 | **상태가 변했을 때만** (동일 에러 반복 주입 안 함) | 가변 |
| 슬래시 커맨드 메타 | 상시 | ~100 tok |

반복 억제는 해시 기반 상태 변화 감지라서 **품질 손실이 없다**: 새 에러가 생기면 즉시 전문으로 다시 보인다. 같은 이유로 trace 자체도 군살을 줄인다 — 같은 파일 재독에 placeholder를 중복 생성하지 않고, 에이전트가 게이트 장부 작성을 위해 `fable-disk/`를 읽는 행위는 작업 컨텍스트가 아니므로 기록에서 제외한다 (자기 기록 루프 차단).

## 데이터 보안

- **로컬 전용.** 모든 기록은 작업 중인 프로젝트의 `fable-disk/` 평문 파일로만 쓰인다. 네트워크 전송, 외부 서비스, 텔레메트리 없음 — 코드 어디에도 소켓/HTTP 호출이 없다 (전부 stdlib 파일 I/O, 직접 감사 가능한 ~2k LOC Python).
- **시크릿 자동 마스킹.** 프롬프트·명령·도구 입력에서 `sk-…`, `ghp_…`, `AKIA…`, JWT, `Bearer …`, `API_KEY=…` 류 패턴을 기록 전에 `<redacted>` 처리. 키 이름이 secret/token/password인 필드는 값 자체를 기록하지 않음.
- **사적 사고 미기록.** transcript에서 텍스트 응답만 추출하고 thinking 블록은 명시적으로 건너뜀 — 기록 대상은 의사결정 아티팩트지 chain of thought가 아님.
- **유출 경로 차단.** `fable-disk/`는 .gitignore 권장 (이 repo는 기본 처리됨) — 실수 push 방지. 일괄 삭제는 `uninstall.sh --purge-data` 한 번.
- **우회 감사 추적.** `PACK_BYPASS=1`로 게이트를 우회하면 그 사실이 meta에 기록되고, 우회된 trace는 골든 코퍼스 승격이 자동 거부된다 — 조용한 변조 불가.

## 설치

Claude Code 안에서 두 줄:

```text
/plugin marketplace add SihyeonJeon/fable-pack
/plugin install fable-pack@fable-pack-marketplace
```

요구사항: `python3` (표준 라이브러리만 사용, PyYAML은 있으면 사용).

제거:

```text
/plugin uninstall fable-pack
```

## 사용법

### 기록 켜기/끄기

```text
/fable-pack:on     ← 이 프로젝트에서 기록 시작
/fable-pack:off    ← 기록 종료
```

`on`은 명시적으로 `off` 하기 전까지 유지된다 (세션을 넘어 지속). 켜져 있는 동안:

| 프롬프트 종류 | 동작 |
|---|---|
| 질문/잡담 | ambient LIGHT trace에 기록만, 차단 없음 |
| 작업 지시 (구현/수정/리팩터링 …) | STANDARD trace 자동 시작 + 게이트 강제 |
| 민감 작업 (인증/결제/마이그레이션/보안 …) | HEAVY trace 자동 시작 + 강화 게이트 |

게이트가 강제되면 에이전트는 `context_pack.yaml`, `task_spec/final.yaml`, decision/observation 로그를 채우기 전까지 구현 edit이 차단된다. 무엇이 자동 기록되는가: 사용자 프롬프트, 파일 read/edit, 명령 실행, 계획(plan mode 전문), todo 분해, 서브에이전트 위임 프롬프트, 어시스턴트 응답 텍스트, 세션 경계/컴팩션 이벤트.

### 수동 제어

자동 판정 대신 직접 지정하려면:

```text
/fable-pack:start <목표>    ← grade 추정 후 gated trace 시작
/fable-pack:status          ← 활성 task와 게이트 상태
/fable-pack:done            ← done 게이트 통과 시 trace 종료
/fable-pack:promote         ← 리뷰 완료된 trace를 골든 코퍼스로 승격
```

CLI 직접 호출도 가능:

```sh
python3 <plugin-root>/adapters/claude-code/scripts/pack task start --goal "..." --grade HEAVY
python3 <plugin-root>/adapters/claude-code/scripts/pack validate --gate all
python3 <plugin-root>/adapters/claude-code/scripts/pack corpus promote --task-id <id>
```

### 데이터 위치

모든 기록은 **작업 중인 프로젝트**의 루트에 쌓인다 (이 repo가 아님):

```text
<your-project>/fable-disk/
  trace/<task-id>/    # 프롬프트, 읽기/수정/명령 로그, 결정 이벤트, spec, 검증 보고
  corpus/             # 리뷰를 통과한 모범/결함 사례, 정제된 체크리스트 규칙
```

`fable-disk/`는 각자 프로젝트에서 .gitignore 처리 권장. 자세한 trace 레이아웃과 게이트 규칙은 [fable-pack/README.md](fable-pack/README.md) 참고.

### 코퍼스 워크플로우 — 작업 기록을 팀 자산으로

1. `/fable-pack:on` — 켜두고 평소처럼 작업
2. 작업성 프롬프트마다 trace 자동 생성, 게이트가 spec 작성 강제
3. `/fable-pack:done` — 검증 증거 채운 뒤 종료
4. `human_review.yaml`에 rating 기입 (`exemplary`/`normal`/`flawed`)
5. `/fable-pack:promote` — `corpus/fable_golden/`(또는 `flawed_examples/`)으로 승격

## 개발

```sh
python3 -m unittest tests.test_pack_smoke    # 테스트 (현재 26개)
```

구조: `fable-pack/core/` (lib·schemas·rules·protocols), `fable-pack/adapters/claude-code/` (hooks·CLI·설치 스크립트), `fable-pack/commands/` (슬래시 커맨드), `fable-pack/hooks/hooks.json` (plugin hook 선언). 플러그인 없이 프로젝트 단위로 쓰려면 `sh fable-pack/adapters/claude-code/install.sh`, 제거는 `sh fable-pack/adapters/claude-code/uninstall.sh`.
