"""Trivia game commands for Discord."""
import discord
from discord import app_commands
from discord.ext import commands
import logging
import asyncio
from typing import Optional

from services.trivia import TriviaService, Difficulty, Category
from utils.helpers import format_success, format_error

logger = logging.getLogger(__name__)


class TriviaCog(commands.Cog):
    """Cog for trivia game commands."""

    def __init__(self, bot: commands.Bot, trivia_service: TriviaService):
        """Initialize trivia cog.

        Args:
            bot: Discord bot instance
            trivia_service: Trivia service instance
        """
        self.bot = bot
        self.trivia = trivia_service

    @app_commands.command(name="trivia_start", description="Start a trivia game!")
    @app_commands.describe(
        difficulty="Question difficulty (easy, medium, hard)",
        category="Question category",
        questions="Number of questions (1-50)"
    )
    async def trivia_start(
        self,
        interaction: discord.Interaction,
        difficulty: Optional[str] = "medium",
        category: Optional[str] = None,
        questions: Optional[int] = 10
    ):
        """Start a new trivia game.

        Args:
            interaction: Discord interaction
            difficulty: Question difficulty
            category: Question category
            questions: Number of questions
        """
        await interaction.response.defer()

        # Validate difficulty
        try:
            diff = Difficulty(difficulty.lower())
        except ValueError:
            await interaction.followup.send(
                format_error(f"Invalid difficulty '{difficulty}'. Choose: easy, medium, hard")
            )
            return

        # Validate category
        cat = None
        if category:
            category_map = {cat.name.lower(): cat for cat in Category}
            cat = category_map.get(category.lower())
            if not cat:
                available = ", ".join(category_map.keys())
                await interaction.followup.send(
                    format_error(f"Invalid category '{category}'. Available: {available}")
                )
                return

        # Validate questions
        if questions < 1 or questions > 50:
            await interaction.followup.send(
                format_error("Number of questions must be between 1 and 50")
            )
            return

        # Check if game already active
        channel_id = interaction.channel_id
        if self.trivia.get_game(channel_id):
            await interaction.followup.send(
                format_error("A trivia game is already active in this channel! Use `/trivia_end` to stop it.")
            )
            return

        # Start game
        game = await self.trivia.start_game(
            channel_id=channel_id,
            difficulty=diff,
            category=cat,
            num_questions=questions
        )

        if not game:
            await interaction.followup.send(
                format_error("Failed to start trivia game. Could not fetch questions.")
            )
            return

        # Add starter as player
        game.add_player(interaction.user.id, interaction.user.name)

        # Send game info
        cat_name = cat.display_name if cat else "Random"
        embed = discord.Embed(
            title="🎮 Trivia Game Started!",
            description=f"Get ready to test your knowledge!",
            color=discord.Color.green()
        )
        embed.add_field(name="Difficulty", value=diff.value.capitalize(), inline=True)
        embed.add_field(name="Category", value=cat_name, inline=True)
        embed.add_field(name="Questions", value=str(questions), inline=True)
        embed.add_field(
            name="How to Play",
            value="• React to this message to join!\n• Answer by typing your answer\n• Be the first to answer correctly for bonus points!",
            inline=False
        )

        message = await interaction.followup.send(embed=embed)

        # Wait for players to join
        await message.add_reaction("✅")
        await asyncio.sleep(10)  # 10 second join period

        # Start asking questions
        await self._run_game(interaction.channel, game)

    async def _run_game(self, channel: discord.TextChannel, game):
        """Run the trivia game loop.

        Args:
            channel: Discord channel
            game: TriviaGame instance
        """
        question_num = 0

        while not game.is_complete():
            question = game.next_question()
            if not question:
                break

            question_num += 1

            # Create question embed
            embed = discord.Embed(
                title=f"❓ Question {question_num}/{len(game.questions)}",
                description=f"**{question.question}**",
                color=discord.Color.blue()
            )
            embed.add_field(name="Category", value=question.category, inline=True)
            embed.add_field(name="Difficulty", value=question.difficulty.capitalize(), inline=True)

            # Add answer options
            answers = question.get_all_answers(shuffle=True)
            if question.question_type == "multiple":
                options_text = "\n".join([f"**{chr(65+i)}.** {ans}" for i, ans in enumerate(answers)])
                embed.add_field(name="Options", value=options_text, inline=False)
                embed.set_footer(text="Type A, B, C, or D to answer! You have 15 seconds.")
            else:  # boolean
                embed.set_footer(text="Type 'True' or 'False' to answer! You have 15 seconds.")

            await channel.send(embed=embed)

            # Wait for answers (15 seconds)
            start_time = asyncio.get_event_loop().time()
            answered_users = set()

            def check(m):
                return (
                    m.channel.id == channel.id and
                    m.author.id in game.players and
                    m.author.id not in answered_users
                )

            while asyncio.get_event_loop().time() - start_time < 15:
                try:
                    msg = await self.bot.wait_for(
                        'message',
                        timeout=15 - (asyncio.get_event_loop().time() - start_time),
                        check=check
                    )

                    # Parse answer
                    answer_text = msg.content.strip().upper()

                    # Convert letter to answer for multiple choice
                    if question.question_type == "multiple" and answer_text in ["A", "B", "C", "D"]:
                        answer_idx = ord(answer_text) - 65
                        if 0 <= answer_idx < len(answers):
                            answer_text = answers[answer_idx]

                    # Submit answer
                    is_correct = game.submit_answer(msg.author.id, answer_text)
                    answered_users.add(msg.author.id)

                    # React to answer
                    if is_correct:
                        await msg.add_reaction("✅")
                        points = game.players[msg.author.id].points
                        streak = game.players[msg.author.id].streak
                        await channel.send(f"✅ **{msg.author.name}** got it right! (+points: {points}, streak: {streak})")
                    else:
                        await msg.add_reaction("❌")

                except asyncio.TimeoutError:
                    break

            # Show correct answer
            result_embed = discord.Embed(
                title="📊 Answer",
                description=f"The correct answer was: **{question.correct_answer}**",
                color=discord.Color.gold()
            )
            await channel.send(embed=result_embed)

            # Short break between questions
            await asyncio.sleep(3)

        # Game complete! Show final scores
        await self._show_final_scores(channel, game)

        # End game and save scores
        self.trivia.end_game(channel.id)

    async def _show_final_scores(self, channel: discord.TextChannel, game):
        """Show final game scores.

        Args:
            channel: Discord channel
            game: TriviaGame instance
        """
        leaderboard = game.get_leaderboard()

        if not leaderboard:
            await channel.send("No one answered any questions! 😅")
            return

        embed = discord.Embed(
            title="🏆 Trivia Game Complete!",
            description="Final Scores",
            color=discord.Color.gold()
        )

        for i, score in enumerate(leaderboard, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            embed.add_field(
                name=f"{medal} {score.username}",
                value=f"**{score.points}** pts | {score.total_correct}/{score.total_answered} correct | {score.accuracy:.1f}% accuracy | Best streak: {score.best_streak}",
                inline=False
            )

        await channel.send(embed=embed)

    @app_commands.command(name="trivia_join", description="Join the active trivia game")
    async def trivia_join(self, interaction: discord.Interaction):
        """Join an active trivia game.

        Args:
            interaction: Discord interaction
        """
        game = self.trivia.get_game(interaction.channel_id)

        if not game:
            await interaction.response.send_message(
                format_error("No active trivia game in this channel! Start one with `/trivia_start`"),
                ephemeral=True
            )
            return

        if not game.active:
            await interaction.response.send_message(
                format_error("This game has already started or ended"),
                ephemeral=True
            )
            return

        game.add_player(interaction.user.id, interaction.user.name)

        await interaction.response.send_message(
            format_success(f"You've joined the trivia game! Get ready! 🎮"),
            ephemeral=True
        )

    @app_commands.command(name="trivia_end", description="End the current trivia game")
    async def trivia_end(self, interaction: discord.Interaction):
        """End the active trivia game.

        Args:
            interaction: Discord interaction
        """
        game = self.trivia.get_game(interaction.channel_id)

        if not game:
            await interaction.response.send_message(
                format_error("No active trivia game in this channel"),
                ephemeral=True
            )
            return

        # Show current scores
        await self._show_final_scores(interaction.channel, game)

        # End game
        self.trivia.end_game(interaction.channel_id)

        await interaction.response.send_message(
            format_success("Trivia game ended!"),
            ephemeral=True
        )

    @app_commands.command(name="trivia_leaderboard", description="Show the all-time trivia leaderboard")
    @app_commands.describe(limit="Number of top players to show (1-25)")
    async def trivia_leaderboard(self, interaction: discord.Interaction, limit: Optional[int] = 10):
        """Show all-time trivia leaderboard.

        Args:
            interaction: Discord interaction
            limit: Number of entries to show
        """
        await interaction.response.defer()

        limit = max(1, min(limit, 25))  # Clamp between 1-25

        leaderboard = self.trivia.get_all_time_leaderboard(limit=limit)

        if not leaderboard:
            await interaction.followup.send(
                format_error("No trivia games have been played yet!")
            )
            return

        embed = discord.Embed(
            title="🏆 All-Time Trivia Leaderboard",
            description=f"Top {len(leaderboard)} Players",
            color=discord.Color.gold()
        )

        for i, score in enumerate(leaderboard, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"**{i}.**"
            embed.add_field(
                name=f"{medal} {score.username}",
                value=f"**{score.points:,}** pts | {score.total_correct}/{score.total_answered} correct | {score.accuracy:.1f}% | Best streak: {score.best_streak}",
                inline=False
            )

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="trivia_stats", description="Show your trivia statistics")
    async def trivia_stats(self, interaction: discord.Interaction):
        """Show user's trivia stats.

        Args:
            interaction: Discord interaction
        """
        stats = self.trivia.all_time_scores.get(interaction.user.id)

        if not stats:
            await interaction.response.send_message(
                format_error("You haven't played any trivia games yet! Start one with `/trivia_start`"),
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"📊 Trivia Stats for {interaction.user.name}",
            color=discord.Color.blue()
        )
        embed.add_field(name="Total Points", value=f"**{stats.points:,}**", inline=True)
        embed.add_field(name="Accuracy", value=f"**{stats.accuracy:.1f}%**", inline=True)
        embed.add_field(name="Best Streak", value=f"**{stats.best_streak}**", inline=True)
        embed.add_field(name="Questions Answered", value=f"{stats.total_answered:,}", inline=True)
        embed.add_field(name="Correct Answers", value=f"{stats.total_correct:,}", inline=True)
        embed.add_field(name="Incorrect Answers", value=f"{stats.total_answered - stats.total_correct:,}", inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="trivia_categories", description="Show available trivia categories")
    async def trivia_categories(self, interaction: discord.Interaction):
        """Show available categories.

        Args:
            interaction: Discord interaction
        """
        categories = [f"• **{cat.name.lower()}**: {cat.display_name}" for cat in Category]

        embed = discord.Embed(
            title="📚 Available Trivia Categories",
            description="\n".join(categories),
            color=discord.Color.purple()
        )
        embed.set_footer(text="Use these category names with /trivia_start")

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    """Setup function for loading the cog."""
    await bot.add_cog(TriviaCog(bot, bot.trivia_service))
