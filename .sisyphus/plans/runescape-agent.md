# RuneScape AI Agent - Acore Adapter

## TL;DR
> **Quick Summary**: Create an Acore Adapter that enables AI personas to play RuneScape (2004/09 private servers) autonomously. Users give high-level goals via Discord/CLI, agent executes them with personality.
> 
> **Deliverables**:
> - `adapters/runescape/` package
> - 2004scape client (port from existing repo)
> - 2009scape protocol implementation (RS2)
> - `RSAgentBrain` (LLM-powered decision making)
> - Integration with Acore persona system
> 
> **Estimated Effort**: XL (Protocol implementation + AI integration)
> **Parallel Execution**: NO - Sequential phases
> **Critical Path**: Framework Completion → 2004scape Port → 2009scape → Agent Brain
> **STATUS**: ⛔ **BLOCKED** - Requires `framework-expansion` completion

---

## Context

### Original Request
Create an AI agent that can play RuneScape private servers (2004scape, 2009scape).

### Technical Approach
- **2004scape**: Browserless client (port from existing repository)
- **2009scape**: Raw RS2 protocol implementation (packets, encryption, state management)
- **Integration**: Acore Adapter pattern (receives commands, emits events)
- **Decision Making**: Hybrid - user gives goals, LLM plans execution

### Dependencies
**This plan is BLOCKED until framework-expansion completes.**
- Requires `core/` abstractions (`AcoreContext`, `AcoreEvent`)
- Requires `adapters/` architecture pattern
- Requires Acore persona system integration points

---

## Work Objectives

### Core Objective
Build a game-playing AI that integrates with Acore as a first-class adapter.

### Concrete Deliverables
- `adapters/runescape/__init__.py` - Adapter entry point
- `adapters/runescape/client_2004.py` - 2004scape client (port)
- `adapters/runescape/client_2009.py` - 2009scape protocol implementation
- `adapters/runescape/brain.py` - LLM decision engine
- `adapters/runescape/actions.py` - Game action library
- `adapters/runescape/state.py` - Game state management
- Documentation for RS protocol integration

### Definition of Done
- [ ] Agent connects to 2004scape server and mines copper
- [ ] Agent connects to 2009scape server and completes Tutorial Island
- [ ] Discord command `/rs play @persona activity` works
- [ ] Agent reports progress via Acore chat system
- [ ] Agent exhibits persona personality while playing

### Must Have
- Server connection (both 2004 and 2009)
- Basic movement (walk to coordinates)
- Basic skilling (click object, wait, repeat)
- Inventory management
- Bank interface
- Acore persona integration
- Goal execution (user command → action sequence)

### Must NOT Have (Scope Boundaries)
- NO PvP against real players (too detectable)
- NO complex quest dialogue parsing (Phase 2)
- NO full grand exchange arbitrage (Phase 2)
- NO multi-account coordination (Phase 3)

---

## Verification Strategy

### Test Decision
- **Infrastructure**: pytest + mock RS servers
- **Automated tests**: YES (mock packet responses)
- **Strategy**: Unit tests for protocol, integration tests for full workflows

### QA Policy
- **Protocol**: Mock server responses, verify correct packets sent
- **Integration**: Test full "mine copper" workflow end-to-end
- **Persona**: Verify different personas make different decisions

---

## Execution Strategy

### Sequential Phases (Blocked Until Framework Done)

```
PHASE 1: 2004scape Port (Blocked: framework-expansion Wave 4)
├── Task 1: Port existing 2004scape bot to adapter pattern [deep]
├── Task 2: Create RS state management (position, inventory) [deep]
├── Task 3: Integrate with Acore event system [unspecified-high]
└── Task 4: Basic action library (walk, click, wait) [unspecified-high]

PHASE 2: 2009scape Protocol (Blocked: Phase 1)
├── Task 5: Implement RS2 packet protocol (revision 562+) [deep]
├── Task 6: ISAAC encryption for login [deep]
├── Task 7: Player/NPC update handlers [deep]
├── Task 8: Inventory/bank/equipment handlers [unspecified-high]
└── Task 9: Map/object system [deep]

PHASE 3: Agent Brain (Blocked: Phase 2)
├── Task 10: LLM goal planning ("get 99 mining" → steps) [ultrabrain]
├── Task 11: Action sequencing and error recovery [artistry]
├── Task 12: Personality injection (Dagoth Ur plays differently) [artistry]
└── Task 13: Learning from failures [deep]

PHASE 4: Integration (Blocked: Phase 3)
├── Task 14: Discord commands (/rs play, /rs status) [unspecified-high]
├── Task 15: CLI commands (rs play, rs stop) [quick]
├── Task 16: Progress reporting to Acore chat [unspecified-high]
└── Task 17: Screenshot capture and sharing [unspecified-high]

PHASE 5: Polish (Blocked: Phase 4)
├── Task 18: Anti-detection (human-like delays, variance) [artistry]
├── Task 19: Quest completion framework [deep]
└── Task 20: Documentation and examples [writing]
```

