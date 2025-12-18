# Persona Management System Workflow

This document describes the complete persona management system in acore_bot, including character loading, framework blending, persona evolution, and behavioral adaptation workflows.

## Overview

The persona system enables **dynamic AI personalities** that can adapt, evolve, and interact with each other. It combines **behavioral frameworks** with **character definitions** to create unique, engaging AI personalities that learn and grow over time.

## Architecture

### Component Structure
```
services/persona/
├── system.py               # Core persona loading and compilation
├── router.py               # Persona selection and routing logic
├── behavior.py             # Behavioral patterns and interactions
├── evolution.py            # Character growth and development
├── relationships.py       # Inter-persona dynamics
├── lorebook.py            # Knowledge and context management
├── channel_profiler.py     # Channel-specific behavior adaptation
└── character_importer.py   # External character card imports

prompts/
├── characters/             # Character definition files (.json)
├── frameworks/             # Behavioral frameworks (.json)
└── compiled/              # Compiled persona outputs (.json)
```

### Service Dependencies
```
Persona System Dependencies:
├── Character Cards         # JSON personality definitions
├── Behavioral Frameworks    # Modular behavior patterns
├── LLM Interface           # Persona-specific prompt generation
├── Memory Systems          # Long-term persona learning
├── Analytics               # Persona performance tracking
├── RAG System             # Knowledge domain filtering
└── Metrics                # Interaction statistics
```

## Persona Loading and Compilation

### 1. Persona System Initialization
**File**: `services/persona/system.py:85-234`

#### 1.1 Core System Setup
```python
class PersonaSystem:
    """Manages loading, compiling, and switching between AI personas."""
    
    def __init__(self, base_path: Optional[Path] = None):
        self.base_path = base_path or Path("./prompts")
        self.frameworks_dir = self.base_path / "frameworks"
        self.characters_dir = self.base_path / "characters"
        self.compiled_dir = self.base_path / "compiled"
        
        # Ensure directories exist
        for dir_path in [self.frameworks_dir, self.characters_dir, self.compiled_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        # Storage
        self.frameworks: Dict[str, Framework] = {}
        self.characters: Dict[str, Character] = {}
        self.compiled_personas: Dict[str, CompiledPersona] = {}
        
        # Load all personas on startup
        self.load_all_personas()

async def load_all_personas(self):
    """Load all frameworks, characters, and compile personas."""
    try:
        # 1. Load frameworks first (characters may depend on them)
        await self.load_frameworks()
        
        # 2. Load characters
        await self.load_characters()
        
        # 3. Compile personas
        await self.compile_all_personas()
        
        logger.info(f"Loaded {len(self.compiled_personas)} personas")
        
    except Exception as e:
        logger.error(f"Error loading personas: {e}")
```

#### 1.2 Framework Loading
```python
async def load_frameworks(self):
    """Load all behavioral frameworks."""
    for framework_file in self.frameworks_dir.glob("*.json"):
        try:
            with open(framework_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            framework = Framework(
                framework_id=data['framework_id'],
                name=data['name'],
                purpose=data['purpose'],
                behavioral_patterns=data['behavioral_patterns'],
                tool_requirements=data['tool_requirements'],
                decision_making=data['decision_making'],
                context_requirements=data['context_requirements'],
                interaction_style=data['interaction_style'],
                anti_hallucination=data['anti_hallucination'],
                prompt_template=data['prompt_template']
            )
            
            self.frameworks[framework.framework_id] = framework
            logger.debug(f"Loaded framework: {framework.name}")
            
        except Exception as e:
            logger.error(f"Error loading framework {framework_file}: {e}")

async def load_characters(self):
    """Load all character definitions."""
    for character_file in self.characters_dir.glob("*.json"):
        try:
            with open(character_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Handle base64 encoded avatar if present
            avatar_url = data.get('avatar_url')
            if avatar_url and avatar_url.startswith('data:image'):
                # Save base64 image and update URL
                avatar_url = await self._save_avatar_image(data['character_id'], avatar_url)
            
            character = Character(
                character_id=data['character_id'],
                display_name=data['display_name'],
                identity=data['identity'],
                knowledge_domain=data['knowledge_domain'],
                opinions=data['opinions'],
                voice_and_tone=data['voice_and_tone'],
                quirks=data['quirks'],
                avatar_url=avatar_url,
                description=data.get('description', ''),
                scenario=data.get('scenario', ''),
                first_message=data.get('first_message', ''),
                mes_example=data.get('mes_example', ''),
                alternate_greetings=data.get('alternate_greetings', []),
                creator_notes=data.get('creator_notes', ''),
                tags=data.get('tags', []),
                creator=data.get('creator', ''),
                character_version=data.get('character_version', ''),
                system_prompt_override=data.get('system_prompt_override', ''),
                topic_interests=data.get('topic_interests', []),
                topic_avoidances=data.get('topic_avoidances', []),
                evolution_stages=data.get('evolution_stages', []),
                activity_preferences=data.get('activity_preferences', {}),
                framework_blending=data.get('framework_blending', {})
            )
            
            self.characters[character.character_id] = character
            logger.debug(f"Loaded character: {character.display_name}")
            
        except Exception as e:
            logger.error(f"Error loading character {character_file}: {e}")
```

