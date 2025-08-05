import os
import json
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv
import logging
from typing import Dict, Any, List, Optional
import sys
import threading
from queue import Queue
import time

# Import the financial autogen system
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from financial_autogen import FinancialAnalysisAutoGenSystem, LambdaLLMAdapter
    import autogen
    from autogen import ConversableAgent, UserProxyAgent
    AUTOGEN_AVAILABLE = True
    print("✅ AutoGen system imported successfully")
except ImportError as e:
    AUTOGEN_AVAILABLE = False
    print(f"⚠️ AutoGen system not available: {e}")

# Load environment variables first
load_env_result = load_dotenv()
print(f"Environment loaded: {load_env_result}")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DiscordAutoGenBridge:
    """Bridge between Discord and AutoGen system to maintain interactive conversations"""
    
    def __init__(self, channel_id: int, user_id: int):
        self.channel_id = channel_id
        self.user_id = user_id
        self.conversation_active = False
        self.waiting_for_user = False
        self.response_queue = Queue()
        self.user_input_queue = Queue()
        self.agents = None
        self.current_manager = None
        
    def setup_autogen_system(self):
        """Initialize the AutoGen system with Discord integration"""
        if not AUTOGEN_AVAILABLE:
            raise ValueError("AutoGen system not available")
            
        anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        
        if not anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment variables")
            
        # Create custom AutoGen system for Discord
        lambda_adapter = LambdaLLMAdapter(anthropic_api_key=anthropic_api_key)
        
        # Configuration for Claude
        claude_config = {
            "model": "claude-3-5-sonnet-20241022",
            "api_key": anthropic_api_key,
            "api_type": "anthropic"
        }
        
        # Financial Analyst Agent
        financial_analyst = ConversableAgent(
            name="financial_analyst",
            system_message="""You are a senior financial analyst specializing in fundamental analysis. 
            Your role is to:
            1. Analyze stock ticker requests from natural language
            2. Coordinate with the data_researcher to get financial data
            3. Provide comprehensive investment recommendations
            4. Explain complex financial metrics in simple terms
            5. Consider both quantitative data and qualitative factors
            
            Always provide balanced, well-reasoned analysis and clearly state that your analysis 
            is for informational purposes only and not investment advice.""",
            llm_config={"config_list": [claude_config]},
            human_input_mode="NEVER",
        )
        
        # Data Researcher Agent
        data_researcher = ConversableAgent(
            name="data_researcher", 
            system_message="""You are a financial data researcher responsible for gathering comprehensive 
            stock analysis data. Your role is to:
            1. Extract ticker symbols from natural language requests
            2. Retrieve financial data using the LOCAL financial analysis function
            3. Format and present data clearly
            4. Identify data quality issues or missing information
            5. Provide context about the data sources and methodology
            
            You have access to a sophisticated LOCAL financial analysis system that provides 
            fundamental analysis scores, valuation metrics, and comprehensive reports using Pinecone vector database.""",
            llm_config={"config_list": [claude_config]},
            human_input_mode="NEVER",
        )
        
        # Custom User Proxy Agent for Discord - restore natural AutoGen behavior
        user_proxy = DiscordUserProxyAgent(
            name="user_proxy",
            system_message="You are the user's representative in this financial analysis conversation via Discord.",
            human_input_mode="ALWAYS",  # Restore natural AutoGen behavior
            max_consecutive_auto_reply=10,  # Same as original terminal version
            code_execution_config=False,
            discord_bridge=self
        )
        
        # Create wrapper function for financial analysis
        def get_financial_analysis_func(ticker: str) -> str:
            return self.get_financial_analysis_wrapper(ticker, lambda_adapter)
        
        # Register function for data researcher
        data_researcher.register_for_llm(
            name="get_financial_analysis",
            description="Get comprehensive financial analysis for a stock ticker using LOCAL financial analysis function"
        )(get_financial_analysis_func)
        
        user_proxy.register_for_execution(
            name="get_financial_analysis"
        )(get_financial_analysis_func)
        
        # Store agents
        self.agents = {
            'user_proxy': user_proxy,
            'financial_analyst': financial_analyst,
            'data_researcher': data_researcher
        }
        
        return lambda_adapter
    
    def get_financial_analysis_wrapper(self, ticker: str, lambda_adapter: LambdaLLMAdapter) -> str:
        """Wrapper for financial analysis function"""
        try:
            result = lambda_adapter.invoke_lambda_function(ticker)
            
            if "error" in result:
                return f"Error retrieving analysis for {ticker}: {result['error']}"
            
            # Extract and format the response
            response_data = result.get("response", {})
            function_response = response_data.get("functionResponse", {})
            response_body = function_response.get("responseBody", {})
            text_data = response_body.get("TEXT", {})
            body_content = text_data.get("body", "{}")
            
            # Parse the analysis data
            analysis_data = json.loads(body_content) if isinstance(body_content, str) else body_content
            
            # Return the analysis report if available
            if "analysisReport" in analysis_data:
                return f"Financial Analysis for {ticker.upper()}:\n\n{analysis_data['analysisReport']}"
            else:
                return f"Analysis data retrieved for {ticker.upper()}: {json.dumps(analysis_data, indent=2)}"
                
        except Exception as e:
            logger.error(f"Error in financial analysis wrapper: {str(e)}")
            return f"Error retrieving financial analysis for {ticker}: {str(e)}"
    
    async def start_conversation(self, initial_message: str):
        """Start a new AutoGen conversation"""
        try:
            lambda_adapter = self.setup_autogen_system()
            
            # Override agent send methods to capture responses for Discord
            self.setup_message_capture()
            
            # Create group chat - restore natural AutoGen behavior
            group_chat = autogen.GroupChat(
                agents=[self.agents['user_proxy'], self.agents['financial_analyst'], self.agents['data_researcher']],
                messages=[],
                max_round=50,  # Increased to allow for follow-up questions
                speaker_selection_method="round_robin"  # Restore original terminal behavior
            )
            
            self.current_manager = autogen.GroupChatManager(
                groupchat=group_chat,
                llm_config={"config_list": [{"model": "claude-3-5-sonnet-20241022", "api_key": lambda_adapter.anthropic_api_key, "api_type": "anthropic"}]}
            )
            
            # Also capture manager responses
            self.capture_manager_responses()
            
            self.conversation_active = True
            
            # Start the conversation in a separate thread
            def run_conversation():
                try:
                    # Start the initial conversation
                    self.agents['user_proxy'].initiate_chat(
                        self.current_manager,
                        message=initial_message
                    )
                    
                    # Keep the conversation alive for follow-up questions
                    while self.conversation_active:
                        if self.waiting_for_user:
                            # Wait for user input
                            time.sleep(1)
                            continue
                        
                        # Check if there are new user inputs to process
                        if not self.user_input_queue.empty():
                            user_input = self.user_input_queue.get()
                            
                            if user_input.strip().lower() in ['exit', 'quit', 'stop']:
                                break
                            
                            # Continue the conversation with new user input
                            try:
                                self.agents['user_proxy'].initiate_chat(
                                    self.current_manager,
                                    message=user_input,
                                    clear_history=False  # Keep conversation history
                                )
                            except Exception as e:
                                logger.error(f"Error in follow-up conversation: {str(e)}")
                                self.response_queue.put(f"❌ Error in follow-up: {str(e)}")
                        
                        time.sleep(0.5)  # Small delay to prevent busy waiting
                        
                except Exception as e:
                    logger.error(f"Error in AutoGen conversation: {str(e)}")
                    self.response_queue.put(f"❌ Error in conversation: {str(e)}")
                finally:
                    self.conversation_active = False
                    self.response_queue.put("✅ **Analysis conversation completed! Use `!analyze` to start a new conversation.**")
            
            # Run in thread to avoid blocking Discord
            thread = threading.Thread(target=run_conversation)
            thread.daemon = True
            thread.start()
            
        except Exception as e:
            logger.error(f"Error starting conversation: {str(e)}")
            self.response_queue.put(f"❌ Error starting conversation: {str(e)}")
    
    def setup_message_capture(self):
        """Setup message capture for all agents to send responses to Discord"""
        for agent_name, agent in self.agents.items():
            # Store original send method
            original_send = agent.send
            
            # Create wrapped send method
            def create_wrapped_send(agent_name, original_send_method):
                def wrapped_send(message, recipient, request_reply=None, silent=False):
                    # Capture the message for Discord
                    if hasattr(message, 'get'):
                        content = message.get('content', str(message))
                    else:
                        content = str(message)
                    
                    # Format message for Discord
                    formatted_message = f"**{agent_name}** (to {recipient.name}):\n\n{content}"
                    self.response_queue.put(formatted_message)
                    
                    # Call original send method
                    return original_send_method(message, recipient, request_reply, silent)
                
                return wrapped_send
            
            # Replace send method with wrapped version
            agent.send = create_wrapped_send(agent_name, original_send)
    
    def capture_manager_responses(self):
        """Capture GroupChatManager responses"""
        if self.current_manager:
            original_send = self.current_manager.send
            
            def wrapped_manager_send(message, recipient, request_reply=None, silent=False):
                # Capture manager messages
                if hasattr(message, 'get'):
                    content = message.get('content', str(message))
                else:
                    content = str(message)
                
                if "Next speaker:" in content:
                    self.response_queue.put(f"📝 **{content}**")
                
                return original_send(message, recipient, request_reply, silent)
            
            self.current_manager.send = wrapped_manager_send
    
    def send_user_input(self, user_input: str):
        """Send user input to the AutoGen system"""
        self.user_input_queue.put(user_input)
    
    def get_responses(self) -> List[str]:
        """Get all pending responses from AutoGen system"""
        responses = []
        while not self.response_queue.empty():
            responses.append(self.response_queue.get())
        return responses

