# Games and Entertainment System Workflow

This document describes the complete games and entertainment system in acore_bot, including trivia games, interactive entertainment features, and user engagement activities.

## Overview

The games and entertainment system provides **interactive fun activities** through **trivia games**, **mini-games**, **entertainment commands**, and **engagement features** to enhance user experience and community interaction.

## Architecture

### Component Structure
```
cogs/
├── entertainment/           # Entertainment commands and games
│   ├── trivia.py           # Trivia game implementation
│   ├── games.py            # Mini-games collection
│   └── fun_commands.py    # Fun and utility commands
└── chat/                  # Entertainment integration in chat

services/
├── trivia/                 # Trivia game service
│   ├── question_bank.py    # Question management
│   ├── scoring.py         # Game scoring system
│   └── categories.py      # Question categories
└── entertainment/          # Entertainment service layer
    ├── game_manager.py     # Game session management
    └── leaderboard.py     # Score tracking and rankings

data/
├── trivia/                 # Trivia data storage
├── game_sessions/          # Active game sessions
└── leaderboards/          # Score rankings
```

### Service Dependencies
```
Entertainment Dependencies:
├── Game State Management   # Session tracking and persistence
├── Scoring System         # Point calculation and ranking
├── Timer Management       # Game timing and deadlines
├── Question Database      # Trivia and game content
├── User Progress          # Player statistics and history
└── Social Features        # Leaderboards and competitions
```

## Trivia Game System

### 1. Trivia Game Implementation
**File**: `cogs/entertainment/trivia.py:45-234`