#### 1.3 Persona Compilation
```python
async def compile_all_personas(self):
    """Compile all personas from characters + frameworks."""
    self.compiled_personas.clear()
    
    for character in self.characters.values():
        try:
            # 1. Determine framework for character
            framework_name = character.identity.get('framework', 'neuro')
            framework = self.frameworks.get(framework_name)
            
            if not framework:
                logger.warning(f"Framework '{framework_name}' not found for {character.display_name}")
                framework = self.frameworks.get('neuro')  # Fallback
            
            # 2. Generate system prompt
            system_prompt = await self._generate_system_prompt(character, framework)
            
            # 3. Determine required tools
            tools_required = self._determine_tools(character, framework)
            
            # 4. Create compiled persona
            compiled_persona = CompiledPersona(
                persona_id=f"{character.character_id}@{framework.framework_id}",
                character=character,
                framework=framework,
                system_prompt=system_prompt,
                tools_required=tools_required,
                config={
                    'temperature': character.voice_and_tone.get('temperature', 0.7),
                    'max_tokens': character.voice_and_tone.get('max_tokens', 500),
                    'top_p': character.voice_and_tone.get('top_p', 1.0),
                    'frequency_penalty': character.voice_and_tone.get('frequency_penalty', 0.0)
                }
            )
            
            # 5. Handle framework blending if configured
            if character.framework_blending:
                compiled_persona.blend_data = await self._prepare_framework_blending(
                    character, framework
                )
            
            self.compiled_personas[compiled_persona.persona_id] = compiled_persona
            
            # 6. Save compiled persona
            await self._save_compiled_persona(compiled_persona)
            
        except Exception as e:
            logger.error(f"Error compiling persona {character.display_name}: {e}")

async def _generate_system_prompt(self, character: Character, framework: Framework) -> str:
    """Generate comprehensive system prompt from character and framework."""
    
    # 1. Start with framework template
    prompt_template = framework.prompt_template
    
    # 2. Build character-specific sections
    identity_section = self._build_identity_section(character)
    behavior_section = self._build_behavior_section(character, framework)
    knowledge_section = self._build_knowledge_section(character)
    interaction_section = self._build_interaction_section(character, framework)
    
    # 3. Apply template variables
    system_prompt = prompt_template.format(
        character_name=character.display_name,
        identity=identity_section,
        behavior=behavior_section,
        knowledge=knowledge_section,
        interaction=interaction_section,
        anti_hallucination=framework.anti_hallucination.get('rules', [])
    )
    
    # 4. Apply character-specific overrides
    if character.system_prompt_override:
        system_prompt = character.system_prompt_override + "\n\n" + system_prompt
    
    return system_prompt
```

### 2. Persona Routing and Selection
**File**: `services/persona/router.py:45-189`