class DiscordUserProxyAgent(UserProxyAgent):
    """Custom UserProxyAgent that works with Discord"""
    
    def __init__(self, discord_bridge, **kwargs):
        super().__init__(**kwargs)
        self.discord_bridge = discord_bridge
    
    def get_human_input(self, prompt: str) -> str:
        """Override to get input from Discord instead of terminal - restore natural AutoGen flow"""
        
        # Send ALL prompts to Discord - let the natural AutoGen flow work
        self.discord_bridge.response_queue.put(f"🤖 **{prompt}**")
        self.discord_bridge.waiting_for_user = True
        
        # Wait for user input from Discord
        timeout_counter = 0
        max_wait = 600  # 60 seconds max wait for user input
        
        while self.discord_bridge.waiting_for_user and self.discord_bridge.conversation_active and timeout_counter < max_wait:
            if not self.discord_bridge.user_input_queue.empty():
                user_input = self.discord_bridge.user_input_queue.get()
                self.discord_bridge.waiting_for_user = False
                
                # Handle "enter" or empty input for auto-reply (natural AutoGen behavior)
                if user_input.strip().lower() in ['', 'enter', 'continue', 'auto']:
                    self.discord_bridge.response_queue.put("⏭️ **NO HUMAN INPUT RECEIVED.**\n⏭️ **USING AUTO REPLY...**")
                    return ""  # Empty string triggers auto-reply - this is the natural AutoGen flow
                elif user_input.strip().lower() in ['exit', 'quit', 'stop']:
                    self.discord_bridge.response_queue.put("⏹️ **Stopping conversation...**")
                    self.discord_bridge.conversation_active = False
                    return "TERMINATE"
                else:
                    # Regular user input - continue conversation with user's message
                    return user_input
            
            time.sleep(0.1)  # Small delay to prevent busy waiting
            timeout_counter += 1
        
        # If we timeout waiting for user input, use auto-reply (natural AutoGen behavior)
        if timeout_counter >= max_wait:
            self.discord_bridge.response_queue.put("⏰ **No user input received, continuing with auto-reply...**")
            self.discord_bridge.waiting_for_user = False
            return ""  # Auto-reply to continue natural AutoGen flow
        
        return ""  # Default to auto-reply if conversation ends