#### 1.1 Trivia Command Interface
```python
@app_commands.command(name="trivia", description="Start a trivia game")
@app_commands.describe(
    category="Question category",
    difficulty="Difficulty level",
    questions="Number of questions"
)
async def start_trivia(
    self,
    interaction: discord.Interaction,
    category: Optional[str] = None,
    difficulty: Optional[str] = "medium",
    questions: Optional[int] = 10
):
    """Start a new trivia game session."""
    await interaction.response.defer(thinking=True)
    
    try:
        # 1. Validate inputs
        valid_difficulties = ['easy', 'medium', 'hard']
        if difficulty not in valid_difficulties:
            await interaction.followup.send(
                f"❌ Invalid difficulty. Choose from: {', '.join(valid_difficulties)}",
                ephemeral=True
            )
            return
        
        if not 5 <= questions <= 20:
            await interaction.followup.send(
                "❌ Questions must be between 5 and 20",
                ephemeral=True
            )
            return
        
        # 2. Check if game already active
        if await self.trivia_service.is_game_active(interaction.channel.id):
            await interaction.followup.send(
                "❌ A trivia game is already in progress in this channel!",
                ephemeral=True
            )
            return
        
        # 3. Create new game session
        game_session = await self.trivia_service.create_game(
            channel_id=interaction.channel.id,
            guild_id=interaction.guild.id,
            host_id=interaction.user.id,
            category=category,
            difficulty=difficulty,
            question_count=questions
        )
        
        # 4. Start the game
        await self.trivia_service.start_game(game_session)
        
        # 5. Announce game start
        embed = discord.Embed(
            title="🎯 Trivia Game Started!",
            description=f"**Host:** {interaction.user.mention}\n"
                      f"**Category:** {category or 'Mixed'}\n"
                      f"**Difficulty:** {difficulty}\n"
                      f"**Questions:** {questions}\n\n"
                      f"React with the correct answer emoji to respond!",
            color=discord.Color.blue()
        )
        
        await interaction.followup.send(embed=embed)
        
        # 6. Send first question
        await self._send_next_question(interaction.channel, game_session)
        
    except Exception as e:
        await interaction.followup.send(
            f"❌ Error starting trivia game: {e}",
            ephemeral=True
        )

async def _send_next_question(self, channel: discord.TextChannel, game_session: GameSession):
    """Send the next trivia question."""
    
    try:
        # 1. Get next question
        question = await self.trivia_service.get_next_question(game_session)
        
        if not question:
            # Game over - show results
            await self._end_game(channel, game_session)
            return
        
        # 2. Create question embed
        embed = discord.Embed(
            title=f"🧠 Question {game_session.current_question + 1}/{game_session.total_questions}",
            description=question.question_text,
            color=discord.Color.gold()
        )
        
        if question.category:
            embed.add_field(name="Category", value=question.category, inline=True)
        
        if question.difficulty:
            embed.add_field(name="Difficulty", value=question.difficulty, inline=True)
        
        # 3. Add answer options (if multiple choice)
        if question.question_type == "multiple_choice":
            # Shuffle options and assign emojis
            options = question.options.copy()
            random.shuffle(options)
            
            option_text = ""
            for i, option in enumerate(options):
                emoji = self.emoji_options[i]
                option_text += f"{emoji} {option}\n"
                game_session.current_options[emoji] = option
            
            embed.add_field(name="Options", value=option_text, inline=False)
            
            # Add reaction emojis to the message
            message = await channel.send(embed=embed)
            for emoji in self.emoji_options[:len(options)]:
                await message.add_reaction(emoji)
        
        else:
            # True/false or open-ended
            if question.question_type == "true_false":
                embed.add_field(name="Options", value="✅ True\n❌ False", inline=False)
                message = await channel.send(embed=embed)
                await message.add_reaction("✅")
                await message.add_reaction("❌")
            else:
                # Open-ended - users type answers
                message = await channel.send(embed=embed)
        
        # 4. Store message and set timer
        game_session.current_message_id = message.id
        game_session.question_start_time = datetime.now()
        
        # 5. Start answer timer (30 seconds default)
        asyncio.create_task(self._question_timer(channel, game_session, 30))
        
    except Exception as e:
        logger.error(f"Error sending question: {e}")
        await channel.send("❌ Error sending question. Skipping to next...")

async def _question_timer(self, channel: discord.TextChannel, game_session: GameSession, seconds: int):
    """Handle question timing and reveal answer."""
    
    try:
        await asyncio.sleep(seconds)
        
        # Check if question is still active
        if game_session.current_message_id and not game_session.question_revealed:
            # Time's up - reveal answer
            await self._reveal_answer(channel, game_session)
            
            # Wait a moment then continue
            await asyncio.sleep(3)
            
            # Send next question or end game
            await self._send_next_question(channel, game_session)
    
    except Exception as e:
        logger.error(f"Error in question timer: {e}")

async def _reveal_answer(self, channel: discord.TextChannel, game_session: GameSession):
    """Reveal the correct answer and show scores."""
    
    try:
        # Mark question as revealed
        game_session.question_revealed = True
        
        # Get current question
        question = game_session.current_question
        
        # Process all reactions
        if game_session.current_message_id:
            try:
                message = await channel.fetch_message(game_session.current_message_id)
                
                correct_answer = question.correct_answer
                correct_emoji = None
                
                # Find the correct emoji for multiple choice
                if question.question_type == "multiple_choice":
                    for emoji, option in game_session.current_options.items():
                        if option == correct_answer:
                            correct_emoji = emoji
                            break
                elif question.question_type == "true_false":
                    correct_emoji = "✅" if correct_answer.lower() == "true" else "❌"
                
                # Award points
                correct_players = []
                for reaction in message.reactions:
                    if str(reaction.emoji) == correct_emoji:
                        # Award points to all users who reacted correctly
                        async for user in reaction.users():
                            if not user.bot:
                                await self.trivia_service.award_points(
                                    game_session, user.id, question.points
                                )
                                correct_players.append(user.mention)
                
                # Create reveal embed
                embed = discord.Embed(
                    title="✅ Answer Revealed!",
                    description=f"**Correct Answer:** {correct_answer}",
                    color=discord.Color.green()
                )
                
                embed.add_field(name="Category", value=question.category or "General", inline=True)
                embed.add_field(name="Points", value=str(question.points), inline=True)
                
                if correct_players:
                    embed.add_field(
                        name="Correct Players",
                        value=", ".join(correct_players),
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="Correct Players",
                        value="Nobody got it right!",
                        inline=False
                    )
                
                # Show current top scores
                top_scores = await self.trivia_service.get_top_scores(game_session, 5)
                if top_scores:
                    score_text = "\n".join([
                        f"**{i+1}.** <@{user_id}>: {score} points"
                        for i, (user_id, score) in enumerate(top_scores)
                    ])
                    embed.add_field(name="🏆 Current Standings", value=score_text, inline=False)
                
                await channel.send(embed=embed)
                
                # Mark question as completed
                game_session.current_question += 1
                game_session.current_options = {}
                
            except discord.NotFound:
                # Message was deleted
                await channel.send("⚠️ Question message was deleted. Moving to next question...")
        
    except Exception as e:
        logger.error(f"Error revealing answer: {e}")
        await channel.send("❌ Error revealing answer. Continuing...")

async def _end_game(self, channel: discord.TextChannel, game_session: GameSession):
    """End the trivia game and show final results."""
    
    try:
        # 1. Get final scores
        final_scores = await self.trivia_service.get_final_scores(game_session)
        
        # 2. Create results embed
        embed = discord.Embed(
            title="🎉 Trivia Game Complete!",
            description=f"**Total Questions:** {game_session.total_questions}\n"
                      f"**Host:** <@{game_session.host_id}>",
            color=discord.Color.gold()
        )
        
        # 3. Add podium (top 3)
        if len(final_scores) >= 1:
            gold, silver, bronze = "🥇", "🥈", "🥉"
            
            if len(final_scores) >= 1:
                winner_id, winner_score = final_scores[0]
                embed.add_field(
                    name=f"{gold} 1st Place",
                    value=f"<@{winner_id}>: {winner_score} points",
                    inline=False
                )
            
            if len(final_scores) >= 2:
                second_id, second_score = final_scores[1]
                embed.add_field(
                    name=f"{silver} 2nd Place",
                    value=f"<@{second_id}>: {second_score} points",
                    inline=False
                )
            
            if len(final_scores) >= 3:
                third_id, third_score = final_scores[2]
                embed.add_field(
                    name=f"{bronze} 3rd Place",
                    value=f"<@{third_id}>: {third_score} points",
                    inline=False
                )
        
        # 4. Add all participants
        if len(final_scores) > 3:
            other_players = []
            for user_id, score in final_scores[3:]:
                other_players.append(f"<@{user_id}>: {score}")
            
            embed.add_field(
                name="🎯 Other Participants",
                value="\n".join(other_players),
                inline=False
            )
        
        # 5. Game statistics
        stats = await self.trivia_service.get_game_statistics(game_session)
        embed.add_field(
            name="📊 Game Statistics",
            value=f"**Average Score:** {stats['average_score']:.1f}\n"
                  f"**Highest Score:** {stats['highest_score']}\n"
                  f"**Total Participants:** {len(final_scores)}",
            inline=False
        )
        
        await channel.send(embed=embed)
        
        # 6. Update leaderboards
        await self.trivia_service.update_leaderboards(game_session)
        
        # 7. Clean up game session
        await self.trivia_service.end_game(game_session)
        
    except Exception as e:
        logger.error(f"Error ending game: {e}")
        await channel.send("❌ Error ending game.")
```