#### 2.1 Router Architecture
```python
class PersonaRouter:
    """Intelligent persona selection and routing."""
    
    def __init__(self, persona_system: PersonaSystem):
        self.persona_system = persona_system
        self.sticky_personas = {}  # channel_id -> persona_id
        self.channel_profiles = {}  # channel_id -> usage statistics
        self.interaction_history = []  # Recent interactions for learning
        
        # Routing weights and preferences
        self.default_weights = Config.PERSONA_WEIGHTS
        self.sticky_timeout = Config.PERSONA_STICKY_TIMEOUT  # 5 minutes default
        
        # Channel-based activity routing
        self.activity_routing_enabled = Config.ACTIVITY_ROUTING_ENABLED
        self.channel_last_response = {}  # channel_id -> (persona_id, timestamp)

async def select_persona(
    self, 
    message_content: str, 
    channel_id: int, 
    user_id: Optional[int] = None,
    force_selection: bool = False
) -> Optional[CompiledPersona]:
    """Select the most appropriate persona for a given context."""
    
    try:
        # 1. Check sticky context (recent responses in same channel)
        if not force_selection:
            sticky_persona = await self._check_sticky_context(channel_id)
            if sticky_persona:
                return sticky_persona
        
        # 2. Activity-based routing (if enabled)
        if self.activity_routing_enabled:
            activity_persona = await self._check_activity_routing(message_content, channel_id)
            if activity_persona:
                return activity_persona
        
        # 3. Content-based selection
        selected_persona = await self._select_by_content(message_content, channel_id, user_id)
        
        # 4. Apply randomization if multiple candidates
        if isinstance(selected_persona, list):
            selected_persona = random.choice(selected_persona)
        
        return selected_persona
        
    except Exception as e:
        logger.error(f"Error selecting persona: {e}")
        # Return default fallback
        return self._get_fallback_persona()

async def _select_by_content(
    self, 
    message_content: str, 
    channel_id: int, 
    user_id: Optional[int]
) -> Optional[CompiledPersona]:
    """Select persona based on content analysis."""
    
    candidates = []
    content_lower = message_content.lower()
    
    for persona in self.persona_system.compiled_personas.values():
        score = 0.0
        
        # 1. Check for direct mentions
        if persona.character.display_name.lower() in content_lower:
            score += 100  # High priority for direct mentions
        
        # 2. Topic interest matching
        for interest in persona.character.topic_interests:
            if interest.lower() in content_lower:
                score += 50
        
        # 3. Knowledge domain matching
        domain = persona.character.knowledge_domain.get('primary', '')
        if domain and domain.lower() in content_lower:
            score += 30
        
        # 4. Channel preference
        if hasattr(persona.character, 'activity_preferences'):
            channel_prefs = persona.character.activity_preferences.get('channels', [])
            if channel_id in channel_prefs:
                score += 20
        
        # 5. Topic avoidance (negative scoring)
        for avoidance in persona.character.topic_avoidances:
            if avoidance.lower() in content_lower:
                score -= 100
        
        # 6. Apply persona weight
        weight = self.default_weights.get(persona.persona_id, 1.0)
        score *= weight
        
        # 7. Consider candidate if score is positive
        if score > 0:
            candidates.append((persona, score))
    
    # 8. Sort by score and return top candidates
    candidates.sort(key=lambda x: x[1], reverse=True)
    
    if candidates:
        # Return top candidate or multiple if close scores
        top_score = candidates[0][1]
        close_candidates = [
            persona for persona, score in candidates 
            if score >= top_score * 0.8  # Within 80% of top score
        ]
        
        return close_candidates[0] if len(close_candidates) == 1 else close_candidates
    
    return None
```

### 3. Persona Evolution System
**File**: `services/persona/evolution.py:67-234**

#### 3.1 Evolution Architecture
```python
class PersonaEvolution:
    """Manages character growth and development over time."""
    
    def __init__(self, persona_system: PersonaSystem):
        self.persona_system = persona_system
        self.evolution_path = Config.PERSONA_EVOLUTION_PATH
        self.milestones = Config.PERSONA_EVOLUTION_MILESTONES  # [50, 100, 500, 1000, 5000]
        
        # Evolution data storage
        self.interaction_counts = {}  # persona_id -> interaction_count
        self.evolution_data = {}      # persona_id -> evolution_state
        self.relationship_memory = {} # persona_id -> relationship_memory
        
        # Load existing evolution data
        self._load_evolution_data()

async def process_interaction(
    self, 
    persona_id: str, 
    interaction_type: str, 
    context: Dict[str, Any]
):
    """Process an interaction for potential evolution."""
    
    try:
        # 1. Update interaction count
        self.interaction_counts[persona_id] = self.interaction_counts.get(persona_id, 0) + 1
        
        # 2. Check for milestone evolution
        current_count = self.interaction_counts[persona_id]
        if current_count in self.milestones:
            await self._trigger_milestone_evolution(persona_id, current_count)
        
        # 3. Update personality traits based on interaction
        await self._update_personality_traits(persona_id, interaction_type, context)
        
        # 4. Update relationship data
        if 'other_persona' in context:
            await self._update_relationship(persona_id, context['other_persona'], interaction_type)
        
        # 5. Save evolution data periodically
        if current_count % 10 == 0:  # Save every 10 interactions
            await self._save_evolution_data(persona_id)
            
    except Exception as e:
        logger.error(f"Error processing evolution for {persona_id}: {e}")