class FinancialDiscordBot(commands.Bot):
    """Discord bot for financial analysis using AutoGen"""
    
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='!', intents=intents)
        
        # Store active conversations per user/channel
        self.active_conversations: Dict[str, DiscordAutoGenBridge] = {}
        
        print("✅ Bot initialized successfully")
    
    async def on_ready(self):
        print(f'🤖 {self.user} has connected to Discord!')
        print(f'📊 Financial Analysis Bot is ready!')
        
        # Debug: Print available commands
        commands_list = [cmd.name for cmd in self.commands]
        print(f"🔧 Available commands: {commands_list}")
        
        if len(commands_list) == 1 and commands_list[0] == 'help':
            print("⚠️ WARNING: Only default 'help' command found. Custom commands may not be registered.")
        
        print("✅ Bot is fully ready for commands!")
    
    async def on_command_error(self, ctx, error):
        """Handle command errors with detailed debugging"""
        if isinstance(error, commands.CommandNotFound):
            available_commands = [cmd.name for cmd in self.commands]
            await ctx.send(f"❌ **Command not found.**\n📋 **Available commands:** `{'`, `'.join(available_commands)}`")
            print(f"🔍 Command not found: '{ctx.message.content}' | Available: {available_commands}")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ **Missing required argument:** {error.param.name}")
        else:
            await ctx.send(f"❌ **An error occurred:** {str(error)}")
            print(f"❌ Command error: {str(error)}")

    def get_conversation_key(self, channel_id: int, user_id: int) -> str:
        """Generate unique key for user conversation"""
        return f"{channel_id}_{user_id}"
    
    async def monitor_conversation(self, ctx, bridge: DiscordAutoGenBridge):
        """Monitor AutoGen conversation and send responses to Discord"""
        timeout_counter = 0
        max_timeout = 1200  # 2 minutes timeout (increased for complex analysis)
        last_response_time = 0
        
        await ctx.send("🔄 **Monitoring AutoGen conversation...**")
        
        while timeout_counter < max_timeout:
            # Get any new responses
            responses = bridge.get_responses()
            
            if responses:
                last_response_time = timeout_counter
                for response in responses:
                    # Format response for Discord (matching output.md style)
                    formatted_response = self.format_response(response)
                    
                    # Split long messages
                    if len(formatted_response) > 2000:
                        chunks = [formatted_response[i:i+2000] for i in range(0, len(formatted_response), 2000)]
                        for chunk in chunks:
                            await ctx.send(chunk)
                            await asyncio.sleep(0.5)  # Small delay between chunks
                    else:
                        await ctx.send(formatted_response)
                        await asyncio.sleep(0.2)  # Small delay between messages
            
            # If waiting for user input, break the monitoring loop
            if bridge.waiting_for_user:
                await ctx.send("⏸️ **Waiting for your input... Type `!continue` or `!continue enter` to proceed with auto-reply**")
                break
            
            # If conversation is no longer active, break
            if not bridge.conversation_active:
                break
            
            await asyncio.sleep(0.5)  # Check every 0.5 seconds
            timeout_counter += 1
            
            # If no responses for a while but conversation still active, send status
            if timeout_counter % 60 == 0 and timeout_counter > last_response_time + 30:  # Every 30 seconds
                await ctx.send(f"🔄 **AutoGen conversation still running... ({timeout_counter//2}s elapsed)**")
        
        # Clean up if conversation ended or timed out
        conversation_key = self.get_conversation_key(ctx.channel.id, ctx.author.id)
        if conversation_key in self.active_conversations:
            if timeout_counter >= max_timeout:
                await ctx.send("⏰ **Conversation timed out. Use `!analyze` to start a new analysis.**")
                bridge.conversation_active = False
            
            # Only delete if conversation is truly finished
            if not bridge.conversation_active:
                del self.active_conversations[conversation_key]
            else:
                # Conversation is still active, let user know they can continue
                await ctx.send("💬 **Conversation is still active! You can:**\n• `!continue <your question>` - Ask follow-up questions\n• `!continue` - Continue with auto-reply\n• `!stop` - End the conversation")
    
    def format_response(self, response: str) -> str:
        """Format AutoGen responses to match output.md style"""
        # Add Discord formatting to match the output.md style
        if "Next speaker:" in response:
            return f"📝 **{response}**"
        elif "HTTP Request:" in response:
            return f"🌐 `{response}`"
        elif response.startswith("🤖"):
            return response
        elif "Financial Analysis for" in response:
            return f"📊 **ANALYSIS RESULTS:**\n```\n{response}\n```"
        elif "Error" in response and "❌" not in response:
            return f"❌ **{response}**"
        else:
            return response

