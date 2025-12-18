# Utilities and Tools System Workflow

This document describes the complete utilities and tools system in acore_bot, including helper functions, utility commands, productivity tools, and system utilities.

## Overview

The utilities and tools system provides **essential helper functions** and **productivity tools** including **reminders**, **notes**, **search capabilities**, **file utilities**, and **system helpers** to enhance bot functionality and user experience.

## Architecture

### Component Structure
```
cogs/
├── reminders.py             # Reminder and notification system
├── notes.py                 # Note-taking and organization
├── search_commands.py       # Search and lookup commands
└── help.py                 # Help system and documentation

services/discord/
├── reminders.py            # Reminder service backend
├── notes.py               # Notes management service
└── web_search.py         # Web search integration

utils/
├── helpers.py             # General utility functions
├── error_handlers.py      # Error handling utilities
├── logging_config.py      # Logging configuration
├── system_context.py      # System context management
├── response_validator.py  # Response validation
└── template_renderer.py   # Template rendering utilities

data/
├── reminders/             # Reminder storage
├── notes/                 # User notes storage
└── search_cache/          # Search result cache
```

### Service Dependencies
```
Utilities Dependencies:
├── Reminder System        # Scheduled notifications
├── Note Management       # User note storage
├── Search Services       # Information retrieval
├── Template Engine      # Dynamic content generation
├── File Management      # File operations and storage
├── Time Management     # Scheduling and timing
└── Data Validation     # Input validation and cleaning
```

## Reminder System

### 1. Reminder Commands and Service
**File**: `cogs/reminders.py:45-234`