### 2. Trivia Service Backend
**File**: `services/trivia/question_bank.py:34-156`

#### 2.1 Question Management System
```python
class QuestionBank:
    """Manages trivia questions and categories."""
    
    def __init__(self, data_path: str = "./data/trivia"):
        self.data_path = Path(data_path)
        self.questions = {}  # category -> questions
        self.categories = set()
        
        # Load questions on initialization
        self._load_questions()

    def _load_questions(self):
        """Load questions from JSON files."""
        
        try:
            # Load general questions
            general_file = self.data_path / "general.json"
            if general_file.exists():
                with open(general_file, 'r', encoding='utf-8') as f:
                    general_questions = json.load(f)
                    self.questions['general'] = general_questions
                    self.categories.add('general')
            
            # Load category-specific questions
            for category_file in self.data_path.glob("*.json"):
                if category_file.name != "general.json":
                    category_name = category_file.stem
                    with open(category_file, 'r', encoding='utf-8') as f:
                        category_questions = json.load(f)
                        self.questions[category_name] = category_questions
                        self.categories.add(category_name)
            
            logger.info(f"Loaded {sum(len(q) for q in self.questions.values())} questions in {len(self.categories)} categories")
            
        except Exception as e:
            logger.error(f"Error loading questions: {e}")

    async def get_questions(
        self, 
        category: Optional[str] = None, 
        difficulty: str = "medium",
        count: int = 10
    ) -> List[TriviaQuestion]:
        """Get questions for a trivia game."""
        
        try:
            # Determine question pool
            if category and category in self.questions:
                pool = self.questions[category]
            else:
                # Mix from all categories
                pool = []
                for questions in self.questions.values():
                    pool.extend(questions)
            
            # Filter by difficulty
            if difficulty != "mixed":
                pool = [q for q in pool if q.get('difficulty', 'medium') == difficulty]
            
            # Shuffle and select questions
            random.shuffle(pool)
            selected_questions = pool[:count]
            
            # Convert to TriviaQuestion objects
            trivia_questions = []
            for q_data in selected_questions:
                question = TriviaQuestion(
                    question_id=q_data.get('id', str(uuid.uuid4())),
                    question_text=q_data['question'],
                    question_type=q_data.get('type', 'multiple_choice'),
                    options=q_data.get('options', []),
                    correct_answer=q_data['correct_answer'],
                    category=q_data.get('category', 'general'),
                    difficulty=q_data.get('difficulty', 'medium'),
                    points=q_data.get('points', 10),
                    explanation=q_data.get('explanation', '')
                )
                trivia_questions.append(question)
            
            return trivia_questions
            
        except Exception as e:
            logger.error(f"Error getting questions: {e}")
            return []

@dataclass
class TriviaQuestion:
    """Represents a single trivia question."""
    question_id: str
    question_text: str
    question_type: str  # multiple_choice, true_false, open_ended
    options: List[str]
    correct_answer: str
    category: str
    difficulty: str
    points: int
    explanation: str = ""

class TriviaService:
    """Manages trivia game sessions and scoring."""
    
    def __init__(self, question_bank: QuestionBank):
        self.question_bank = question_bank
        self.active_games = {}  # channel_id -> GameSession
        self.game_sessions = {}  # session_id -> GameSession
        self.player_stats = {}  # user_id -> PlayerStats
        
        # Game configuration
        self.default_question_time = 30  # seconds
        self.max_game_duration = 300  # 5 minutes
        self.max_players_per_game = 20

    async def create_game(
        self,
        channel_id: int,
        guild_id: int,
        host_id: int,
        category: Optional[str],
        difficulty: str,
        question_count: int
    ) -> GameSession:
        """Create a new trivia game session."""
        
        # Generate unique session ID
        session_id = str(uuid.uuid4())
        
        # Get questions for the game
        questions = await self.question_bank.get_questions(
            category=category,
            difficulty=difficulty,
            count=question_count
        )
        
        if len(questions) < question_count:
            raise ValueError(f"Not enough questions available. Only {len(questions)} found.")
        
        # Create game session
        game_session = GameSession(
            session_id=session_id,
            channel_id=channel_id,
            guild_id=guild_id,
            host_id=host_id,
            questions=questions,
            current_question=0,
            total_questions=question_count,
            players={},  # user_id -> PlayerScore
            started_at=datetime.now(),
            status='active'
        )
        
        # Store sessions
        self.active_games[channel_id] = game_session
        self.game_sessions[session_id] = game_session
        
        return game_session

    async def award_points(self, game_session: GameSession, user_id: int, points: int):
        """Award points to a player."""
        
        if user_id not in game_session.players:
            game_session.players[user_id] = PlayerScore(
                user_id=user_id,
                score=0,
                correct_answers=0,
                total_answered=0
            )
        
        player = game_session.players[user_id]
        player.score += points
        player.correct_answers += 1
        player.total_answered += 1
        
        # Update overall player stats
        await self._update_player_stats(user_id, points)

    async def _update_player_stats(self, user_id: int, points: int):
        """Update overall player statistics."""
        
        if user_id not in self.player_stats:
            self.player_stats[user_id] = PlayerStats(
                user_id=user_id,
                total_games_played=0,
                total_points=0,
                highest_score=0,
                average_score=0.0,
                favorite_category=None,
                questions_answered=0,
                correct_answers=0
            )
        
        stats = self.player_stats[user_id]
        stats.total_points += points
        stats.questions_answered += 1
        
        # Calculate accuracy if we tracked correct answers
        # This would need more detailed tracking in a full implementation

@dataclass
class GameSession:
    """Represents an active trivia game."""
    session_id: str
    channel_id: int
    guild_id: int
    host_id: int
    questions: List[TriviaQuestion]
    current_question: int
    total_questions: int
    players: Dict[int, PlayerScore]
    started_at: datetime
    status: str  # active, paused, completed
    current_message_id: Optional[int] = None
    current_options: Dict[str, str] = field(default_factory=dict)
    question_start_time: Optional[datetime] = None
    question_revealed: bool = False

@dataclass
class PlayerScore:
    """Score for a player in a specific game."""
    user_id: int
    score: int
    correct_answers: int
    total_answered: int

@dataclass
class PlayerStats:
    """Overall statistics for a player."""
    user_id: int
    total_games_played: int
    total_points: int
    highest_score: int
    average_score: float
    favorite_category: Optional[str]
    questions_answered: int
    correct_answers: int
```

