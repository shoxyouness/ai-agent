# main.py
import asyncio
import sys
from dotenv import load_dotenv
from langgraph.types import Command
from langchain_core.messages import HumanMessage, AIMessageChunk

# Rich imports for UI
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.markdown import Markdown
from rich.prompt import Prompt
from rich.live import Live
from rich.spinner import Spinner

# Import your graph
from src.graph.workflow import build_graph
from src.utils.audio_utils import transcribe_audio_file, tts_to_file, AUDIO_INPUT_PATH

load_dotenv()

# Initialize Rich Console
console = Console()

# --- Configuration: Agent Colors & Icons ---
AGENT_STYLE = {
    "supervisor":      {"emoji": "🧠", "color": "magenta", "title": "Supervisor"},
    "email_agent":     {"emoji": "📧", "color": "cyan",    "title": "Email Agent"},
    "calendar_agent":  {"emoji": "📅", "color": "green",   "title": "Calendar Agent"},
    "sheet_agent":     {"emoji": "📊", "color": "yellow",  "title": "Sheet Agent"},
    "browser_agent":   {"emoji": "🌍", "color": "blue",    "title": "Browser Agent"},
    "memory_agent":    {"emoji": "💾", "color": "white",   "title": "Memory Agent"},
    "reviewer_agent":  {"emoji": "👤", "color": "red",     "title": "Human Reviewer"},
    "default":         {"emoji": "🤖", "color": "white",   "title": "Agent"},
}

app = build_graph()

def _get_agent_style(node_name: str):
    """Helper to get style for a given node name."""
    key = node_name.lower() if node_name else "default"
    return AGENT_STYLE.get(key, AGENT_STYLE["default"])

async def _stream_graph(inputs_or_command, config):
    """Streams output from the graph with stylized headers."""
    last_node = None
    
    async for msg, metadata in app.astream(inputs_or_command, config, stream_mode="messages"):
        if isinstance(msg, AIMessageChunk) and msg.content:
            node_name = metadata.get("langgraph_node", "default")
            
            # Print header only when the active agent changes
            if node_name != last_node:
                style = _get_agent_style(node_name)
                console.print() 
                console.rule(f"[{style['color']}]{style['emoji']} {style['title']}[/]", style=style['color'])
                last_node = node_name
                
            # Stream content
            style_color = _get_agent_style(node_name)["color"]
            console.print(msg.content, end="", style=style_color)
    
    console.print() # Final newline

async def run_streaming_loop():
    """Runs the interactive text chat loop."""
    thread_id = "multi_agent_thread"
    config = {"configurable": {"thread_id": thread_id}}
    
    # Welcome Banner
    console.print(Panel.fit(
        "[bold cyan]Multi-Agent Orchestrator System[/bold cyan]\n"
        "[dim]Powered by LangGraph & LangChain[/dim]",
        border_style="cyan"
    ))
    console.print("[dim]Type 'exit' to quit.[/dim]\n")

    while True:
        try:
            # User Input
            user_input = Prompt.ask("\n[bold green]You[/bold green]")
            
            if user_input.lower() in ["exit", "quit"]:
                console.print("[bold red]👋 Goodbye![/bold red]")
                break
            
            if not user_input:
                continue

            inputs = {
                "messages": [HumanMessage(content=user_input)],
                "core_messages": [HumanMessage(content=user_input)],
            }

            # Run with streaming
            await _stream_graph(inputs, config)

            # --- HANDLE INTERRUPTS (Reviewer) ---
            while True:
                snapshot = app.get_state(config)
                if not snapshot.next:
                    break
                
                # 1. Retrieve the draft text (payload) from the interrupt
                try:
                    interrupt_value = snapshot.tasks[0].interrupts[0].value
                except (IndexError, AttributeError):
                    interrupt_value = "Review required (No draft details found)."

                # 2. Display the Draft nicely
                console.print("\n")
                console.rule("[bold red]👤 Human Review Required[/bold red]", style="red")
                
                console.print(Panel(
                    Markdown(str(interrupt_value)), 
                    title="[bold yellow]Draft Email[/bold yellow]",
                    border_style="yellow",
                    padding=(1, 2)
                ))
                
                # 3. Get Natural Language Feedback
                # We do NOT use fixed choices here. The Reviewer Agent will interpret the text.
                human_response = Prompt.ask(
                    "[bold yellow]Your Feedback[/bold yellow] "
                    "[dim](Type 'approved' to send, or describe changes)[/dim]"
                )

                # 4. Resume execution
                # The input string is passed to reviewer_agent.ainvoke() via nodes.py
                await _stream_graph(Command(resume=human_response), config)

        except Exception as e:
            console.print(f"[bold red]❌ System Error:[/bold red] {e}")
            # import traceback
            # traceback.print_exc()

def run_audio_mode():
    """One-shot audio execution."""
    console.print(Panel("[bold magenta]🎙️  Audio Mode Activated[/bold magenta]", border_style="magenta"))

    with console.status("[bold cyan]Transcribing audio file...[/bold cyan]", spinner="dots"):
        text = transcribe_audio_file(AUDIO_INPUT_PATH)
    
    console.print(f"\n[bold green]📝 Transcribed:[/bold green] \"{text}\"\n")

    with console.status("[bold magenta]Agents are thinking...[/bold magenta]", spinner="earth"):
        result = app.invoke(
            {"messages": [HumanMessage(content=text)], "core_messages": [HumanMessage(content=text)]},
            config={"configurable": {"thread_id": "audio_thread"}}
        )
    
    supervisor_response = result.get("supervisor_response", "Task completed.")
    
    console.rule("[bold magenta]🧠 Supervisor Final Response[/bold magenta]")
    console.print(Panel(Markdown(supervisor_response), border_style="magenta"))

    with console.status("[bold cyan]Generating Audio Response...[/bold cyan]", spinner="dots"):
        tts_to_file(supervisor_response)
    
    console.print(f"\n[bold green]✅ Audio saved![/bold green]")

if __name__ == "__main__":
    try:
        if len(sys.argv) > 1 and sys.argv[1] == "audio":
            run_audio_mode()
        else:
            asyncio.run(run_streaming_loop())
    except KeyboardInterrupt:
        console.print("\n[bold red]🛑 System Interrupted by User[/bold red]")