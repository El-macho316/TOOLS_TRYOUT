import os
import json
import asyncio
import logging
import threading
import time
import re
from queue import Queue
from typing import Dict, List, Optional

import discord
from discord.ext import commands
from dotenv import load_dotenv

# Local AutoGen integration
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from financial_autogen import LambdaLLMAdapter
    import autogen
    from autogen import ConversableAgent, UserProxyAgent
    AUTOGEN_AVAILABLE = True
    print("✅ AutoGen system imported successfully (v2)")
except Exception as import_error:
    AUTOGEN_AVAILABLE = False
    print(f"⚠️ AutoGen system not available: {import_error}")


load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MessageFormatter:
    """Format and sanitize messages for Discord to match output.md style (no logs)."""

    @staticmethod
    def sanitize(raw: str) -> str:
        if not raw:
            return ""

        # Drop obvious logs and noisy artifacts
        drop_prefixes = (
            "INFO:", "DEBUG:", "WARNING:", "ERROR:", "CRITICAL:",
            "[",  # e.g., [01/Aug/... INFO - ...]
            "httpx:",
            "Call ID:",
            ">>>",
        )

        lines = [line for line in str(raw).splitlines() if line.strip()]
        cleaned: List[str] = []
        for line in lines:
            # Skip lines with obvious HTTP request logs
            if "HTTP Request:" in line or "https://api.anthropic.com" in line:
                continue
            # Skip decorative or tool-response divider lines
            if (line.startswith("*****") and line.endswith("*****")) or (set(line.strip()) == {"*"} and len(line.strip()) > 8):
                continue
            # Skip terminal/UX prompts from AutoGen terminal flow
            if "Replying as user_proxy" in line or "Provide feedback to" in line or "Press enter to skip" in line:
                continue
            if line.startswith(drop_prefixes):
                continue
            cleaned.append(line)

        # Deduplicate consecutive lines
        deduped: List[str] = []
        for line in cleaned:
            if not deduped or deduped[-1] != line:
                deduped.append(line)

        # Collapse multiple blank lines to a single blank line
        text = "\n".join(deduped)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @staticmethod
    def format_for_discord(response: str) -> str:
        content = MessageFormatter.sanitize(response)
        if not content:
            return ""

        if "Next speaker:" in content:
            # Suppress noisy next-speaker lines for user-friendly output
            return ""

        if content.startswith("🤖"):
            return content

        if "Financial Analysis for" in content:
            return f"📊 **ANALYSIS RESULTS:**\n```\n{content}\n```"

        # Default: pass through
        return content