### 3. Mini-Games Collection
**File**: `cogs/entertainment/games.py:45-189`

#### 3.1 Word Games and Puzzles
```python
@app_commands.command(name="wordle", description="Play a Wordle-style word game")
async def wordle_game(self, interaction: discord.Interaction):
    """Start a Wordle-style word guessing game."""
    await interaction.response.defer(thinking=True)
    
    try:
        # 1. Select random 5-letter word
        word = await self._get_random_word(5)
        
        # 2. Create game session
        game_data = {
            'word': word.upper(),
            'attempts': [],
            'max_attempts': 6,
            'user_id': interaction.user.id,
            'channel_id': interaction.channel.id
        }
        
        # Store game state
        self.wordle_games[interaction.channel.id] = game_data
        
        # 3. Create game embed
        embed = discord.Embed(
            title="🎯 Wordle Game",
            description=f"Guess the 5-letter word in 6 attempts!\n\n"
                      f"🟩 = Correct letter, correct position\n"
                      f"🟨 = Correct letter, wrong position\n"
                      f"⬛ = Letter not in word\n\n"
                      f"Type your guess in chat!",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Attempts Remaining",
            value=f"{game_data['max_attempts']} attempts left",
            inline=True
        )
        
        embed.set_footer(text="Type your guess in the chat channel")
        
        await interaction.followup.send(embed=embed)
        
        # 4. Set up message listener
        self.bot.add_listener(self._on_wordle_guess)
        
    except Exception as e:
        await interaction.followup.send(
            f"❌ Error starting Wordle game: {e}",
            ephemeral=True
        )

async def _on_wordle_guess(self, message: discord.Message):
    """Handle Wordle guess attempts."""
    
    # Check if there's an active game in this channel
    if message.channel.id not in self.wordle_games:
        return
    
    game_data = self.wordle_games[message.channel.id]
    
    # Check if it's the player's turn (Wordle is single-player)
    if message.author.id != game_data['user_id']:
        return
    
    # Check if it's a valid guess
    guess = message.content.strip().upper()
    
    if len(guess) != 5 or not guess.isalpha():
        await message.reply("❌ Please enter a valid 5-letter word!")
        return
    
    # Check if game is over
    if len(game_data['attempts']) >= game_data['max_attempts']:
        return
    
    try:
        # 1. Process the guess
        result = self._check_wordle_guess(game_data['word'], guess)
        game_data['attempts'].append({
            'guess': guess,
            'result': result
        })
        
        # 2. Create response embed
        embed = discord.Embed(
            title="📝 Wordle Guess",
            color=discord.Color.gold()
        )
        
        # Show guess with emojis
        guess_display = ""
        for letter, status in zip(guess, result):
            if status == 'correct':
                emoji = "🟩"
            elif status == 'present':
                emoji = "🟨"
            else:
                emoji = "⬛"
            guess_display += emoji
        
        embed.add_field(name="Your Guess", value=f"`{guess}`\n{guess_display}", inline=False)
        
        # Check for win
        if all(status == 'correct' for status in result):
            embed.description = "🎉 **CONGRATULATIONS!** You got the word!"
            embed.color = discord.Color.green()
            
            # End the game
            del self.wordle_games[message.channel.id]
            
            # Show attempts
            attempts_text = "\n".join([
                f"Attempt {i+1}: `{attempt['guess']}` {self._format_wordle_result(attempt['result'])}"
                for i, attempt in enumerate(game_data['attempts'])
            ])
            embed.add_field(name="All Attempts", value=attempts_text, inline=False)
        
        # Check for loss (out of attempts)
        elif len(game_data['attempts']) >= game_data['max_attempts']:
            embed.description = f"💔 **Game Over!** The word was `{game_data['word']}`"
            embed.color = discord.Color.red()
            
            # End the game
            del self.wordle_games[message.channel.id]
        
        else:
            # Continue game
            attempts_remaining = game_data['max_attempts'] - len(game_data['attempts'])
            embed.add_field(
                name="Attempts Remaining",
                value=f"{attempts_remaining} attempts left",
                inline=True
            )
            
            # Show previous attempts
            attempts_text = "\n".join([
                f"Attempt {i+1}: {self._format_wordle_result(attempt['result'])}"
                for i, attempt in enumerate(game_data['attempts'][:-1])
            ])
            
            if attempts_text:
                embed.add_field(name="Previous Attempts", value=attempts_text, inline=False)
        
        await message.reply(embed=embed)
        
        # Delete the guess message to keep channel clean
        try:
            await message.delete()
        except discord.Forbidden:
            pass  # Don't have permission to delete
        
    except Exception as e:
        logger.error(f"Error processing Wordle guess: {e}")
        await message.reply("❌ Error processing your guess!")

def _check_wordle_guess(self, target_word: str, guess: str) -> List[str]:
    """Check a Wordle guess against the target word."""
    
    result = []
    target_chars = list(target_word)
    
    # First pass: mark correct letters
    for i, (target_char, guess_char) in enumerate(zip(target_word, guess)):
        if guess_char == target_char:
            result.append('correct')
            target_chars[i] = None  # Mark as used
        else:
            result.append('absent')
    
    # Second pass: mark present letters
    for i, (target_char, guess_char) in enumerate(zip(target_word, guess)):
        if result[i] == 'absent' and guess_char in target_chars:
            result[i] = 'present'
            target_chars[target_chars.index(guess_char)] = None  # Mark as used
    
    return result

@app_commands.command(name="rps", description="Play Rock Paper Scissors")
@app_commands.describe(choice="Your choice: rock, paper, or scissors")
async def rock_paper_scissors(self, interaction: discord.Interaction, choice: str):
    """Play Rock Paper Scissors against the bot."""
    await interaction.response.defer(thinking=True)
    
    try:
        # 1. Validate choice
        valid_choices = ['rock', 'paper', 'scissors']
        if choice.lower() not in valid_choices:
            await interaction.followup.send(
                f"❌ Invalid choice. Choose from: {', '.join(valid_choices)}",
                ephemeral=True
            )
            return
        
        user_choice = choice.lower()
        
        # 2. Bot makes choice
        bot_choice = random.choice(valid_choices)
        
        # 3. Determine winner
        if user_choice == bot_choice:
            result = "tie"
            result_emoji = "🤝"
            result_message = "It's a tie!"
        elif (
            (user_choice == 'rock' and bot_choice == 'scissors') or
            (user_choice == 'paper' and bot_choice == 'rock') or
            (user_choice == 'scissors' and bot_choice == 'paper')
        ):
            result = "win"
            result_emoji = "🎉"
            result_message = "You win!"
        else:
            result = "lose"
            result_emoji = "😔"
            result_message = "You lose!"
        
        # 4. Create result embed
        embed = discord.Embed(
            title="✂️ Rock Paper Scissors",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Your Choice",
            value=f"{self._get_rps_emoji(user_choice)} {user_choice.title()}",
            inline=True
        )
        
        embed.add_field(
            name="Bot's Choice",
            value=f"{self._get_rps_emoji(bot_choice)} {bot_choice.title()}",
            inline=True
        )
        
        embed.add_field(
            name="Result",
            value=f"{result_emoji} {result_message}",
            inline=False
        )
        
        await interaction.followup.send(embed=embed)
        
        # 5. Update statistics
        await self._update_rps_stats(interaction.user.id, result)
        
    except Exception as e:
        await interaction.followup.send(
            f"❌ Error playing Rock Paper Scissors: {e}",
            ephemeral=True
        )

def _get_rps_emoji(self, choice: str) -> str:
    """Get emoji for Rock Paper Scissors choice."""
    emojis = {
        'rock': '🗿',
        'paper': '📄',
        'scissors': '✂️'
    }
    return emojis.get(choice, '❓')
```