async def _trigger_milestone_evolution(self, persona_id: str, milestone: int):
    """Trigger evolution at specific interaction milestones."""
    
    try:
        persona = self.persona_system.compiled_personas.get(persona_id)
        if not persona:
            return
        
        # 1. Get evolution stage for milestone
        evolution_stages = persona.character.evolution_stages
        target_stage = None
        
        for stage in evolution_stages:
            if stage.get('milestone') == milestone:
                target_stage = stage
                break
        
        if not target_stage:
            logger.info(f"No evolution stage defined for milestone {milestone}")
            return
        
        # 2. Apply evolution changes
        changes = target_stage.get('changes', {})
        
        # Update personality traits
        if 'personality' in changes:
            await self._apply_personality_changes(persona_id, changes['personality'])
        
        # Update knowledge domains
        if 'knowledge' in changes:
            await self._apply_knowledge_changes(persona_id, changes['knowledge'])
        
        # Update behavioral patterns
        if 'behavior' in changes:
            await self._apply_behavior_changes(persona_id, changes['behavior'])
        
        # 3. Recompile persona with new traits
        await self._recompile_persona(persona_id)
        
        # 4. Log evolution event
        logger.info(f"Persona {persona.character.display_name} evolved at milestone {milestone}")
        
        # 5. Send evolution notification (if configured)
        await self._notify_evolution(persona, milestone, target_stage)
        
    except Exception as e:
        logger.error(f"Error triggering evolution for {persona_id}: {e}")

async def _apply_personality_changes(self, persona_id: str, personality_changes: Dict):
    """Apply personality trait changes to a persona."""
    
    persona = self.persona_system.compiled_personas.get(persona_id)
    if not persona:
        return
    
    # 1. Update voice and tone
    voice_tone = persona.character.voice_and_tone
    if 'temperature' in personality_changes:
        voice_tone['temperature'] = personality_changes['temperature']
    if 'formality' in personality_changes:
        voice_tone['formality'] = personality_changes['formality']
    if 'verbosity' in personality_changes:
        voice_tone['verbosity'] = personality_changes['verbosity']
    
    # 2. Update quirks and personality traits
    quirks = persona.character.quirks
    if 'new_quirks' in personality_changes:
        quirks.extend(personality_changes['new_quirks'])
    if 'remove_quirks' in personality_changes:
        for quirk in personality_changes['remove_quirks']:
            if quirk in quirks:
                quirks.remove(quirk)
    
    # 3. Update opinions and beliefs
    opinions = persona.character.opinions
    if 'opinion_changes' in personality_changes:
        opinions.update(personality_changes['opinion_changes'])
```

### 4. Framework Blending System
**File**: `services/persona/framework_blender.py:45-156`

#### 4.1 Dynamic Framework Adaptation
```python
class FrameworkBlender:
    """Blends multiple frameworks for dynamic persona adaptation."""
    
    def __init__(self, persona_system: PersonaSystem):
        self.persona_system = persona_system
        self.blend_cache = {}  # persona_id -> blended_frameworks
        self.context_weights = {}  # context_type -> framework_weights
        
        # Default context weights
        self.default_context_weights = {
            'technical': {'neuro': 0.8, 'assistant': 0.2},
            'casual': {'caring': 0.6, 'chaotic': 0.4},
            'formal': {'assistant': 0.9, 'neuro': 0.1},
            'creative': {'chaotic': 0.7, 'caring': 0.3},
            'educational': {'assistant': 0.8, 'neuro': 0.2}
        }