#### 1.1 Reminder Command Interface
```python
@app_commands.command(name="remind", description="Set a reminder")
@app_commands.describe(
    time="When to remind (e.g., 'in 5 minutes', 'tomorrow at 3pm')",
    message="What to remind you about"
)
async def set_reminder(
    self,
    interaction: discord.Interaction,
    time: str,
    message: str
):
    """Set a new reminder."""
    await interaction.response.defer(thinking=True)
    
    try:
        # 1. Parse time
        reminder_time = await self._parse_time(time, interaction.user)
        
        if not reminder_time:
            await interaction.followup.send(
                "❌ Could not understand time format. Try: 'in 5 minutes', 'tomorrow at 3pm', '2024-12-25 14:00'",
                ephemeral=True
            )
            return
        
        # 2. Validate reminder time
        if reminder_time <= datetime.now():
            await interaction.followup.send(
                "❌ Reminder time must be in the future",
                ephemeral=True
            )
            return
        
        # 3. Check user's reminder limit
        user_reminders = await self.reminder_service.get_user_reminders(interaction.user.id)
        if len(user_reminders) >= Config.MAX_REMINDERS_PER_USER:
            await interaction.followup.send(
                f"❌ You have reached the maximum of {Config.MAX_REMINDERS_PER_USER} reminders",
                ephemeral=True
            )
            return
        
        # 4. Create reminder
        reminder = await self.reminder_service.create_reminder(
            user_id=interaction.user.id,
            guild_id=interaction.guild.id,
            channel_id=interaction.channel.id,
            message=message,
            reminder_time=reminder_time
        )
        
        # 5. Schedule reminder
        await self.reminder_service.schedule_reminder(reminder)
        
        # 6. Confirm to user
        time_until = reminder_time - datetime.now()
        
        embed = discord.Embed(
            title="⏰ Reminder Set",
            description=f"**Message:** {message}",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="Reminder Time",
            value=f"<t:{int(reminder_time.timestamp())}:F>",
            inline=True
        )
        
        embed.add_field(
            name="Time Until",
            value=self._format_timedelta(time_until),
            inline=True
        )
        
        embed.add_field(
            name="Reminder ID",
            value=f"`{reminder.id}`",
            inline=True
        )
        
        embed.set_footer(text="Use /reminders list to see all reminders")
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        await interaction.followup.send(
            f"❌ Error setting reminder: {e}",
            ephemeral=True
        )

@app_commands.command(name="reminders", description="Manage your reminders")
@app_commands.describe(action="Action to perform")
async def manage_reminders(
    self,
    interaction: discord.Interaction,
    action: str
):
    """Manage existing reminders."""
    await interaction.response.defer(thinking=True)
    
    try:
        if action == "list":
            await self._list_reminders(interaction)
        elif action == "clear":
            await self._clear_reminders(interaction)
        elif action.startswith("delete"):
            # Extract reminder ID
            parts = action.split()
            if len(parts) >= 2:
                reminder_id = parts[1]
                await self._delete_reminder(interaction, reminder_id)
            else:
                await interaction.followup.send(
                    "❌ Usage: reminders delete <reminder_id>",
                    ephemeral=True
                )
        else:
            await interaction.followup.send(
                "❌ Available actions: list, clear, delete <id>",
                ephemeral=True
            )
        
    except Exception as e:
        await interaction.followup.send(
            f"❌ Error managing reminders: {e}",
            ephemeral=True
        )

async def _list_reminders(self, interaction: discord.Interaction):
    """List user's active reminders."""
    
    try:
        # Get user's reminders
        reminders = await self.reminder_service.get_user_reminders(interaction.user.id)
        
        if not reminders:
            await interaction.followup.send(
                "📭 You have no active reminders",
                ephemeral=True
            )
            return
        
        # Create embed
        embed = discord.Embed(
            title="⏰ Your Reminders",
            color=discord.Color.blue()
        )
        
        # Group reminders by time
        now = datetime.now()
        upcoming_reminders = [r for r in reminders if r.reminder_time > now]
        overdue_reminders = [r for r in reminders if r.reminder_time <= now]
        
        # Show upcoming reminders
        if upcoming_reminders:
            upcoming_text = ""
            for reminder in sorted(upcoming_reminders, key=lambda r: r.reminder_time)[:10]:
                time_until = reminder.reminder_time - now
                upcoming_text += (
                    f"**`{reminder.id[:8]}`** <t:{int(reminder.reminder_time.timestamp())}:R>\n"
                    f"{reminder.message[:50]}{'...' if len(reminder.message) > 50 else ''}\n\n"
                )
            
            embed.add_field(
                name=f"📅 Upcoming ({len(upcoming_reminders)})",
                value=upcoming_text,
                inline=False
            )
        
        # Show overdue reminders
        if overdue_reminders:
            overdue_text = ""
            for reminder in sorted(overdue_reminders, key=lambda r: r.reminder_time)[:5]:
                overdue_text += (
                    f"**`{reminder.id[:8]}`** <t:{int(reminder.reminder_time.timestamp())}:R>\n"
                    f"{reminder.message[:50]}{'...' if len(reminder.message) > 50 else ''}\n\n"
                )
            
            embed.add_field(
                name=f"⚠️ Overdue ({len(overdue_reminders)})",
                value=overdue_text,
                inline=False
            )
        
        embed.set_footer(text="Use /reminders delete <id> to remove a reminder")
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        
    except Exception as e:
        logger.error(f"Error listing reminders: {e}")
        await interaction.followup.send(
            "❌ Error loading reminders",
            ephemeral=True
        )

async def _parse_time(self, time_str: str, user: discord.User) -> Optional[datetime]:
    """Parse various time string formats."""
    
    try:
        time_str = time_str.lower().strip()
        now = datetime.now()
        
        # Relative time patterns
        relative_patterns = {
            r'in (\d+) seconds?': lambda m: now + timedelta(seconds=int(m.group(1))),
            r'in (\d+) minutes?': lambda m: now + timedelta(minutes=int(m.group(1))),
            r'in (\d+) hours?': lambda m: now + timedelta(hours=int(m.group(1))),
            r'in (\d+) days?': lambda m: now + timedelta(days=int(m.group(1))),
            r'in (\d+) weeks?': lambda m: now + timedelta(weeks=int(m.group(1))),
            r'tomorrow': lambda m: now + timedelta(days=1),
            r'today': lambda m: now,
            r'next week': lambda m: now + timedelta(weeks=1),
        }
        
        # Check relative patterns
        for pattern, handler in relative_patterns.items():
            match = re.match(pattern, time_str)
            if match:
                return handler(match)
        
        # Specific time patterns
        specific_patterns = [
            r'tomorrow at (\d{1,2})(?::(\d{2}))\s*(am|pm)?',
            r'today at (\d{1,2})(?::(\d{2}))\s*(am|pm)?',
            r'(\d{4})-(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{2})',
        ]
        
        for pattern in specific_patterns:
            match = re.match(pattern, time_str)
            if match:
                return self._parse_specific_time(match)
        
        # Try dateutil parser as fallback
        try:
            from dateutil import parser
            parsed = parser.parse(time_str)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=user.timezone if hasattr(user, 'timezone') else None)
            return parsed
        except:
            pass
        
        return None
        
    except Exception as e:
        logger.error(f"Error parsing time '{time_str}': {e}")
        return None

async def _parse_specific_time(self, match) -> Optional[datetime]:
    """Parse specific time formats from regex match."""
    
    try:
        groups = match.groups()
        
        # Handle different formats
        if len(groups) >= 6:  # YYYY-MM-DD HH:MM
            year, month, day, hour, minute = groups[:5]
            return datetime(int(year), int(month), int(day), int(hour), int(minute))
        
        elif len(groups) >= 4:  # tomorrow at HH:MM
            hour, minute, period = groups[:3]
            hour = int(hour)
            minute = int(minute or 0)
            
            tomorrow = datetime.now() + timedelta(days=1)
            
            # Handle AM/PM
            if period:
                if period.lower() == 'pm' and hour < 12:
                    hour += 12
                elif period.lower() == 'am' and hour == 12:
                    hour = 0
            
            return tomorrow.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
    except Exception as e:
        logger.error(f"Error parsing specific time: {e}")
        return None
```

