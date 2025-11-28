# Quick Fixes: Immediate Actions

## 🎯 Priority 1: Merge Naturalness Services (15 minutes)

**Problem**: `naturalness.py` and `naturalness_enhancer.py` do the same thing

**Solution**: Merge them

```bash
# 1. Backup
cp services/naturalness_enhancer.py services/naturalness_enhancer.py.bak

# 2. Add Neuro features to naturalness.py
# (Already has most features, just add missing ones)

# 3. Update imports in chat.py
# Change: from services.naturalness_enhancer import NaturalnessEnhancer
# To: from services.naturalness import NaturalnessEnhancer

# 4. Remove old file
rm services/naturalness_enhancer.py
```

---

## 🎯 Priority 2: Choose Persona Standard (5 minutes)

**Recommendation**: **Keep simple for now**, enhance later

**Why**:
- Simple JSON system works
- Advanced systems (PersonaSystem, AIDecisionEngine) aren't fully wired up
- Can migrate later when ready for autonomous features

**Action**: Document that `prompts/{name}.json` is the current standard

---

## 🎯 Priority 3: Remove Unused Services (10 minutes)

Check if these are actually used:

```bash
# Check if custom_intents.py is used
grep -r "custom_intents" . --include="*.py" | grep -v "^#"

# If not used, move to archive
mkdir -p archive/unused_services
mv services/custom_intents.py archive/unused_services/

# Same for pattern_learner if not used
grep -r "pattern_learner" . --include="*.py" | grep -v "^#"
```

---

## 🎯 Priority 4: Clean Up Prompts Directory (10 minutes)

**Current mess**:
```
prompts/
├── arbiter.json (simple)
├── dagoth.json (simple)
├── dagoth_autonomous.json (advanced - orphaned)
├── dagoth_neuro.json (advanced - orphaned)
├── characters/
│   └── dagoth_ur.json (modular - unused)
└── frameworks/
    ├── neuro.json (modular - unused)
    └── assistant.json (modular - unused)
```

**Proposed cleanup**:
```
prompts/
├── active/           # Currently used personas
│   ├── arbiter.json + arbiter.txt
│   ├── chief.json + chief.txt
│   └── dagoth.json + dagoth.txt
├── experimental/     # Advanced personas for future use
│   ├── dagoth_autonomous.json
│   └── dagoth_neuro.json
└── frameworks/       # For future modular system
    ├── neuro.json
    └── assistant.json
```

**Commands**:
```bash
cd prompts
mkdir -p active experimental

# Move active personas
mv arbiter.* chief.* dagoth.json dagoth.txt default.* gothmommy.* active/
mv friendly.txt gaming.txt pirate.txt professional.txt arby.txt active/

# Move experimental
mv dagoth_autonomous.json dagoth_neuro.json experimental/

# Update PersonaLoader path
# Edit utils/persona_loader.py to look in prompts/active/
```

---

## 📋 Summary of Quick Wins

| Action | Time | Impact | Risk |
|--------|------|--------|------|
| Merge naturalness services | 15 min | High | Low |
| Document current standard | 5 min | Medium | None |
| Archive unused services | 10 min | Low | None |
| Organize prompts directory | 10 min | Medium | Low |

**Total Time**: ~40 minutes
**Total Impact**: Cleaner, more maintainable codebase

---

## ⚠️ What NOT to do yet

1. **Don't migrate to Character + Framework yet**
   - AIDecisionEngine not fully integrated
   - PersonaSystem not wired up
   - Would break current working system

2. **Don't remove PersonaSystem/AIDecisionEngine**
   - They're initialized but not fully integrated
   - Keep for future enhancement
   - Just document they're "planned features"

3. **Don't touch conversation_manager**
   - It works and is used
   - Different concern from conversational_callbacks

---

## 🔜 Next Steps (Future Work)

After quick fixes, consider:

1. **Phase 2**: Wire up AIDecisionEngine
   - Integrate with chat response generation
   - Use persona frameworks for decision-making

2. **Phase 3**: Full persona migration
   - Migrate all personas to Character + Framework
   - Deprecate simple JSON format
   - Full autonomous behavior support

3. **Phase 4**: Feature consolidation
   - Merge conversation services if needed
   - Standardize all AI decision flows
   - Single source of truth for personality