async def blend_frameworks(
    self, 
    persona_id: str, 
    context_type: str, 
    context_data: Dict[str, Any]
) -> Optional[str]:
    """Create blended framework prompt for specific context."""
    
    try:
        persona = self.persona_system.compiled_personas.get(persona_id)
        if not persona:
            return None
        
        # 1. Check if persona has framework blending enabled
        blend_config = persona.character.framework_blending
        if not blend_config or not blend_config.get('enabled', False):
            return persona.framework.prompt_template
        
        # 2. Determine framework weights for context
        weights = await self._calculate_framework_weights(persona, context_type, context_data)
        
        # 3. Get relevant frameworks
        frameworks = {}
        for framework_id, weight in weights.items():
            if weight > 0.1:  # Only include significant frameworks
                framework = self.persona_system.frameworks.get(framework_id)
                if framework:
                    frameworks[framework_id] = {'framework': framework, 'weight': weight}
        
        if not frameworks:
            return persona.framework.prompt_template
        
        # 4. Create blended prompt
        blended_prompt = await self._create_blended_prompt(persona, frameworks, context_data)
        
        # 5. Cache result
        cache_key = f"{persona_id}_{context_type}_{hash(str(context_data))}"
        self.blend_cache[cache_key] = blended_prompt
        
        return blended_prompt
        
    except Exception as e:
        logger.error(f"Error blending frameworks for {persona_id}: {e}")
        return None

async def _create_blended_prompt(
    self, 
    persona: CompiledPersona, 
    frameworks: Dict[str, Dict], 
    context_data: Dict[str, Any]
) -> str:
    """Create blended framework prompt."""
    
    # 1. Start with base framework
    base_framework = persona.framework
    blended_sections = {
        'behavioral_patterns': {},
        'decision_making': {},
        'interaction_style': {},
        'anti_hallucination': {}
    }
    
    # 2. Blend sections from multiple frameworks
    for section_name in blended_sections.keys():
        section_weights = {}
        
        for framework_id, framework_data in frameworks.items():
            framework = framework_data['framework']
            weight = framework_data['weight']
            
            if hasattr(framework, section_name):
                section_content = getattr(framework, section_name)
                
                if isinstance(section_content, dict):
                    for key, value in section_content.items():
                        if key not in section_weights:
                            section_weights[key] = {}
                        section_weights[key][framework_id] = {
                            'value': value,
                            'weight': weight
                        }
        
        # 3. Resolve conflicts and select best values
        blended_sections[section_name] = await self._resolve_section_conflicts(section_weights)
    
    # 4. Build final blended prompt
    blended_prompt = await self._build_blended_prompt(persona, blended_sections, context_data)
    
    return blended_prompt

async def _resolve_section_conflicts(self, section_weights: Dict) -> Dict:
    """Resolve conflicts between different framework values."""
    
    resolved = {}
    
    for key, framework_values in section_weights.items():
        if len(framework_values) == 1:
            # Only one framework defines this key
            framework_id = list(framework_values.keys())[0]
            resolved[key] = framework_values[framework_id]['value']
        else:
            # Multiple frameworks define this key - need to resolve
            
            # Strategy 1: Weighted voting for discrete values
            if all(isinstance(fv['value'], str) for fv in framework_values.values()):
                votes = {}
                for framework_id, fv in framework_values.items():
                    value = fv['value']
                    weight = fv['weight']
                    votes[value] = votes.get(value, 0) + weight
                
                # Select value with highest weighted vote
                resolved[key] = max(votes.keys(), key=lambda k: votes[k])
            
            # Strategy 2: Weighted average for numeric values
            elif all(isinstance(fv['value'], (int, float)) for fv in framework_values.items()):
                weighted_sum = sum(fv['value'] * fv['weight'] for fv in framework_values.values())
                total_weight = sum(fv['weight'] for fv in framework_values.values())
                resolved[key] = weighted_sum / total_weight
            
            # Strategy 3: Weighted merge for list values
            elif all(isinstance(fv['value'], list) for fv in framework_values.items()):
                merged_items = {}
                for framework_id, fv in framework_values.items():
                    for item in fv['value']:
                        if isinstance(item, str):
                            item_key = item.lower()
                        else:
                            item_key = str(item)
                        
                        if item_key not in merged_items:
                            merged_items[item_key] = {'item': item, 'weight': 0}
                        merged_items[item_key]['weight'] += fv['weight']
                
                # Sort by weight and take top items
                sorted_items = sorted(
                    merged_items.values(), 
                    key=lambda x: x['weight'], 
                    reverse=True
                )
                resolved[key] = [item['item'] for item in sorted_items[:5]]  # Top 5 items
    
    return resolved
