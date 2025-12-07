"""Trivia game service with multiple categories and difficulty levels."""
import asyncio
import json
import logging
import random
import html
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from enum import Enum
from dataclasses import dataclass, asdict
import aiohttp

logger = logging.getLogger(__name__)


class Difficulty(Enum):
    """Trivia difficulty levels."""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class Category(Enum):
    """Trivia categories."""
    GENERAL = ("General Knowledge", 9)
    SCIENCE = ("Science & Nature", 17)
    COMPUTERS = ("Computers", 18)
    MATHEMATICS = ("Mathematics", 19)
    SPORTS = ("Sports", 21)
    GEOGRAPHY = ("Geography", 22)
    HISTORY = ("History", 23)
    MOVIES = ("Movies", 11)
    MUSIC = ("Music", 12)
    VIDEO_GAMES = ("Video Games", 15)
    ANIMALS = ("Animals", 27)
    MYTHOLOGY = ("Mythology", 20)

    def __init__(self, display_name: str, opentdb_id: int):
        self.display_name = display_name
        self.opentdb_id = opentdb_id


@dataclass
class TriviaQuestion:
    """A trivia question."""
    question: str
    correct_answer: str
    incorrect_answers: List[str]
    category: str
    difficulty: str
    question_type: str  # "multiple" or "boolean"

    def get_all_answers(self, shuffle: bool = True) -> List[str]:
        """Get all answers (correct + incorrect).

        Args:
            shuffle: Whether to shuffle the answers

        Returns:
            List of all answers
        """
        answers = [self.correct_answer] + self.incorrect_answers
        if shuffle:
            random.shuffle(answers)
        return answers

    def get_correct_index(self) -> int:
        """Get the index of the correct answer in shuffled list.

        Returns:
            Index of correct answer (0-based)
        """
        answers = self.get_all_answers(shuffle=False)
        return answers.index(self.correct_answer)


@dataclass
class TriviaScore:
    """Player's trivia score."""
    user_id: int
    username: str
    total_correct: int = 0
    total_answered: int = 0
    streak: int = 0
    best_streak: int = 0
    points: int = 0

    def answer_correct(self, difficulty: Difficulty):
        """Record a correct answer.

        Args:
            difficulty: Question difficulty
        """
        self.total_correct += 1
        self.total_answered += 1
        self.streak += 1
        self.best_streak = max(self.best_streak, self.streak)

        # Award points based on difficulty and streak
        base_points = {
            Difficulty.EASY: 10,
            Difficulty.MEDIUM: 20,
            Difficulty.HARD: 30,
        }
        streak_bonus = min(self.streak * 5, 50)  # Cap at +50
        self.points += base_points.get(difficulty, 10) + streak_bonus

    def answer_incorrect(self):
        """Record an incorrect answer."""
        self.total_answered += 1
        self.streak = 0

    @property
    def accuracy(self) -> float:
        """Calculate accuracy percentage.

        Returns:
            Accuracy as percentage (0-100)
        """
        if self.total_answered == 0:
            return 0.0
        return (self.total_correct / self.total_answered) * 100