# Define commands as separate functions first, then register them
async def test_command(ctx):
    """Test command to verify bot is working"""
    await ctx.send("✅ **Bot is working!** Commands are registered properly.")
    autogen_status = "✅ Available" if AUTOGEN_AVAILABLE else "❌ Not Available"
    await ctx.send(f"🔧 **AutoGen System:** {autogen_status}")
    print("✅ Test command executed successfully")

async def analyze_command(ctx, *, request: str):
    """Start financial analysis conversation"""
    if not AUTOGEN_AVAILABLE:
        await ctx.send("❌ **AutoGen system not available.** Please check your setup.")
        return
        
    bot = ctx.bot
    conversation_key = bot.get_conversation_key(ctx.channel.id, ctx.author.id)
    
    # Check if user already has active conversation
    if conversation_key in bot.active_conversations:
        if bot.active_conversations[conversation_key].conversation_active:
            await ctx.send("❌ You already have an active analysis conversation. Please wait for it to complete or use `!stop` to cancel it.")
            return
    
    # Create new conversation bridge
    bridge = DiscordAutoGenBridge(ctx.channel.id, ctx.author.id)
    bot.active_conversations[conversation_key] = bridge
    
    # Send initial message
    await ctx.send(f"🚀 **Starting financial analysis for:** {request}\n🤖 **Initializing AutoGen agents...**")
    
    # Start the AutoGen conversation
    await bridge.start_conversation(request)
    
    # Monitor for responses
    await bot.monitor_conversation(ctx, bridge)