class DiscordAutoGenBridgeV2:
    """Bridge between Discord and AutoGen for interactive conversations (improved)."""

    def __init__(self, channel_id: int, user_id: int, use_mock_data_default: bool = True):
        self.channel_id = channel_id
        self.user_id = user_id
        self.conversation_active = False
        self.waiting_for_user = False
        self.response_queue: "Queue[str]" = Queue()
        self.user_input_queue: "Queue[str]" = Queue()
        self.agents: Optional[Dict[str, ConversableAgent]] = None
        self.current_manager = None
        self.adapter: Optional[LambdaLLMAdapter] = None
        self.use_mock_data_default = use_mock_data_default

    def setup_autogen_system(self) -> LambdaLLMAdapter:
        if not AUTOGEN_AVAILABLE:
            raise RuntimeError("AutoGen system not available")

        anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        if not anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not found in environment variables")

        # Decide mock mode to ensure it 'just works'
        pinecone_key = os.getenv("PINECONE_API_KEY")
        use_mock = self.use_mock_data_default or not bool(pinecone_key)

        self.adapter = LambdaLLMAdapter(anthropic_api_key=anthropic_api_key, use_mock_data=use_mock)

        claude_config = {
            "model": "claude-3-5-sonnet-20241022",
            "api_key": anthropic_api_key,
            "api_type": "anthropic",
        }

        financial_analyst = ConversableAgent(
            name="financial_analyst",
            system_message=(
                "You are a senior financial analyst specializing in fundamental analysis.\n"
                "1) Analyze stock requests from natural language.\n"
                "2) Coordinate with data_researcher to get local data.\n"
                "3) Provide balanced recommendations with disclaimers."
            ),
            llm_config={"config_list": [claude_config]},
            human_input_mode="NEVER",
        )

        data_researcher = ConversableAgent(
            name="data_researcher",
            system_message=(
                "You gather comprehensive stock data using the LOCAL financial analysis function.\n"
                "Extract tickers from natural language, call get_financial_analysis, and format results."
            ),
            llm_config={"config_list": [claude_config]},
            human_input_mode="NEVER",
        )

        user_proxy = DiscordUserProxyAgentV2(
            discord_bridge=self,
            name="user_proxy",
            system_message="You represent the Discord user in this conversation.",
            human_input_mode="ALWAYS",
            max_consecutive_auto_reply=10,
            code_execution_config=False,
        )

        # Function wrapper
        def get_financial_analysis_func(ticker: str) -> str:
            return self.get_financial_analysis_wrapper(ticker)

        data_researcher.register_for_llm(
            name="get_financial_analysis",
            description=(
                "Get comprehensive financial analysis using the LOCAL function (Pinecone-backed or mock)."
            ),
        )(get_financial_analysis_func)

        user_proxy.register_for_execution(name="get_financial_analysis")(get_financial_analysis_func)

        self.agents = {
            "user_proxy": user_proxy,
            "financial_analyst": financial_analyst,
            "data_researcher": data_researcher,
        }

        return self.adapter

    def get_financial_analysis_wrapper(self, ticker: str) -> str:
        try:
            if not self.adapter:
                raise RuntimeError("Adapter not initialized")
            result = self.adapter.invoke_lambda_function(ticker)
            if "error" in result:
                return f"Error retrieving analysis for {ticker}: {result['error']}"

            response_data = result.get("response", {})
            function_response = response_data.get("functionResponse", {})
            response_body = function_response.get("responseBody", {})
            text_data = response_body.get("TEXT", {})
            body_content = text_data.get("body", "{}")
            analysis_data = json.loads(body_content) if isinstance(body_content, str) else body_content

            if "analysisReport" in analysis_data:
                return f"Financial Analysis for {ticker.upper()}:\n\n{analysis_data['analysisReport']}"
            return f"Analysis data retrieved for {ticker.upper()}: {json.dumps(analysis_data, indent=2)}"
        except Exception as error:
            logger.error(f"Error in financial analysis wrapper: {error}")
            return f"Error retrieving financial analysis for {ticker}: {error}"

    async def start_conversation(self, initial_message: str):
        try:
            adapter = self.setup_autogen_system()

            self._setup_message_capture()

            group_chat = autogen.GroupChat(
                agents=[
                    self.agents["user_proxy"],
                    self.agents["financial_analyst"],
                    self.agents["data_researcher"],
                ],
                messages=[],
                max_round=50,
                speaker_selection_method="round_robin",
            )

            self.current_manager = autogen.GroupChatManager(
                groupchat=group_chat,
                llm_config={
                    "config_list": [
                        {
                            "model": "claude-3-5-sonnet-20241022",
                            "api_key": adapter.anthropic_api_key,
                            "api_type": "anthropic",
                        }
                    ]
                },
            )

            self._capture_manager_responses()
            self.conversation_active = True

            def run_conversation():
                try:
                    self.agents["user_proxy"].initiate_chat(
                        self.current_manager, message=initial_message
                    )
                    while self.conversation_active:
                        if self.waiting_for_user:
                            time.sleep(0.2)
                            continue
                        if not self.user_input_queue.empty():
                            user_input = self.user_input_queue.get()
                            if user_input.strip().lower() in {"exit", "quit", "stop"}:
                                break
                            try:
                                self.agents["user_proxy"].initiate_chat(
                                    self.current_manager,
                                    message=user_input,
                                    clear_history=False,
                                )
                            except Exception as follow_error:
                                logger.error(f"Follow-up error: {follow_error}")
                                self.response_queue.put(
                                    f"❌ Error in follow-up: {follow_error}"
                                )
                        time.sleep(0.2)
                except Exception as run_error:
                    logger.error(f"AutoGen conversation error: {run_error}")
                    self.response_queue.put(f"❌ Error in conversation: {run_error}")
                finally:
                    self.conversation_active = False
                    self.response_queue.put(
                        "✅ **Analysis conversation completed! Use `!analyze` to start a new conversation.**"
                    )

            thread = threading.Thread(target=run_conversation, daemon=True)
            thread.start()
        except Exception as start_error:
            logger.error(f"Error starting conversation: {start_error}")
            self.response_queue.put(f"❌ Error starting conversation: {start_error}")

    def _setup_message_capture(self):
        friendly_name = {
            "user_proxy": ("You", "🙋"),
            "financial_analyst": ("Analyst", "🧠"),
            "data_researcher": ("Researcher", "🔎"),
        }

        for agent_name, agent in self.agents.items():
            original_send = agent.send

            def create_wrapped_send(name, original_send_method):
                def wrapped_send(message, recipient, request_reply=None, silent=False):
                    if hasattr(message, "get"):
                        content = message.get("content", str(message))
                    else:
                        content = str(message)
                    label, emoji = friendly_name.get(name, (name, "💬"))
                    formatted = f"{emoji} **{label}:**\n\n{content}"
                    self.response_queue.put(formatted)
                    return original_send_method(message, recipient, request_reply, silent)

                return wrapped_send

            agent.send = create_wrapped_send(agent_name, original_send)

    def _capture_manager_responses(self):
        if not self.current_manager:
            return
        original_send = self.current_manager.send

        def wrapped_manager_send(message, recipient, request_reply=None, silent=False):
            if hasattr(message, "get"):
                content = message.get("content", str(message))
            else:
                content = str(message)
            # Suppress manager chatter to reduce noise
            if "Next speaker:" in content:
                return original_send(message, recipient, request_reply, silent)
            return original_send(message, recipient, request_reply, silent)

        self.current_manager.send = wrapped_manager_send

    def send_user_input(self, user_input: str) -> None:
        self.user_input_queue.put(user_input)

    def get_responses(self) -> List[str]:
        responses: List[str] = []
        while not self.response_queue.empty():
            responses.append(self.response_queue.get())
        return responses