### 4. Entertainment Commands
**File**: `cogs/entertainment/fun_commands.py:34-145`

#### 4.1 Fun and Utility Commands
```python
@app_commands.command(name="8ball", description="Ask the magic 8-ball a question")
@app_commands.describe(question="Your yes/no question")
async def magic_8ball(self, interaction: discord.Interaction, question: str):
    """Get a response from the magic 8-ball."""
    await interaction.response.defer(thinking=True)
    
    try:
        # 8-ball responses
        responses = {
            'positive': [
                "It is certain.", "It is decidedly so.", "Without a doubt.",
                "Yes, definitely.", "You may rely on it.", "As I see it, yes.",
                "Most likely.", "Outlook good.", "Yes.", "Signs point to yes."
            ],
            'neutral': [
                "Reply hazy, try again.", "Ask again later.", "Better not tell you now.",
                "Cannot predict now.", "Concentrate and ask again."
            ],
            'negative': [
                "Don't count on it.", "My reply is no.", "My sources say no.",
                "Outlook not so good.", "Very doubtful."
            ]
        }
        
        # Random selection weighted towards positive
        weights = {'positive': 0.4, 'neutral': 0.3, 'negative': 0.3}
        category = random.choices(list(weights.keys()), weights=list(weights.values()))[0]
        response = random.choice(responses[category])
        
        # Create embed
        embed = discord.Embed(
            title="🎱 Magic 8-Ball",
            description=f"**Question:** {question}\n\n**Answer:** {response}",
            color=discord.Color.purple()
        )
        
        embed.set_thumbnail(url="https://i.imgur.com/m8b3T8N.png")  # 8-ball image
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        await interaction.followup.send(
            f"❌ Error consulting the magic 8-ball: {e}",
            ephemeral=True
        )

@app_commands.command(name="roll", description="Roll dice")
@app_commands.describe(
    sides="Number of sides on the dice",
    count="Number of dice to roll",
    modifier="Optional modifier to add/subtract"
)
async def roll_dice(
    self,
    interaction: discord.Interaction,
    sides: int = 6,
    count: int = 1,
    modifier: Optional[int] = None
):
    """Roll dice with optional modifier."""
    await interaction.response.defer(thinking=True)
    
    try:
        # Validate inputs
        if not 2 <= sides <= 100:
            await interaction.followup.send(
                "❌ Dice must have between 2 and 100 sides",
                ephemeral=True
            )
            return
        
        if not 1 <= count <= 20:
            await interaction.followup.send(
                "❌ You can roll between 1 and 20 dice",
                ephemeral=True
            )
            return
        
        # Roll the dice
        rolls = [random.randint(1, sides) for _ in range(count)]
        total = sum(rolls)
        
        # Apply modifier
        if modifier is not None:
            total += modifier
            modifier_text = f" + {modifier}" if modifier >= 0 else f" - {abs(modifier)}"
        else:
            modifier_text = ""
        
        # Create embed
        embed = discord.Embed(
            title="🎲 Dice Roll",
            color=discord.Color.blue()
        )
        
        # Show individual rolls
        if count == 1:
            embed.description = f"You rolled a **{sides}-sided die**!"
        else:
            rolls_text = ", ".join([f"`{roll}`" for roll in rolls])
            embed.description = f"You rolled **{count} {sides}-sided dice**!"
            embed.add_field(name="Individual Rolls", value=rolls_text, inline=False)
        
        # Show total
        embed.add_field(
            name="Total",
            value=f"**{total}**{modifier_text}",
            inline=True
        )
        
        # Show statistics
        if count > 1:
            avg = total / count
            embed.add_field(
                name="Statistics",
                value=f"Average: {avg:.1f}\nMax: {max(rolls)}\nMin: {min(rolls)}",
                inline=True
            )
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        await interaction.followup.send(
            f"❌ Error rolling dice: {e}",
            ephemeral=True
        )

@app_commands.command(name="coinflip", description="Flip a coin")
@app_commands.describe(times="Number of times to flip (1-10)")
async def flip_coin(self, interaction: discord.Interaction, times: int = 1):
    """Flip a coin one or more times."""
    await interaction.response.defer(thinking=True)
    
    try:
        # Validate input
        if not 1 <= times <= 10:
            await interaction.followup.send(
                "❌ You can flip between 1 and 10 coins",
                ephemeral=True
            )
            return
        
        # Flip coins
        flips = []
        heads_count = 0
        tails_count = 0
        
        for _ in range(times):
            result = random.choice(['heads', 'tails'])
            flips.append(result)
            if result == 'heads':
                heads_count += 1
            else:
                tails_count += 1
        
        # Create embed
        embed = discord.Embed(
            title="🪙 Coin Flip",
            color=discord.Color.gold()
        )
        
        if times == 1:
            coin_emoji = "🟡" if flips[0] == 'heads' else "⚪"
            embed.description = f"{coin_emoji} **{flips[0].title()}**"
        else:
            # Show results
            flip_emojis = [":large_yellow_circle:" if f == 'heads' else ":white_circle:" for f in flips]
            flip_text = " ".join(flip_emojis)
            
            embed.add_field(name="Results", value=flip_text, inline=False)
            
            embed.add_field(
                name="Summary",
                value=f"🟡 Heads: {heads_count}\n⚪ Tails: {tails_count}",
                inline=True
            )
            
            # Show winner
            if heads_count > tails_count:
                winner = "🟡 **Heads** wins!"
            elif tails_count > heads_count:
                winner = "⚪ **Tails** wins!"
            else:
                winner = "🤝 **It's a tie!**"
            
            embed.add_field(name="Winner", value=winner, inline=True)
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        await interaction.followup.send(
            f"❌ Error flipping coin: {e}",
            ephemeral=True
        )
```