class TriviaGame:
    """Active trivia game instance."""

    def __init__(self, channel_id: int, difficulty: Difficulty = Difficulty.MEDIUM,
                 category: Optional[Category] = None, num_questions: int = 10):
        """Initialize a trivia game.

        Args:
            channel_id: Discord channel ID
            difficulty: Question difficulty
            category: Question category (None for random)
            num_questions: Number of questions in the game
        """
        self.channel_id = channel_id
        self.difficulty = difficulty
        self.category = category
        self.num_questions = num_questions
        self.questions: List[TriviaQuestion] = []
        self.current_question_index = 0
        self.current_question: Optional[TriviaQuestion] = None
        self.players: Dict[int, TriviaScore] = {}  # user_id -> score
        self.active = False
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.current_answers: Dict[int, str] = {}  # user_id -> answer for current question

    def add_player(self, user_id: int, username: str):
        """Add a player to the game.

        Args:
            user_id: User ID
            username: Username
        """
        if user_id not in self.players:
            self.players[user_id] = TriviaScore(user_id=user_id, username=username)

    def next_question(self) -> Optional[TriviaQuestion]:
        """Get the next question.

        Returns:
            Next question or None if game is over
        """
        if self.current_question_index >= len(self.questions):
            return None

        self.current_question = self.questions[self.current_question_index]
        self.current_question_index += 1
        self.current_answers.clear()
        return self.current_question

    def submit_answer(self, user_id: int, answer: str) -> bool:
        """Submit an answer for the current question.

        Args:
            user_id: User ID
            answer: Answer text

        Returns:
            True if correct, False if incorrect
        """
        if user_id not in self.players or not self.current_question:
            return False

        self.current_answers[user_id] = answer

        is_correct = answer.lower().strip() == self.current_question.correct_answer.lower().strip()

        if is_correct:
            self.players[user_id].answer_correct(Difficulty(self.difficulty))
        else:
            self.players[user_id].answer_incorrect()

        return is_correct

    def get_leaderboard(self) -> List[TriviaScore]:
        """Get current leaderboard sorted by points.

        Returns:
            List of scores sorted by points (descending)
        """
        return sorted(self.players.values(), key=lambda s: s.points, reverse=True)

    def is_complete(self) -> bool:
        """Check if the game is complete.

        Returns:
            True if all questions answered
        """
        return self.current_question_index >= len(self.questions)