class DiscordUserProxyAgentV2(UserProxyAgent):
    def __init__(self, discord_bridge: DiscordAutoGenBridgeV2, **kwargs):
        super().__init__(**kwargs)
        self.discord_bridge = discord_bridge

    def get_human_input(self, prompt: str) -> str:
        # Forward prompt to Discord and wait for user
        self.discord_bridge.response_queue.put(f"🤖 **{prompt}**")
        self.discord_bridge.waiting_for_user = True

        elapsed_ticks = 0
        # 0.1s per tick; 600 ticks = 60 seconds
        max_ticks = 600
        while (
            self.discord_bridge.waiting_for_user
            and self.discord_bridge.conversation_active
            and elapsed_ticks < max_ticks
        ):
            if not self.discord_bridge.user_input_queue.empty():
                user_input = self.discord_bridge.user_input_queue.get()
                self.discord_bridge.waiting_for_user = False
                lowered = user_input.strip().lower()
                if lowered in {"", "enter", "continue", "auto"}:
                    self.discord_bridge.response_queue.put(
                        "⏭️ **NO HUMAN INPUT RECEIVED.**\n⏭️ **USING AUTO REPLY...**"
                    )
                    return ""  # trigger auto-reply
                if lowered in {"exit", "quit", "stop"}:
                    self.discord_bridge.response_queue.put("⏹️ **Stopping conversation...**")
                    self.discord_bridge.conversation_active = False
                    return "TERMINATE"
                return user_input
            time.sleep(0.1)
            elapsed_ticks += 1

        if elapsed_ticks >= max_ticks:
            self.discord_bridge.response_queue.put(
                "⏰ **No user input received, continuing with auto-reply...**"
            )
            self.discord_bridge.waiting_for_user = False
            return ""
        return ""