### 2. Reminder Service Backend
**File**: `services/discord/reminders.py:45-156`

#### 2.1 Reminder Management System
```python
class ReminderService:
    """Manages reminder creation, scheduling, and delivery."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.reminders_path = Path(Config.DATA_DIR) / "reminders"
        self.reminders = {}  # reminder_id -> Reminder
        self.user_reminders = {}  # user_id -> [reminder_ids]
        self.scheduled_tasks = {}  # reminder_id -> asyncio.Task
        
        # Ensure directory exists
        self.reminders_path.mkdir(parents=True, exist_ok=True)
        
        # Load existing reminders
        self.load_reminders()
        
        # Start cleanup task
        asyncio.create_task(self._cleanup_loop())

    async def create_reminder(
        self,
        user_id: int,
        guild_id: int,
        channel_id: int,
        message: str,
        reminder_time: datetime
    ) -> Reminder:
        """Create a new reminder."""
        
        reminder = Reminder(
            id=str(uuid.uuid4()),
            user_id=user_id,
            guild_id=guild_id,
            channel_id=channel_id,
            message=message,
            reminder_time=reminder_time,
            created_at=datetime.now(),
            status='active'
        )
        
        # Store reminder
        self.reminders[reminder.id] = reminder
        
        # Update user index
        if user_id not in self.user_reminders:
            self.user_reminders[user_id] = []
        self.user_reminders[user_id].append(reminder.id)
        
        # Save to file
        await self._save_reminder(reminder)
        
        return reminder

    async def schedule_reminder(self, reminder: Reminder):
        """Schedule a reminder for delivery."""
        
        try:
            # Calculate delay
            now = datetime.now()
            if reminder.reminder_time <= now:
                # Immediate delivery
                asyncio.create_task(self._deliver_reminder(reminder))
            else:
                # Schedule for future
                delay = (reminder.reminder_time - now).total_seconds()
                
                task = asyncio.create_task(
                    self._schedule_and_deliver(reminder, delay)
                )
                self.scheduled_tasks[reminder.id] = task
        
        except Exception as e:
            logger.error(f"Error scheduling reminder {reminder.id}: {e}")

    async def _schedule_and_deliver(self, reminder: Reminder, delay: float):
        """Schedule reminder and deliver after delay."""
        
        try:
            # Wait for reminder time
            await asyncio.sleep(delay)
            
            # Deliver reminder
            await self._deliver_reminder(reminder)
            
        except asyncio.CancelledError:
            logger.info(f"Reminder {reminder.id} was cancelled")
        except Exception as e:
            logger.error(f"Error in scheduled reminder {reminder.id}: {e}")

    async def _deliver_reminder(self, reminder: Reminder):
        """Deliver a reminder to the user."""
        
        try:
            # Get target channel
            channel = self.bot.get_channel(reminder.channel_id)
            if not channel:
                logger.error(f"Channel {reminder.channel_id} not found for reminder {reminder.id}")
                return
            
            # Get user
            user = self.bot.get_user(reminder.user_id)
            if not user:
                logger.error(f"User {reminder.user_id} not found for reminder {reminder.id}")
                return
            
            # Create reminder embed
            embed = discord.Embed(
                title="⏰ Reminder!",
                description=reminder.message,
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="Set on",
                value=f"<t:{int(reminder.created_at.timestamp())}:F>",
                inline=True
            )
            
            embed.add_field(
                name="Original time",
                value=f"<t:{int(reminder.reminder_time.timestamp())}:F>",
                inline=True
            )
            
            # Add user mention
            embed.set_footer(text=f"Reminder for {user.display_name}")
            
            # Send reminder
            await channel.send(f"Hey {user.mention}!", embed=embed)
            
            # Mark as delivered
            reminder.status = 'delivered'
            reminder.delivered_at = datetime.now()
            
            # Update stored reminder
            self.reminders[reminder.id] = reminder
            await self._save_reminder(reminder)
            
            # Clean up scheduled task
            if reminder.id in self.scheduled_tasks:
                del self.scheduled_tasks[reminder.id]
        
        except Exception as e:
            logger.error(f"Error delivering reminder {reminder.id}: {e}")

    async def cancel_reminder(self, reminder_id: str) -> bool:
        """Cancel a scheduled reminder."""
        
        try:
            # Cancel scheduled task
            if reminder_id in self.scheduled_tasks:
                task = self.scheduled_tasks[reminder_id]
                task.cancel()
                del self.scheduled_tasks[reminder_id]
            
            # Update reminder status
            if reminder_id in self.reminders:
                reminder = self.reminders[reminder_id]
                reminder.status = 'cancelled'
                reminder.cancelled_at = datetime.now()
                
                await self._save_reminder(reminder)
                return True
            
            return False
        
        except Exception as e:
            logger.error(f"Error cancelling reminder {reminder_id}: {e}")
            return False

    async def _cleanup_loop(self):
        """Periodic cleanup of old reminders."""
        
        while True:
            try:
                await asyncio.sleep(3600)  # Run every hour
                
                cutoff_time = datetime.now() - timedelta(days=30)
                
                # Find old delivered/cancelled reminders
                old_reminders = [
                    reminder_id for reminder_id, reminder in self.reminders.items()
                    if (reminder.status in ['delivered', 'cancelled'] and 
                        (reminder.delivered_at or reminder.cancelled_at or reminder.created_at) < cutoff_time)
                ]
                
                # Remove old reminders
                for reminder_id in old_reminders:
                    await self._remove_reminder(reminder_id)
                
                if old_reminders:
                    logger.info(f"Cleaned up {len(old_reminders)} old reminders")
                
            except Exception as e:
                logger.error(f"Error in reminder cleanup: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes on error

@dataclass
class Reminder:
    """Represents a scheduled reminder."""
    id: str
    user_id: int
    guild_id: int
    channel_id: int
    message: str
    reminder_time: datetime
    created_at: datetime
    status: str  # active, delivered, cancelled
    delivered_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
```