## Configuration

### Games and Entertainment Settings
```bash
# Trivia Configuration
TRIVIA_ENABLED=true                              # Enable trivia games
TRIVIA_QUESTION_TIME=30                         # Time per question (seconds)
TRIVIA_MAX_PLAYERS=20                           # Max players per game
TRIVIA_POINT_MULTIPLIER=1.0                     # Score multiplier

# Game Configuration
GAMES_ENABLED=true                                # Enable mini-games
WORDLE_MAX_ATTEMPTS=6                          # Wordle attempts
RPS_COOLDOWN=5                                  # Rock Paper Scissors cooldown

# Entertainment Commands
FUN_COMMANDS_ENABLED=true                         # Enable fun commands
8BALL_COOLDOWN=10                               # 8-ball command cooldown
DICE_MAX_SIDES=100                              # Maximum dice sides
COINFLIP_MAX_TIMES=10                           # Maximum coin flips

# Data Storage
TRIVIA_DATA_PATH=./data/trivia                  # Trivia data storage
GAME_SESSIONS_PATH=./data/game_sessions          # Active game sessions
LEADERBOARDS_PATH=./data/leaderboards          # Score rankings

# Performance
GAME_SESSION_TIMEOUT=300                         # Game timeout (seconds)
MAX_CONCURRENT_GAMES=10                         # Maximum concurrent games per channel
CLEANUP_INTERVAL=300                           # Session cleanup interval
```