### Dependency Matrix
- **Phase 1**: Blocked by framework-expansion completion
- **Phase 2**: Depends on Phase 1
- **Phase 3**: Depends on Phase 2
- **Phase 4**: Depends on Phase 3
- **Phase 5**: Depends on Phase 4

**Total: 20 tasks across 5 sequential phases**

---

## TODOs

### Phase 1: 2004scape Port

- [ ] 1. Port Existing 2004scape Bot

  **What to do**:
  - Port existing 2004scape implementation from external repo
  - Refactor to fit Acore Adapter interface
  - Create `adapters/runescape/client_2004.py`

  **Must NOT do**:
  - Don't rewrite from scratch - port and adapt existing working code

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: None

  **Parallelization**:
  - **Blocked By**: framework-expansion complete
  - **Can Run In Parallel**: NO (Phase 1 is sequential)

  **Acceptance Criteria**:
  - [ ] `adapters/runescape/client_2004.py` exists
  - [ ] Can connect to 2004scape server
  - [ ] Can log in with credentials

  **Commit**: YES
  - Message: `feat(rs): port 2004scape client`

- [ ] 2. RS State Management

  **What to do**:
  - Create `adapters/runescape/state.py`
  - Track: player position, inventory, skills, equipment
  - Update state from server packets

  **Commit**: `feat(rs): add game state management`

- [ ] 3. Acore Event Integration

  **What to do**:
  - Wire RS client to emit `AcoreEvent` instances
  - Handle incoming commands from Acore core
  - Bridge RS events to Acore chat

  **Commit**: `feat(rs): integrate with acore events`

- [ ] 4. Basic Action Library

  **What to do**:
  - `actions.walk_to(x, y)`
  - `actions.click_object(obj_id)`
  - `actions.wait_ticks(n)`
  - `actions.open_bank()`

  **Commit**: `feat(rs): add basic action library`

### Phase 2: 2009scape Protocol

- [ ] 5. RS2 Packet Protocol

  **What to do**:
  - Implement packet encoder/decoder for revision 562+
  - Handle variable-length packets
  - Parse packet headers and payloads

  **Commit**: `feat(rs): implement rs2 protocol`

- [ ] 6. ISAAC Encryption

  **What to do**:
  - Implement ISAAC cipher for login encryption
  - Handle handshake and session keys

  **Commit**: `feat(rs): add isaac encryption`

- [ ] 7. Player/NPC Update Handlers

  **What to do**:
  - Parse player appearance/movement packets
  - Parse NPC spawn/update packets
  - Maintain local entity lists

  **Commit**: `feat(rs): player and npc handlers`

- [ ] 8. Inventory/Bank/Equipment

  **What to do**:
  - Parse inventory item packets
  - Bank interface packet handling
  - Equipment slot management

  **Commit**: `feat(rs): inventory system`

- [ ] 9. Map and Object System

  **What to do**:
  - Parse region loading packets
  - Track ground items and objects
  - Pathfinding integration (A*)

  **Commit**: `feat(rs): map and object system`

### Phase 3: Agent Brain

- [ ] 10. LLM Goal Planning

  **What to do**:
  - Take user goal: "get 99 mining"
  - Break into steps: find pickaxe → find rocks → mine → bank → repeat
  - Use Acore LLM service for planning

  **Commit**: `feat(rs): llm goal planner`

- [ ] 11. Action Sequencing

  **What to do**:
  - Execute action sequences with error handling
  - Retry on failure (e.g., rock empty, try another)
  - Pause/resume capability

  **Commit**: `feat(rs): action sequencer`

- [ ] 12. Personality Injection

  **What to do**:
  - Different personas play differently
  - Dagoth Ur: aggressive, efficient, risks PK
  - Scav: cautious, banks often, resource-focused

  **Commit**: `feat(rs): persona personality`