### 3. Notes System
**File**: `cogs/notes.py:45-189`

#### 3.1 Note Management Commands
```python
@app_commands.command(name="note", description="Manage your notes")
@app_commands.describe(
    action="Action to perform",
    title="Note title",
    content="Note content",
    category="Note category"
)
async def manage_notes(
    self,
    interaction: discord.Interaction,
    action: str,
    title: Optional[str] = None,
    content: Optional[str] = None,
    category: Optional[str] = None
):
    """Manage personal notes."""
    await interaction.response.defer(thinking=True)
    
    try:
        if action == "create":
            await self._create_note(interaction, title, content, category)
        elif action == "list":
            await self._list_notes(interaction, category)
        elif action == "search":
            await self._search_notes(interaction, title)  # Using title as search term
        elif action.startswith("show"):
            await self._show_note(interaction, action.split()[1] if len(action.split()) > 1 else None)
        elif action.startswith("delete"):
            await self._delete_note(interaction, action.split()[1] if len(action.split()) > 1 else None)
        elif action == "categories":
            await self._list_categories(interaction)
        else:
            await interaction.followup.send(
                "❌ Available actions: create, list, search, show <id>, delete <id>, categories",
                ephemeral=True
            )
    
    except Exception as e:
        await interaction.followup.send(
            f"❌ Error managing notes: {e}",
            ephemeral=True
        )

async def _create_note(
    self,
    interaction: discord.Interaction,
    title: Optional[str],
    content: Optional[str],
    category: Optional[str]
):
    """Create a new note."""
    
    if not title or not content:
        await interaction.followup.send(
            "❌ Title and content are required for creating notes",
            ephemeral=True
        )
        return
    
    try:
        # Create note
        note = await self.notes_service.create_note(
            user_id=interaction.user.id,
            title=title,
            content=content,
            category=category or "general"
        )
        
        # Create confirmation embed
        embed = discord.Embed(
            title="📝 Note Created",
            description=f"**Title:** {title}\n**Category:** {category or 'general'}",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="Note ID",
            value=f"`{note.id[:8]}`",
            inline=True
        )
        
        embed.add_field(
            name="Content Preview",
            value=content[:200] + ("..." if len(content) > 200 else ""),
            inline=False
        )
        
        embed.set_footer(text="Use /note show <id> to view full note")
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        
    except Exception as e:
        logger.error(f"Error creating note: {e}")
        await interaction.followup.send(
            "❌ Error creating note",
            ephemeral=True
        )

async def _list_notes(self, interaction: discord.Interaction, category: Optional[str]):
    """List user's notes."""
    
    try:
        # Get notes
        notes = await self.notes_service.get_user_notes(
            interaction.user.id,
            category=category
        )
        
        if not notes:
            await interaction.followup.send(
                f"📭 No notes found{f' in category \"{category}\"' if category else ''}",
                ephemeral=True
            )
            return
        
        # Group notes by category
        categories = {}
        for note in notes:
            if note.category not in categories:
                categories[note.category] = []
            categories[note.category].append(note)
        
        # Create embed
        embed = discord.Embed(
            title=f"📚 Your Notes{f' ({category})' if category else ''}",
            color=discord.Color.blue()
        )
        
        # Add notes by category
        for cat_name, cat_notes in categories.items():
            notes_text = ""
            for note in sorted(cat_notes, key=lambda n: n.created_at, reverse=True)[:10]:
                created_str = note.created_at.strftime("%m/%d/%Y")
                notes_text += f"**`{note.id[:8]}`** {note.title} *({created_str})*\n"
            
            embed.add_field(
                name=f"📁 {cat_name.title()} ({len(cat_notes)})",
                value=notes_text,
                inline=False
            )
        
        embed.set_footer(text="Use /note show <id> to view full note")
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        
    except Exception as e:
        logger.error(f"Error listing notes: {e}")
        await interaction.followup.send(
            "❌ Error loading notes",
            ephemeral=True
        )

async def _search_notes(self, interaction: discord.Interaction, search_term: Optional[str]):
    """Search through user's notes."""
    
    if not search_term:
        await interaction.followup.send(
            "❌ Search term is required",
            ephemeral=True
        )
        return
    
    try:
        # Search notes
        matching_notes = await self.notes_service.search_notes(
            interaction.user.id,
            search_term
        )
        
        if not matching_notes:
            await interaction.followup.send(
                f"🔍 No notes found matching \"{search_term}\"",
                ephemeral=True
            )
            return
        
        # Create results embed
        embed = discord.Embed(
            title=f"🔍 Search Results for \"{search_term}\"",
            color=discord.Color.gold()
        )
        
        # Show matching notes
        results_text = ""
        for note in matching_notes[:10]:
            # Highlight search term in content
            highlighted_content = note.content.replace(
                search_term, 
                f"**{search_term}**"
            )
            
            preview = highlighted_content[:100] + ("..." if len(highlighted_content) > 100 else "")
            results_text += f"**`{note.id[:8]}`** {note.title}\n{preview}\n\n"
        
        embed.add_field(
            name=f"Found {len(matching_notes)} notes",
            value=results_text,
            inline=False
        )
        
        embed.set_footer(text="Use /note show <id> to view full note")
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        
    except Exception as e:
        logger.error(f"Error searching notes: {e}")
        await interaction.followup.send(
            "❌ Error searching notes",
            ephemeral=True
        )
```