```

### 5. Inter-Persona Relationships
**File**: `services/persona/relationships.py:34-145`

#### 5.1 Relationship Dynamics
```python
class PersonaRelationships:
    """Manages relationships and interactions between personas."""
    
    def __init__(self, persona_system: PersonaSystem):
        self.persona_system = persona_system
        self.affinity_matrix = {}  # persona_id -> {other_persona_id: affinity_score}
        self.interaction_history = []  # List of recent inter-persona interactions
        self.relationship_traits = {}  # persona_id -> {trait_name: trait_value}
        
        # Relationship decay and growth rates
        self.decay_rate = Config.CONFLICT_DECAY_RATE
        self.escalation_amount = Config.CONFLICT_ESCALATION_AMOUNT
        
        # Load existing relationship data
        self._load_relationship_data()

async def record_interaction(
    self, 
    speaker_id: str, 
    responder_id: str, 
    interaction_type: str,
    context: Dict[str, Any]
):
    """Record an interaction between two personas."""
    
    try:
        # 1. Update interaction history
        interaction_record = {
            'speaker_id': speaker_id,
            'responder_id': responder_id,
            'type': interaction_type,
            'context': context,
            'timestamp': datetime.now().isoformat()
        }
        
        self.interaction_history.append(interaction_record)
        
        # Keep history bounded
        if len(self.interaction_history) > 1000:
            self.interaction_history = self.interaction_history[-800:]
        
        # 2. Update affinity scores
        await self._update_affinity(speaker_id, responder_id, interaction_type, context)
        
        # 3. Update relationship traits
        await self._update_relationship_traits(speaker_id, responder_id, interaction_type)
        
        # 4. Check for relationship milestones
        await self._check_relationship_milestones(speaker_id, responder_id)
        
    except Exception as e:
        logger.error(f"Error recording persona interaction: {e}")

async def _update_affinity(
    self, 
    speaker_id: str, 
    responder_id: str, 
    interaction_type: str,
    context: Dict[str, Any]
):
    """Update affinity scores between personas."""
    
    # 1. Initialize affinity matrix entries
    if speaker_id not in self.affinity_matrix:
        self.affinity_matrix[speaker_id] = {}
    if responder_id not in self.affinity_matrix:
        self.affinity_matrix[responder_id] = {}
    
    # 2. Determine affinity change based on interaction type
    affinity_changes = {
        'agreement': 2.0,
        'disagreement': -1.0,
        'compliment': 3.0,
        'insult': -3.0,
        'question': 0.5,
        'answer': 1.0,
        'banter': 1.5,
        'argument': -2.0,
        'collaboration': 2.5,
        'competition': -0.5
    }
    
    base_change = affinity_changes.get(interaction_type, 0.0)
    
    # 3. Apply contextual modifiers
    modifiers = await self._calculate_affinity_modifiers(speaker_id, responder_id, context)
    final_change = base_change * modifiers
    
    # 4. Update scores (bidirectional but potentially different)
    self.affinity_matrix[speaker_id][responder_id] = (
        self.affinity_matrix[speaker_id].get(responder_id, 0.0) + final_change
    )
    
    # Responder might feel differently about the interaction
    responder_change = final_change * modifiers * 0.8  # Slightly less impact
    self.affinity_matrix[responder_id][speaker_id] = (
        self.affinity_matrix[responder_id].get(speaker_id, 0.0) + responder_change
    )
    
    # 5. Clamp values to reasonable bounds
    self.affinity_matrix[speaker_id][responder_id] = max(-10.0, min(10.0, 
        self.affinity_matrix[speaker_id][responder_id]))
    self.affinity_matrix[responder_id][speaker_id] = max(-10.0, min(10.0, 
        self.affinity_matrix[responder_id][speaker_id]))

async def get_interaction_probability(
    self, 
    speaker_id: str, 
    potential_responder_id: str
) -> float:
    """Calculate probability of interaction between two personas."""
    
    try:
        # 1. Get base affinity
        affinity = self.affinity_matrix.get(speaker_id, {}).get(potential_responder_id, 0.0)
        
        # 2. Convert affinity to probability
        # Affinity range: -10 (hate) to +10 (love)
        # Probability: 0.0 (never) to 1.0 (always)
        base_probability = (affinity + 10.0) / 20.0
        
        # 3. Apply interaction history weight
        recent_interactions = await self._get_recent_interaction_count(
            speaker_id, potential_responder_id, hours=24
        )
        
        # Reduce probability if recently interacted (avoid spam)
        history_modifier = max(0.3, 1.0 - (recent_interactions * 0.1))
        
        # 4. Apply personality compatibility
        compatibility = await self._calculate_compatibility(speaker_id, potential_responder_id)
        
        # 5. Apply random chance for natural variation
        random_factor = random.uniform(0.8, 1.2)
        
        final_probability = base_probability * history_modifier * compatibility * random_factor
        
        return max(0.0, min(1.0, final_probability))
        
    except Exception as e:
        logger.error(f"Error calculating interaction probability: {e}")
        return 0.1  # Default low probability
