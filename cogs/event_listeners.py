"""Event listeners for natural bot reactions to Discord events."""
import discord
from discord.ext import commands
import logging
import random

logger = logging.getLogger(__name__)


class EventListenersCog(commands.Cog):
    """Cog for reacting to Discord events naturally."""

    def __init__(self, bot: commands.Bot):
        """Initialize event listeners.

        Args:
            bot: Discord bot instance
        """
        self.bot = bot
        logger.info("Event listeners initialized")

    def _is_user_in_conversation(self, user_id: int) -> bool:
        """Check if a user is currently in an active conversation with the bot.

        Args:
            user_id: Discord user ID

        Returns:
            True if user is in active conversation, False otherwise
        """
        # Get chat cog to access active sessions
        chat_cog = self.bot.get_cog('ChatCog')
        if not chat_cog or not hasattr(chat_cog, 'active_sessions'):
            return False

        # Check if any channel has an active session with this user
        for channel_id, session in chat_cog.active_sessions.items():
            if session.get('user_id') == user_id:
                return True

        return False

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """React to voice state changes.
        
        Args:
            member: Member whose voice state changed
            before: Previous voice state
            after: New voice state
        """
        # Ignore bot's own voice state changes
        if member.bot and member.id == self.bot.user.id:
            return

        # User joined voice
        if before.channel is None and after.channel is not None:
            # Only react if user is in active conversation with bot
            if not self._is_user_in_conversation(member.id):
                return

            reaction_sent = False
            if random.random() < 0.05:  # 5% chance
                reactions = [
                    f"Oh, {member.mention} decided to join us. How delightful.",
                    f"{member.mention} has entered voice. My condolences to everyone already there.",
                    f"Ah, {member.mention}. The party can truly begin now. Or end. Probably end.",
                    f"Welcome, {member.mention}. Try not to embarrass yourself too much.",
                ]
                # Find a text channel to send to
                target_channel = after.channel.guild.text_channels[0] if after.channel.guild.text_channels else None
                if target_channel:
                    await target_channel.send(random.choice(reactions))
                    logger.info(f"Reacted to {member.name} joining voice")
                    reaction_sent = True
            
            # Fallback to generic naturalness
            if not reaction_sent and hasattr(self.bot, 'naturalness') and self.bot.naturalness:
                comment = await self.bot.naturalness.on_voice_state_update(member, before, after)
                if comment:
                    # Find target channel
                    target_channel = None
                    from config import Config
                    if Config.AMBIENT_CHANNELS:
                        target_channel = self.bot.get_channel(Config.AMBIENT_CHANNELS[0])
                    
                    if not target_channel and after.channel.guild.text_channels:
                        target_channel = after.channel.guild.text_channels[0]
                        
                    if target_channel:
                        await target_channel.send(comment)

        # User left voice
        elif before.channel is not None and after.channel is None:
            # Only react if user is in active conversation with bot
            if not self._is_user_in_conversation(member.id):
                return

            reaction_sent = False
            if random.random() < 0.05:  # 5% chance
                reactions = [
                    f"And {member.mention} is gone. Shocking.",
                    f"{member.mention} has left. The average IQ just went up.",
                    f"Farewell, {member.mention}. You won't be missed.",
                    f"{member.mention} abandoned ship. Wise choice.",
                ]
                text_channel = before.channel.guild.text_channels[0] if before.channel.guild.text_channels else None
                if text_channel:
                    await text_channel.send(random.choice(reactions))
                    logger.info(f"Reacted to {member.name} leaving voice")
                    reaction_sent = True
            
            # Fallback to generic naturalness
            if not reaction_sent and hasattr(self.bot, 'naturalness') and self.bot.naturalness:
                comment = await self.bot.naturalness.on_voice_state_update(member, before, after)
                if comment:
                    # Find target channel
                    target_channel = None
                    from config import Config
                    if Config.AMBIENT_CHANNELS:
                        target_channel = self.bot.get_channel(Config.AMBIENT_CHANNELS[0])
                    
                    if not target_channel and before.channel.guild.text_channels:
                        target_channel = before.channel.guild.text_channels[0]
                        
                    if target_channel:
                        await target_channel.send(comment)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """React to member updates (role changes, nickname changes, etc).
        
        Args:
            before: Member before update
            after: Member after update
        """
        # Role added
        if len(after.roles) > len(before.roles):
            # Only react if user is in active conversation with bot
            if not self._is_user_in_conversation(after.id):
                return

            new_role = list(set(after.roles) - set(before.roles))[0]
            if random.random() < 0.05:  # 5% chance
                reactions = [
                    f"Congrats on the new role, {after.mention}. Very impressive. Truly.",
                    f"{after.mention} got a role. {new_role.name}. How... nice.",
                    f"A new role for {after.mention}. I'm sure they earned it. Somehow.",
                ]
                # Find a text channel
                text_channel = after.guild.text_channels[0] if after.guild.text_channels else None
                if text_channel:
                    await text_channel.send(random.choice(reactions))
                    logger.info(f"Reacted to {after.name} getting role {new_role.name}")

    @commands.Cog.listener()
    async def on_presence_update(self, before: discord.Member, after: discord.Member):
        """React to presence updates (game changes, status changes).
        
        Args:
            before: Member before update
            after: Member after update
        """
        # Game/activity changed
        if before.activity != after.activity and after.activity:
            # Only react if user is in active conversation with bot
            if not self._is_user_in_conversation(after.id):
                return

            # Check if we should react (10% chance)
            if random.random() < 0.1 and hasattr(after.activity, 'name'):
                game_name = after.activity.name
                
                # Generate AI-powered reaction
                try:
                    # Get persona context
                    persona_name = "Dagoth Ur"
                    if hasattr(self.bot, 'get_cog'):
                        chat_cog = self.bot.get_cog('ChatCog')
                        if chat_cog and hasattr(chat_cog, 'current_persona') and chat_cog.current_persona:
                            persona_name = chat_cog.current_persona.name
                    
                    # Generate contextual roast
                    prompt = f"""User {after.display_name} just started playing "{game_name}". 
Generate a SHORT (1-2 sentences max), sarcastic reaction as {persona_name}.
Be witty and in-character. Reference the specific game if you know it.
Do not use quotation marks or say "I would say" - just give the direct reaction."""
                    
                    response = await self.bot.ollama.generate(prompt)
                    reaction = response.strip().strip('"').strip("'")
                    
                    # Mention the user
                    full_reaction = f"{after.mention} {reaction}"
                    
                    # Find target channel
                    target_channel = None
                    from config import Config
                    if Config.AMBIENT_CHANNELS:
                        target_channel = self.bot.get_channel(Config.AMBIENT_CHANNELS[0])
                    
                    if not target_channel and after.guild.text_channels:
                        target_channel = after.guild.text_channels[0]
                        
                    if target_channel:
                        await target_channel.send(full_reaction)
                        logger.info(f"AI-generated reaction to {after.name} playing {game_name}")
                        
                except Exception as e:
                    logger.error(f"Failed to generate AI reaction: {e}")
                    # Fallback to generic comment if AI fails
                    if hasattr(self.bot, 'naturalness') and self.bot.naturalness:
                        comment = await self.bot.naturalness.on_presence_update(before, after)
                        if comment:
                            target_channel = None
                            from config import Config
                            if Config.AMBIENT_CHANNELS:
                                target_channel = self.bot.get_channel(Config.AMBIENT_CHANNELS[0])
                            
                            if not target_channel and after.guild.text_channels:
                                target_channel = after.guild.text_channels[0]
                                
                            if target_channel:
                                await target_channel.send(comment)


async def setup(bot: commands.Bot):
    """Setup function for loading the cog."""
    await bot.add_cog(EventListenersCog(bot))