### 4. Search Utilities
**File**: `cogs/search_commands.py:34-145`

#### 4.1 Search and Lookup Commands
```python
@app_commands.command(name="search", description="Search for information")
@app_commands.describe(
    query="What to search for",
    source="Where to search (web, wiki, urban, etc.)"
)
async def search_information(
    self,
    interaction: discord.Interaction,
    query: str,
    source: str = "web"
):
    """Search for information from various sources."""
    await interaction.response.defer(thinking=True)
    
    try:
        # Route to appropriate search service
        if source == "web":
            result = await self.web_search_service.search_web(query)
            await self._send_web_search_results(interaction, query, result)
        
        elif source == "wiki":
            result = await self.web_search_service.search_wikipedia(query)
            await self._send_wikipedia_results(interaction, query, result)
        
        elif source == "urban":
            result = await self.web_search_service.search_urban_dictionary(query)
            await self._send_urban_dictionary_results(interaction, query, result)
        
        elif source == "image":
            result = await self.web_search_service.search_images(query)
            await self._send_image_search_results(interaction, query, result)
        
        else:
            await interaction.followup.send(
                f"❌ Unknown source: {source}. Available: web, wiki, urban, image",
                ephemeral=True
            )
    
    except Exception as e:
        await interaction.followup.send(
            f"❌ Error searching: {e}",
            ephemeral=True
        )

async def _send_web_search_results(self, interaction: discord.Interaction, query: str, results):
    """Send web search results."""
    
    if not results or not results.get('results'):
        await interaction.followup.send(
            f"🔍 No results found for \"{query}\"",
            ephemeral=True
        )
        return
    
    # Create results embed
    embed = discord.Embed(
        title=f"🔍 Web Search: {query}",
        color=discord.Color.blue()
    )
    
    # Show top results
    for i, result in enumerate(results['results'][:5], 1):
        title = result.get('title', 'No title')
        url = result.get('url', '')
        snippet = result.get('snippet', 'No description')[:200]
        
        embed.add_field(
            name=f"{i}. {title}",
            value=f"{snippet}\n[Read more]({url})",
            inline=False
        )
    
    # Add attribution
    if results.get('source'):
        embed.set_footer(text=f"Source: {results['source']}")
    
    await interaction.followup.send(embed=embed, ephemeral=True)

@app_commands.command(name="define", description="Look up word definitions")
@app_commands.describe(word="Word to define", source="Dictionary source")
async def define_word(
    self,
    interaction: discord.Interaction,
    word: str,
    source: str = "dictionary"
):
    """Look up word definitions."""
    await interaction.response.defer(thinking=True)
    
    try:
        if source == "dictionary":
            definition = await self.web_search_service.get_dictionary_definition(word)
            await self._send_dictionary_definition(interaction, word, definition)
        
        elif source == "urban":
            definition = await self.web_search_service.search_urban_dictionary(word)
            await self._send_urban_dictionary_results(interaction, word, definition)
        
        else:
            await interaction.followup.send(
                f"❌ Unknown source: {source}. Available: dictionary, urban",
                ephemeral=True
            )
    
    except Exception as e:
        await interaction.followup.send(
            f"❌ Error defining word: {e}",
            ephemeral=True
        )

@app_commands.command(name="weather", description="Get weather information")
@app_commands.describe(location="City name or location")
async def get_weather(self, interaction: discord.Interaction, location: str):
    """Get weather information for a location."""
    await interaction.response.defer(thinking=True)
    
    try:
        weather = await self.web_search_service.get_weather(location)
        
        if not weather:
            await interaction.followup.send(
                f"🌤️ Could not find weather information for \"{location}\"",
                ephemeral=True
            )
            return
        
        # Create weather embed
        embed = discord.Embed(
            title=f"🌤️ Weather for {weather.get('location', location)}",
            color=discord.Color.blue()
        )
        
        # Current conditions
        current = weather.get('current', {})
        embed.add_field(
            name="🌡️ Temperature",
            value=f"{current.get('temperature', 'N/A')}°{current.get('unit', 'C')}",
            inline=True
        )
        
        embed.add_field(
            name="💧 Humidity",
            value=f"{current.get('humidity', 'N/A')}%",
            inline=True
        )
        
        embed.add_field(
            name="💨 Wind",
            value=f"{current.get('wind_speed', 'N/A')} {current.get('wind_unit', 'km/h')}",
            inline=True
        )
        
        embed.add_field(
            name="☁️ Conditions",
            value=current.get('description', 'N/A'),
            inline=True
        )
        
        embed.add_field(
            name="👤 Feels Like",
            value=f"{current.get('feels_like', 'N/A')}°{current.get('unit', 'C')}",
            inline=True
        )
        
        # Forecast if available
        forecast = weather.get('forecast')
        if forecast:
            forecast_text = ""
            for day in forecast[:3]:  # Next 3 days
                date_str = day.get('date', 'Unknown date')
                high_temp = day.get('high', 'N/A')
                low_temp = day.get('low', 'N/A')
                conditions = day.get('conditions', 'N/A')
                
                forecast_text += f"**{date_str}:** {high_temp}°/{low_temp}° - {conditions}\n"
            
            embed.add_field(
                name="📅 3-Day Forecast",
                value=forecast_text,
                inline=False
            )
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        await interaction.followup.send(
            f"❌ Error getting weather: {e}",
            ephemeral=True
        )
```