## Integration Points

### With Chat System
- **Game Commands**: Integrated with chat command system
- **Message Listeners**: Game-specific message handling
- **Response Timing**: Games respect chat rate limits

### With User Management
- **Player Statistics**: Track player performance
- **Score Persistence**: Save scores to user profiles
- **Achievement Tracking**: Game-based achievements

### With Analytics System
- **Game Metrics**: Track game participation and popularity
- **Performance Analysis**: Game system performance monitoring
- **User Engagement**: Game contribution to engagement metrics

## Performance Considerations

### 1. Game Session Management
- **Memory Efficiency**: Bounded game sessions with automatic cleanup
- **Timeout Handling**: Automatic session expiration
- **Concurrency Control**: Prevent game conflicts in channels

### 2. Question Database
- **Caching**: Frequently used questions cached in memory
- **Lazy Loading**: Questions loaded on-demand
- **Memory Bounding**: Limit question pool size

### 3. Response Times
- **Pre-computation**: Pre-calculate game results where possible
- **Efficient Data Structures**: Use optimized data structures for game state
- **Background Processing**: Heavy computations run in background

## Security Considerations

### 1. Game Fairness
- **Random Number Generation**: Use cryptographically secure random sources
- **Anti-cheating**: Prevent multiple accounts in same game
- **Input Validation**: Validate all user inputs to prevent exploits