class FinancialDiscordBotV2(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        self.active_conversations: Dict[str, DiscordAutoGenBridgeV2] = {}
        print("✅ Bot v2 initialized successfully")

    async def on_ready(self):
        print(f"🤖 {self.user} connected | v2 ready")
        print(f"🔧 Commands: {[cmd.name for cmd in self.commands]}")

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            available = [cmd.name for cmd in self.commands]
            await ctx.send(
                f"❌ **Command not found.**\n📋 **Available commands:** `{'`, `'.join(available)}`"
            )
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ **Missing required argument:** {error.param.name}")
        else:
            await ctx.send(f"❌ **An error occurred:** {str(error)}")

    def key(self, channel_id: int, user_id: int) -> str:
        return f"{channel_id}_{user_id}"

    async def _send_output(self, ctx, formatted: str):
        """Send formatted output as either plain text or a rich embed when suitable."""
        if not formatted:
            return
        # Render analysis results as embed
        if formatted.startswith("📊 **ANALYSIS RESULTS:**"):
            # Extract code block content
            try:
                start = formatted.index("```") + 3
                end = formatted.rindex("```")
                body = formatted[start:end].strip()
                # Title is first line, description is the rest
                first_nl = body.find("\n")
                if first_nl == -1:
                    title = "Analysis Results"
                    description = body
                else:
                    title = body[:first_nl].strip()
                    description = body[first_nl + 1 :].strip()
                # Discord embed description limit ~4096
                chunks = [description[i : i + 4000] for i in range(0, len(description), 4000)] or [""]
                embed = discord.Embed(title=title, description=chunks[0], color=0x2ECC71)
                await ctx.send(embed=embed)
                for extra in chunks[1:]:
                    embed = discord.Embed(description=extra, color=0x2ECC71)
                    await ctx.send(embed=embed)
                return
            except Exception:
                # Fallback to text if parsing fails
                pass
        # Default: plain text
        if len(formatted) > 2000:
            parts = [formatted[i : i + 2000] for i in range(0, len(formatted), 2000)]
            for p in parts:
                await ctx.send(p)
                await asyncio.sleep(0.15)
        else:
            await ctx.send(formatted)

    async def monitor(self, ctx, bridge: DiscordAutoGenBridgeV2):
        await ctx.send("🔄 **Monitoring AutoGen conversation...**")
        ticks = 0
        # 0.5s per tick; 240 ticks = 120s (2 minutes)
        max_ticks = 240
        last_activity = 0

        while ticks < max_ticks:
            responses = bridge.get_responses()
            if responses:
                last_activity = ticks
                for r in responses:
                    formatted = MessageFormatter.format_for_discord(r)
                    if not formatted:
                        continue
                    await self._send_output(ctx, formatted)

            if bridge.waiting_for_user:
                await ctx.send(
                    "⏸️ **Waiting for your input...** Use `!continue` or `!continue enter` to auto-continue"
                )
                break

            if not bridge.conversation_active:
                break

            await asyncio.sleep(0.5)
            ticks += 1
            if ticks % 60 == 0 and ticks > last_activity + 30:
                await ctx.send(f"🔄 **Still running... ({ticks//2}s elapsed)**")

        # Cleanup or keep active if still running
        k = self.key(ctx.channel.id, ctx.author.id)
        if k in self.active_conversations:
            if ticks >= max_ticks:
                await ctx.send("⏰ **Conversation monitor timed out.** Use `!continue` to resume.")
            if not bridge.conversation_active:
                del self.active_conversations[k]
            else:
                await ctx.send(
                    "💬 **Conversation active.** Commands: `!continue [message]`, `!stop`, `!status`"
                )


# Commands
async def v2_test(ctx):
    await ctx.send("✅ **Bot v2 is working!**")
    await ctx.send(f"🔧 **AutoGen:** {'✅ Available' if AUTOGEN_AVAILABLE else '❌ Not Available'}")


async def v2_analyze(ctx, *, request: str):
    if not AUTOGEN_AVAILABLE:
        await ctx.send("❌ **AutoGen system not available.** Check your setup.")
        return

    bot: FinancialDiscordBotV2 = ctx.bot  # type: ignore
    key = bot.key(ctx.channel.id, ctx.author.id)

    if key in bot.active_conversations and bot.active_conversations[key].conversation_active:
        await ctx.send(
            "❌ You already have an active conversation. Use `!stop` to end it or `!continue` to interact."
        )
        return

    # Decide default mock mode for reliability
    use_mock_default = os.getenv("USE_MOCK_DATA", "true").strip().lower() in {"1", "true", "yes", "y", "on"}
    bridge = DiscordAutoGenBridgeV2(ctx.channel.id, ctx.author.id, use_mock_default)
    bot.active_conversations[key] = bridge

    await ctx.send(
        f"🚀 **Starting financial analysis for:** {request}\n🤖 **Initializing AutoGen agents (v2)...**"
    )

    await bridge.start_conversation(request)
    await bot.monitor(ctx, bridge)


async def v2_continue(ctx, *, user_input: str = ""):
    bot: FinancialDiscordBotV2 = ctx.bot  # type: ignore
    key = bot.key(ctx.channel.id, ctx.author.id)
    if key not in bot.active_conversations:
        await ctx.send("❌ No active conversation. Use `!analyze <request>` to start.")
        return
    bridge = bot.active_conversations[key]
    if not bridge.conversation_active:
        await ctx.send("❌ No active conversation. Use `!analyze <request>` to start.")
        return
    if user_input.strip() == "":
        await ctx.send("⏭️ **Continuing with auto-reply...**")
    else:
        await ctx.send(f"💬 **Follow-up:** {user_input}")
    bridge.send_user_input(user_input)
    await asyncio.sleep(1)
    responses = bridge.get_responses()
    bot: FinancialDiscordBotV2 = ctx.bot  # type: ignore
    for r in responses:
        formatted = MessageFormatter.format_for_discord(r)
        if not formatted:
            continue
        await bot._send_output(ctx, formatted)
    if bridge.waiting_for_user:
        await ctx.send("⏸️ **Waiting for your input...** Use `!continue` again to proceed")
    elif bridge.conversation_active:
        await ctx.send("💬 **Conversation still active.** Use `!continue` for more questions.")


async def v2_stop(ctx):
    bot: FinancialDiscordBotV2 = ctx.bot  # type: ignore
    key = bot.key(ctx.channel.id, ctx.author.id)
    if key in bot.active_conversations:
        bridge = bot.active_conversations[key]
        bridge.conversation_active = False
        del bot.active_conversations[key]
        await ctx.send("⏹️ **Conversation stopped.**")
    else:
        await ctx.send("❌ No active conversation to stop.")


async def v2_status(ctx):
    bot: FinancialDiscordBotV2 = ctx.bot  # type: ignore
    key = bot.key(ctx.channel.id, ctx.author.id)
    if key not in bot.active_conversations:
        await ctx.send("ℹ️ **No session.** Use `!analyze <request>` to start.")
        return
    bridge = bot.active_conversations[key]
    await ctx.send(
        f"📈 **Status:** active={bridge.conversation_active}, waiting_for_user={bridge.waiting_for_user}"
    )


async def v2_mock(ctx, mode: str):
    mode_l = mode.strip().lower()
    if mode_l not in {"on", "off"}:
        await ctx.send("❌ Usage: `!mock on|off`")
        return
    enabled = mode_l == "on"
    os.environ["USE_MOCK_DATA"] = "true" if enabled else "false"
    await ctx.send(
        f"🛠️ **Mock mode set to:** {'ON' if enabled else 'OFF'} (new sessions will reflect this)"
    )


def create_bot_v2() -> FinancialDiscordBotV2:
    bot = FinancialDiscordBotV2()
    # Register commands
    bot.add_command(commands.Command(v2_test, name="test"))
    bot.add_command(commands.Command(v2_analyze, name="analyze"))
    bot.add_command(commands.Command(v2_continue, name="continue"))
    bot.add_command(commands.Command(v2_stop, name="stop"))
    bot.add_command(commands.Command(v2_status, name="status"))
    bot.add_command(commands.Command(v2_mock, name="mock"))
    print(f"✅ Commands registered (v2): {[cmd.name for cmd in bot.commands]}")
    return bot


def main():
    token = os.getenv("DISCORD_BOT_TOKEN")
    anthropic = os.getenv("ANTHROPIC_API_KEY")
    print(f"Discord token found: {'Yes' if token else 'No'}")
    print(f"Anthropic key found: {'Yes' if anthropic else 'No'}")
    if not token:
        print("❌ DISCORD_BOT_TOKEN not found in environment variables.")
        print("Please set your Discord bot token in the .env file.")
        return
    try:
        bot = create_bot_v2()
        print("🎉 Starting Discord Financial Analysis Bot v2...")
        print("💬 Commands: !test, !analyze, !continue, !stop, !status, !mock on|off")
        bot.run(token)
    except KeyboardInterrupt:
        print("\n⏹️ Bot stopped by user")
    except Exception as start_error:
        logger.error(f"Failed to start Discord bot v2: {start_error}")
        print(f"❌ Error: {start_error}")


if __name__ == "__main__":
    main()