## Configuration

### Utilities Settings
```bash
# Reminder System
REMINDERS_ENABLED=true                        # Enable reminder functionality
MAX_REMINDERS_PER_USER=10                   # Max reminders per user
REMINDER_CLEANUP_DAYS=30                     # How long to keep old reminders

# Notes System
NOTES_ENABLED=true                            # Enable note functionality
MAX_NOTES_PER_USER=100                       # Max notes per user
NOTE_MAX_LENGTH=10000                        # Maximum note length
NOTES_ENCRYPTION_ENABLED=false                # Encrypt note storage

# Search Services
WEB_SEARCH_ENABLED=true                        # Enable web search
WEB_SEARCH_ENGINE=duckduckgo                  # Default search engine
WEB_SEARCH_MAX_RESULTS=5                     # Max search results
SEARCH_CACHE_DURATION=3600                   # Cache search results (seconds)

# Utilities Configuration
TIMEZONE_DETECTION=true                        # Auto-detect user timezones
SPELL_CHECK_ENABLED=true                      # Spell check in commands
AUTO_CORRECTION_ENABLED=true                  # Auto-correct common typos

# Data Storage
UTILITIES_DATA_PATH=./data/utilities          # Utilities data storage
REMINDERS_PATH=./data/reminders              # Reminder storage
NOTES_PATH=./data/notes                      # Notes storage
SEARCH_CACHE_PATH=./data/search_cache         # Search cache
```