class TriviaService:
    """Service for managing trivia games."""

    def __init__(self, data_dir: Path, web_search=None):
        """Initialize trivia service.

        Args:
            data_dir: Directory for storing scores
            web_search: Optional web search service for verification
        """
        self.data_dir = data_dir
        self.web_search = web_search
        self.active_games: Dict[int, TriviaGame] = {}  # channel_id -> game
        self.leaderboard_file = data_dir / "trivia_leaderboard.json"
        self.all_time_scores: Dict[int, TriviaScore] = {}  # user_id -> cumulative score
        self.session: Optional[aiohttp.ClientSession] = None

        # Create data directory
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Load all-time leaderboard
        self._load_leaderboard()

        logger.info("Trivia service initialized")

    async def initialize(self):
        """Initialize HTTP session for API calls."""
        if not self.session:
            self.session = aiohttp.ClientSession()

    async def close(self):
        """Close HTTP session."""
        if self.session:
            await self.session.close()
            self.session = None

    def _load_leaderboard(self):
        """Load all-time leaderboard from file."""
        if self.leaderboard_file.exists():
            try:
                with open(self.leaderboard_file, 'r') as f:
                    data = json.load(f)
                    for user_id_str, score_dict in data.items():
                        user_id = int(user_id_str)
                        self.all_time_scores[user_id] = TriviaScore(**score_dict)
                logger.info(f"Loaded {len(self.all_time_scores)} players from leaderboard")
            except Exception as e:
                logger.error(f"Failed to load leaderboard: {e}")

    def _save_leaderboard(self):
        """Save all-time leaderboard to file."""
        try:
            data = {
                str(user_id): asdict(score)
                for user_id, score in self.all_time_scores.items()
            }
            with open(self.leaderboard_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save leaderboard: {e}")

    async def fetch_questions(
        self,
        amount: int = 10,
        category: Optional[Category] = None,
        difficulty: Optional[Difficulty] = None
    ) -> List[TriviaQuestion]:
        """Fetch trivia questions from Open Trivia Database API.

        Args:
            amount: Number of questions
            category: Question category
            difficulty: Question difficulty

        Returns:
            List of trivia questions
        """
        if not self.session:
            await self.initialize()

        # Build API URL
        url = f"https://opentdb.com/api.php?amount={amount}"
        if category:
            url += f"&category={category.opentdb_id}"
        if difficulty:
            url += f"&difficulty={difficulty.value}"

        try:
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    logger.error(f"OpenTDB API error: {resp.status}")
                    return []

                data = await resp.json()

                if data.get("response_code") != 0:
                    logger.error(f"OpenTDB returned error code: {data.get('response_code')}")
                    return []

                questions = []
                for item in data.get("results", []):
                    question = TriviaQuestion(
                        question=html.unescape(item["question"]),
                        correct_answer=html.unescape(item["correct_answer"]),
                        incorrect_answers=[html.unescape(ans) for ans in item["incorrect_answers"]],
                        category=html.unescape(item["category"]),
                        difficulty=item["difficulty"],
                        question_type=item["type"],
                    )
                    questions.append(question)

                logger.info(f"Fetched {len(questions)} trivia questions")
                return questions

        except Exception as e:
            logger.error(f"Failed to fetch trivia questions: {e}")
            return []

    async def start_game(
        self,
        channel_id: int,
        difficulty: Difficulty = Difficulty.MEDIUM,
        category: Optional[Category] = None,
        num_questions: int = 10
    ) -> Optional[TriviaGame]:
        """Start a new trivia game in a channel.

        Args:
            channel_id: Discord channel ID
            difficulty: Question difficulty
            category: Question category
            num_questions: Number of questions

        Returns:
            TriviaGame instance or None if failed
        """
        # Check if game already active
        if channel_id in self.active_games:
            return None

        # Fetch questions
        questions = await self.fetch_questions(
            amount=num_questions,
            category=category,
            difficulty=difficulty
        )

        if not questions:
            return None

        # Create game
        game = TriviaGame(
            channel_id=channel_id,
            difficulty=difficulty,
            category=category,
            num_questions=num_questions
        )
        game.questions = questions
        game.active = True
        game.start_time = datetime.now()

        self.active_games[channel_id] = game
        logger.info(f"Started trivia game in channel {channel_id}")

        return game

    def get_game(self, channel_id: int) -> Optional[TriviaGame]:
        """Get active game in a channel.

        Args:
            channel_id: Discord channel ID

        Returns:
            TriviaGame or None
        """
        return self.active_games.get(channel_id)

    def end_game(self, channel_id: int):
        """End a trivia game and update all-time scores.

        Args:
            channel_id: Discord channel ID
        """
        game = self.active_games.get(channel_id)
        if not game:
            return

        game.active = False
        game.end_time = datetime.now()

        # Update all-time scores
        for user_id, score in game.players.items():
            if user_id not in self.all_time_scores:
                self.all_time_scores[user_id] = TriviaScore(
                    user_id=user_id,
                    username=score.username
                )

            all_time = self.all_time_scores[user_id]
            all_time.total_correct += score.total_correct
            all_time.total_answered += score.total_answered
            all_time.points += score.points
            all_time.best_streak = max(all_time.best_streak, score.best_streak)

        self._save_leaderboard()

        # Remove from active games
        del self.active_games[channel_id]
        logger.info(f"Ended trivia game in channel {channel_id}")

    def get_all_time_leaderboard(self, limit: int = 10) -> List[TriviaScore]:
        """Get all-time leaderboard.

        Args:
            limit: Maximum number of entries

        Returns:
            List of top scores
        """
        return sorted(
            self.all_time_scores.values(),
            key=lambda s: s.points,
            reverse=True
        )[:limit]

    async def verify_answer(self, question: str, answer: str) -> Optional[bool]:
        """Verify an answer using web search (optional feature).

        Args:
            question: Question text
            answer: Answer to verify

        Returns:
            True if likely correct, False if likely incorrect, None if unable to verify
        """
        if not self.web_search:
            return None

        try:
            query = f"{question} {answer}"
            results = await self.web_search.search(query, max_results=3)

            if not results:
                return None

            # Simple heuristic: check if answer appears in top results
            answer_lower = answer.lower()
            for result in results:
                snippet = result.get("snippet", "").lower()
                if answer_lower in snippet:
                    return True

            return False

        except Exception as e:
            logger.error(f"Answer verification failed: {e}")
            return None