```

## Configuration

### Persona System Settings
```bash
# Core Persona Settings
USE_PERSONA_SYSTEM=true                          # Enable multi-character support
CHARACTERS_DIR=./prompts/characters             # Character definition files
ACTIVE_PERSONAS=["dagoth_ur.json", "..."]      # Available characters
PERSONA_WEIGHTS={}                              # Selection weights per persona

# Evolution Settings
PERSONA_EVOLUTION_ENABLED=true                   # Enable character growth
PERSONA_EVOLUTION_PATH=./data/persona_evolution # Evolution data storage
PERSONA_EVOLUTION_MILESTONES=50,100,500,1000,5000 # Interaction milestones

# Framework Blending
FRAMEWORK_BLENDING_ENABLED=true                  # Enable dynamic frameworks
CONTEXT_ROUTING_ENABLED=true                     # Activity-based selection
ACTIVITY_ROUTING_PRIORITY=100                   # Priority vs other routing

# Relationship Settings
PERSONA_CONFLICTS_ENABLED=true                   # Enable inter-persona dynamics
CONFLICT_DECAY_RATE=0.1                         # Relationship decay over time
CONFLICT_ESCALATION_AMOUNT=0.2                  # Conflict escalation rate

# Routing and Selection
PERSONA_STICKY_TIMEOUT=300                      # Sticky persona timeout (5 minutes)
PERSONA_FOLLOWUP_COOLDOWN=300                   # Followup question cooldown
GLOBAL_RESPONSE_CHANCE=1.0                       # Base response probability
```

## Integration Points

### With Chat System
- **Dynamic Persona Selection**: Real-time character switching based on context
- **Sticky Context**: Channel-specific persona memory
- **Inter-Persona Banter**: Characters can interact with each other

### With Memory System
- **Evolution Data**: Long-term storage of persona growth
- **Relationship History**: Tracking of inter-persona dynamics
- **Learning Integration**: Personality adaptation based on interactions

### With Voice System
- **Persona-Specific Voices**: Each character uses unique TTS/RVC settings
- **Voice Personality**: Audio characteristics match character traits

## Performance Considerations

### 1. Compilation Optimization
- **Lazy Loading**: Personas compiled on first use
- **Caching**: Compiled personas cached in memory
- **Incremental Updates**: Only recompile changed personas

### 2. Memory Management
- **Bounded History**: Limited interaction history storage
- **Data Compression**: Compress evolution data for long-term storage
- **Periodic Cleanup**: Automatic cleanup of old data

### 3. Computation Efficiency
- **Parallel Processing**: Multiple personas evolved concurrently
- **Batch Operations**: Group relationship updates
- **Algorithm Optimization**: Efficient affinity calculations

## Common Issues and Troubleshooting

### 1. Persona Loading Failures
```bash
# Check character file validity
python -m json.tool prompts/characters/dagoth_ur.json

# Verify framework availability
ls -la prompts/frameworks/

# Check compiled outputs
ls -la prompts/compiled/
```

### 2. Evolution Not Working
```python
# Check evolution milestones
print(Config.PERSONA_EVOLUTION_MILESTONES)

# Verify interaction counting
router = bot.get_cog("ChatCog").persona_router
print(router.interaction_counts)

# Check evolution data path
print(Config.PERSONA_EVOLUTION_PATH)
```

### 3. Framework Blending Issues
- **Configuration**: Verify framework blending is enabled in character config
- **Weight Calculation**: Check context weights are properly defined
- **Cache Issues**: Clear blend cache if updates not applied

## Files Reference

| File | Purpose | Key Functions |
|-------|---------|------------------|
| `services/persona/system.py` | Core persona loading and compilation |
| `services/persona/router.py` | Persona selection and routing logic |
| `services/persona/evolution.py` | Character growth and development |
| `services/persona/relationships.py` | Inter-persona dynamics |
| `services/persona/framework_blender.py` | Dynamic framework adaptation |
| `services/persona/behavior.py` | Behavioral patterns and interactions |
| `services/persona/lorebook.py` | Knowledge and context management |

---

**Last Updated**: 2025-12-16
**Version**: 1.0