## Integration Points

### With Chat System
- **Command Integration**: Utility commands integrated with chat
- **Context Awareness**: Commands use chat context
- **Natural Language**: Natural language reminder creation

### With User Management
- **Personal Data**: User-specific reminders and notes
- **Preferences**: Utility feature preferences
- **Permissions**: Role-based access to utilities

### With Analytics System
- **Usage Tracking**: Monitor utility command usage
- **Performance Metrics**: Track search performance
- **User Engagement**: Analyze utility feature engagement

## Performance Considerations

### 1. Reminder Scheduling
- **Efficient Scheduling**: Use asyncio tasks for reminders
- **Memory Bounding**: Limit active reminders per user
- **Background Cleanup**: Periodic cleanup of old reminders

### 2. Note Storage
- **Lazy Loading**: Load notes on-demand
- **Compression**: Compress large notes for storage
- **Indexing**: Fast note search with indexing

### 3. Search Performance
- **Result Caching**: Cache search results
- **Rate Limiting**: Respect API rate limits
- **Parallel Requests**: Multiple search sources in parallel

## Security Considerations

### 1. Data Privacy
- **User Isolation**: Users can only access their own data
- **Encryption**: Sensitive data encrypted at rest
- **Data Minimization**: Only collect necessary data

### 2. Input Validation
- **XSS Prevention**: Sanitize all user inputs
- **SQL Injection**: Parameterized queries for data storage
- **Command Injection**: Validate all command parameters