async def continue_command(ctx, *, user_input: str = ""):
    """Continue the active conversation"""
    bot = ctx.bot
    conversation_key = bot.get_conversation_key(ctx.channel.id, ctx.author.id)
    
    if conversation_key not in bot.active_conversations:
        await ctx.send("❌ No active conversation found. Use `!analyze <request>` to start a new analysis.")
        return
    
    bridge = bot.active_conversations[conversation_key]
    
    if not bridge.conversation_active:
        await ctx.send("❌ No active conversation found. Use `!analyze <request>` to start a new analysis.")
        return
    
    # Provide feedback about what kind of continue this is
    if user_input.strip() == "":
        await ctx.send("⏭️ **Continuing with auto-reply...**")
    else:
        await ctx.send(f"💬 **Asking follow-up question:** {user_input}")
    
    # Send user input to AutoGen
    bridge.send_user_input(user_input)
    
    # Continue monitoring (but don't restart the monitoring completely)
    # Just wait a moment for responses to come through
    await asyncio.sleep(1)
    
    # Check for immediate responses
    responses = bridge.get_responses()
    if responses:
        for response in responses:
            formatted_response = bot.format_response(response)
            if len(formatted_response) > 2000:
                chunks = [formatted_response[i:i+2000] for i in range(0, len(formatted_response), 2000)]
                for chunk in chunks:
                    await ctx.send(chunk)
                    await asyncio.sleep(0.5)
            else:
                await ctx.send(formatted_response)
                await asyncio.sleep(0.2)
    
    # If waiting for user input, let them know
    if bridge.waiting_for_user:
        await ctx.send("⏸️ **Waiting for your input... Type `!continue` or `!continue <your question>` to proceed**")
    elif bridge.conversation_active:
        await ctx.send("💬 **Conversation is still active! You can ask more questions with `!continue <question>`**")

async def stop_command(ctx):
    """Stop the active conversation"""  
    bot = ctx.bot
    conversation_key = bot.get_conversation_key(ctx.channel.id, ctx.author.id)
    
    if conversation_key in bot.active_conversations:
        bridge = bot.active_conversations[conversation_key]
        bridge.conversation_active = False
        del bot.active_conversations[conversation_key]
        await ctx.send("⏹️ **Conversation stopped.**")
    else:
        await ctx.send("❌ No active conversation to stop.")

def create_bot():
    """Create and configure the bot"""
    try:
        # Create bot instance
        bot = FinancialDiscordBot()
        
        # Register commands manually to ensure they work
        bot.add_command(commands.Command(test_command, name='test'))
        bot.add_command(commands.Command(analyze_command, name='analyze'))
        bot.add_command(commands.Command(continue_command, name='continue'))
        bot.add_command(commands.Command(stop_command, name='stop'))
        
        print(f"✅ Commands registered: {[cmd.name for cmd in bot.commands]}")
        return bot
        
    except Exception as e:
        print(f"❌ Error creating bot: {str(e)}")
        raise

def main():
    """Main function to run the Discord bot"""
    
    # Check for Discord token
    discord_token = os.getenv("DISCORD_BOT_TOKEN")
    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
    
    print(f"Discord token found: {'Yes' if discord_token else 'No'}")
    print(f"Anthropic key found: {'Yes' if anthropic_api_key else 'No'}")
    
    if not discord_token:
        print("❌ DISCORD_BOT_TOKEN not found in environment variables.")
        print("Please set your Discord bot token in the .env file.")
        return
    
    try:
        # Create bot
        bot = create_bot()
        
        print("🎉 Starting Discord Financial Analysis Bot...")
        print("💬 Commands: !test, !analyze, !continue, !stop")
        print("🔄 Starting bot connection...")
        
        # Run the bot
        bot.run(discord_token)
        
    except KeyboardInterrupt:
        print("\n⏹️ Bot stopped by user")
    except Exception as e:
        logger.error(f"Failed to start Discord bot: {str(e)}")
        print(f"❌ Error: {str(e)}")
        print("💡 Check your Discord token and internet connection")

if __name__ == "__main__":
    main()