- [ ] 13. Learning System

  **What to do**:
  - Track successful/failed strategies
  - Optimize routes over time
  - Remember good mining spots

  **Commit**: `feat(rs): learning system`

### Phase 4: Integration

- [ ] 14. Discord Commands

  **What to do**:
  - `/rs play @persona activity` - Start playing
  - `/rs status` - Current activity
  - `/rs stop` - Stop agent

  **Commit**: `feat(rs): discord integration`

- [ ] 15. CLI Commands

  **What to do**:
  - `rs play --persona dagoth_ur --activity mining`
  - `rs status`
  - `rs stop`

  **Commit**: `feat(rs): cli commands`

- [ ] 16. Progress Reporting

  **What to do**:
  - Send updates to Acore chat
  - "Mining coal (47/99), inventory 15/28"
  - "Level up! Mining is now 50"
  - Screenshot on achievements

  **Commit**: `feat(rs): progress reporting`

- [ ] 17. Screenshot Capture

  **What to do**:
  - Capture game screen (if rendering)
  - Or generate text representation of state
  - Send to Discord on request

  **Commit**: `feat(rs): screenshot capture`

### Phase 5: Polish

- [ ] 18. Anti-Detection

  **What to do**:
  - Human-like delays (random 100-300ms)
  - Pattern variance (don't click same pixel)
  - Session limits (max 4 hours continuous)
  - Breaks (random AFK)

  **Commit**: `feat(rs): anti-detection`

- [ ] 19. Quest Framework

  **What to do**:
  - Load quest guides from text files
  - Parse step-by-step instructions
  - Execute quest sequences

  **Commit**: `feat(rs): quest framework`

- [ ] 20. Documentation

  **What to do**:
  - `docs/RUNESCAPE_AGENT.md`
  - Setup instructions
  - Protocol reference
  - Example commands

  **Commit**: `docs(rs): add documentation`

---

## Final Verification Wave

- [ ] F1. Protocol Compliance - RS packets match spec
- [ ] F2. Integration Test - Full "mine copper" workflow
- [ ] F3. Persona Test - Dagoth Ur vs Scav behave differently
- [ ] F4. Regression Test - No impact on other adapters

---

## Success Criteria

### Metrics
- Can mine copper from level 1 to 15 autonomously
- Can complete Tutorial Island without user intervention
- Responds to Discord commands within 2 seconds
- Reports progress every 5 minutes
- Plays for 2+ hours without getting banned (private server)

### Verification Commands
```bash
# Test 2004scape connection
python -m adapters.runescape test --server 2004scape

# Test 2009scape connection
python -m adapters.runescape test --server 2009scape

# Run mining workflow
python -m adapters.runescape play --persona dagoth_ur --activity mining
```

---

## Blockers

### Current Blockers
1. **framework-expansion** must complete first
2. Requires `core/` types (`AcoreContext`, `AcoreEvent`)
3. Requires `adapters/` interface pattern
4. Requires Acore persona system integration points

### When to Start
Run `/start-work runescape-agent` only after:
- `/start-work framework-expansion` completes
- `adapters/discord/` and `adapters/cli/` are working
- Core event system is stable

---

## Commit Strategy

| Phase | Tasks | Focus |
|-------|-------|-------|
| 1 | 4 | 2004scape port |
| 2 | 5 | 2009scape protocol |
| 3 | 4 | AI decision making |
| 4 | 4 | Acore integration |
| 5 | 3 | Polish & docs |

---

## Notes

### Existing Resources
- 2004scape implementation exists in external repo (TBD: link/copy)
- RS2 protocol specs available in OSRS/RuneScape communities
- Acore LLM service available for decision making

### Risks
- **Protocol changes**: RSPS servers may change protocols
- **Detection**: Even on private servers, obvious bots may be banned
- **Complexity**: RS2 protocol is complex (hundreds of packet types)
- **Maintenance**: Must keep up with server updates

### Future Extensions
- Grand Exchange arbitrage
- Quest speedrunning
- Multi-account coordination
- PvP combat (if allowed)
- Bot competitions (multiple personas competing)

---

**Plan saved to**: `.sisyphus/plans/runescape-agent.md`

**STATUS**: ⛔ BLOCKED - Start with `/start-work framework-expansion` first