## Common Issues and Troubleshooting

### 1. Reminders Not Working
```python
# Check reminder service
reminder_service = ReminderService(bot)
await reminder_service.load_reminders()

# Test time parsing
await reminder_service._parse_time("in 5 minutes", user)

# Check scheduled tasks
print(f"Scheduled tasks: {len(reminder_service.scheduled_tasks)}")
```

### 2. Notes Not Saving
```bash
# Check notes directory
ls -la ./data/notes/

# Test note creation
python -c "
import asyncio
from services.discord.notes import NotesService
async def test():
    service = NotesService()
    note = await service.create_note(123, 'Test', 'Test content')
    print(f'Created note: {note.id}')
asyncio.run(test())
"
```

### 3. Search Not Working
```bash
# Check web search configuration
echo $WEB_SEARCH_ENABLED
echo $WEB_SEARCH_ENGINE

# Test search API
python -c "
import asyncio
from services.discord.web_search import WebSearchService
async def test():
    service = WebSearchService()
    result = await service.search_web('test query')
    print(f'Search results: {result}')
asyncio.run(test())
"
```

## Files Reference

| File | Purpose | Key Functions |
|-------|---------|------------------|
| `cogs/reminders.py` | Reminder command interface |
| `cogs/notes.py` | Note management commands |
| `cogs/search_commands.py` | Search and lookup commands |
| `services/discord/reminders.py` | Reminder service backend |
| `services/discord/notes.py` | Notes management service |
| `services/discord/web_search.py` | Web search integration |
| `utils/helpers.py` | General utility functions |
| `utils/template_renderer.py` | Template rendering utilities |

---

**Last Updated**: 2025-12-16
**Version**: 1.0