### 2. Resource Protection
- **Rate Limiting**: Limit game creation frequency
- **Session Limits**: Prevent game session exhaustion
- **Memory Protection**: Bound memory usage for game state

## Common Issues and Troubleshooting

### 1. Games Not Starting
```python
# Check if game already active
if channel_id in trivia_service.active_games:
    print("Game already in progress")

# Check question availability
questions = await question_bank.get_questions(count=10)
print(f"Available questions: {len(questions)}")
```

### 2. Trivia Questions Not Loading
```bash
# Check trivia data files
ls -la ./data/trivia/

# Validate JSON format
python -m json.tool ./data/trivia/general.json

# Check permissions
ls -la ./data/trivia/general.json
```

### 3. Game Sessions Not Ending
```python
# Check active games
for channel_id, game in trivia_service.active_games.items():
    print(f"Channel {channel_id}: {game.status}")

# Force cleanup old sessions
await trivia_service.cleanup_expired_sessions()
```

## Files Reference

| File | Purpose | Key Functions |
|-------|---------|------------------|
| `cogs/entertainment/trivia.py` | Trivia game commands and logic |
| `services/trivia/question_bank.py` | Question management and loading |
| `services/trivia/scoring.py` | Game scoring and statistics |
| `cogs/entertainment/games.py` | Mini-games implementation |
| `cogs/entertainment/fun_commands.py` | Fun utility commands |
| `services/entertainment/game_manager.py` | Game session management |

---

**Last Updated**: 2025-12-16
**Version**: 1.0